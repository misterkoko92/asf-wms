from __future__ import annotations

from django.db.models import Q

from contacts.models import Contact, ContactType

from .models import OrganizationRole, OrganizationRoleAssignment, RecipientBinding


ROLE_VALUES = {choice[0] for choice in OrganizationRole.choices}


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
