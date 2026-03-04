from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from contacts.models import Contact, ContactType
from contacts.querysets import contacts_with_tags
from contacts.tagging import (
    TAG_CORRESPONDENT,
    TAG_DONOR,
    TAG_RECIPIENT,
    TAG_SHIPPER,
    TAG_TRANSPORTER,
)

from .models import (
    MigrationReviewItem,
    MigrationReviewItemStatus,
    OrganizationRole,
    OrganizationRoleAssignment,
    RecipientBinding,
    ShipperScope,
)

ROLE_TAGS = {
    OrganizationRole.SHIPPER: TAG_SHIPPER,
    OrganizationRole.RECIPIENT: TAG_RECIPIENT,
    OrganizationRole.CORRESPONDENT: TAG_CORRESPONDENT,
    OrganizationRole.DONOR: TAG_DONOR,
    OrganizationRole.TRANSPORTER: TAG_TRANSPORTER,
}

ROLE_DEFAULT_ACTIVE = {
    OrganizationRole.SHIPPER: True,
    OrganizationRole.RECIPIENT: True,
    OrganizationRole.CORRESPONDENT: True,
    OrganizationRole.DONOR: True,
    OrganizationRole.TRANSPORTER: True,
}

REVIEW_REASON_UNSUPPORTED_CONTACT_TYPE = "unsupported_contact_type"
REVIEW_REASON_MISSING_DESTINATION = "missing_destination"
REVIEW_REASON_MISSING_SHIPPER_LINKS = "missing_shipper_links"


def _contact_destination_ids(contact: Contact) -> list[int]:
    destination_ids = set(contact.destinations.values_list("id", flat=True))
    if contact.destination_id:
        destination_ids.add(contact.destination_id)
    return sorted(destination_ids)


def _queue_review_item(*, legacy_contact, organization, role, reason_code, payload) -> bool:
    _item, created = MigrationReviewItem.objects.get_or_create(
        legacy_contact=legacy_contact,
        organization=organization,
        role=role,
        reason_code=reason_code,
        status=MigrationReviewItemStatus.OPEN,
        defaults={"payload": payload or {}},
    )
    return created


def _ensure_role_assignment(*, organization: Contact, role: str):
    return OrganizationRoleAssignment.objects.get_or_create(
        organization=organization,
        role=role,
        defaults={"is_active": ROLE_DEFAULT_ACTIVE.get(role, True)},
    )


def _backfill_shipper_scope(*, shipper_assignment, source_contact, now, stats):
    destination_ids = _contact_destination_ids(source_contact)
    if not destination_ids:
        _scope, created = ShipperScope.objects.get_or_create(
            role_assignment=shipper_assignment,
            all_destinations=True,
            is_active=True,
            defaults={"destination": None, "valid_from": now},
        )
        if created:
            stats["created_shipper_scopes"] += 1
        return

    for destination_id in destination_ids:
        _scope, created = ShipperScope.objects.get_or_create(
            role_assignment=shipper_assignment,
            destination_id=destination_id,
            defaults={
                "all_destinations": False,
                "is_active": True,
                "valid_from": now,
            },
        )
        if created:
            stats["created_shipper_scopes"] += 1


def _backfill_recipient_bindings(*, recipient_contact, recipient_assignment, now, stats):
    destination_ids = _contact_destination_ids(recipient_contact)
    if not destination_ids:
        if _queue_review_item(
            legacy_contact=recipient_contact,
            organization=recipient_contact,
            role=recipient_assignment.role,
            reason_code=REVIEW_REASON_MISSING_DESTINATION,
            payload={"recipient_id": recipient_contact.id},
        ):
            stats["queued_review_items"] += 1
        return

    linked_shippers = list(
        recipient_contact.linked_shippers.filter(
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
    )
    if not linked_shippers:
        if _queue_review_item(
            legacy_contact=recipient_contact,
            organization=recipient_contact,
            role=recipient_assignment.role,
            reason_code=REVIEW_REASON_MISSING_SHIPPER_LINKS,
            payload={"recipient_id": recipient_contact.id},
        ):
            stats["queued_review_items"] += 1
        return

    for shipper_contact in linked_shippers:
        shipper_assignment, _created = _ensure_role_assignment(
            organization=shipper_contact,
            role=OrganizationRole.SHIPPER,
        )
        for destination_id in destination_ids:
            _binding, created = RecipientBinding.objects.get_or_create(
                shipper_org=shipper_assignment.organization,
                recipient_org=recipient_assignment.organization,
                destination_id=destination_id,
                is_active=True,
                defaults={"valid_from": now},
            )
            if created:
                stats["created_recipient_bindings"] += 1


def _execute_backfill():
    now = timezone.now()
    stats = {
        "processed_contacts": 0,
        "created_role_assignments": 0,
        "created_shipper_scopes": 0,
        "created_recipient_bindings": 0,
        "queued_review_items": 0,
    }

    for role, tag_names in ROLE_TAGS.items():
        for contact in contacts_with_tags(tag_names).prefetch_related(
            "destinations",
            "linked_shippers",
        ):
            stats["processed_contacts"] += 1
            if contact.contact_type != ContactType.ORGANIZATION:
                if _queue_review_item(
                    legacy_contact=contact,
                    organization=contact.organization,
                    role=role,
                    reason_code=REVIEW_REASON_UNSUPPORTED_CONTACT_TYPE,
                    payload={"contact_id": contact.id, "contact_type": contact.contact_type},
                ):
                    stats["queued_review_items"] += 1
                continue

            assignment, created = _ensure_role_assignment(
                organization=contact,
                role=role,
            )
            if created:
                stats["created_role_assignments"] += 1

            if role == OrganizationRole.SHIPPER:
                _backfill_shipper_scope(
                    shipper_assignment=assignment,
                    source_contact=contact,
                    now=now,
                    stats=stats,
                )
            elif role == OrganizationRole.RECIPIENT:
                _backfill_recipient_bindings(
                    recipient_contact=contact,
                    recipient_assignment=assignment,
                    now=now,
                    stats=stats,
                )

    return stats


def backfill_contacts_to_org_roles(*, dry_run=False):
    if not dry_run:
        return _execute_backfill()

    with transaction.atomic():
        stats = _execute_backfill()
        transaction.set_rollback(True)
        return stats
