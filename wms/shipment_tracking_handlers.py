from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone

from .models import (
    CartonStatus,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
)

TRACKING_TO_SHIPMENT_STATUS = {
    ShipmentTrackingStatus.PLANNING_OK: ShipmentStatus.PACKED,
    ShipmentTrackingStatus.PLANNED: ShipmentStatus.PLANNED,
    ShipmentTrackingStatus.MOVED_EXPORT: ShipmentStatus.PLANNED,
    ShipmentTrackingStatus.BOARDING_OK: ShipmentStatus.SHIPPED,
    ShipmentTrackingStatus.RECEIVED_CORRESPONDENT: ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentTrackingStatus.RECEIVED_RECIPIENT: ShipmentStatus.DELIVERED,
}
DISPUTE_RESETTABLE_STATUSES = {
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
}


def _redirect_to_tracking(shipment):
    return redirect("scan:scan_shipment_track", tracking_token=shipment.tracking_token)


def _handle_dispute_action(request, shipment):
    action = (request.POST.get("action") or "").strip()
    if action == "set_disputed":
        if not shipment.is_disputed:
            shipment.is_disputed = True
            shipment.disputed_at = timezone.now()
            shipment.save(update_fields=["is_disputed", "disputed_at"])
        messages.warning(request, "Expedition marquee en litige.")
        return _redirect_to_tracking(shipment)

    if action != "resolve_dispute":
        return None

    updates = {}
    previous_status = shipment.status
    if shipment.is_disputed:
        updates["is_disputed"] = False
        updates["disputed_at"] = None
    if previous_status in DISPUTE_RESETTABLE_STATUSES:
        updates["status"] = ShipmentStatus.PACKED
        if shipment.ready_at is None:
            updates["ready_at"] = timezone.now()
    if updates:
        for field_name, field_value in updates.items():
            setattr(shipment, field_name, field_value)
        shipment.save(update_fields=list(updates.keys()))
        if previous_status in {
            ShipmentStatus.SHIPPED,
            ShipmentStatus.RECEIVED_CORRESPONDENT,
            ShipmentStatus.DELIVERED,
        }:
            shipment.carton_set.filter(status=CartonStatus.SHIPPED).update(
                status=CartonStatus.LABELED
            )
    messages.success(request, "Litige resolu. Expedition remise a l'etat Pret.")
    return _redirect_to_tracking(shipment)


def handle_shipment_tracking_post(request, *, shipment, form):
    if request.method != "POST":
        return None

    dispute_response = _handle_dispute_action(request, shipment)
    if dispute_response:
        return dispute_response

    if shipment.is_disputed:
        messages.error(
            request,
            "Expedition en litige: resolvez le litige avant de continuer le suivi.",
        )
        return _redirect_to_tracking(shipment)

    if not form.is_valid():
        return None
    status_value = form.cleaned_data["status"]
    ShipmentTrackingEvent.objects.create(
        shipment=shipment,
        status=status_value,
        actor_name=form.cleaned_data["actor_name"],
        actor_structure=form.cleaned_data["actor_structure"],
        comments=form.cleaned_data["comments"] or "",
        created_by=request.user if request.user.is_authenticated else None,
    )
    target_status = TRACKING_TO_SHIPMENT_STATUS.get(status_value)
    if target_status and shipment.status != target_status:
        shipment.status = target_status
        update_fields = ["status"]
        if target_status == ShipmentStatus.PACKED and shipment.ready_at is None:
            shipment.ready_at = timezone.now()
            update_fields.append("ready_at")
        shipment.save(update_fields=update_fields)
        if target_status == ShipmentStatus.SHIPPED:
            shipment.carton_set.exclude(status=CartonStatus.SHIPPED).update(
                status=CartonStatus.SHIPPED
            )
    messages.success(request, "Suivi mis à jour.")
    return _redirect_to_tracking(shipment)
