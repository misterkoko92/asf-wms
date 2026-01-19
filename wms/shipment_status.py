from django.utils import timezone

from .models import CartonStatus, ShipmentStatus


def compute_shipment_progress(shipment):
    cartons = shipment.carton_set.all()
    total = cartons.count()
    ready = cartons.filter(
        status__in=[CartonStatus.PACKED, CartonStatus.SHIPPED]
    ).count()
    if total == 0 or ready == 0:
        return total, ready, ShipmentStatus.DRAFT, "DRAFT"
    if ready < total:
        return total, ready, ShipmentStatus.PICKING, f"PARTIEL ({ready}/{total})"
    return total, ready, ShipmentStatus.PACKED, "READY"


def sync_shipment_ready_state(shipment):
    if shipment.status in {ShipmentStatus.SHIPPED, ShipmentStatus.DELIVERED}:
        return
    total, ready, new_status, _ = compute_shipment_progress(shipment)
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
