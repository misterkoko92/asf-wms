from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from contacts.models import Contact, ContactType

from .forms_scan_admin_contacts_cockpit import (
    GuidedContactCreateForm,
    OrganizationContactUpsertForm,
    RecipientBindingCloseForm,
    RecipientBindingUpsertForm,
    RoleContactActionForm,
    ShipperScopeDisableForm,
    ShipperScopeUpsertForm,
)
from .models import (
    AssociationContactTitle,
    Destination,
    OrganizationContact,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRoleContact,
    RecipientBinding,
    ShipperScope,
)

ROLE_VALUES = {choice[0] for choice in OrganizationRole.choices}
ACTION_ASSIGN_ROLE = "assign_role"
ACTION_UNASSIGN_ROLE = "unassign_role"
ACTION_UPSERT_ORG_CONTACT = "upsert_org_contact"
ACTION_LINK_ROLE_CONTACT = "link_role_contact"
ACTION_UNLINK_ROLE_CONTACT = "unlink_role_contact"
ACTION_SET_PRIMARY_ROLE_CONTACT = "set_primary_role_contact"
ACTION_UPSERT_SHIPPER_SCOPE = "upsert_shipper_scope"
ACTION_DISABLE_SHIPPER_SCOPE = "disable_shipper_scope"
ACTION_UPSERT_RECIPIENT_BINDING = "upsert_recipient_binding"
ACTION_CLOSE_RECIPIENT_BINDING = "close_recipient_binding"
ACTION_CREATE_GUIDED_CONTACT = "create_guided_contact"
CONTACT_TITLE_GROUP_KEYS = (
    (
        _lazy("Classiques"),
        (
            AssociationContactTitle.MR,
            AssociationContactTitle.MRS,
            AssociationContactTitle.MS,
        ),
    ),
    (
        _lazy("Religieux"),
        (
            AssociationContactTitle.PERE,
            AssociationContactTitle.SOEUR,
            AssociationContactTitle.FRERE,
            AssociationContactTitle.ABBE,
            AssociationContactTitle.IMAM,
            AssociationContactTitle.RABBIN,
            AssociationContactTitle.PASTEUR,
            AssociationContactTitle.EVEQUE,
            AssociationContactTitle.MONSEIGNEUR,
        ),
    ),
    (
        _lazy("Médicaux"),
        (
            AssociationContactTitle.DR,
            AssociationContactTitle.PR,
        ),
    ),
    (
        _lazy("Officiels"),
        (
            AssociationContactTitle.PRESIDENT,
            AssociationContactTitle.MINISTRE,
            AssociationContactTitle.AMBASSADEUR,
            AssociationContactTitle.MAIRE,
            AssociationContactTitle.PREFET,
            AssociationContactTitle.GOUVERNEUR,
            AssociationContactTitle.DEPUTE,
            AssociationContactTitle.SENATEUR,
            AssociationContactTitle.GENERAL,
            AssociationContactTitle.COLONEL,
            AssociationContactTitle.COMMANDANT,
            AssociationContactTitle.CAPITAINE,
            AssociationContactTitle.LIEUTENANT,
            AssociationContactTitle.ADJUDANT,
            AssociationContactTitle.SERGENT,
        ),
    ),
)


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
    return _("Validation impossible.")


