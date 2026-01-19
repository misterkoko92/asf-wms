from .contact_filters import contacts_with_tags


def resolve_contact_by_name(tag, name):
    if not name:
        return None
    return contacts_with_tags(tag).filter(name__iexact=name).first()


def sorted_choices(choices):
    return sorted(choices, key=lambda choice: str(choice[1] or "").lower())
