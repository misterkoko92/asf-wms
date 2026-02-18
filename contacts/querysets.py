from contacts.models import Contact, ContactTag
from contacts.tagging import normalize_tag_name


def contacts_with_tags(tag_names):
    queryset = Contact.objects.filter(is_active=True)
    if not tag_names:
        return queryset.order_by("name")

    normalized_targets = {
        normalized
        for normalized in (normalize_tag_name(name) for name in tag_names)
        if normalized
    }
    if not normalized_targets:
        return queryset.none()

    matching_tag_ids = [
        tag.id
        for tag in ContactTag.objects.only("id", "name")
        if normalize_tag_name(tag.name) in normalized_targets
    ]
    if not matching_tag_ids:
        return queryset.none()
    return queryset.filter(tags__id__in=matching_tag_ids).distinct().order_by("name")
