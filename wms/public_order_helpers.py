from contacts.models import Contact, ContactType

from .scan_helpers import parse_int


def _clean_text(value):
    return (value or "").strip()


def _resolve_existing_contact(form_data):
    contact_id = parse_int(form_data.get("association_contact_id"))
    if contact_id:
        contact = Contact.objects.filter(id=contact_id, is_active=True).first()
        if contact:
            return contact

    association_name = _clean_text(form_data.get("association_name"))
    if not association_name:
        return None
    return Contact.objects.filter(
        name__iexact=association_name,
        is_active=True,
    ).first()


def _sync_contact_identity(contact, form_data):
    updated_fields = []
    association_name = _clean_text(form_data.get("association_name"))
    association_email = _clean_text(form_data.get("association_email"))
    association_phone = _clean_text(form_data.get("association_phone"))

    if association_name and contact.name != association_name:
        contact.name = association_name
        updated_fields.append("name")
    if association_email and contact.email != association_email:
        contact.email = association_email
        updated_fields.append("email")
    if association_phone and contact.phone != association_phone:
        contact.phone = association_phone
        updated_fields.append("phone")
    if contact.contact_type != ContactType.ORGANIZATION:
        contact.contact_type = ContactType.ORGANIZATION
        updated_fields.append("contact_type")
    if not contact.is_active:
        contact.is_active = True
        updated_fields.append("is_active")
    if updated_fields:
        contact.save(update_fields=updated_fields)


def upsert_public_order_contact(form_data):
    contact = _resolve_existing_contact(form_data)
    if not contact:
        contact = Contact.objects.create(
            name=_clean_text(form_data.get("association_name")),
            contact_type=ContactType.ORGANIZATION,
            email=_clean_text(form_data.get("association_email")),
            phone=_clean_text(form_data.get("association_phone")),
            is_active=True,
        )

    _sync_contact_identity(contact, form_data)
    return contact
