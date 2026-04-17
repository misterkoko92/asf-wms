from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from contacts.capabilities import ensure_contact_capability
from contacts.models import Contact, ContactAddress, ContactType

from .admin_contacts_duplicate_detection import find_similar_contacts
from .admin_contacts_merge_service import merge_contacts
from .application.parties.use_cases import update_runtime_recipient_shared_profile
from .models import (
    Destination,
    ShipmentShipper,
    ShipmentValidationStatus,
)


def _primary_entity_type(cleaned_data) -> str:
    business_type = (cleaned_data.get("business_type") or "").strip()
    if business_type in {"shipper", "recipient", "correspondent"}:
        return "organization"
    if business_type == "volunteer":
        return "person"
    entity_type = (cleaned_data.get("entity_type") or "").strip()
    return entity_type or "organization"


def build_contact_duplicate_candidates(cleaned_data, *, exclude_contact_id=None):
    destination = cleaned_data.get("destination_id")
    destination_id = destination.id if isinstance(destination, Destination) else destination
    return find_similar_contacts(
        business_type=cleaned_data.get("business_type", ""),
        entity_type=_primary_entity_type(cleaned_data),
        organization_name=cleaned_data.get("organization_name", ""),
        first_name=cleaned_data.get("first_name", ""),
        last_name=cleaned_data.get("last_name", ""),
        email=cleaned_data.get("email", ""),
        phone=cleaned_data.get("phone", ""),
        asf_id=cleaned_data.get("asf_id", ""),
        destination_id=destination_id,
        exclude_contact_id=exclude_contact_id,
    )


def _resolve_destination(value):
    if isinstance(value, Destination):
        return value
    if not value:
        return None
    return Destination.objects.filter(pk=value, is_active=True).first()


def _resolve_contact_list(values):
    if not values:
        return []
    contact_ids = [value.id if isinstance(value, Contact) else value for value in values]
    return list(Contact.objects.filter(pk__in=contact_ids, is_active=True).order_by("name", "id"))


def _set_address(contact, cleaned_data, *, overwrite: bool):
    has_address_values = any(
        [
            cleaned_data.get("address_line1"),
            cleaned_data.get("city"),
            cleaned_data.get("postal_code"),
            cleaned_data.get("region"),
            cleaned_data.get("country"),
        ]
    )
    if not has_address_values:
        return

    address = contact.addresses.filter(is_default=True).first() or contact.addresses.first()
    if address is None:
        address = ContactAddress(contact=contact, is_default=True)
        overwrite = True

    for field_name in (
        "address_line1",
        "address_line2",
        "postal_code",
        "city",
        "region",
        "country",
    ):
        incoming = (cleaned_data.get(field_name) or "").strip()
        current = getattr(address, field_name)
        if overwrite:
            setattr(address, field_name, incoming)
        elif not current and incoming:
            setattr(address, field_name, incoming)
    address.save()


