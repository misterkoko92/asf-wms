from django.db.models import Q

from contacts.models import Contact

TAG_DONOR = ("donateur",)
TAG_TRANSPORTER = ("transporteur",)
TAG_ASSOCIATION = ("nom association", "association")
TAG_SHIPPER = ("expediteur", "expediteurs")
TAG_RECIPIENT = ("destinataire", "destinataires")
TAG_CORRESPONDENT = ("correspondant", "correspondants")


def contacts_with_tags(tag_names):
    queryset = Contact.objects.filter(is_active=True)
    if not tag_names:
        return queryset
    tag_query = Q()
    for name in tag_names:
        tag_query |= Q(tags__name__iexact=name)
    return queryset.filter(tag_query).distinct()
