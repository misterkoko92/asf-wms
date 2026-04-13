from django.db import transaction
from django.utils import timezone

from .carton_status_events import set_carton_status
from .document_scan import DocumentScanStatus
from .models import (
    CartonSourceKind,
    CartonStatus,
    OrderDocumentType,
    ReceiptConformityStatus,
    ShipmentStatus,
)
from .order_helpers import resolve_linked_order_for_shipment

LOCKED_SHIPMENT_STATUSES = {
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
}
LABELED_CARTON_STATUSES = {CartonStatus.LABELED, CartonStatus.SHIPPED}
READY_CONFIRMABLE_CARTON_STATUSES = {
    CartonStatus.ASSIGNED,
    CartonStatus.LABELED,
}
READY_ORDER_DOCUMENT_ERROR = "Attestation donation manquante ou non scannée."
READY_HUMANITARIAN_DOCUMENT_ERROR = "Attestation aide humanitaire manquante ou non scannée."
READY_RECEIPT_REQUIRED_ERROR = (
    "Réception association requise pour les colis préparés par l'expéditeur."
)
READY_RECEIPT_NON_CONFORM_ERROR = "Réception association non conforme."
READY_PACKING_LIST_GLOBAL_ERROR = "Liste de colisage globale manquante ou non scannée."
READY_PACKING_LIST_BY_CARTON_ERROR = "Liste de colisage par colis manquante ou non scannée."


def compute_shipment_progress(shipment):
    cartons = shipment.carton_set.all()
    total = cartons.count()
    labeled = cartons.filter(status__in=LABELED_CARTON_STATUSES).count()
    if total == 0:
        return total, labeled, ShipmentStatus.DRAFT, "CRÉATION"
    if labeled < total:
        return total, labeled, ShipmentStatus.PICKING, f"EN COURS ({labeled}/{total})"
    return total, labeled, ShipmentStatus.PACKED, "PRÊT"


def _shipment_has_ready_cartons(shipment):
    if getattr(shipment, "is_disputed", False):
        return False
    if shipment.status != ShipmentStatus.PICKING:
        return False
    cartons = shipment.carton_set.all()
    if not cartons.exists():
        return False
    return not cartons.exclude(status__in=READY_CONFIRMABLE_CARTON_STATUSES).exists()


def _order_requires_humanitarian_attestation(order):
    for contact in (
        getattr(order, "shipper_contact", None),
        getattr(order, "association_contact", None),
    ):
        if contact is not None and getattr(contact, "is_humanitarian_attestation_exempt", False):
            return False
    return True


def _clean_order_document_types(order):
    if order is None:
        return set()
    return set(
        order.documents.filter(scan_status=DocumentScanStatus.CLEAN).values_list(
            "doc_type",
            flat=True,
        )
    )


def _shipment_ready_blockers(shipment):
    order = resolve_linked_order_for_shipment(shipment)
    if order is None:
        return []

    blockers = []
    clean_doc_types = _clean_order_document_types(order)
    if OrderDocumentType.DONATION_ATTESTATION not in clean_doc_types:
        blockers.append(READY_ORDER_DOCUMENT_ERROR)
    if _order_requires_humanitarian_attestation(order) and (
        OrderDocumentType.HUMANITARIAN_ATTESTATION not in clean_doc_types
    ):
        blockers.append(READY_HUMANITARIAN_DOCUMENT_ERROR)

    has_shipper_cartons = shipment.carton_set.filter(
        source_kind=CartonSourceKind.SHIPPER_RECEIVED
    ).exists()
    if not has_shipper_cartons:
        return blockers

    inbound_delivery = getattr(order, "inbound_delivery", None)
    receipt = getattr(inbound_delivery, "receipt", None) if inbound_delivery is not None else None
    if receipt is None:
        blockers.append(READY_RECEIPT_REQUIRED_ERROR)
    elif receipt.conformity_status == ReceiptConformityStatus.NON_CONFORM:
        blockers.append(READY_RECEIPT_NON_CONFORM_ERROR)
    if OrderDocumentType.PACKING_LIST_GLOBAL not in clean_doc_types:
        blockers.append(READY_PACKING_LIST_GLOBAL_ERROR)
    if OrderDocumentType.PACKING_LIST_BY_CARTON not in clean_doc_types:
        blockers.append(READY_PACKING_LIST_BY_CARTON_ERROR)
    return blockers


def sync_shipment_ready_state(shipment):
    if shipment.status in LOCKED_SHIPMENT_STATUSES:
        return
    total, labeled, new_status, _ = compute_shipment_progress(shipment)
    was_packed = shipment.status == ShipmentStatus.PACKED
    updates = {}
    if shipment.status != new_status:
        updates["status"] = new_status
    if new_status == ShipmentStatus.PACKED:
        if not was_packed or shipment.ready_at is None:
            updates["ready_at"] = timezone.now()
    elif shipment.ready_at is not None:
        updates["ready_at"] = None
    if updates:
        shipment.status = updates.get("status", shipment.status)
        shipment.ready_at = updates.get("ready_at", shipment.ready_at)
        shipment.save(update_fields=list(updates))


def shipment_can_be_confirmed_ready(shipment):
    if not _shipment_has_ready_cartons(shipment):
        return False
    return not _shipment_ready_blockers(shipment)


def confirm_shipment_ready(*, shipment, user=None):
    from .domain.stock import StockError

    if not getattr(shipment, "pk", None):
        raise StockError("Expédition introuvable.")

    with transaction.atomic():
        locked_shipment = type(shipment).objects.select_for_update().get(pk=shipment.pk)
        cartons = list(locked_shipment.carton_set.select_for_update().order_by("id"))
        if not cartons:
            raise StockError("Aucun colis à confirmer pour cette expédition.")
        if not _shipment_has_ready_cartons(locked_shipment):
            raise StockError(
                "Tous les colis doivent être affectés ou étiquetés avant confirmation."
            )
        blockers = _shipment_ready_blockers(locked_shipment)
        if blockers:
            raise StockError(blockers[0])

        for carton in cartons:
            if carton.status == CartonStatus.ASSIGNED:
                set_carton_status(
                    carton=carton,
                    new_status=CartonStatus.LABELED,
                    reason="shipment_confirm_ready",
                    user=user,
                )

        update_fields = []
        if locked_shipment.status != ShipmentStatus.PACKED:
            locked_shipment.status = ShipmentStatus.PACKED
            update_fields.append("status")
        if locked_shipment.ready_at is None:
            locked_shipment.ready_at = timezone.now()
            update_fields.append("ready_at")
        if update_fields:
            locked_shipment.save(update_fields=update_fields)

    shipment.status = locked_shipment.status
    shipment.ready_at = locked_shipment.ready_at
    return locked_shipment