def _apply_contact_fields(contact, *, data, overwrite: bool, excluded_fields=None):
    excluded_fields = set(excluded_fields or ())
    updated_fields = []
    scalar_fields = {
        "name": (data.get("organization_name") or "").strip()
        if contact.contact_type == ContactType.ORGANIZATION
        else " ".join(
            part
            for part in (
                (data.get("first_name") or "").strip(),
                (data.get("last_name") or "").strip(),
            )
            if part
        ).strip(),
        "title": (data.get("title") or "").strip(),
        "first_name": (data.get("first_name") or "").strip(),
        "last_name": (data.get("last_name") or "").strip(),
        "asf_id": (data.get("asf_id") or "").strip() or None,
        "email": (data.get("email") or "").strip(),
        "email2": (data.get("email2") or "").strip(),
        "phone": (data.get("phone") or "").strip(),
        "phone2": (data.get("phone2") or "").strip(),
        "role": (data.get("role") or "").strip(),
        "siret": (data.get("siret") or "").strip(),
        "vat_number": (data.get("vat_number") or "").strip(),
        "legal_registration_number": (data.get("legal_registration_number") or "").strip(),
        "notes": (data.get("notes") or "").strip(),
    }
    for field_name in excluded_fields:
        scalar_fields.pop(field_name, None)
    if contact.contact_type == ContactType.PERSON:
        scalar_fields["use_organization_address"] = bool(data.get("use_organization_address"))
    for field_name, incoming in scalar_fields.items():
        current = getattr(contact, field_name)
        if overwrite:
            if current != incoming:
                setattr(contact, field_name, incoming)
                updated_fields.append(field_name)
        elif (current in ("", None, False)) and incoming not in ("", None, False):
            setattr(contact, field_name, incoming)
            updated_fields.append(field_name)
    is_active = bool(data.get("is_active"))
    if overwrite:
        if contact.is_active != is_active:
            contact.is_active = is_active
            updated_fields.append("is_active")
    elif is_active and not contact.is_active:
        contact.is_active = True
        updated_fields.append("is_active")

    if contact.contact_type == ContactType.ORGANIZATION:
        legal_form = (data.get("legal_form") or "").strip()
        if overwrite:
            if contact.legal_form != legal_form:
                contact.legal_form = legal_form
                updated_fields.append("legal_form")
        elif not contact.legal_form and legal_form:
            contact.legal_form = legal_form
            updated_fields.append("legal_form")

        beneficiary_count = data.get("beneficiary_count")
        if overwrite:
            if contact.beneficiary_count != beneficiary_count:
                contact.beneficiary_count = beneficiary_count
                updated_fields.append("beneficiary_count")
        elif contact.beneficiary_count is None and beneficiary_count is not None:
            contact.beneficiary_count = beneficiary_count
            updated_fields.append("beneficiary_count")

    if contact.pk is None:
        contact.save()
    elif updated_fields:
        contact.save(update_fields=updated_fields)
    _set_address(contact, data, overwrite=overwrite)
    return contact


def _ensure_organization(cleaned_data, *, target=None, overwrite: bool):
    organization = target
    if organization is None:
        organization = Contact(contact_type=ContactType.ORGANIZATION, is_active=True)
    elif organization.contact_type != ContactType.ORGANIZATION:
        raise ValidationError("La fiche cible doit être une structure.")
    return _apply_contact_fields(organization, data=cleaned_data, overwrite=overwrite)


def _ensure_person(
    *,
    cleaned_data,
    organization=None,
    overwrite: bool,
    target=None,
    excluded_fields=None,
):
    first_name = (cleaned_data.get("first_name") or "").strip()
    last_name = (cleaned_data.get("last_name") or "").strip()
    person = target
    if person is not None and person.contact_type != ContactType.PERSON:
        raise ValidationError("La fiche cible doit être une personne.")
    if person is None:
        queryset = Contact.objects.filter(
            contact_type=ContactType.PERSON,
            first_name=first_name,
            last_name=last_name,
        )
        if organization is not None:
            queryset = queryset.filter(organization=organization)
        person = queryset.order_by("id").first()
    if person is None:
        person = Contact(contact_type=ContactType.PERSON, organization=organization, is_active=True)
    elif organization is not None and person.organization_id != organization.id and overwrite:
        person.organization = organization
        person.save(update_fields=["organization"])
    return _apply_contact_fields(
        person,
        data=cleaned_data,
        overwrite=overwrite,
        excluded_fields=excluded_fields,
    )


def _ensure_shipper_runtime(*, organization, referent, cleaned_data):
    shipper, _created = ShipmentShipper.objects.update_or_create(
        organization=organization,
        defaults={
            "default_contact": referent,
            "validation_status": ShipmentValidationStatus.VALIDATED,
            "can_send_to_all": bool(cleaned_data.get("can_send_to_all")),
            "is_active": bool(cleaned_data.get("is_active")),
        },
    )
    return shipper


