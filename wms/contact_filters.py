from django.db.models import Q

from contacts.models import Contact

TAG_DONOR = ("donateur",)
TAG_TRANSPORTER = ("transporteur",)
TAG_SHIPPER = ("expediteur", "expediteurs")
TAG_RECIPIENT = ("destinataire", "destinataires")
TAG_CORRESPONDENT = ("correspondant", "correspondants")


def contacts_with_tags(tag_names):
    queryset = Contact.objects.filter(is_active=True)
    if not tag_names:
        return queryset.order_by("name")
    tag_query = Q()
    for name in tag_names:
        tag_query |= Q(tags__name__iexact=name)
    return queryset.filter(tag_query).distinct().order_by("name")


def filter_contacts_for_destination(queryset, destination):
    if not destination:
        return queryset
    return queryset.filter(
        Q(destination__isnull=True) | Q(destination=destination)
    )
