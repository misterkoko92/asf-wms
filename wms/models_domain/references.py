from django.apps import apps
from django.db import IntegrityError, connection, transaction
from django.db.models.functions import Length
from django.utils import timezone

from .. import reference_sequences

RECEIPT_REFERENCE_RE = reference_sequences.RECEIPT_REFERENCE_RE
normalize_reference_fragment = reference_sequences.normalize_reference_fragment


def _model(model_name: str):
    return apps.get_model("wms", model_name)


def generate_receipt_reference(*, received_on=None, source_contact=None) -> str:
    return reference_sequences.generate_receipt_reference(
        received_on=received_on,
        source_contact=source_contact,
        receipt_model=_model("Receipt"),
        receipt_sequence_model=_model("ReceiptSequence"),
        receipt_donor_sequence_model=_model("ReceiptDonorSequence"),
        transaction_module=transaction,
        connection_obj=connection,
        integrity_error=IntegrityError,
        receipt_reference_re=RECEIPT_REFERENCE_RE,
        localdate_fn=timezone.localdate,
    )


def generate_shipment_reference() -> str:
    return reference_sequences.generate_shipment_reference(
        shipment_model=_model("Shipment"),
        shipment_sequence_model=_model("ShipmentSequence"),
        transaction_module=transaction,
        connection_obj=connection,
        integrity_error=IntegrityError,
        length_cls=Length,
        localdate_fn=timezone.localdate,
    )
