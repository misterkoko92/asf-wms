import re
import unicodedata

from django.db.models import Q

from contacts.models import Contact, ContactTag

TAG_DONOR = ("donateur", "donateurs")
TAG_TRANSPORTER = ("transporteur", "transporteurs")
TAG_SHIPPER = ("expediteur", "expediteurs", "expéditeur", "expéditeurs")
TAG_RECIPIENT = (
    "destinataire",
    "destinataires",
    "beneficiaire",
    "beneficiaires",
    "bénéficiaire",
    "bénéficiaires",
)
TAG_CORRESPONDENT = ("correspondant", "correspondants")


def _normalize_tag_name(value):
    text = str(value or "")
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized


def contacts_with_tags(tag_names):
    queryset = Contact.objects.filter(is_active=True)
    if not tag_names:
        return queryset.order_by("name")

    normalized_targets = {
        normalized
        for normalized in (_normalize_tag_name(name) for name in tag_names)
        if normalized
    }
    if not normalized_targets:
        return queryset.none()

    matching_tag_ids = [
        tag.id
        for tag in ContactTag.objects.only("id", "name")
        if _normalize_tag_name(tag.name) in normalized_targets
    ]
    if not matching_tag_ids:
        return queryset.none()
    return queryset.filter(tags__id__in=matching_tag_ids).distinct().order_by("name")


def filter_contacts_for_destination(queryset, destination):
    if not destination:
        return queryset
    return queryset.filter(
        Q(destination=destination)
        | Q(destinations=destination)
        | Q(destination__isnull=True, destinations__isnull=True)
    ).distinct()
