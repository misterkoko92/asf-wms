from contacts.correspondent_recipient_promotion import SUPPORT_ORGANIZATION_NAME

from .shipment_party_snapshot import (
    build_shipment_party_contact_label,
    build_shipment_party_label,
)


def _normalized_text(value):
    return str(value or "").strip()


def build_shipment_contact_select_label(contact):
    if not contact:
        return ""
    organization = getattr(contact, "organization", None)
    organization_name = _normalized_text(getattr(organization, "name", ""))
    if not organization_name and getattr(contact, "contact_type", "") == "organization":
        organization_name = _normalized_text(getattr(contact, "name", ""))
    contact_label = build_shipment_party_contact_label(
        contact,
        fallback_name=_normalized_text(getattr(contact, "name", "")) or _normalized_text(contact),
    )
    if (
        organization_name
        and contact_label
        and organization_name.casefold() != contact_label.casefold()
    ):
        return f"{organization_name}, {contact_label}"
    return (
        organization_name
        or contact_label
        or build_shipment_party_label(
            contact,
            fallback_name=_normalized_text(contact),
        )
    )


def build_contact_select_label(contact):
    if not contact:
        return ""
    organization = getattr(contact, "organization", None)
    organization_name = _normalized_text(getattr(organization, "name", ""))
    contact_label = build_shipment_party_contact_label(
        contact,
        fallback_name=_normalized_text(getattr(contact, "name", "")) or _normalized_text(contact),
    )
    if (
        organization_name
        and contact_label
        and organization_name.casefold() != contact_label.casefold()
    ):
        return f"{contact_label}, {organization_name}"
    return (
        organization_name
        or contact_label
        or build_shipment_party_label(
            contact,
            fallback_name=_normalized_text(contact),
        )
    )


def build_shipment_recipient_select_label(contact, *, destination=None):
    if not contact:
        return ""

    organization = getattr(contact, "organization", None)
    organization_name = (getattr(organization, "name", "") or "").strip()
    iata_code = (getattr(destination, "iata_code", "") or "").strip()
    if (
        organization_name == SUPPORT_ORGANIZATION_NAME
        and getattr(contact, "contact_type", "") == "person"
        and iata_code
    ):
        person_label = build_shipment_party_contact_label(
            contact,
            fallback_name=_normalized_text(getattr(contact, "name", "")),
        )
        organization_label = f"Correspondant ASF - {iata_code}"
        if person_label and person_label.casefold() != organization_label.casefold():
            return f"{organization_label} - {person_label}"
        return person_label or organization_label

    return build_shipment_contact_select_label(contact)
