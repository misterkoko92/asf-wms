from __future__ import annotations

from wms.shipment_party_setup import PRIORITY_SHIPPER_NAME

DEFAULT_RECIPIENT_SHIPPER_ASF_ID = "ASF-ORG-ROOT"


def default_recipient_shipper_name() -> str:
    return PRIORITY_SHIPPER_NAME.upper()


def default_recipient_shipper_asf_id() -> str:
    return DEFAULT_RECIPIENT_SHIPPER_ASF_ID
