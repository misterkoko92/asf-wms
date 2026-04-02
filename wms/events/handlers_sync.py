from django.db import transaction

from contacts.correspondent_recipient_promotion import (
    ensure_destination_correspondent_recipient_ready,
)
from wms.default_shipper_bindings import (
    ensure_default_shipper_links_for_destination_id,
    ensure_default_shipper_links_for_recipient_organization_id,
)
from wms.events.types import RuntimeEvent
from wms.models import Destination


def handle_default_shipper_links_for_recipient_organization_event(*, event: RuntimeEvent) -> None:
    recipient_organization_id = int(event.scope_id)
    transaction.on_commit(
        lambda: ensure_default_shipper_links_for_recipient_organization_id(
            recipient_organization_id
        )
    )


def handle_default_shipper_links_for_destination_event(*, event: RuntimeEvent) -> None:
    destination_id = int(event.scope_id)
    transaction.on_commit(lambda: ensure_default_shipper_links_for_destination_id(destination_id))


def handle_destination_correspondent_recipient_support_event(*, event: RuntimeEvent) -> None:
    destination_id = int(event.scope_id)

    def _sync() -> None:
        destination = (
            Destination.objects.filter(pk=destination_id)
            .select_related("correspondent_contact")
            .first()
        )
        if destination is None:
            return
        ensure_destination_correspondent_recipient_ready(destination)

    transaction.on_commit(_sync)
