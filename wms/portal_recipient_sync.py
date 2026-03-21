from django.db import transaction

from contacts.models import Contact, ContactAddress, ContactType
from wms.models import (
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)
from wms.shipment_party_registry import default_recipient_contact_for_link
from wms.shipment_party_setup import (
    ensure_authorized_recipient_contact,
    ensure_shipment_recipient_link,
    ensure_shipment_shipper,
)

PORTAL_RECIPIENT_ADDRESS_LABEL = "Portail association"


def _normalized_text(value) -> str:
    return str(value or "").strip()


def _first_multi_value(raw_value: str, fallback: str = "") -> str:
    value = (raw_value or "").replace("\n", ";").replace(",", ";")
    for item in value.split(";"):
        normalized = item.strip()
        if normalized:
            return normalized
    return (fallback or "").strip()


def _build_contact_notes(recipient) -> str:
    notes = (recipient.notes or "").strip()
    association = f"Association: {recipient.association_contact}"
    if notes:
        return f"{association}\n{notes}"
    return association


def _recipient_structure_name(recipient) -> str:
    structure_name = _normalized_text(recipient.structure_name)
    if structure_name:
        return structure_name[:200]
    display_name = _normalized_text(recipient.get_display_name())
    if display_name:
        return display_name[:200]
    return f"Destinataire {recipient.pk}"[:200]


def _recipient_person_name(recipient, *, primary_email: str) -> str:
    contact_display = _normalized_text(recipient.get_contact_display_name())
    if contact_display:
        return contact_display[:200]
    if primary_email:
        return primary_email[:200]
    structure_name = _recipient_structure_name(recipient)
    return f"Referent {structure_name}"[:200]


def _get_synced_contact(recipient):
    if not recipient.pk or not recipient.synced_contact_id:
        return None
    return Contact.objects.filter(pk=recipient.synced_contact_id).first()


def _upsert_contact_address(*, contact, recipient, primary_phone, primary_email):
    if not recipient.address_line1:
        return
    address = (
        contact.addresses.filter(label=PORTAL_RECIPIENT_ADDRESS_LABEL).order_by("-id").first()
        or contact.addresses.filter(is_default=True).order_by("-id").first()
    )
    if address is None:
        address = ContactAddress(contact=contact)
    address.label = PORTAL_RECIPIENT_ADDRESS_LABEL
    address.address_line1 = recipient.address_line1
    address.address_line2 = recipient.address_line2
    address.postal_code = recipient.postal_code
    address.city = recipient.city
    address.country = recipient.country or "France"
    address.phone = primary_phone[:40]
    address.email = primary_email[:254]
    address.is_default = True
    address.notes = recipient.notes or ""
    address.save()


def _ensure_shipment_shipper_for_association(association_contact):
    return ensure_shipment_shipper(
        association_contact,
        validation_status=ShipmentValidationStatus.VALIDATED,
    )


def _can_reuse_synced_contact_for_destination(contact, destination):
    existing = ShipmentRecipientOrganization.objects.filter(organization=contact).first()
    if existing is None:
        return True
    return existing.destination_id == getattr(destination, "id", None)


def _find_existing_recipient_organization(recipient, *, prefer_existing_structure=True):
    synced_contact = _get_synced_contact(recipient)
    if synced_contact is not None and synced_contact.contact_type == ContactType.ORGANIZATION:
        existing = ShipmentRecipientOrganization.objects.filter(organization=synced_contact).first()
        if existing is not None and existing.destination_id == recipient.destination_id:
            return existing

    structure_name = _recipient_structure_name(recipient)
    if prefer_existing_structure and recipient.destination_id and structure_name:
        exact_matches = list(
            ShipmentRecipientOrganization.objects.select_related("organization")
            .filter(
                destination=recipient.destination,
                organization__name__iexact=structure_name,
            )
            .order_by("id")[:2]
        )
        if len(exact_matches) == 1:
            return exact_matches[0]

    if (
        synced_contact is not None
        and synced_contact.contact_type == ContactType.ORGANIZATION
        and _can_reuse_synced_contact_for_destination(synced_contact, recipient.destination)
    ):
        return (
            ShipmentRecipientOrganization.objects.select_related("organization")
            .filter(organization=synced_contact)
            .first()
        )
    return None


