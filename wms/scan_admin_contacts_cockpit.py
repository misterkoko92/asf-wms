from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db.models import Q

from contacts.models import Contact, ContactType

from .models import OrganizationRole, OrganizationRoleAssignment, RecipientBinding


ROLE_VALUES = {choice[0] for choice in OrganizationRole.choices}
ACTION_ASSIGN_ROLE = "assign_role"
ACTION_UNASSIGN_ROLE = "unassign_role"


def parse_cockpit_filters(*, role: str = "", shipper_org_id: str = "") -> dict:
    normalized_role = (role or "").strip().lower()
    if normalized_role not in ROLE_VALUES:
        normalized_role = ""
    normalized_shipper_org_id = (shipper_org_id or "").strip()
    if normalized_shipper_org_id and not normalized_shipper_org_id.isdigit():
        normalized_shipper_org_id = ""
    return {
        "role": normalized_role,
        "shipper_org_id": normalized_shipper_org_id,
    }


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_role(role: str) -> str:
    normalized_role = (role or "").strip().lower()
    if normalized_role in ROLE_VALUES:
        return normalized_role
    return ""


def _validation_message(exc: ValidationError) -> str:
    if getattr(exc, "message_dict", None):
        for messages in exc.message_dict.values():
            if messages:
                return str(messages[0])
    if getattr(exc, "messages", None):
        return str(exc.messages[0])
    return "Validation impossible."


def _resolve_active_organization(organization_id: str):
    resolved_id = _to_int(organization_id)
    if not resolved_id:
        return None
    return Contact.objects.filter(
        pk=resolved_id,
        contact_type=ContactType.ORGANIZATION,
        is_active=True,
    ).first()


def assign_role(*, organization_id: str, role: str) -> tuple[bool, str]:
    organization = _resolve_active_organization(organization_id)
    if organization is None:
        return False, "Organisation invalide."
    normalized_role = _normalize_role(role)
    if not normalized_role:
        return False, "Role invalide."

    assignment, _created = OrganizationRoleAssignment.objects.get_or_create(
        organization=organization,
        role=normalized_role,
        defaults={"is_active": False},
    )
    assignment.is_active = True
    try:
        assignment.save()
    except ValidationError as exc:
        assignment.is_active = False
        assignment.save(update_fields=["is_active"])
        return False, _validation_message(exc)

    return True, f"Role {assignment.get_role_display()} active."


def unassign_role(*, organization_id: str, role: str) -> tuple[bool, str]:
    organization = _resolve_active_organization(organization_id)
    if organization is None:
        return False, "Organisation invalide."
    normalized_role = _normalize_role(role)
    if not normalized_role:
        return False, "Role invalide."

    assignment = OrganizationRoleAssignment.objects.filter(
        organization=organization,
        role=normalized_role,
    ).first()
    if assignment is None:
        return False, "Role introuvable."
    if not assignment.is_active:
        return True, f"Role {assignment.get_role_display()} deja inactif."

    assignment.is_active = False
    assignment.save(update_fields=["is_active"])
    return True, f"Role {assignment.get_role_display()} desactive."


def _build_organizations_queryset(*, query: str, filters: dict):
    queryset = Contact.objects.filter(
        contact_type=ContactType.ORGANIZATION,
        is_active=True,
    )
    role = (filters.get("role") or "").strip().lower()
    if role:
        queryset = queryset.filter(
            organization_role_assignments__role=role,
            organization_role_assignments__is_active=True,
        )

    shipper_org_id = (filters.get("shipper_org_id") or "").strip()
    if shipper_org_id:
        queryset = queryset.filter(
            recipient_bindings_as_recipient__shipper_org_id=int(shipper_org_id),
            recipient_bindings_as_recipient__is_active=True,
        )

    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(asf_id__icontains=query)
            | Q(email__icontains=query)
            | Q(phone__icontains=query)
            | Q(destinations__iata_code__icontains=query)
            | Q(recipient_bindings_as_recipient__destination__iata_code__icontains=query)
        )

    return queryset.order_by("name", "id").distinct()


def build_cockpit_rows(*, query: str, filters: dict) -> list[dict]:
    organizations = list(_build_organizations_queryset(query=query, filters=filters))
    rows = []
    for organization in organizations:
        assignments = list(
            OrganizationRoleAssignment.objects.filter(
                organization=organization,
                is_active=True,
            ).order_by("role", "id")
        )
        active_roles = [assignment.role for assignment in assignments]
        recipient_bindings_count = RecipientBinding.objects.filter(
            recipient_org=organization,
            is_active=True,
        ).count()
        rows.append(
            {
                "organization": organization,
                "active_roles": active_roles,
                "recipient_bindings_count": recipient_bindings_count,
            }
        )
    return rows


def build_cockpit_context(*, query: str, filters: dict) -> dict:
    return {
        "query": query,
        "cockpit_filters": filters,
        "cockpit_rows": build_cockpit_rows(query=query, filters=filters),
        "cockpit_mode": "org_roles",
    }
