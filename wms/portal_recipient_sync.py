from __future__ import annotations

from wms.application.parties.use_cases import (
    resolve_portal_recipient_party_contact,
    sync_portal_recipient,
)


def sync_association_recipient_to_contact(
    recipient,
    *,
    set_as_default=True,
    prefer_existing_structure=True,
):
    result = sync_portal_recipient(
        recipient=recipient,
        set_as_default=set_as_default,
        prefer_existing_structure=prefer_existing_structure,
    )
    return result.get("synced_contact")


def resolve_association_recipient_party_contact(recipient):
    return resolve_portal_recipient_party_contact(recipient)