def _normalize_match_value(value: str) -> str:
    raw_value = (value or "").strip()
    if not raw_value:
        return ""
    normalized = unicodedata.normalize("NFKD", raw_value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    return re.sub(r"\s+", " ", normalized)


def _is_fuzzy_match(*, source: str, candidate: str) -> bool:
    if not source or not candidate:
        return False
    if source == candidate:
        return True
    if source in candidate or candidate in source:
        return True
    return SequenceMatcher(None, source, candidate).ratio() >= 0.88


def _find_similar_organizations(*, name: str, limit: int = 3):
    normalized_target = _normalize_match_value(name)
    if not normalized_target:
        return []
    matches = []
    for organization in Contact.objects.filter(contact_type=ContactType.ORGANIZATION).order_by(
        "name",
        "id",
    ):
        normalized_candidate = _normalize_match_value(organization.name)
        if _is_fuzzy_match(source=normalized_target, candidate=normalized_candidate):
            matches.append(organization)
            if len(matches) >= limit:
                break
    return matches


def _format_duplicate_message(*, prefix: str, items) -> str:
    if not items:
        return ""
    labels = ", ".join((item.name or "").strip() for item in items[:3] if (item.name or "").strip())
    if labels:
        return f"{prefix}: {labels}."
    return prefix


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
        return False, _("Organisation invalide.")
    normalized_role = _normalize_role(role)
    if not normalized_role:
        return False, _("Role invalide.")

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

    return True, _("Role %(role)s active.") % {"role": assignment.get_role_display()}


def unassign_role(*, organization_id: str, role: str) -> tuple[bool, str]:
    organization = _resolve_active_organization(organization_id)
    if organization is None:
        return False, _("Organisation invalide.")
    normalized_role = _normalize_role(role)
    if not normalized_role:
        return False, _("Role invalide.")

    assignment = OrganizationRoleAssignment.objects.filter(
        organization=organization,
        role=normalized_role,
    ).first()
    if assignment is None:
        return False, _("Role introuvable.")
    if not assignment.is_active:
        return True, _("Role %(role)s deja inactif.") % {"role": assignment.get_role_display()}

    assignment.is_active = False
    assignment.save(update_fields=["is_active"])
    return True, _("Role %(role)s desactive.") % {"role": assignment.get_role_display()}


def _resolve_role_assignment(role_assignment_id: int | None):
    if not role_assignment_id:
        return None
    return (
        OrganizationRoleAssignment.objects.select_related("organization")
        .filter(pk=role_assignment_id)
        .first()
    )


def _resolve_org_contact(organization_contact_id: int | None):
    if not organization_contact_id:
        return None
    return (
        OrganizationContact.objects.select_related("organization")
        .filter(pk=organization_contact_id)
        .first()
    )


def _resolve_role_contact_action_targets(data) -> tuple[bool, str, object, object]:
    form = RoleContactActionForm(data)
    if not form.is_valid():
        return False, _("Donnees de liaison invalides."), None, None
    assignment = _resolve_role_assignment(form.cleaned_data["role_assignment_id"])
    if assignment is None:
        return False, _("Affectation de role introuvable."), None, None
    org_contact = _resolve_org_contact(form.cleaned_data["organization_contact_id"])
    if org_contact is None:
        return False, _("Contact organisation introuvable."), None, None
    if org_contact.organization_id != assignment.organization_id:
        return False, _("Le contact doit appartenir a la meme organisation."), None, None
    return True, "", assignment, org_contact


def upsert_org_contact(*, data) -> tuple[bool, str]:
    form = OrganizationContactUpsertForm(data)
    if not form.is_valid():
        return False, _("Donnees de contact invalides.")

    organization = _resolve_active_organization(form.cleaned_data["organization_id"])
    if organization is None:
        return False, _("Organisation invalide.")

    organization_contact_id = form.cleaned_data.get("organization_contact_id")
    org_contact = None
    if organization_contact_id:
        org_contact = _resolve_org_contact(organization_contact_id)
        if org_contact is None:
            return False, _("Contact organisation introuvable.")
        if org_contact.organization_id != organization.id:
            return False, _("Le contact doit appartenir a la meme organisation.")
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
        return True, _("Contact organisation mis a jour.")
    return True, _("Contact organisation cree.")


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
    return True, _("Contact lie au role.")


def unlink_role_contact(*, data) -> tuple[bool, str]:
    ok, message, assignment, org_contact = _resolve_role_contact_action_targets(data)
    if not ok:
        return False, message

    role_contact = OrganizationRoleContact.objects.filter(
        role_assignment=assignment,
        contact=org_contact,
    ).first()
    if role_contact is None:
        return False, _("Liaison role-contact introuvable.")

    role_contact.is_active = False
    role_contact.is_primary = False
    role_contact.save(update_fields=["is_active", "is_primary"])
    return True, _("Contact delie du role.")


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

    return True, _("Contact principal mis a jour.")


def upsert_shipper_scope(*, data) -> tuple[bool, str]:
    form = ShipperScopeUpsertForm(data)
    if not form.is_valid():
        return False, _("Donnees de scope expediteur invalides.")

    assignment = _resolve_role_assignment(form.cleaned_data["role_assignment_id"])
    if assignment is None:
        return False, _("Affectation de role introuvable.")
    if assignment.role != OrganizationRole.SHIPPER:
        return False, _("Le scope d'escales est reserve au role expediteur.")

    scope = None
    scope_id = form.cleaned_data.get("scope_id")
    if scope_id:
        scope = ShipperScope.objects.filter(pk=scope_id).first()
        if scope is None:
            return False, _("Scope expediteur introuvable.")
        if scope.role_assignment_id != assignment.id:
            return False, _("Scope expediteur incompatible avec l'affectation.")
    if scope is None:
        scope = ShipperScope(role_assignment=assignment)

    destination = None
    destination_id = form.cleaned_data.get("destination_id")
    if destination_id:
        destination = Destination.objects.filter(pk=destination_id, is_active=True).first()
        if destination is None:
            return False, _("Escale invalide.")

    all_destinations = bool(form.cleaned_data["all_destinations"])
    if destination is None and not all_destinations:
        all_destinations = True
    scope.all_destinations = all_destinations
    scope.destination = destination
    scope.is_active = True
    scope.valid_from = form.cleaned_data.get("valid_from") or scope.valid_from
    scope.valid_to = form.cleaned_data.get("valid_to")

    try:
        scope.save()
    except ValidationError as exc:
        return False, _validation_message(exc)

    return True, _("Scope expediteur enregistre.")


def disable_shipper_scope(*, data) -> tuple[bool, str]:
    form = ShipperScopeDisableForm(data)
    if not form.is_valid():
        return False, _("Scope expediteur invalide.")

    scope = ShipperScope.objects.filter(pk=form.cleaned_data["scope_id"]).first()
    if scope is None:
        return False, _("Scope expediteur introuvable.")
    if not scope.is_active:
        return True, _("Scope expediteur deja inactif.")

    scope.is_active = False
    scope.save(update_fields=["is_active"])
    return True, _("Scope expediteur desactive.")


def _resolve_active_org_by_id(org_id: int | None):
    return _resolve_active_organization(org_id)


def _build_contact_title_groups() -> list[dict]:
    labels_by_value = dict(AssociationContactTitle.choices)
    groups = []
    for group_label, group_values in CONTACT_TITLE_GROUP_KEYS:
        group_choices = [(value, labels_by_value[value]) for value in group_values]
        groups.append({"label": group_label, "choices": group_choices})
    return groups


def _organization_has_active_role(*, organization, role: str) -> bool:
    if organization is None:
        return False
    return OrganizationRoleAssignment.objects.filter(
        organization=organization,
        role=role,
        is_active=True,
    ).exists()


def upsert_recipient_binding(*, data) -> tuple[bool, str]:
    form = RecipientBindingUpsertForm(data)
    if not form.is_valid():
        return False, _("Donnees de binding destinataire invalides.")

    shipper_org = _resolve_active_org_by_id(form.cleaned_data["shipper_org_id"])
    if shipper_org is None:
        return False, _("Expediteur invalide.")
    if not _organization_has_active_role(
        organization=shipper_org,
        role=OrganizationRole.SHIPPER,
    ):
        return False, _("Expediteur sans role actif.")
    recipient_org = _resolve_active_org_by_id(form.cleaned_data["recipient_org_id"])
    if recipient_org is None:
        return False, _("Destinataire invalide.")
    if not _organization_has_active_role(
        organization=recipient_org,
        role=OrganizationRole.RECIPIENT,
    ):
        return False, _("Destinataire sans role actif.")
    destination = Destination.objects.filter(
        pk=form.cleaned_data["destination_id"],
        is_active=True,
    ).first()
    if destination is None:
        return False, _("Escale invalide.")

    binding = None
    binding_id = form.cleaned_data.get("binding_id")
    if binding_id:
        binding = RecipientBinding.objects.filter(pk=binding_id).first()
        if binding is None:
            return False, _("Binding destinataire introuvable.")
    existing_active_binding = RecipientBinding.objects.filter(
        shipper_org=shipper_org,
        recipient_org=recipient_org,
        destination=destination,
        is_active=True,
    ).first()
    if binding is None:
        binding = existing_active_binding or RecipientBinding()
    elif existing_active_binding and existing_active_binding.id != binding.id:
        return (
            False,
            _("Un binding actif existe deja pour cet expediteur, ce destinataire et cette escale."),
        )

    binding.shipper_org = shipper_org
    binding.recipient_org = recipient_org
    binding.destination = destination
    binding.is_active = True
    binding.valid_from = form.cleaned_data.get("valid_from") or binding.valid_from
    if binding.valid_from is None:
        binding.valid_from = timezone.now()
    binding.valid_to = form.cleaned_data.get("valid_to")

    try:
        binding.save()
    except ValidationError as exc:
        return False, _validation_message(exc)

    return True, _("Binding destinataire enregistre.")


def close_recipient_binding(*, data) -> tuple[bool, str]:
    form = RecipientBindingCloseForm(data)
    if not form.is_valid():
        return False, _("Donnees de cloture binding invalides.")

    binding = RecipientBinding.objects.filter(pk=form.cleaned_data["binding_id"]).first()
    if binding is None:
        return False, _("Binding destinataire introuvable.")

    binding.valid_to = form.cleaned_data["valid_to"]
    binding.is_active = False
    try:
        binding.save(update_fields=["valid_to", "is_active"])
    except ValidationError as exc:
        return False, _validation_message(exc)
    return True, _("Binding destinataire cloture.")


def create_guided_contact(*, data) -> tuple[bool, str]:
    form = GuidedContactCreateForm(data)
    if not form.is_valid():
        return False, _("Donnees de creation guidee invalides.")

    entity_kind = form.cleaned_data["entity_kind"]
    role = _normalize_role(form.cleaned_data.get("role") or "")
    is_active = form.cleaned_data.get("is_active")
    if "is_active" not in form.data:
        is_active = True

    organization_name = (form.cleaned_data.get("organization_name") or "").strip()
    similar_organizations = _find_similar_organizations(name=organization_name)
    if similar_organizations:
        return (
            False,
            _format_duplicate_message(
                prefix=_("Organisation similaire deja presente"),
                items=similar_organizations,
            ),
        )

    organization = Contact.objects.create(
        contact_type=ContactType.ORGANIZATION,
        name=organization_name,
        email=(form.cleaned_data.get("email") or "").strip(),
        phone=(form.cleaned_data.get("phone") or "").strip(),
        is_active=is_active,
    )
    assignment, _created = OrganizationRoleAssignment.objects.get_or_create(
        organization=organization,
        role=role,
        defaults={"is_active": False},
    )

    if entity_kind == "organization_with_contact":
        org_contact = OrganizationContact.objects.create(
            organization=organization,
            first_name=(form.cleaned_data.get("first_name") or "").strip(),
            last_name=(form.cleaned_data.get("last_name") or "").strip(),
            email=(form.cleaned_data.get("email") or "").strip(),
            phone=(form.cleaned_data.get("phone") or "").strip(),
            is_active=is_active,
        )
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
            role_contact.is_primary = True
            role_contact.is_active = True
            role_contact.save(update_fields=["is_primary", "is_active"])
        assignment.is_active = True
        try:
            assignment.save(update_fields=["is_active"])
        except ValidationError:
            assignment.is_active = False
            assignment.save(update_fields=["is_active"])
        return True, _("Organisation et contact rattache crees.")

    return True, _("Organisation creee.")


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
            | Q(
                organization_role_assignments__shipper_scopes__destination__iata_code__icontains=query
            )
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
                "active_role_labels": [assignment.get_role_display() for assignment in assignments],
                "recipient_bindings_count": recipient_bindings_count,
            }
        )
    return rows


