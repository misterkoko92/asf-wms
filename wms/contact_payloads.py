from .contact_filters import TAG_SHIPPER, contacts_with_tags
from .portal_helpers import get_contact_address


def build_shipper_contact_payload():
    contacts = list(
        contacts_with_tags(TAG_SHIPPER).prefetch_related("addresses").order_by("name")
    )
    payload = []
    for contact in contacts:
        address = get_contact_address(contact)
        payload.append(
            {
                "id": contact.id,
                "name": contact.name,
                "email": contact.email or "",
                "phone": contact.phone or "",
                "address_line1": address.address_line1 if address else "",
                "address_line2": address.address_line2 if address else "",
                "postal_code": address.postal_code if address else "",
                "city": address.city if address else "",
                "country": address.country if address else "",
            }
        )
    return payload
