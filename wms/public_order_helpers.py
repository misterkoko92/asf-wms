from contacts.models import Contact, ContactAddress, ContactTag

from .contact_filters import TAG_SHIPPER
from .scan_helpers import parse_int


def upsert_public_order_contact(form_data):
    contact_id = parse_int(form_data.get("association_contact_id"))
    contact = None
    if contact_id:
        contact = Contact.objects.filter(id=contact_id, is_active=True).first()
    if not contact:
        contact = Contact.objects.filter(
            name__iexact=form_data.get("association_name"), is_active=True
        ).first()

    if not contact:
        contact = Contact.objects.create(
            name=form_data.get("association_name"),
            email=form_data.get("association_email"),
            phone=form_data.get("association_phone"),
            is_active=True,
        )
        tag, _ = ContactTag.objects.get_or_create(name=TAG_SHIPPER[0])
        contact.tags.add(tag)
        ContactAddress.objects.create(
            contact=contact,
            address_line1=form_data.get("association_line1"),
            address_line2=form_data.get("association_line2"),
            postal_code=form_data.get("association_postal_code"),
            city=form_data.get("association_city"),
            country=form_data.get("association_country") or "France",
            phone=form_data.get("association_phone"),
            email=form_data.get("association_email"),
            is_default=True,
        )
        return contact

    updated_fields = []
    if (
        form_data.get("association_email")
        and contact.email != form_data.get("association_email")
    ):
        contact.email = form_data.get("association_email")
        updated_fields.append("email")
    if (
        form_data.get("association_phone")
        and contact.phone != form_data.get("association_phone")
    ):
        contact.phone = form_data.get("association_phone")
        updated_fields.append("phone")
    if updated_fields:
        contact.save(update_fields=updated_fields)

    address = (
        contact.addresses.filter(is_default=True).first()
        or contact.addresses.first()
    )
    if address:
        address.address_line1 = form_data.get("association_line1")
        address.address_line2 = form_data.get("association_line2")
        address.postal_code = form_data.get("association_postal_code")
        address.city = form_data.get("association_city")
        address.country = form_data.get("association_country") or "France"
        address.phone = form_data.get("association_phone")
        address.email = form_data.get("association_email")
        address.save(
            update_fields=[
                "address_line1",
                "address_line2",
                "postal_code",
                "city",
                "country",
                "phone",
                "email",
            ]
        )
    else:
        ContactAddress.objects.create(
            contact=contact,
            address_line1=form_data.get("association_line1"),
            address_line2=form_data.get("association_line2"),
            postal_code=form_data.get("association_postal_code"),
            city=form_data.get("association_city"),
            country=form_data.get("association_country") or "France",
            phone=form_data.get("association_phone"),
            email=form_data.get("association_email"),
            is_default=True,
        )
    return contact