def _ensure_recipient_runtime(*, organization, referent, cleaned_data, is_correspondent: bool):
    destination = _resolve_destination(cleaned_data.get("destination_id"))
    if destination is None:
        raise ValidationError("La destination destinataire est obligatoire.")

    result = update_runtime_recipient_shared_profile(
        organization=organization,
        referent=referent,
        destination=destination,
        allowed_shipper_contacts=_resolve_contact_list(cleaned_data.get("allowed_shipper_ids")),
        is_correspondent=is_correspondent,
        is_active=bool(cleaned_data.get("is_active")),
    )
    return result.recipient_organization


def _ensure_capability(contact, business_type: str):
    capability_map = {
        "donor": "donor",
        "transporter": "transporter",
        "partner": "partner",
        "other": "other",
        "volunteer": "volunteer",
    }
    capability = capability_map.get(business_type)
    if capability:
        ensure_contact_capability(contact, capability)


def _build_unique_duplicate_name(*, base_name: str, exclude_contact_id=None) -> str:
    normalized_base_name = (base_name or "").strip()
    if not normalized_base_name:
        return normalized_base_name
    suffix = " - doublon"
    index = 1
    while True:
        candidate_name = (
            f"{normalized_base_name}{suffix}"
            if index == 1
            else f"{normalized_base_name}{suffix} {index}"
        )
        existing = Contact.objects.filter(name__iexact=candidate_name, is_active=True)
        if exclude_contact_id is not None:
            existing = existing.exclude(pk=exclude_contact_id)
        if not existing.exists():
            return candidate_name
        index += 1


def _rename_for_duplicate_resolution(cleaned_data, *, editing_contact=None):
    adjusted_data = dict(cleaned_data)
    business_type = (adjusted_data.get("business_type") or "").strip()
    if business_type not in {"shipper", "recipient", "correspondent"}:
        return adjusted_data
    adjusted_data["organization_name"] = _build_unique_duplicate_name(
        base_name=adjusted_data.get("organization_name", ""),
        exclude_contact_id=getattr(editing_contact, "id", None),
    )
    return adjusted_data


def _save_contact_core(cleaned_data, *, target_contact=None, overwrite: bool):
    business_type = (cleaned_data.get("business_type") or "").strip()
    if business_type in {"shipper", "recipient", "correspondent"}:
        organization = _ensure_organization(
            cleaned_data,
            target=target_contact
            if getattr(target_contact, "contact_type", None) == ContactType.ORGANIZATION
            else getattr(target_contact, "organization", None),
            overwrite=overwrite,
        )
        referent = _ensure_person(
            cleaned_data=cleaned_data,
            organization=organization,
            overwrite=overwrite,
            target=target_contact
            if getattr(target_contact, "contact_type", None) == ContactType.PERSON
            else None,
            excluded_fields={"asf_id"},
        )
        if business_type == "shipper":
            _ensure_shipper_runtime(
                organization=organization,
                referent=referent,
                cleaned_data=cleaned_data,
            )
        else:
            _ensure_recipient_runtime(
                organization=organization,
                referent=referent,
                cleaned_data=cleaned_data,
                is_correspondent=business_type == "correspondent",
            )
        return organization

    entity_type = _primary_entity_type(cleaned_data)
    if entity_type == ContactType.ORGANIZATION:
        primary_contact = _ensure_organization(
            cleaned_data,
            target=target_contact
            if getattr(target_contact, "contact_type", None) == ContactType.ORGANIZATION
            else None,
            overwrite=overwrite,
        )
    else:
        organization = None
        organization_name = (cleaned_data.get("organization_name") or "").strip()
        if organization_name:
            organization = (
                Contact.objects.filter(
                    contact_type=ContactType.ORGANIZATION,
                    name=organization_name,
                )
                .order_by("id")
                .first()
            )
            if organization is None:
                organization = Contact.objects.create(
                    contact_type=ContactType.ORGANIZATION,
                    name=organization_name,
                    is_active=True,
                )
        primary_contact = (
            target_contact
            if getattr(target_contact, "contact_type", None) == ContactType.PERSON
            else None
        )
        if primary_contact is None:
            primary_contact = Contact(
                contact_type=ContactType.PERSON, organization=organization, is_active=True
            )
        elif (
            organization is not None
            and overwrite
            and primary_contact.organization_id != organization.id
        ):
            primary_contact.organization = organization
            primary_contact.save(update_fields=["organization"])
        primary_contact = _apply_contact_fields(
            primary_contact, data=cleaned_data, overwrite=overwrite
        )

    _ensure_capability(primary_contact, business_type)
    return primary_contact


