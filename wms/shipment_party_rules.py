from __future__ import annotations

from django.db.models import Q, QuerySet

from contacts.models import Contact, ContactType

from .organization_role_resolvers import (
    eligible_recipients_for_shipper_destination,
    eligible_shippers_for_destination,
    is_org_roles_engine_enabled,
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


def eligible_shipper_contacts_for_destination(destination):
    if not is_org_roles_engine_enabled():
        return Contact.objects.none()
    org_ids = list(eligible_shippers_for_destination(destination).values_list("id", flat=True))
    return _eligible_contacts_for_org_ids(org_ids)


def eligible_recipient_contacts_for_shipper_destination(*, shipper_contact, destination):
    if not is_org_roles_engine_enabled():
        return Contact.objects.none()
    shipper_org = normalize_party_contact_to_org(shipper_contact)
    org_ids = list(
        eligible_recipients_for_shipper_destination(
            shipper_org=shipper_org,
            destination=destination,
        ).values_list("id", flat=True)
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
