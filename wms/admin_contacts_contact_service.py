from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from contacts.capabilities import ContactCapabilityType, ensure_contact_capability
from contacts.models import Contact, ContactAddress, ContactType

from .admin_contacts_duplicate_detection import find_similar_contacts
from .models import (
    Destination,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentValidationStatus,
)
from .shipment_party_setup import (
    ensure_authorized_recipient_contact,
    ensure_shipment_recipient_link,
    ensure_shipment_shipper,
)


def _primary_entity_type(cleaned_data) -> str:
    business_type = (cleaned_data.get("business_type") or "").strip()
    if business_type in {"shipper", "recipient", "correspondent"}:
        return ContactType.ORGANIZATION
    if business_type == "volunteer":
        return ContactType.PERSON
    entity_type = (cleaned_data.get("entity_type") or "").strip()
    return entity_type or ContactType.ORGANIZATION


def build_contact_duplicate_candidates(cleaned_data, *, exclude_contact_id=None):
    return find_similar_contacts(
        business_type=cleaned_data.get("business_type", ""),
        entity_type=_primary_entity_type(cleaned_data),
        organization_name=cleaned_data.get("organization_name", ""),
        first_name=cleaned_data.get("first_name", ""),
        last_name=cleaned_data.get("last_name", ""),
        email=cleaned_data.get("email", ""),
        phone=cleaned_data.get("phone", ""),
        asf_id=cleaned_data.get("asf_id", ""),
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


def _apply_contact_fields(contact, *, data, overwrite: bool):
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


def _ensure_person(*, cleaned_data, organization=None, overwrite: bool, target=None):
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
    return _apply_contact_fields(person, data=cleaned_data, overwrite=overwrite)


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

    recipient_org, _created = ShipmentRecipientOrganization.objects.update_or_create(
        organization=organization,
        defaults={
            "destination": destination,
            "validation_status": ShipmentValidationStatus.VALIDATED,
            "is_correspondent": is_correspondent,
            "is_active": bool(cleaned_data.get("is_active")),
        },
    )
    recipient_contact, _created = ShipmentRecipientContact.objects.update_or_create(
        recipient_organization=recipient_org,
        contact=referent,
        defaults={"is_active": bool(cleaned_data.get("is_active"))},
    )
    if is_correspondent:
        ShipmentRecipientOrganization.objects.filter(
            destination=destination,
            is_correspondent=True,
        ).exclude(pk=recipient_org.pk).update(is_correspondent=False)
        destination.correspondent_contact = referent
        destination.save(update_fields=["correspondent_contact"])
        return recipient_org

    for shipper_org in _resolve_contact_list(cleaned_data.get("allowed_shipper_ids")):
        shipper = ensure_shipment_shipper(shipper_org)
        link = ensure_shipment_recipient_link(
            shipper=shipper,
            recipient_organization=recipient_org,
        )
        ensure_authorized_recipient_contact(
            link=link,
            recipient_contact=recipient_contact,
            is_active=bool(cleaned_data.get("is_active")),
            set_as_default=True,
        )
    return recipient_org


def _ensure_capability(contact, business_type: str):
    capability_map = {
        "donor": ContactCapabilityType.DONOR,
        "transporter": ContactCapabilityType.TRANSPORTER,
        "volunteer": ContactCapabilityType.VOLUNTEER,
    }
    capability = capability_map.get(business_type)
    if capability:
        ensure_contact_capability(contact, capability)


def save_contact_from_form(cleaned_data, *, editing_contact=None):
    business_type = (cleaned_data.get("business_type") or "").strip()
    overwrite = (cleaned_data.get("duplicate_action") or "").strip() == "replace"
    duplicate_action = (cleaned_data.get("duplicate_action") or "").strip()
    duplicate_target_id = cleaned_data.get("duplicate_target_id")

    target_contact = editing_contact
    if duplicate_action in {"replace", "merge"}:
        target_contact = Contact.objects.filter(pk=duplicate_target_id).first()
        if target_contact is None:
            raise ValidationError("La fiche cible est introuvable.")
        overwrite = duplicate_action == "replace"

    with transaction.atomic():
        if business_type in {"shipper", "recipient", "correspondent"}:
            organization = _ensure_organization(
                cleaned_data,
                target=target_contact
                if getattr(target_contact, "contact_type", None) == ContactType.ORGANIZATION
                else None,
                overwrite=overwrite,
            )
            referent = _ensure_person(
                cleaned_data=cleaned_data,
                organization=organization,
                overwrite=overwrite,
                target=target_contact
                if getattr(target_contact, "contact_type", None) == ContactType.PERSON
                else None,
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