def _save_shipment_party_contact_from_form(cleaned_data, *, editing_contact=None):
    duplicate_action = (cleaned_data.get("duplicate_action") or "").strip()
    if not duplicate_action:
        return _save_contact_core(
            cleaned_data,
            target_contact=editing_contact,
            overwrite=editing_contact is not None,
        )

    if duplicate_action == "duplicate":
        return _save_contact_core(
            _rename_for_duplicate_resolution(cleaned_data, editing_contact=editing_contact),
            target_contact=editing_contact,
            overwrite=editing_contact is not None,
        )

    duplicate_target_id = cleaned_data.get("duplicate_target_id")
    target_contact = Contact.objects.filter(pk=duplicate_target_id).first()
    if target_contact is None:
        raise ValidationError("La fiche cible est introuvable.")

    keep_choice = (cleaned_data.get("duplicate_keep_choice") or "").strip() or "existing"
    scalar_mode = "none" if duplicate_action == "replace" else "fill_empty"

    if editing_contact is None:
        if keep_choice == "existing":
            if duplicate_action == "merge":
                return _save_contact_core(
                    cleaned_data,
                    target_contact=target_contact,
                    overwrite=False,
                )
            return target_contact

        source_contact = _save_contact_core(
            cleaned_data,
            target_contact=None,
            overwrite=False,
        )
        return merge_contacts(
            source_contact=target_contact,
            target_contact=source_contact,
            scalar_mode=scalar_mode,
        )

    if keep_choice == "existing":
        if duplicate_action == "merge":
            source_contact = _save_contact_core(
                cleaned_data,
                target_contact=editing_contact,
                overwrite=True,
            )
            return merge_contacts(
                source_contact=source_contact,
                target_contact=target_contact,
                scalar_mode=scalar_mode,
            )
        return merge_contacts(
            source_contact=editing_contact,
            target_contact=target_contact,
            scalar_mode=scalar_mode,
        )

    source_contact = _save_contact_core(
        cleaned_data,
        target_contact=editing_contact,
        overwrite=True,
    )
    return merge_contacts(
        source_contact=target_contact,
        target_contact=source_contact,
        scalar_mode=scalar_mode,
    )


def save_contact_from_form(cleaned_data, *, editing_contact=None):
    business_type = (cleaned_data.get("business_type") or "").strip()
    duplicate_action = (cleaned_data.get("duplicate_action") or "").strip()
    duplicate_target_id = cleaned_data.get("duplicate_target_id")

    with transaction.atomic():
        if business_type in {"shipper", "recipient", "correspondent"}:
            return _save_shipment_party_contact_from_form(
                cleaned_data,
                editing_contact=editing_contact,
            )

        target_contact = editing_contact
        overwrite = editing_contact is not None
        if duplicate_action in {"replace", "merge"}:
            target_contact = Contact.objects.filter(pk=duplicate_target_id).first()
            if target_contact is None:
                raise ValidationError("La fiche cible est introuvable.")
            overwrite = duplicate_action == "replace"

        return _save_contact_core(
            cleaned_data,
            target_contact=target_contact,
            overwrite=overwrite,
        )


def deactivate_contact(contact):
    if isinstance(contact, int):
        contact = Contact.objects.filter(pk=contact).first()
    if contact is None:
        raise ValidationError("Contact introuvable.")
    if not contact.is_active:
        return contact
    contact.is_active = False
    contact.save(update_fields=["is_active"])
    return contact
