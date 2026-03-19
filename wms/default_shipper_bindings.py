from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

from django.utils import timezone

from contacts.models import Contact, ContactType

from .models import (
    Destination,
    OrganizationRole,
    OrganizationRoleAssignment,
    RecipientBinding,
    ShipperScope,
)

_DEFAULT_SHIPPER_BINDING_SYNC_ENABLED = ContextVar(
    "default_shipper_binding_sync_enabled",
    default=True,
)
DEFAULT_RECIPIENT_SHIPPER_NAME = "AVIATION SANS FRONTIERES"


def default_shipper_binding_sync_enabled() -> bool:
    return _DEFAULT_SHIPPER_BINDING_SYNC_ENABLED.get()


@contextmanager
def suppress_default_shipper_binding_sync():
    token = _DEFAULT_SHIPPER_BINDING_SYNC_ENABLED.set(False)
    try:
        yield
    finally:
        _DEFAULT_SHIPPER_BINDING_SYNC_ENABLED.reset(token)


def _resolve_default_shipper_organization() -> Contact | None:
    default_shipper = (
        OrganizationRoleAssignment.objects.filter(
            role=OrganizationRole.SHIPPER,
            is_active=True,
            organization__is_active=True,
            organization__name__iexact=DEFAULT_RECIPIENT_SHIPPER_NAME,
        )
        .select_related("organization")
        .order_by("id")
        .first()
    )
    default_shipper = default_shipper.organization if default_shipper else None
    if default_shipper is None:
        default_shipper = Contact.objects.filter(
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            name__iexact=DEFAULT_RECIPIENT_SHIPPER_NAME,
        ).first()
    if default_shipper is None:
        return None
    if default_shipper.contact_type == ContactType.ORGANIZATION:
        return default_shipper if default_shipper.is_active else None

    organization = default_shipper.organization
    if (
        organization
        and organization.is_active
        and organization.contact_type == ContactType.ORGANIZATION
    ):
        return organization
    return None


def _ensure_default_shipper_assignment_and_scope(shipper_org: Contact) -> None:
    assignment, _created = OrganizationRoleAssignment.objects.get_or_create(
        organization=shipper_org,
        role=OrganizationRole.SHIPPER,
        defaults={"is_active": True},
    )
    if not assignment.is_active:
        assignment.is_active = True
        assignment.save(update_fields=["is_active", "updated_at"])

    global_scope = (
        ShipperScope.objects.filter(
            role_assignment=assignment,
            all_destinations=True,
        )
        .order_by("-is_active", "-id")
        .first()
    )
    if global_scope is None:
        ShipperScope.objects.create(
            role_assignment=assignment,
            all_destinations=True,
            destination=None,
            is_active=True,
            valid_from=timezone.now(),
        )
        return
    updated_fields = []
    if global_scope.destination_id is not None:
        global_scope.destination = None
        updated_fields.append("destination")
    if not global_scope.is_active:
        global_scope.is_active = True
        updated_fields.append("is_active")
    if updated_fields:
        updated_fields.append("updated_at")
        global_scope.save(update_fields=updated_fields)


def _ensure_bindings_for_pairs(
    *,
    shipper_org: Contact,
    recipient_org_ids: list[int],
    destination_ids: list[int],
) -> int:
    if not recipient_org_ids or not destination_ids:
        return 0

    existing_pairs = set(
        RecipientBinding.objects.filter(
            shipper_org=shipper_org,
            recipient_org_id__in=recipient_org_ids,
            destination_id__in=destination_ids,
            is_active=True,
        ).values_list("recipient_org_id", "destination_id")
    )

    created = 0
    now = timezone.now()
    for recipient_org_id in recipient_org_ids:
        for destination_id in destination_ids:
            pair = (recipient_org_id, destination_id)
            if pair in existing_pairs:
                continue
            RecipientBinding.objects.create(
                shipper_org=shipper_org,
                recipient_org_id=recipient_org_id,
                destination_id=destination_id,
                is_active=True,
                valid_from=now,
            )
            existing_pairs.add(pair)
            created += 1
    return created


def ensure_default_shipper_bindings_for_destination_id(destination_id: int) -> int:
    destination = Destination.objects.filter(pk=destination_id, is_active=True).only("id").first()
    if destination is None:
        return 0

    shipper_org = _resolve_default_shipper_organization()
    if shipper_org is None:
        return 0
    _ensure_default_shipper_assignment_and_scope(shipper_org)

    recipient_org_ids = list(
        OrganizationRoleAssignment.objects.filter(
            role=OrganizationRole.RECIPIENT,
            is_active=True,
            organization__is_active=True,
            organization__contact_type=ContactType.ORGANIZATION,
        ).values_list("organization_id", flat=True)
    )
    return _ensure_bindings_for_pairs(
        shipper_org=shipper_org,
        recipient_org_ids=recipient_org_ids,
        destination_ids=[destination.id],
    )


def ensure_default_shipper_bindings_for_recipient_assignment_id(
    role_assignment_id: int,
) -> int:
    role_assignment = (
        OrganizationRoleAssignment.objects.filter(
            pk=role_assignment_id,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
            organization__is_active=True,
            organization__contact_type=ContactType.ORGANIZATION,
        )
        .select_related("organization")
        .first()
    )
    if role_assignment is None:
        return 0

    shipper_org = _resolve_default_shipper_organization()
    if shipper_org is None:
        return 0
    _ensure_default_shipper_assignment_and_scope(shipper_org)

    destination_ids = list(Destination.objects.filter(is_active=True).values_list("id", flat=True))
    return _ensure_bindings_for_pairs(
        shipper_org=shipper_org,
        recipient_org_ids=[role_assignment.organization_id],
        destination_ids=destination_ids,
    )
