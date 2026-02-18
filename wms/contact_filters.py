from django.db.models import Q

from contacts.querysets import contacts_with_tags
from contacts.tagging import (
    TAG_CORRESPONDENT,
    TAG_DONOR,
    TAG_RECIPIENT,
    TAG_SHIPPER,
    TAG_TRANSPORTER,
)


def filter_contacts_for_destination(queryset, destination):
    if not destination:
        return queryset.filter(Q(destinations__isnull=True)).distinct()
    return queryset.filter(
        Q(destinations=destination)
        | Q(destinations__isnull=True)
    ).distinct()


def filter_recipients_for_shipper(queryset, shipper):
    if not shipper:
        return queryset.none()
    return queryset.filter(
        Q(linked_shippers=shipper) | Q(linked_shippers__isnull=True)
    ).distinct()
