from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from .carton_status_events import set_carton_status
from .models import (
    CartonStatus,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
)
from .shipment_status import sync_shipment_ready_state
from .workflow_observability import log_shipment_dispute_action

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
ASSIGNED_OR_READY_CARTON_STATUSES = {
    CartonStatus.ASSIGNED,
    CartonStatus.LABELED,
    CartonStatus.SHIPPED,
}
READY_CARTON_STATUSES = {
    CartonStatus.LABELED,
    CartonStatus.SHIPPED,
}
DEFAULT_RETURN_LIST_VIEW = "scan:scan_shipments_tracking"
DEFAULT_RETURN_TO_KEY = "shipments_tracking"


def _redirect_to_tracking(
    shipment,
    *,
    return_to_list=False,
    return_to_view=DEFAULT_RETURN_LIST_VIEW,
    return_to_key=DEFAULT_RETURN_TO_KEY,
):
    if return_to_list:
        return redirect(return_to_view or DEFAULT_RETURN_LIST_VIEW)
    tracking_url = reverse(
        "scan:scan_shipment_track",
        kwargs={"tracking_token": shipment.tracking_token},
    )
    if return_to_key:
        tracking_url = f"{tracking_url}?return_to={return_to_key}"
    return redirect(tracking_url)


def _latest_tracking_status(shipment):
    return shipment.tracking_events.values_list("status", flat=True).first()


def allowed_tracking_statuses_for_shipment(shipment):
    current_status = shipment.status
    last_status = _latest_tracking_status(shipment)
    if current_status == ShipmentStatus.DELIVERED:
        return []
    if current_status == ShipmentStatus.RECEIVED_CORRESPONDENT:
        return [ShipmentTrackingStatus.RECEIVED_RECIPIENT]
    if current_status == ShipmentStatus.SHIPPED:
        return [ShipmentTrackingStatus.RECEIVED_CORRESPONDENT]
    if current_status == ShipmentStatus.PLANNED:
        if last_status == ShipmentTrackingStatus.MOVED_EXPORT:
            return [ShipmentTrackingStatus.BOARDING_OK]
        return [ShipmentTrackingStatus.MOVED_EXPORT, ShipmentTrackingStatus.BOARDING_OK]
    if current_status == ShipmentStatus.PACKED:
        if last_status == ShipmentTrackingStatus.PLANNING_OK:
            return [ShipmentTrackingStatus.PLANNED]
        return [ShipmentTrackingStatus.PLANNING_OK]
    if current_status in {ShipmentStatus.DRAFT, ShipmentStatus.PICKING}:
        return [ShipmentTrackingStatus.PLANNING_OK]
    return []


def _validate_ready_for_planning(shipment):
    cartons = shipment.carton_set.all()
    total = cartons.count()
    assigned_or_ready = cartons.filter(status__in=ASSIGNED_OR_READY_CARTON_STATUSES).count()
    ready = cartons.filter(status__in=READY_CARTON_STATUSES).count()
    if total == 0:
        return "Aucun colis affecté à cette expédition."
    if assigned_or_ready < total:
        return (
            "Tous les colis doivent être affectés avant de poursuivre la planification."
        )
    if ready < total:
        return (
            "Tous les colis doivent être étiquetés avant de poursuivre la planification."
        )
    return ""


def validate_tracking_transition(shipment, status_value):
    allowed_statuses = allowed_tracking_statuses_for_shipment(shipment)
    if status_value not in allowed_statuses:
        return "Transition non autorisée pour le statut actuel de l'expédition."
    if status_value in {
        ShipmentTrackingStatus.PLANNING_OK,
        ShipmentTrackingStatus.PLANNED,
        ShipmentTrackingStatus.MOVED_EXPORT,
        ShipmentTrackingStatus.BOARDING_OK,
    }:
        ready_error = _validate_ready_for_planning(shipment)
        if ready_error:
            return ready_error
    return ""


def _handle_dispute_action(
    request,
    shipment,
    *,
    return_to_list=False,
    return_to_view=DEFAULT_RETURN_LIST_VIEW,
    return_to_key=DEFAULT_RETURN_TO_KEY,
):
    action = (request.POST.get("action") or "").strip()
    if action == "set_disputed":
        previous_status = shipment.status
        if not shipment.is_disputed:
            shipment.is_disputed = True
            shipment.disputed_at = timezone.now()
            shipment.save(update_fields=["is_disputed", "disputed_at"])
        log_shipment_dispute_action(
            shipment=shipment,
            action="set_disputed",
            user=getattr(request, "user", None),
            previous_status=previous_status,
            new_status=shipment.status,
        )
        messages.warning(request, "Expédition marquée en litige.")
        return _redirect_to_tracking(
            shipment,
            return_to_list=return_to_list,
            return_to_view=return_to_view,
            return_to_key=return_to_key,
        )

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
            for carton in shipment.carton_set.filter(status=CartonStatus.SHIPPED):
                set_carton_status(
                    carton=carton,
                    new_status=CartonStatus.LABELED,
                    reason="dispute_resolve_reset",
                    user=getattr(request, "user", None),
                )
        sync_shipment_ready_state(shipment)
        log_shipment_dispute_action(
            shipment=shipment,
            action="resolve_dispute",
            user=getattr(request, "user", None),
            previous_status=previous_status,
            new_status=shipment.status,
        )
    messages.success(request, "Litige résolu. Expédition remise à l'état Prêt.")
    return _redirect_to_tracking(
        shipment,
        return_to_list=return_to_list,
        return_to_view=return_to_view,
        return_to_key=return_to_key,
    )


def handle_shipment_tracking_post(
    request,
    *,
    shipment,
    form,
    return_to_list=False,
    return_to_view=DEFAULT_RETURN_LIST_VIEW,
    return_to_key=DEFAULT_RETURN_TO_KEY,
):
    if request.method != "POST":
        return None

    dispute_response = _handle_dispute_action(
        request,
        shipment,
        return_to_list=return_to_list,
        return_to_view=return_to_view,
        return_to_key=return_to_key,
    )
    if dispute_response:
        return dispute_response

    if shipment.is_disputed:
        messages.error(
            request,
            "Expédition en litige : résolvez le litige avant de continuer le suivi.",
        )
        return _redirect_to_tracking(
            shipment,
            return_to_list=return_to_list,
            return_to_view=return_to_view,
            return_to_key=return_to_key,
        )

    if not form.is_valid():
        return None
    status_value = form.cleaned_data["status"]
    transition_error = validate_tracking_transition(shipment, status_value)
    if transition_error:
        form.add_error("status", transition_error)
        return None
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
            for carton in shipment.carton_set.exclude(status=CartonStatus.SHIPPED):
                set_carton_status(
                    carton=carton,
                    new_status=CartonStatus.SHIPPED,
                    reason="tracking_boarding_ok",
                    user=getattr(request, "user", None),
                )
    messages.success(request, "Suivi mis à jour.")
    return _redirect_to_tracking(
        shipment,
        return_to_list=return_to_list,
        return_to_view=return_to_view,
        return_to_key=return_to_key,
    )
