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
