def build_contact_select_label(contact):
    if not contact:
        return ""

    organization = getattr(contact, "organization", None)
    organization_name = (getattr(organization, "name", "") or "").strip()
    if organization_name:
        return organization_name

    title = (getattr(contact, "title", "") or "").strip()
    first_name = (getattr(contact, "first_name", "") or "").strip()
    last_name = (getattr(contact, "last_name", "") or "").strip()
    if title or first_name or last_name:
        parts = [title, first_name, last_name.upper() if last_name else ""]
        return ", ".join(part for part in parts if part)

    name = (getattr(contact, "name", "") or "").strip()
    if name:
        return name
    return str(contact)
