from __future__ import annotations

from wms.shipment_party_setup import PRIORITY_SHIPPER_NAME


def default_recipient_shipper_name() -> str:
    return PRIORITY_SHIPPER_NAME.upper()