def _upsert_recipient_structure_contact(
    *,
    recipient,
    primary_email,
    primary_phone,
    prefer_existing_structure=True,
):
    existing_recipient_org = _find_existing_recipient_organization(
        recipient,
        prefer_existing_structure=prefer_existing_structure,
    )
    synced_contact = _get_synced_contact(recipient)
    contact = existing_recipient_org.organization if existing_recipient_org is not None else None
    if (
        contact is None
        and synced_contact is not None
        and synced_contact.contact_type == ContactType.ORGANIZATION
        and _can_reuse_synced_contact_for_destination(synced_contact, recipient.destination)
    ):
        contact = synced_contact

    if contact is None:
        contact = Contact.objects.create(
            contact_type=ContactType.ORGANIZATION,
            name=_recipient_structure_name(recipient),
            email=primary_email[:254],
            phone=primary_phone[:40],
            notes=_build_contact_notes(recipient),
            is_active=True,
        )
    else:
        contact.contact_type = ContactType.ORGANIZATION
        contact.name = _recipient_structure_name(recipient)
        contact.email = primary_email[:254]
        contact.phone = primary_phone[:40]
        contact.notes = _build_contact_notes(recipient)
        contact.is_active = True
        contact.save(
            update_fields=[
                "contact_type",
                "name",
                "email",
                "phone",
                "notes",
                "is_active",
            ]
        )

    _upsert_contact_address(
        contact=contact,
        recipient=recipient,
        primary_phone=primary_phone,
        primary_email=primary_email,
    )
    if recipient.synced_contact_id != contact.id:
        recipient.synced_contact = contact
        recipient.save(update_fields=["synced_contact"])
    return contact


def _ensure_recipient_organization(*, contact, recipient):
    recipient_organization, created = ShipmentRecipientOrganization.objects.get_or_create(
        organization=contact,
        defaults={
            "destination": recipient.destination,
            "validation_status": ShipmentValidationStatus.PENDING,
            "is_correspondent": False,
            "is_active": True,
        },
    )
    if created:
        return recipient_organization

    updated_fields = []
    if (
        recipient.destination_id
        and recipient_organization.destination_id != recipient.destination_id
        and not recipient_organization.is_active
    ):
        recipient_organization.destination = recipient.destination
        updated_fields.append("destination")
    if not recipient_organization.is_active:
        recipient_organization.is_active = True
        updated_fields.append("is_active")
    if updated_fields:
        recipient_organization.save(update_fields=updated_fields)
    return recipient_organization


def _find_matching_person_contact(*, organization, recipient, primary_email):
    people = organization.members.filter(contact_type=ContactType.PERSON).order_by("id")

    if primary_email:
        match = people.filter(email__iexact=primary_email).first()
        if match is not None:
            return match

    first_name = _normalized_text(recipient.contact_first_name)
    last_name = _normalized_text(recipient.contact_last_name)
    if first_name or last_name:
        query = people
        if first_name:
            query = query.filter(first_name__iexact=first_name)
        if last_name:
            query = query.filter(last_name__iexact=last_name)
        match = query.first()
        if match is not None:
            return match

    contact_name = _normalized_text(recipient.get_contact_display_name())
    if contact_name:
        return people.filter(name__iexact=contact_name).first()
    return None


def _upsert_recipient_person_contact(
    *, recipient_organization, recipient, primary_email, primary_phone
):
    organization = recipient_organization.organization
    person = _find_matching_person_contact(
        organization=organization,
        recipient=recipient,
        primary_email=primary_email,
    )
    if person is None:
        person = Contact(organization=organization)

    person.contact_type = ContactType.PERSON
    person.organization = organization
    person.title = _normalized_text(recipient.get_contact_title_display())
    person.first_name = _normalized_text(recipient.contact_first_name)[:120]
    person.last_name = _normalized_text(recipient.contact_last_name)[:120]
    person.name = _recipient_person_name(recipient, primary_email=primary_email)
    person.email = primary_email[:254]
    person.phone = primary_phone[:40]
    person.use_organization_address = True
    person.is_active = True
    if person.pk is None:
        person.save()
    else:
        person.save(
            update_fields=[
                "contact_type",
                "organization",
                "title",
                "first_name",
                "last_name",
                "name",
                "email",
                "phone",
                "use_organization_address",
                "is_active",
            ]
        )

    shipment_contact, created = ShipmentRecipientContact.objects.get_or_create(
        recipient_organization=recipient_organization,
        contact=person,
        defaults={"is_active": True},
    )
    if not created and not shipment_contact.is_active:
        shipment_contact.is_active = True
        shipment_contact.save(update_fields=["is_active"])
    return shipment_contact


