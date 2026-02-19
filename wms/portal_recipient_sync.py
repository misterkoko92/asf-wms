from django.db.models import Q

from contacts.models import Contact, ContactAddress, ContactTag, ContactType
from contacts.querysets import contacts_with_tags
from contacts.rules import ensure_default_shipper_for_recipient
from contacts.tagging import TAG_RECIPIENT, TAG_SHIPPER, normalize_tag_name

RECIPIENT_TAG_DEFAULT_NAME = "Destinataire"
SHIPPER_TAG_DEFAULT_NAME = "Expediteur"
PORTAL_RECIPIENT_SOURCE_PREFIX = "[Portail association]"
PORTAL_RECIPIENT_ADDRESS_LABEL = "Portail association"


def _source_marker(recipient_id: int) -> str:
    return f"{PORTAL_RECIPIENT_SOURCE_PREFIX}[recipient_id={recipient_id}]"


def _first_multi_value(raw_value: str, fallback: str = "") -> str:
    value = (raw_value or "").replace("\n", ";").replace(",", ";")
    for item in value.split(";"):
        normalized = item.strip()
        if normalized:
            return normalized
    return (fallback or "").strip()


def _build_contact_notes(recipient) -> str:
    notes = (recipient.notes or "").strip()
    source = _source_marker(recipient.pk)
    association = f"Association: {recipient.association_contact}"
    if notes:
        return f"{source}\n{association}\n{notes}"
    return f"{source}\n{association}"


def _recipient_display_name(recipient) -> str:
    display = (recipient.get_display_name() or "").strip()
    if display:
        return display[:200]
    return f"Destinataire {recipient.pk}"[:200]


def _get_or_create_recipient_tag() -> ContactTag:
    normalized_targets = {
        normalize_tag_name(alias)
        for alias in TAG_RECIPIENT
        if normalize_tag_name(alias)
    }
    for tag in ContactTag.objects.only("id", "name"):
        if normalize_tag_name(tag.name) in normalized_targets:
            return tag
    return ContactTag.objects.create(name=RECIPIENT_TAG_DEFAULT_NAME)


def _get_or_create_shipper_tag() -> ContactTag:
    normalized_targets = {
        normalize_tag_name(alias)
        for alias in TAG_SHIPPER
        if normalize_tag_name(alias)
    }
    for tag in ContactTag.objects.only("id", "name"):
        if normalize_tag_name(tag.name) in normalized_targets:
            return tag
    return ContactTag.objects.create(name=SHIPPER_TAG_DEFAULT_NAME)


def _ensure_association_shipper_scope(*, association_contact, destination_id):
    if not association_contact:
        return
    shipper_tag = _get_or_create_shipper_tag()
    association_contact.tags.add(shipper_tag)
    if destination_id:
        association_contact.destinations.add(destination_id)


def _candidate_shipper_ids_for_association(association_contact):
    if not association_contact or not association_contact.pk:
        return []
    filters = Q(pk=association_contact.pk)
    name = (association_contact.name or "").strip()
    email = (association_contact.email or "").strip()
    if name:
        filters |= Q(name__iexact=name)
    if email:
        filters |= Q(email__iexact=email)

    shipper_ids = set(
        contacts_with_tags(TAG_SHIPPER)
        .filter(filters)
        .values_list("id", flat=True)
    )
    shipper_ids.add(association_contact.pk)
    return sorted(shipper_ids)


def _find_synced_contact_by_marker(recipient):
    if not recipient.pk:
        return None
    return Contact.objects.filter(
        notes__startswith=_source_marker(recipient.pk),
    ).order_by("-id").first()


def _find_legacy_synced_contact(recipient):
    association = recipient.association_contact
    if not association:
        return None
    legacy_source = f"{PORTAL_RECIPIENT_SOURCE_PREFIX} {association}"
    recipients = (
        contacts_with_tags(TAG_RECIPIENT)
        .filter(
            linked_shippers=association,
            name__iexact=_recipient_display_name(recipient),
            notes__startswith=legacy_source,
        )
        .distinct()
    )
    destination_id = recipient.destination_id
    if destination_id:
        recipients = recipients.filter(
            Q(destination_id=destination_id) | Q(destinations=destination_id)
        )
    if recipients.count() == 1:
        return recipients.first()
    return None


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


def sync_association_recipient_to_contact(recipient):
    if not recipient:
        return None
    _ensure_association_shipper_scope(
        association_contact=recipient.association_contact,
        destination_id=recipient.destination_id,
    )
    recipient_tag = _get_or_create_recipient_tag()
    primary_email = _first_multi_value(recipient.emails, recipient.email)
    primary_phone = _first_multi_value(recipient.phones, recipient.phone)

    contact = _find_synced_contact_by_marker(recipient) or _find_legacy_synced_contact(
        recipient
    )
    if contact is None:
        contact = Contact.objects.create(
            contact_type=ContactType.ORGANIZATION,
            name=_recipient_display_name(recipient),
            email=primary_email[:254],
            phone=primary_phone[:40],
            destination=recipient.destination,
            notes=_build_contact_notes(recipient),
            is_active=recipient.is_active,
        )
    else:
        contact.contact_type = ContactType.ORGANIZATION
        contact.name = _recipient_display_name(recipient)
        contact.email = primary_email[:254]
        contact.phone = primary_phone[:40]
        contact.destination = recipient.destination
        contact.notes = _build_contact_notes(recipient)
        contact.is_active = recipient.is_active
        contact.save(
            update_fields=[
                "contact_type",
                "name",
                "email",
                "phone",
                "destination",
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

    contact.tags.add(recipient_tag)
    if recipient.destination_id:
        contact.destinations.set([recipient.destination_id])
    else:
        contact.destinations.clear()
    for shipper_id in _candidate_shipper_ids_for_association(
        recipient.association_contact
    ):
        contact.linked_shippers.add(shipper_id)
    ensure_default_shipper_for_recipient(contact)
    return contact