def build_cockpit_context(*, query: str, filters: dict) -> dict:
    organizations = list(
        Contact.objects.filter(
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        ).order_by("name", "id")
    )
    role_assignments = list(
        OrganizationRoleAssignment.objects.select_related("organization")
        .filter(organization__is_active=True)
        .order_by("organization__name", "role", "id")
    )
    organization_contacts = list(
        OrganizationContact.objects.select_related("organization")
        .filter(organization__is_active=True)
        .order_by("organization__name", "last_name", "first_name", "id")
    )
    linked_contact_ids = set(
        OrganizationRoleContact.objects.filter(is_active=True).values_list("contact_id", flat=True)
    )
    organization_contacts = sorted(
        organization_contacts,
        key=lambda current: (
            f"{(current.last_name or '').strip()} {(current.first_name or '').strip()} {(current.email or '').strip()}".lower(),
            (current.organization.name or "").lower(),
            current.id,
        ),
    )
    linked_organization_contacts = [
        current for current in organization_contacts if current.id in linked_contact_ids
    ]
    destinations = list(
        Destination.objects.filter(is_active=True).order_by("city", "iata_code", "id")
    )
    shipper_scopes = list(
        ShipperScope.objects.select_related(
            "role_assignment__organization",
            "destination",
        ).order_by("-is_active", "role_assignment__organization__name", "id")
    )
    recipient_bindings = list(
        RecipientBinding.objects.select_related(
            "shipper_org",
            "recipient_org",
            "destination",
        ).order_by(
            "-is_active",
            "shipper_org__name",
            "recipient_org__name",
            "destination__iata_code",
            "id",
        )
    )
    active_shipper_org_ids = {
        assignment.organization_id
        for assignment in role_assignments
        if assignment.role == OrganizationRole.SHIPPER and assignment.is_active
    }
    active_recipient_org_ids = {
        assignment.organization_id
        for assignment in role_assignments
        if assignment.role == OrganizationRole.RECIPIENT and assignment.is_active
    }
    binding_shipper_organizations = [
        organization for organization in organizations if organization.id in active_shipper_org_ids
    ]
    binding_recipient_organizations = [
        organization
        for organization in organizations
        if organization.id in active_recipient_org_ids
    ]
    active_destination_ids = {destination.id for destination in destinations}
    latest_destination_by_recipient_id: dict[int, int] = {}
    active_recipient_bindings = list(
        RecipientBinding.objects.filter(is_active=True)
        .order_by("recipient_org_id", "-valid_from", "-id")
        .values_list("recipient_org_id", "destination_id")
    )
    for recipient_org_id, destination_id in active_recipient_bindings:
        if recipient_org_id not in latest_destination_by_recipient_id:
            latest_destination_by_recipient_id[recipient_org_id] = destination_id
    recipient_default_destination_by_org_id: dict[int, int | None] = {}
    for organization in binding_recipient_organizations:
        suggested_destination_id = latest_destination_by_recipient_id.get(organization.id)
        recipient_default_destination_by_org_id[organization.id] = suggested_destination_id
        setattr(organization, "default_destination_id", suggested_destination_id or "")
    shipper_role_assignments = [
        assignment for assignment in role_assignments if assignment.role == OrganizationRole.SHIPPER
    ]
    return {
        "query": query,
        "cockpit_filters": filters,
        "cockpit_rows": build_cockpit_rows(query=query, filters=filters),
        "cockpit_mode": "org_roles",
        "cockpit_role_choices": OrganizationRole.choices,
        "cockpit_contact_title_groups": _build_contact_title_groups(),
        "cockpit_organizations": organizations,
        "cockpit_binding_shipper_organizations": binding_shipper_organizations,
        "cockpit_binding_recipient_organizations": binding_recipient_organizations,
        "cockpit_recipient_default_destination_by_org_id": recipient_default_destination_by_org_id,
        "cockpit_role_assignments": role_assignments,
        "cockpit_shipper_role_assignments": shipper_role_assignments,
        "cockpit_organization_contacts": organization_contacts,
        "cockpit_linked_organization_contacts": linked_organization_contacts,
        "cockpit_all_organization_contacts": organization_contacts,
        "cockpit_destinations": destinations,
        "cockpit_shipper_scopes": shipper_scopes,
        "cockpit_recipient_bindings": recipient_bindings,
    }
