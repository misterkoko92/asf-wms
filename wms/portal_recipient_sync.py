from contacts.models import Contact, ContactAddress, ContactTag, ContactType
from contacts.rules import ensure_default_shipper_for_recipient
from contacts.tagging import TAG_RECIPIENT, normalize_tag_name

RECIPIENT_TAG_DEFAULT_NAME = "Destinataire"
PORTAL_RECIPIENT_SOURCE_PREFIX = "[Portail association]"


def _first_multi_value(raw_value: str, fallback: str = "") -> str:
    value = (raw_value or "").replace("\n", ";").replace(",", ";")
    for item in value.split(";"):
        normalized = item.strip()
        if normalized:
            return normalized
    return (fallback or "").strip()


def _build_contact_notes(recipient) -> str:
    notes = (recipient.notes or "").strip()
    source = f"{PORTAL_RECIPIENT_SOURCE_PREFIX} {recipient.association_contact}"
    if notes:
        return f"{source}\n{notes}"
    return source


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


def sync_association_recipient_to_contact(recipient):
    if not recipient:
        return None
    recipient_tag = _get_or_create_recipient_tag()
    primary_email = _first_multi_value(recipient.emails, recipient.email)
    primary_phone = _first_multi_value(recipient.phones, recipient.phone)

    contact = Contact.objects.create(
        contact_type=ContactType.ORGANIZATION,
        name=_recipient_display_name(recipient),
        email=primary_email[:254],
        phone=primary_phone[:40],
        destination=recipient.destination,
        notes=_build_contact_notes(recipient),
        is_active=recipient.is_active,
    )

    if recipient.address_line1:
        ContactAddress.objects.create(
            contact=contact,
            label="Portail association",
            address_line1=recipient.address_line1,
            address_line2=recipient.address_line2,
            postal_code=recipient.postal_code,
            city=recipient.city,
            country=recipient.country or "France",
            phone=primary_phone[:40],
            email=primary_email[:254],
            is_default=True,
            notes=recipient.notes or "",
        )

    contact.tags.add(recipient_tag)
    if recipient.destination_id:
        contact.destinations.add(recipient.destination_id)
    if recipient.association_contact_id:
        contact.linked_shippers.add(recipient.association_contact_id)
    ensure_default_shipper_for_recipient(contact)
    return contact
