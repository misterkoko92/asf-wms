from contacts.models import Contact, ContactCapability, ContactCapabilityType, ContactType


def ensure_contact_capability(contact: Contact, capability: str) -> ContactCapability:
    capability_row, _created = ContactCapability.objects.get_or_create(
        contact=contact,
        capability=capability,
        defaults={"is_active": True},
    )
    if not capability_row.is_active:
        capability_row.is_active = True
        capability_row.save(update_fields=["is_active"])
    return capability_row


def active_contacts_for_capability(capability: str):
    return (
        Contact.objects.filter(
            is_active=True,
            capabilities__capability=capability,
            capabilities__is_active=True,
        )
        .distinct()
        .order_by("name")
    )


def active_organizations_for_capability(capability: str):
    return active_contacts_for_capability(capability).filter(contact_type=ContactType.ORGANIZATION)


__all__ = [
    "ContactCapability",
    "ContactCapabilityType",
    "active_contacts_for_capability",
    "active_organizations_for_capability",
    "ensure_contact_capability",
]
