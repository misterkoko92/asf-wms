from contacts.models import Contact
from contacts.querysets import contacts_with_tags
from contacts.tagging import TAG_RECIPIENT, TAG_SHIPPER, normalize_tag_name

DEFAULT_RECIPIENT_SHIPPER_NAME = "AVIATION SANS FRONTIERES"
ERROR_RECIPIENT_LINKED_SHIPPERS_REQUIRED = (
    "Au moins un expéditeur lié est requis pour créer un destinataire."
)


def tags_match(tag_objects, expected_tags):
    expected = {
        normalize_tag_name(tag_name)
        for tag_name in expected_tags
        if normalize_tag_name(tag_name)
    }
    if not expected:
        return False
    return any(
        normalize_tag_name(getattr(tag, "name", tag)) in expected
        for tag in (tag_objects or [])
    )


def get_default_recipient_shipper():
    return (
        contacts_with_tags(TAG_SHIPPER)
        .filter(name__iexact=DEFAULT_RECIPIENT_SHIPPER_NAME)
        .first()
        or Contact.objects.filter(
            is_active=True,
            name__iexact=DEFAULT_RECIPIENT_SHIPPER_NAME,
        ).first()
    )


def validate_recipient_links_for_creation(*, is_creation, tags, linked_shippers):
    if is_creation and tags_match(tags, TAG_RECIPIENT) and not linked_shippers:
        return ERROR_RECIPIENT_LINKED_SHIPPERS_REQUIRED
    return None


def ensure_default_shipper_for_recipient(contact, *, tags=None):
    if not contact or not contact.pk:
        return False
    tag_source = tags if tags is not None else contact.tags.all()
    if not tags_match(tag_source, TAG_RECIPIENT):
        return False
    default_shipper = get_default_recipient_shipper()
    if not default_shipper or default_shipper.pk == contact.pk:
        return False
    if contact.linked_shippers.filter(pk=default_shipper.pk).exists():
        return False
    contact.linked_shippers.add(default_shipper)
    return True
