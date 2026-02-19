import json
import logging

from django.utils import timezone

LOGGER = logging.getLogger("wms.workflow")


def _actor_payload(user):
    if user is None:
        return None
    user_id = getattr(user, "pk", None)
    if not user_id:
        return None
    username = ""
    if hasattr(user, "get_username"):
        username = user.get_username() or ""
    if not username:
        username = getattr(user, "username", "") or ""
    return {
        "id": user_id,
        "username": username,
    }


def _shipment_payload(shipment):
    if shipment is None:
        return None
    return {
        "id": getattr(shipment, "pk", None),
        "reference": getattr(shipment, "reference", ""),
        "status": getattr(shipment, "status", ""),
        "destination_id": getattr(shipment, "destination_id", None),
        "is_disputed": bool(getattr(shipment, "is_disputed", False)),
    }


def _carton_payload(carton):
    if carton is None:
        return None
    return {
        "id": getattr(carton, "pk", None),
        "code": getattr(carton, "code", ""),
        "status": getattr(carton, "status", ""),
        "shipment_id": getattr(carton, "shipment_id", None),
    }


def log_workflow_event(event_type, *, shipment=None, carton=None, user=None, **payload):
    event_payload = {
        "event_type": event_type,
        "occurred_at": timezone.now().isoformat(),
        "shipment": _shipment_payload(shipment),
        "carton": _carton_payload(carton),
        "actor": _actor_payload(user),
    }
    event_payload.update(payload)
    LOGGER.info(
        json.dumps(
            event_payload,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    )


def log_carton_status_transition(
    *,
    carton,
    previous_status,
    new_status,
    reason="",
    user=None,
    source="",
):
    log_workflow_event(
        "carton_status_transition",
        carton=carton,
        shipment=getattr(carton, "shipment", None),
        user=user,
        previous_status=previous_status or "",
        new_status=new_status or "",
        reason=reason or "",
        source=source or "",
    )


def log_shipment_status_transition(
    *,
    shipment,
    previous_status,
    new_status,
    reason="",
    user=None,
    source="",
):
    log_workflow_event(
        "shipment_status_transition",
        shipment=shipment,
        user=user,
        previous_status=previous_status or "",
        new_status=new_status or "",
        reason=reason or "",
        source=source or "",
    )


def log_shipment_tracking_event(*, tracking_event, user=None):
    shipment = getattr(tracking_event, "shipment", None)
    log_workflow_event(
        "shipment_tracking_event",
        shipment=shipment,
        user=user,
        tracking_event_id=getattr(tracking_event, "pk", None),
        tracking_status=getattr(tracking_event, "status", ""),
        actor_name=getattr(tracking_event, "actor_name", ""),
        actor_structure=getattr(tracking_event, "actor_structure", ""),
    )


def log_shipment_dispute_action(
    *,
    shipment,
    action,
    user=None,
    previous_status="",
    new_status="",
):
    log_workflow_event(
        "shipment_dispute_action",
        shipment=shipment,
        user=user,
        action=action,
        previous_status=previous_status or "",
        new_status=new_status or "",
    )


def log_shipment_case_closed(*, shipment, user=None):
    log_workflow_event(
        "shipment_case_closed",
        shipment=shipment,
        user=user,
        closed_at=getattr(shipment, "closed_at", None),
    )
