from django.shortcuts import redirect

from .carton_status_events import set_carton_status
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
    if shipment.status in LOCKED_SHIPMENT_STATUSES:
        return True
    return bool(getattr(shipment, "is_disputed", False))


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
            set_carton_status(
                carton=carton,
                new_status=status_value,
                reason="manual_update",
                user=getattr(request, "user", None),
            )
        return redirect("scan:scan_cartons_ready")

    if not carton or not carton.shipment_id or _shipment_is_locked(carton):
        return redirect("scan:scan_cartons_ready")

    shipment = carton.shipment
    if action == "mark_carton_labeled":
        if carton.status in {CartonStatus.ASSIGNED, CartonStatus.PACKED}:
            set_carton_status(
                carton=carton,
                new_status=CartonStatus.LABELED,
                reason="mark_labeled",
                user=getattr(request, "user", None),
            )
            sync_shipment_ready_state(shipment)
        return redirect("scan:scan_cartons_ready")

    if action == "mark_carton_assigned":
        if carton.status == CartonStatus.LABELED:
            set_carton_status(
                carton=carton,
                new_status=CartonStatus.ASSIGNED,
                reason="mark_assigned",
                user=getattr(request, "user", None),
            )
            sync_shipment_ready_state(shipment)
    return redirect("scan:scan_cartons_ready")