def _matching_shipment_recipient_contact(*, recipient, recipient_organization):
    queryset = ShipmentRecipientContact.objects.filter(
        recipient_organization=recipient_organization,
    ).select_related("contact")

    primary_email = _first_multi_value(recipient.emails, recipient.email)
    if primary_email:
        shipment_contact = (
            queryset.filter(contact__email__iexact=primary_email).order_by("id").first()
        )
        if shipment_contact is not None:
            return shipment_contact

    first_name = _normalized_text(recipient.contact_first_name)
    last_name = _normalized_text(recipient.contact_last_name)
    if first_name or last_name:
        match_query = queryset
        if first_name:
            match_query = match_query.filter(contact__first_name__iexact=first_name)
        if last_name:
            match_query = match_query.filter(contact__last_name__iexact=last_name)
        shipment_contact = match_query.order_by("id").first()
        if shipment_contact is not None:
            return shipment_contact

    contact_name = _normalized_text(recipient.get_contact_display_name())
    if contact_name:
        return queryset.filter(contact__name__iexact=contact_name).order_by("id").first()
    return None


def sync_association_recipient_to_contact(
    recipient,
    *,
    set_as_default=True,
    prefer_existing_structure=True,
):
    if not recipient:
        return None
    primary_email = _first_multi_value(recipient.emails, recipient.email)
    primary_phone = _first_multi_value(recipient.phones, recipient.phone)

    with transaction.atomic():
        shipper = _ensure_shipment_shipper_for_association(recipient.association_contact)
        structure_contact = _upsert_recipient_structure_contact(
            recipient=recipient,
            primary_email=primary_email,
            primary_phone=primary_phone,
            prefer_existing_structure=prefer_existing_structure,
        )
        recipient_organization = _ensure_recipient_organization(
            contact=structure_contact,
            recipient=recipient,
        )
        shipment_contact = _upsert_recipient_person_contact(
            recipient_organization=recipient_organization,
            recipient=recipient,
            primary_email=primary_email,
            primary_phone=primary_phone,
        )
        link = ensure_shipment_recipient_link(
            shipper=shipper,
            recipient_organization=recipient_organization,
        )
        ensure_authorized_recipient_contact(
            link=link,
            recipient_contact=shipment_contact,
            is_active=bool(recipient.is_active),
            set_as_default=set_as_default,
        )
        return structure_contact


def resolve_association_recipient_party_contact(recipient):
    synced_contact = _get_synced_contact(recipient)
    if synced_contact is None:
        synced_contact = sync_association_recipient_to_contact(
            recipient,
            set_as_default=False,
        )
    if synced_contact is None:
        return None

    recipient_organization = (
        ShipmentRecipientOrganization.objects.filter(
            organization=synced_contact,
            destination=recipient.destination,
        )
        .select_related("organization")
        .first()
        or ShipmentRecipientOrganization.objects.filter(organization=synced_contact)
        .select_related("organization")
        .first()
    )
    if recipient_organization is None:
        return synced_contact

    shipment_contact = _matching_shipment_recipient_contact(
        recipient=recipient,
        recipient_organization=recipient_organization,
    )
    shipper = ShipmentShipper.objects.filter(organization=recipient.association_contact).first()
    link = None
    if shipper is not None:
        link = (
            ShipmentShipperRecipientLink.objects.filter(
                shipper=shipper,
                recipient_organization=recipient_organization,
            )
            .order_by("id")
            .first()
        )

    if shipment_contact is not None:
        if link is None:
            return shipment_contact.contact
        authorized = ShipmentAuthorizedRecipientContact.objects.filter(
            link=link,
            recipient_contact=shipment_contact,
            is_active=True,
        ).exists()
        if authorized:
            return shipment_contact.contact

    default_contact = default_recipient_contact_for_link(link) if link is not None else None
    if default_contact is not None:
        return default_contact.contact
    return synced_contact
