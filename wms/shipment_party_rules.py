from __future__ import annotations

from django.db.models import Q, QuerySet
from django.utils import timezone

from contacts.models import Contact, ContactType

from .models import (
    OrganizationRole,
    OrganizationRoleAssignment,
    RecipientBinding,
    ShipperScope,
)


def normalize_party_contact_to_org(contact: Contact | None) -> Contact | None:
    if contact is None:
        return None
    if contact.contact_type == ContactType.PERSON and getattr(contact, "organization_id", None):
        return contact.organization
    return contact


def _eligible_contacts_for_org_ids(org_ids) -> QuerySet[Contact]:
    if not org_ids:
        return Contact.objects.none()
    return (
        Contact.objects.filter(is_active=True)
        .filter(Q(pk__in=org_ids) | Q(organization_id__in=org_ids))
        .order_by("name", "id")
        .distinct()
    )


def _current_window_q(prefix: str = ""):
    now = timezone.now()
    return Q(**{f"{prefix}valid_from__lte": now}) & (
        Q(**{f"{prefix}valid_to__isnull": True}) | Q(**{f"{prefix}valid_to__gt": now})
    )


def _active_org_ids_for_role(role: str) -> list[int]:
    return list(
        OrganizationRoleAssignment.objects.filter(
            role=role,
            is_active=True,
            organization__is_active=True,
            organization__contact_type=ContactType.ORGANIZATION,
        ).values_list("organization_id", flat=True)
    )


def active_shipper_contacts() -> QuerySet[Contact]:
    return _eligible_contacts_for_org_ids(_active_org_ids_for_role(OrganizationRole.SHIPPER))


def active_recipient_contacts() -> QuerySet[Contact]:
    return _eligible_contacts_for_org_ids(_active_org_ids_for_role(OrganizationRole.RECIPIENT))


def recipient_contacts_for_destination(destination) -> QuerySet[Contact]:
    if destination is None:
        return Contact.objects.none()
    org_ids = list(
        RecipientBinding.objects.filter(
            destination=destination,
            is_active=True,
            shipper_org__is_active=True,
            recipient_org__is_active=True,
        )
        .filter(_current_window_q())
        .values_list("recipient_org_id", flat=True)
    )
    return _eligible_contacts_for_org_ids(org_ids)


def eligible_shipper_contacts_for_destination(destination):
    if destination is None:
        return Contact.objects.none()
    assignment_ids = (
        ShipperScope.objects.filter(
            is_active=True,
        )
        .filter(_current_window_q())
        .filter(Q(all_destinations=True) | Q(destination=destination))
        .values_list("role_assignment_id", flat=True)
    )
    org_ids = list(
        OrganizationRoleAssignment.objects.filter(
            id__in=assignment_ids,
            role=OrganizationRole.SHIPPER,
            is_active=True,
            organization__is_active=True,
            organization__contact_type=ContactType.ORGANIZATION,
        ).values_list("organization_id", flat=True)
    )
    return _eligible_contacts_for_org_ids(org_ids)


def eligible_recipient_contacts_for_shipper_destination(*, shipper_contact, destination):
    shipper_org = normalize_party_contact_to_org(shipper_contact)
    if shipper_org is None or destination is None:
        return Contact.objects.none()
    org_ids = list(
        RecipientBinding.objects.filter(
            shipper_org=shipper_org,
            destination=destination,
            is_active=True,
            shipper_org__is_active=True,
            recipient_org__is_active=True,
        )
        .filter(_current_window_q())
        .values_list("recipient_org_id", flat=True)
    )
    return _eligible_contacts_for_org_ids(org_ids)


def eligible_correspondent_contacts_for_destination(destination):
    if destination is None or destination.correspondent_contact_id is None:
        return Contact.objects.none()
    return Contact.objects.filter(
        pk=destination.correspondent_contact_id,
        is_active=True,
    ).order_by("name", "id")


def _contact_emails(contact: Contact | None) -> list[str]:
    if contact is None:
        return []
    emails: list[str] = []
    seen: set[str] = set()
    for value in (getattr(contact, "email", ""), getattr(contact, "email2", "")):
        normalized = str(value or "").strip()
        key = normalized.lower()
        if normalized and key not in seen:
            emails.append(normalized)
            seen.add(key)
    return emails


def build_party_contact_reference(contact: Contact | None, fallback_name: str = "") -> dict:
    if contact is None:
        return {
            "contact_id": None,
            "contact_name": str(fallback_name or "").strip(),
            "notification_emails": [],
        }

    return {
        "contact_id": contact.pk,
        "contact_name": contact.name,
        "contact_title": getattr(contact, "title", ""),
        "contact_first_name": getattr(contact, "first_name", ""),
        "contact_last_name": getattr(contact, "last_name", ""),
        "notification_emails": _contact_emails(contact),
        "phone": getattr(contact, "phone", ""),
        "phone2": getattr(contact, "phone2", ""),
    }
