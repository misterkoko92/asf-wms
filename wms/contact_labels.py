from contacts.correspondent_recipient_promotion import SUPPORT_ORGANIZATION_NAME


def _build_person_label(contact):
    title = (getattr(contact, "title", "") or "").strip()
    first_name = (getattr(contact, "first_name", "") or "").strip()
    last_name = (getattr(contact, "last_name", "") or "").strip()
    if title or first_name or last_name:
        parts = [title, first_name, last_name.upper() if last_name else ""]
        return ", ".join(part for part in parts if part)

    return (getattr(contact, "name", "") or "").strip()


def build_contact_select_label(contact):
    if not contact:
        return ""

    organization = getattr(contact, "organization", None)
    organization_name = (getattr(organization, "name", "") or "").strip()
    person_label = _build_person_label(contact)

    if organization_name:
        if person_label and person_label.casefold() != organization_name.casefold():
            return f"{organization_name} ({person_label})"
        return organization_name

    if person_label:
        return person_label
    return str(contact)


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
        first_name = (getattr(contact, "first_name", "") or "").strip()
        last_name = (getattr(contact, "last_name", "") or "").strip().upper()
        person_label = " ".join(part for part in [first_name, last_name] if part).strip()
        if person_label:
            return f"{organization_name} - {iata_code} ({person_label})"
        fallback_name = (getattr(contact, "name", "") or "").strip()
        if fallback_name:
            return f"{organization_name} - {iata_code} ({fallback_name})"

    return build_contact_select_label(contact)
