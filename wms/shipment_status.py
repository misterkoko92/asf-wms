from django.utils import timezone

from .models import CartonStatus, ShipmentStatus

LOCKED_SHIPMENT_STATUSES = {
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
}
LABELED_CARTON_STATUSES = {CartonStatus.LABELED, CartonStatus.SHIPPED}


def compute_shipment_progress(shipment):
    cartons = shipment.carton_set.all()
    total = cartons.count()
    labeled = cartons.filter(status__in=LABELED_CARTON_STATUSES).count()
    if total == 0:
        return total, labeled, ShipmentStatus.DRAFT, "CREATION"
    if labeled < total:
        return total, labeled, ShipmentStatus.PICKING, f"EN COURS ({labeled}/{total})"
    return total, labeled, ShipmentStatus.PACKED, "PRET"


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
