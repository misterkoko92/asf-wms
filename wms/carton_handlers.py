from django.shortcuts import redirect

from .models import Carton, CartonStatus, ShipmentStatus
from .shipment_status import sync_shipment_ready_state

LOCKED_SHIPMENT_STATUSES = {
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
}


def _shipment_is_locked(carton):
    shipment = getattr(carton, "shipment", None)
    if not shipment:
        return False
    return shipment.status in LOCKED_SHIPMENT_STATUSES


def handle_carton_status_update(request):
    if request.method != "POST":
        return None
    action = (request.POST.get("action") or "").strip()
    allowed_actions = {
        "update_carton_status",
        "mark_carton_labeled",
        "mark_carton_assigned",
    }
    if action not in allowed_actions:
        return None
    carton_id = request.POST.get("carton_id")
    carton = Carton.objects.filter(pk=carton_id).select_related("shipment").first()
    status_value = (request.POST.get("status") or "").strip()
    allowed = {
        CartonStatus.DRAFT,
        CartonStatus.PICKING,
        CartonStatus.PACKED,
    }
    if action == "update_carton_status":
        if (
            carton
            and carton.status != CartonStatus.SHIPPED
            and status_value in allowed
            and carton.shipment_id is None
        ):
            if carton.status != status_value:
                carton.status = status_value
                carton.save(update_fields=["status"])
        return redirect("scan:scan_cartons_ready")

    if not carton or not carton.shipment_id or _shipment_is_locked(carton):
        return redirect("scan:scan_cartons_ready")

    shipment = carton.shipment
    if action == "mark_carton_labeled":
        if carton.status in {CartonStatus.ASSIGNED, CartonStatus.PACKED}:
            carton.status = CartonStatus.LABELED
            carton.save(update_fields=["status"])
            sync_shipment_ready_state(shipment)
        return redirect("scan:scan_cartons_ready")

    if action == "mark_carton_assigned":
        if carton.status == CartonStatus.LABELED:
            carton.status = CartonStatus.ASSIGNED
            carton.save(update_fields=["status"])
            sync_shipment_ready_state(shipment)
    return redirect("scan:scan_cartons_ready")
