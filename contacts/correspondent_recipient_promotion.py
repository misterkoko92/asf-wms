from contacts.models import Contact, ContactTag, ContactType
from contacts.rules import tags_match
from contacts.tagging import TAG_CORRESPONDENT, TAG_RECIPIENT, normalize_tag_name
from wms.models import OrganizationRole, OrganizationRoleAssignment

RECIPIENT_TAG_DEFAULT_NAME = "Destinataire"
SUPPORT_ORGANIZATION_NAME = "ASF - CORRESPONDANT"
SUPPORT_ORGANIZATION_NOTES_MARKER = "[system] correspondent recipient support organization"


def _get_or_create_recipient_tag() -> ContactTag:
    normalized_targets = {
        normalize_tag_name(alias) for alias in TAG_RECIPIENT if normalize_tag_name(alias)
    }
    for tag in ContactTag.objects.only("id", "name"):
        if normalize_tag_name(tag.name) in normalized_targets:
            return tag
    return ContactTag.objects.create(name=RECIPIENT_TAG_DEFAULT_NAME)


def _get_or_create_support_organization():
    existing = (
        Contact.objects.filter(
            name__iexact=SUPPORT_ORGANIZATION_NAME,
            contact_type=ContactType.ORGANIZATION,
        )
        .order_by("-is_active", "id")
        .first()
    )
    if existing is None:
        return Contact.objects.create(
            name=SUPPORT_ORGANIZATION_NAME,
            contact_type=ContactType.ORGANIZATION,
            notes=SUPPORT_ORGANIZATION_NOTES_MARKER,
            is_active=True,
        )

    updated_fields = []
    if not existing.is_active:
        existing.is_active = True
        updated_fields.append("is_active")
    notes = (existing.notes or "").strip()
    if SUPPORT_ORGANIZATION_NOTES_MARKER not in notes:
        existing.notes = (
            f"{notes}\n{SUPPORT_ORGANIZATION_NOTES_MARKER}".strip()
            if notes
            else SUPPORT_ORGANIZATION_NOTES_MARKER
        )
        updated_fields.append("notes")
    if updated_fields:
        existing.save(update_fields=updated_fields)
    return existing


def _resolve_recipient_organization(contact):
    if contact.contact_type == ContactType.ORGANIZATION:
        return contact
    if contact.contact_type != ContactType.PERSON:
        return None
    if contact.organization_id:
        organization = contact.organization
        if organization and organization.contact_type == ContactType.ORGANIZATION:
            if not organization.is_active:
                organization.is_active = True
                organization.save(update_fields=["is_active"])
            return organization
    support_organization = _get_or_create_support_organization()
    if contact.organization_id != support_organization.id:
        contact.organization = support_organization
        contact.save(update_fields=["organization"])
    return support_organization


def promote_correspondent_to_recipient_ready(contact, *, tags=None) -> bool:
    if not contact or not contact.pk:
        return False
    tag_source = tags if tags is not None else contact.tags.all()
    if not tags_match(tag_source, TAG_CORRESPONDENT):
        return False
    if not contact.is_active:
        return False

    changed = False
    organization = _resolve_recipient_organization(contact)
    if organization is None:
        return False
    recipient_tag = _get_or_create_recipient_tag()
    if not contact.tags.filter(pk=recipient_tag.pk).exists():
        contact.tags.add(recipient_tag)
        changed = True

    assignment, created = OrganizationRoleAssignment.objects.get_or_create(
        organization=organization,
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
