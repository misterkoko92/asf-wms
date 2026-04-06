from django.db import transaction
from django.utils import timezone

from .carton_status_events import set_carton_status
from .models import CartonStatus, ShipmentStatus

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


def compute_shipment_progress(shipment):
    cartons = shipment.carton_set.all()
    total = cartons.count()
    labeled = cartons.filter(status__in=LABELED_CARTON_STATUSES).count()
    if total == 0:
        return total, labeled, ShipmentStatus.DRAFT, "CRÉATION"
    if labeled < total:
        return total, labeled, ShipmentStatus.PICKING, f"EN COURS ({labeled}/{total})"
    return total, labeled, ShipmentStatus.PACKED, "PRÊT"


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
    if getattr(shipment, "is_disputed", False):
        return False
    if shipment.status != ShipmentStatus.PICKING:
        return False
    cartons = shipment.carton_set.all()
    if not cartons.exists():
        return False
    return not cartons.exclude(status__in=READY_CONFIRMABLE_CARTON_STATUSES).exists()


def confirm_shipment_ready(*, shipment, user=None):
    from .domain.stock import StockError

    if not getattr(shipment, "pk", None):
        raise StockError("Expédition introuvable.")

    with transaction.atomic():
        locked_shipment = type(shipment).objects.select_for_update().get(pk=shipment.pk)
        cartons = list(locked_shipment.carton_set.select_for_update().order_by("id"))
        if not cartons:
            raise StockError("Aucun colis à confirmer pour cette expédition.")
        if not shipment_can_be_confirmed_ready(locked_shipment):
            raise StockError(
                "Tous les colis doivent être affectés ou étiquetés avant confirmation."
            )

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
