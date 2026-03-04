from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from contacts.models import Contact, ContactType

from .forms_scan_admin_contacts_cockpit import (
    OrganizationContactUpsertForm,
    RoleContactActionForm,
)
from .models import (
    OrganizationContact,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRoleContact,
    RecipientBinding,
)


ROLE_VALUES = {choice[0] for choice in OrganizationRole.choices}
ACTION_ASSIGN_ROLE = "assign_role"
ACTION_UNASSIGN_ROLE = "unassign_role"
ACTION_UPSERT_ORG_CONTACT = "upsert_org_contact"
ACTION_LINK_ROLE_CONTACT = "link_role_contact"
ACTION_UNLINK_ROLE_CONTACT = "unlink_role_contact"
ACTION_SET_PRIMARY_ROLE_CONTACT = "set_primary_role_contact"


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


def _resolve_role_assignment(role_assignment_id: int | None):
    if not role_assignment_id:
        return None
    return OrganizationRoleAssignment.objects.select_related("organization").filter(
        pk=role_assignment_id
    ).first()


def _resolve_org_contact(organization_contact_id: int | None):
    if not organization_contact_id:
        return None
    return OrganizationContact.objects.select_related("organization").filter(
        pk=organization_contact_id
    ).first()


def _resolve_role_contact_action_targets(data) -> tuple[bool, str, object, object]:
    form = RoleContactActionForm(data)
    if not form.is_valid():
        return False, "Donnees de liaison invalides.", None, None
    assignment = _resolve_role_assignment(form.cleaned_data["role_assignment_id"])
    if assignment is None:
        return False, "Affectation de role introuvable.", None, None
    org_contact = _resolve_org_contact(form.cleaned_data["organization_contact_id"])
    if org_contact is None:
        return False, "Contact organisation introuvable.", None, None
    if org_contact.organization_id != assignment.organization_id:
        return False, "Le contact doit appartenir a la meme organisation.", None, None
    return True, "", assignment, org_contact


def upsert_org_contact(*, data) -> tuple[bool, str]:
    form = OrganizationContactUpsertForm(data)
    if not form.is_valid():
        return False, "Donnees de contact invalides."

    organization = _resolve_active_organization(form.cleaned_data["organization_id"])
    if organization is None:
        return False, "Organisation invalide."

    organization_contact_id = form.cleaned_data.get("organization_contact_id")
    org_contact = None
    if organization_contact_id:
        org_contact = _resolve_org_contact(organization_contact_id)
        if org_contact is None:
            return False, "Contact organisation introuvable."
        if org_contact.organization_id != organization.id:
            return False, "Le contact doit appartenir a la meme organisation."
    if org_contact is None:
        org_contact = OrganizationContact(organization=organization)

    org_contact.title = form.cleaned_data["title"]
    org_contact.first_name = form.cleaned_data["first_name"]
    org_contact.last_name = form.cleaned_data["last_name"]
    org_contact.email = form.cleaned_data["email"]
    org_contact.phone = form.cleaned_data["phone"]
    org_contact.is_active = bool(form.cleaned_data["is_active"])

    try:
        org_contact.save()
    except ValidationError as exc:
        return False, _validation_message(exc)

    if organization_contact_id:
        return True, "Contact organisation mis a jour."
    return True, "Contact organisation cree."


def link_role_contact(*, data) -> tuple[bool, str]:
    ok, message, assignment, org_contact = _resolve_role_contact_action_targets(data)
    if not ok:
        return False, message

    role_contact, _created = OrganizationRoleContact.objects.get_or_create(
        role_assignment=assignment,
        contact=org_contact,
        defaults={"is_primary": False, "is_active": True},
    )
    if not role_contact.is_active:
        role_contact.is_active = True
        role_contact.save(update_fields=["is_active"])
    return True, "Contact lie au role."


def unlink_role_contact(*, data) -> tuple[bool, str]:
    ok, message, assignment, org_contact = _resolve_role_contact_action_targets(data)
    if not ok:
        return False, message

    role_contact = OrganizationRoleContact.objects.filter(
        role_assignment=assignment,
        contact=org_contact,
    ).first()
    if role_contact is None:
        return False, "Liaison role-contact introuvable."

    role_contact.is_active = False
    role_contact.is_primary = False
    role_contact.save(update_fields=["is_active", "is_primary"])
    return True, "Contact delie du role."


def set_primary_role_contact(*, data) -> tuple[bool, str]:
    ok, message, assignment, org_contact = _resolve_role_contact_action_targets(data)
    if not ok:
        return False, message

    with transaction.atomic():
        OrganizationRoleContact.objects.filter(
            role_assignment=assignment,
            is_primary=True,
        ).update(is_primary=False)
        role_contact, _created = OrganizationRoleContact.objects.get_or_create(
            role_assignment=assignment,
            contact=org_contact,
            defaults={"is_primary": True, "is_active": True},
        )
        role_contact.is_active = True
        role_contact.is_primary = True
        role_contact.save(update_fields=["is_active", "is_primary"])

    return True, "Contact principal mis a jour."


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
