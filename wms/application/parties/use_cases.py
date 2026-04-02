from __future__ import annotations

from wms.parties.sync import (
    resolve_portal_recipient_party_contact as resolve_portal_recipient_party_contact_runtime,
)
from wms.parties.sync import (
    sync_portal_recipient_graph,
)


def sync_portal_recipient(
    *,
    recipient,
    set_as_default=True,
    prefer_existing_structure=True,
):
    result = sync_portal_recipient_graph(
        recipient,
        set_as_default=set_as_default,
        prefer_existing_structure=prefer_existing_structure,
    )
    if result is None:
        return {}

    synced_contact = result["synced_contact"]
    shipper = result["shipper"]
    recipient_organization = result["recipient_organization"]
    shipment_contact = result["shipment_contact"]
    link = result["link"]
    return {
        "synced_contact": synced_contact,
        "synced_contact_id": synced_contact.id,
        "shipper": shipper,
        "shipper_id": shipper.id,
        "recipient_organization": recipient_organization,
        "recipient_organization_id": recipient_organization.id,
        "shipment_contact": shipment_contact,
        "shipment_contact_id": shipment_contact.id,
        "link": link,
        "link_id": link.id,
    }


def resolve_portal_recipient_party_contact(recipient):
    return resolve_portal_recipient_party_contact_runtime(recipient)
