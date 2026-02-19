"""WMS model facade.

Model classes are defined in `wms.models_domain` modules grouped by business aggregates.
This file keeps backward compatibility for existing imports (`from wms.models import ...`).
"""

from django.db import IntegrityError, connection, transaction
from django.db.models.functions import Length
from django.utils import timezone

from . import reference_sequences
from .models_domain.catalog import Product, ProductCategory, ProductKitItem, ProductTag
from .models_domain.integration import (
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    WmsChange,
)
from .models_domain.inventory import (
    Destination,
    Location,
    ProductLot,
    ProductLotStatus,
    RackColor,
    Receipt,
    ReceiptDonorSequence,
    ReceiptHorsFormat,
    ReceiptLine,
    ReceiptSequence,
    ReceiptStatus,
    ReceiptType,
    ShipmentSequence,
    Warehouse,
)
from .models_domain.portal import (
    AccountDocument,
    AccountDocumentType,
    AssociationContactTitle,
    AssociationPortalContact,
    AssociationProfile,
    AssociationRecipient,
    DocumentReviewStatus,
    Order,
    OrderDocument,
    OrderDocumentType,
    OrderLine,
    OrderReservation,
    OrderReviewStatus,
    OrderStatus,
    PublicAccountRequest,
    PublicAccountRequestStatus,
    PublicAccountRequestType,
    PublicOrderLink,
)
from .models_domain.shipment import (
    Carton,
    CartonFormat,
    CartonItem,
    CartonStatus,
    CartonStatusEvent,
    Document,
    DocumentType,
    MovementType,
    PrintTemplate,
    PrintTemplateVersion,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
    StockMovement,
    TEMP_SHIPMENT_REFERENCE_PREFIX,
)

RECEIPT_REFERENCE_RE = reference_sequences.RECEIPT_REFERENCE_RE
normalize_reference_fragment = reference_sequences.normalize_reference_fragment


def generate_receipt_reference(*, received_on=None, source_contact=None) -> str:
    return reference_sequences.generate_receipt_reference(
        received_on=received_on,
        source_contact=source_contact,
        receipt_model=Receipt,
        receipt_sequence_model=ReceiptSequence,
        receipt_donor_sequence_model=ReceiptDonorSequence,
        transaction_module=transaction,
        connection_obj=connection,
        integrity_error=IntegrityError,
        receipt_reference_re=RECEIPT_REFERENCE_RE,
        localdate_fn=timezone.localdate,
    )


def generate_shipment_reference() -> str:
    return reference_sequences.generate_shipment_reference(
        shipment_model=Shipment,
        shipment_sequence_model=ShipmentSequence,
        transaction_module=transaction,
        connection_obj=connection,
        integrity_error=IntegrityError,
        length_cls=Length,
        localdate_fn=timezone.localdate,
    )


__all__ = [
    "ProductCategory",
    "ProductTag",
    "Product",
    "ProductKitItem",
    "Warehouse",
    "Location",
    "RackColor",
    "ProductLotStatus",
    "ProductLot",
    "ReceiptType",
    "ReceiptStatus",
    "Receipt",
    "ReceiptLine",
    "ReceiptHorsFormat",
    "ReceiptSequence",
    "ReceiptDonorSequence",
    "ShipmentSequence",
    "Destination",
    "ShipmentStatus",
    "TEMP_SHIPMENT_REFERENCE_PREFIX",
    "Shipment",
    "ShipmentTrackingStatus",
    "ShipmentTrackingEvent",
    "OrderStatus",
    "OrderReviewStatus",
    "Order",
    "PublicOrderLink",
    "PublicAccountRequestStatus",
    "PublicAccountRequestType",
    "PublicAccountRequest",
    "AssociationProfile",
    "AssociationContactTitle",
    "AssociationPortalContact",
    "AssociationRecipient",
    "DocumentReviewStatus",
    "AccountDocumentType",
    "AccountDocument",
    "OrderLine",
    "OrderReservation",
    "OrderDocumentType",
    "OrderDocument",
    "CartonFormat",
    "CartonStatus",
    "Carton",
    "CartonStatusEvent",
    "CartonItem",
    "MovementType",
    "StockMovement",
    "DocumentType",
    "Document",
    "PrintTemplate",
    "PrintTemplateVersion",
    "WmsChange",
    "IntegrationDirection",
    "IntegrationStatus",
    "IntegrationEvent",
    "RECEIPT_REFERENCE_RE",
    "normalize_reference_fragment",
    "generate_receipt_reference",
    "generate_shipment_reference",
]
