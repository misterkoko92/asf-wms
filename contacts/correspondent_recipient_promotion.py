from contacts.models import ContactTag, ContactType
from contacts.rules import tags_match
from contacts.tagging import TAG_CORRESPONDENT, TAG_RECIPIENT, normalize_tag_name
from wms.models import OrganizationRole, OrganizationRoleAssignment

RECIPIENT_TAG_DEFAULT_NAME = "Destinataire"


def _get_or_create_recipient_tag() -> ContactTag:
    normalized_targets = {
        normalize_tag_name(alias) for alias in TAG_RECIPIENT if normalize_tag_name(alias)
    }
    for tag in ContactTag.objects.only("id", "name"):
        if normalize_tag_name(tag.name) in normalized_targets:
            return tag
    return ContactTag.objects.create(name=RECIPIENT_TAG_DEFAULT_NAME)


def promote_correspondent_to_recipient_ready(contact, *, tags=None) -> bool:
    if not contact or not contact.pk:
        return False
    tag_source = tags if tags is not None else contact.tags.all()
    if not tags_match(tag_source, TAG_CORRESPONDENT):
        return False
    if contact.contact_type != ContactType.ORGANIZATION or not contact.is_active:
        return False

    changed = False
    recipient_tag = _get_or_create_recipient_tag()
    if not contact.tags.filter(pk=recipient_tag.pk).exists():
        contact.tags.add(recipient_tag)
        changed = True

    assignment, created = OrganizationRoleAssignment.objects.get_or_create(
        organization=contact,
        role=OrganizationRole.RECIPIENT,
        defaults={"is_active": True},
    )
    if created:
        return True
    if not assignment.is_active:
        assignment.is_active = True
        assignment.save(update_fields=["is_active"])
        changed = True
    return changed
