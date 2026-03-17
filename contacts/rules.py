from contacts.models import Contact
from contacts.tagging import TAG_RECIPIENT, normalize_tag_name
from wms.models import OrganizationRole
from wms.organization_role_resolvers import active_organizations_for_role

DEFAULT_RECIPIENT_SHIPPER_NAME = "AVIATION SANS FRONTIERES"
ERROR_RECIPIENT_LINKED_SHIPPERS_REQUIRED = (
    "Au moins un expéditeur lié est requis pour créer un destinataire."
)


def tags_match(tag_objects, expected_tags):
    expected = {
        normalize_tag_name(tag_name) for tag_name in expected_tags if normalize_tag_name(tag_name)
    }
    if not expected:
        return False
    return any(
        normalize_tag_name(getattr(tag, "name", tag)) in expected for tag in (tag_objects or [])
    )


def get_default_recipient_shipper():
    return (
        active_organizations_for_role(OrganizationRole.SHIPPER)
        .filter(name__iexact=DEFAULT_RECIPIENT_SHIPPER_NAME)
        .first()
        or Contact.objects.filter(
            contact_type="organization",
            is_active=True,
            name__iexact=DEFAULT_RECIPIENT_SHIPPER_NAME,
        ).first()
    )


def validate_recipient_links_for_creation(*, is_creation, tags, linked_shippers):
    return None


def ensure_default_shipper_for_recipient(contact, *, tags=None):
    return False
