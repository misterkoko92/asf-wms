from __future__ import annotations

from contacts.models import Contact, ContactType

from .shipment_party_rules import build_party_contact_reference, normalize_party_contact_to_org


def _normalized_text(value) -> str:
    return str(value or "").strip()


def _build_person_label(contact: Contact | None) -> str:
    if contact is None:
        return ""
    title = _normalized_text(getattr(contact, "title", ""))
    first_name = _normalized_text(getattr(contact, "first_name", ""))
    last_name = _normalized_text(getattr(contact, "last_name", ""))
    if title or first_name or last_name:
        parts = [title, first_name, last_name.upper() if last_name else ""]
        return " ".join(part for part in parts if part)
    return _normalized_text(getattr(contact, "name", ""))


def build_shipment_party_contact_label(
    contact: Contact | None,
    *,
    fallback_name: str = "",
) -> str:
    if contact is None:
        return _normalized_text(fallback_name)
    if getattr(contact, "contact_type", "") == ContactType.PERSON:
        return _build_person_label(contact)
    return _normalized_text(getattr(contact, "name", "")) or _normalized_text(fallback_name)


def build_shipment_party_label(
    contact: Contact | None,
    *,
    fallback_name: str = "",
) -> str:
    contact_label = build_shipment_party_contact_label(contact, fallback_name=fallback_name)
    organization = normalize_party_contact_to_org(contact)
    organization_label = _normalized_text(getattr(organization, "name", ""))
    if (
        organization_label
        and contact_label
        and organization_label.casefold() != contact_label.casefold()
    ):
        return f"{contact_label}, {organization_label}"
    return contact_label or organization_label or _normalized_text(fallback_name)


def build_shipment_party_snapshot_entry(
    contact: Contact | None,
    *,
    fallback_name: str = "",
) -> dict:
    contact_label = build_shipment_party_contact_label(contact, fallback_name=fallback_name)
    organization = normalize_party_contact_to_org(contact)
    organization_label = _normalized_text(getattr(organization, "name", ""))
    return {
        "label": build_shipment_party_label(contact, fallback_name=fallback_name),
        "contact_label": contact_label,
        "organization_label": organization_label,
        "contact": build_party_contact_reference(contact, fallback_name=contact_label),
        "organization": build_party_contact_reference(
            organization,
            fallback_name=organization_label,
        ),
    }


def build_shipment_party_snapshot(
    *,
    shipper_contact: Contact | None,
    recipient_contact: Contact | None,
    correspondent_contact: Contact | None,
    shipper_name: str = "",
    recipient_name: str = "",
    correspondent_name: str = "",
) -> dict:
    return {
        "shipper": build_shipment_party_snapshot_entry(
            shipper_contact,
            fallback_name=shipper_name,
        ),
        "recipient": build_shipment_party_snapshot_entry(
            recipient_contact,
            fallback_name=recipient_name,
        ),
        "correspondent": build_shipment_party_snapshot_entry(
            correspondent_contact,
            fallback_name=correspondent_name,
        ),
    }


def build_shipment_party_snapshot_payload(
    *,
    shipper_contact: Contact | None,
    recipient_contact: Contact | None,
    correspondent_contact: Contact | None,
    shipper_name: str = "",
    recipient_name: str = "",
    correspondent_name: str = "",
) -> dict:
    snapshot = build_shipment_party_snapshot(
        shipper_contact=shipper_contact,
        recipient_contact=recipient_contact,
        correspondent_contact=correspondent_contact,
        shipper_name=shipper_name,
        recipient_name=recipient_name,
        correspondent_name=correspondent_name,
    )
    return {"party_snapshot": snapshot}


def apply_shipment_party_snapshot(
    shipment,
    *,
    shipper_contact: Contact | None,
    recipient_contact: Contact | None,
    correspondent_contact: Contact | None,
    shipper_name: str = "",
    recipient_name: str = "",
    correspondent_name: str = "",
) -> dict:
    payload = build_shipment_party_snapshot_payload(
        shipper_contact=shipper_contact,
        recipient_contact=recipient_contact,
        correspondent_contact=correspondent_contact,
        shipper_name=shipper_name,
        recipient_name=recipient_name,
        correspondent_name=correspondent_name,
    )
    shipment.party_snapshot = payload["party_snapshot"]
    return payload
