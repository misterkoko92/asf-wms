from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from contacts.models import Contact, ContactType

from .compliance import is_role_operation_allowed
from .models import (
    OrganizationRole,
    OrganizationRoleAssignment,
    RecipientBinding,
    ShipperScope,
)

MESSAGE_DESTINATION_REQUIRED = "Escale requise."
MESSAGE_SHIPPER_REQUIRED = "Expediteur requis."
MESSAGE_SHIPPER_REVIEW_PENDING = "Expediteur en cours de revue ASF."
MESSAGE_SHIPPER_COMPLIANCE_REQUIRED = "Expediteur non conforme: documents manquants."
MESSAGE_SHIPPER_OUT_OF_SCOPE = "Expediteur non autorise pour cette escale."
MESSAGE_RECIPIENT_REQUIRED = "Destinataire requis."
MESSAGE_RECIPIENT_REVIEW_PENDING = "Destinataire en cours de revue ASF."
MESSAGE_RECIPIENT_COMPLIANCE_REQUIRED = "Destinataire non conforme: documents manquants."
MESSAGE_RECIPIENT_BINDING_MISSING = "Destinataire non autorise pour cet expediteur et cette escale."


class OrganizationRoleResolutionError(Exception):
    pass


def _current_window_q(prefix: str = ""):
    now = timezone.now()
    return Q(**{f"{prefix}valid_from__lte": now}) & (
        Q(**{f"{prefix}valid_to__isnull": True}) | Q(**{f"{prefix}valid_to__gt": now})
    )


def active_organizations_for_roles(*roles):
    normalized_roles = [role for role in roles if role]
    if not normalized_roles:
        return Contact.objects.none()
    return (
        Contact.objects.filter(
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            organization_role_assignments__role__in=normalized_roles,
            organization_role_assignments__is_active=True,
        )
        .order_by("name")
        .distinct()
    )


def active_organizations_for_role(role):
    return active_organizations_for_roles(role)


def eligible_shippers_for_destination(destination):
    if destination is None:
        return Contact.objects.none()

    assignment_ids = (
        ShipperScope.objects.filter(
            is_active=True,
        )
        .filter(
            _current_window_q(),
        )
        .filter(Q(all_destinations=True) | Q(destination=destination))
        .values_list("role_assignment_id", flat=True)
    )

    org_ids = OrganizationRoleAssignment.objects.filter(
        id__in=assignment_ids,
        role=OrganizationRole.SHIPPER,
        is_active=True,
        organization__is_active=True,
        organization__contact_type=ContactType.ORGANIZATION,
    ).values_list("organization_id", flat=True)

    return Contact.objects.filter(pk__in=org_ids).order_by("name").distinct()


def eligible_recipients_for_shipper_destination(*, shipper_org, destination):
    if shipper_org is None or destination is None:
        return Contact.objects.none()

    recipient_ids = (
        RecipientBinding.objects.filter(
            shipper_org=shipper_org,
            destination=destination,
            is_active=True,
        )
        .filter(_current_window_q())
        .values_list("recipient_org_id", flat=True)
    )

    return (
        Contact.objects.filter(
            pk__in=recipient_ids,
            is_active=True,
            contact_type=ContactType.ORGANIZATION,
        )
        .order_by("name")
        .distinct()
    )


def resolve_shipper_for_operation(*, shipper_org, destination):
    if destination is None:
        raise OrganizationRoleResolutionError(MESSAGE_DESTINATION_REQUIRED)
    if shipper_org is None:
        raise OrganizationRoleResolutionError(MESSAGE_SHIPPER_REQUIRED)

    assignment = (
        OrganizationRoleAssignment.objects.filter(
            organization=shipper_org,
            role=OrganizationRole.SHIPPER,
        )
        .order_by("id")
        .first()
    )

    if assignment is None or not assignment.is_active:
        raise OrganizationRoleResolutionError(MESSAGE_SHIPPER_REVIEW_PENDING)
    if not is_role_operation_allowed(assignment):
        raise OrganizationRoleResolutionError(MESSAGE_SHIPPER_COMPLIANCE_REQUIRED)

    in_scope = (
        ShipperScope.objects.filter(
            role_assignment=assignment,
            is_active=True,
        )
        .filter(
            _current_window_q(),
        )
        .filter(Q(all_destinations=True) | Q(destination=destination))
        .exists()
    )
    if not in_scope:
        raise OrganizationRoleResolutionError(MESSAGE_SHIPPER_OUT_OF_SCOPE)

    return assignment


def resolve_recipient_binding_for_operation(*, shipper_org, recipient_org, destination):
    if destination is None:
        raise OrganizationRoleResolutionError(MESSAGE_DESTINATION_REQUIRED)
    if recipient_org is None:
        raise OrganizationRoleResolutionError(MESSAGE_RECIPIENT_REQUIRED)
    if shipper_org is None:
        raise OrganizationRoleResolutionError(MESSAGE_SHIPPER_REQUIRED)

    recipient_assignment = (
        OrganizationRoleAssignment.objects.filter(
            organization=recipient_org,
            role=OrganizationRole.RECIPIENT,
        )
        .order_by("id")
        .first()
    )

    if recipient_assignment is None or not recipient_assignment.is_active:
        raise OrganizationRoleResolutionError(MESSAGE_RECIPIENT_REVIEW_PENDING)
    if not is_role_operation_allowed(recipient_assignment):
        raise OrganizationRoleResolutionError(MESSAGE_RECIPIENT_COMPLIANCE_REQUIRED)

    binding = (
        RecipientBinding.objects.filter(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination,
            is_active=True,
        )
        .filter(_current_window_q())
        .order_by("-valid_from", "-id")
        .first()
    )
    if binding is None:
        raise OrganizationRoleResolutionError(MESSAGE_RECIPIENT_BINDING_MISSING)

    return binding
