from dataclasses import dataclass

from django.db import transaction

from contacts.destination_scope import contact_destination_ids, set_contact_destination_scope
from contacts.models import Contact, ContactTag, ContactType
from contacts.querysets import contacts_with_tags
from contacts.rules import tags_match
from contacts.tagging import TAG_CORRESPONDENT, TAG_RECIPIENT, normalize_tag_name
from wms.models import Destination, OrganizationRole, OrganizationRoleAssignment

RECIPIENT_TAG_DEFAULT_NAME = "Destinataire"
SUPPORT_ORGANIZATION_NAME = "ASF - CORRESPONDANT"
SUPPORT_ORGANIZATION_NOTES_MARKER = "[system] correspondent recipient support organization"


@dataclass(frozen=True)
class CorrespondentRecipientPromotionResult:
    changed: bool = False
    recipient_tag_added: bool = False
    support_organization_created: bool = False
    attached_to_support_organization: bool = False
    destination_scope_synced: bool = False
    recipient_role_created: bool = False
    recipient_role_reactivated: bool = False


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
        return (
            Contact.objects.create(
                name=SUPPORT_ORGANIZATION_NAME,
                contact_type=ContactType.ORGANIZATION,
                notes=SUPPORT_ORGANIZATION_NOTES_MARKER,
                is_active=True,
            ),
            True,
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
    return existing, False


def _resolve_recipient_organization(contact):
    if contact.contact_type == ContactType.ORGANIZATION:
        return contact, False, False
    if contact.contact_type != ContactType.PERSON:
        return None, False, False
    if contact.organization_id:
        organization = contact.organization
        if organization and organization.contact_type == ContactType.ORGANIZATION:
            if not organization.is_active:
                organization.is_active = True
                organization.save(update_fields=["is_active"])
            return organization, False, False
    support_organization, created = _get_or_create_support_organization()
    if contact.organization_id != support_organization.id:
        contact.organization = support_organization
        contact.save(update_fields=["organization"])
        return support_organization, created, True
    return support_organization, created, False


def _destination_ids_from_correspondent_assignments(contact) -> list[int]:
    return sorted(
        Destination.objects.filter(
            correspondent_contact=contact,
            is_active=True,
        ).values_list("id", flat=True)
    )


def promote_correspondent_to_recipient_ready(
    contact, *, tags=None
) -> CorrespondentRecipientPromotionResult:
    if not contact or not contact.pk:
        return CorrespondentRecipientPromotionResult()
    tag_source = tags if tags is not None else contact.tags.all()
    if not tags_match(tag_source, TAG_CORRESPONDENT):
        return CorrespondentRecipientPromotionResult()
    if not contact.is_active:
        return CorrespondentRecipientPromotionResult()

    organization, support_created, attached_to_support = _resolve_recipient_organization(contact)
    if organization is None:
        return CorrespondentRecipientPromotionResult()

    recipient_tag_added = False
    recipient_tag = _get_or_create_recipient_tag()
    if not contact.tags.filter(pk=recipient_tag.pk).exists():
        contact.tags.add(recipient_tag)
        recipient_tag_added = True

    destination_scope_synced = False
    destination_ids = _destination_ids_from_correspondent_assignments(contact)
    if destination_ids and contact_destination_ids(contact) != destination_ids:
        set_contact_destination_scope(contact=contact, destination_ids=destination_ids)
        destination_scope_synced = True

    assignment, created = OrganizationRoleAssignment.objects.get_or_create(
        organization=organization,
        role=OrganizationRole.RECIPIENT,
        defaults={"is_active": True},
    )
    reactivated = False
    if not assignment.is_active:
        assignment.is_active = True
        assignment.save(update_fields=["is_active"])
        reactivated = True
    return CorrespondentRecipientPromotionResult(
        changed=any(
            [
                recipient_tag_added,
                support_created,
                attached_to_support,
                destination_scope_synced,
                created,
                reactivated,
            ]
        ),
        recipient_tag_added=recipient_tag_added,
        support_organization_created=support_created,
        attached_to_support_organization=attached_to_support,
        destination_scope_synced=destination_scope_synced,
        recipient_role_created=created,
        recipient_role_reactivated=reactivated,
    )


def _backfill_correspondent_recipients_impl():
    summary = {
        "processed_contacts": 0,
        "changed_contacts": 0,
        "recipient_tags_added": 0,
        "support_organizations_created": 0,
        "contacts_attached_to_support_org": 0,
        "recipient_roles_created": 0,
        "recipient_roles_reactivated": 0,
    }
    correspondents = contacts_with_tags(TAG_CORRESPONDENT).select_related("organization")
    for contact in correspondents:
        summary["processed_contacts"] += 1
        result = promote_correspondent_to_recipient_ready(contact)
        if result.changed:
            summary["changed_contacts"] += 1
        if result.recipient_tag_added:
            summary["recipient_tags_added"] += 1
        if result.support_organization_created:
            summary["support_organizations_created"] += 1
        if result.attached_to_support_organization:
            summary["contacts_attached_to_support_org"] += 1
        if result.recipient_role_created:
            summary["recipient_roles_created"] += 1
        if result.recipient_role_reactivated:
            summary["recipient_roles_reactivated"] += 1
    return summary


def backfill_correspondent_recipients(*, dry_run=False):
    if not dry_run:
        return _backfill_correspondent_recipients_impl()

    with transaction.atomic():
        summary = _backfill_correspondent_recipients_impl()
        transaction.set_rollback(True)
        return summary
