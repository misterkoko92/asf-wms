from __future__ import annotations

from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from .models import Shipment, ShipmentStatus, ShipmentTrackingStatus, ShipmentWorkflowProjection
from .runtime_settings import get_runtime_config

CURRENT_SEGMENT_CREATION_EXPEDITION = "creation_expedition"
CURRENT_SEGMENT_PLANNED_TO_BOARDING = "planned_to_boarding"
CURRENT_SEGMENT_BOARDING_TO_CORRESPONDENT = "boarding_to_correspondent"
CURRENT_SEGMENT_CORRESPONDENT_TO_DELIVERY = "correspondent_to_delivery"
CURRENT_SEGMENT_DELIVERY_TO_CLOSE = "delivery_to_close"
CURRENT_SEGMENT_CLOSED = "closed"

DELAY_STATE_ON_TIME = "on_time"
DELAY_STATE_NEW = "new"
DELAY_STATE_PERSISTENT = "persistent"
DELAY_STATE_CRITICAL = "critical"

_TRACKING_SEGMENTS = {
    CURRENT_SEGMENT_PLANNED_TO_BOARDING,
    CURRENT_SEGMENT_BOARDING_TO_CORRESPONDENT,
    CURRENT_SEGMENT_CORRESPONDENT_TO_DELIVERY,
}


def _safe_related_events(shipment):
    prefetched = getattr(shipment, "_prefetched_objects_cache", {})
    if "tracking_events" in prefetched:
        return list(prefetched["tracking_events"])
    return list(shipment.tracking_events.all())


def _tracking_milestones(shipment):
    milestones = {
        "planned_at": None,
        "boarding_ok_at": None,
        "received_correspondent_at": None,
        "delivered_at": None,
    }
    for event in _safe_related_events(shipment):
        if event.status == ShipmentTrackingStatus.PLANNED and milestones["planned_at"] is None:
            milestones["planned_at"] = event.created_at
        elif (
            event.status == ShipmentTrackingStatus.BOARDING_OK
            and milestones["boarding_ok_at"] is None
        ):
            milestones["boarding_ok_at"] = event.created_at
        elif (
            event.status == ShipmentTrackingStatus.RECEIVED_CORRESPONDENT
            and milestones["received_correspondent_at"] is None
        ):
            milestones["received_correspondent_at"] = event.created_at
        elif (
            event.status == ShipmentTrackingStatus.RECEIVED_RECIPIENT
            and milestones["delivered_at"] is None
        ):
            milestones["delivered_at"] = event.created_at
    return milestones


def _hours_between(start_at, end_at):
    if start_at is None or end_at is None:
        return None
    if end_at <= start_at:
        return 0.0
    return round((end_at - start_at).total_seconds() / 3600, 1)


def _current_segment_state(shipment, milestones):
    shipment_created_at = getattr(shipment, "created_at", None)
    planned_at = milestones["planned_at"]
    boarding_ok_at = milestones["boarding_ok_at"]
    received_correspondent_at = milestones["received_correspondent_at"]
    delivered_at = milestones["delivered_at"]
    closed_at = getattr(shipment, "closed_at", None)

    if closed_at:
        return CURRENT_SEGMENT_CLOSED, closed_at, 0.0
    if shipment.status == ShipmentStatus.DELIVERED or delivered_at:
        started_at = delivered_at or received_correspondent_at or boarding_ok_at or planned_at
        started_at = started_at or shipment_created_at
        return (
            CURRENT_SEGMENT_DELIVERY_TO_CLOSE,
            started_at,
            _hours_between(started_at, timezone.now()) or 0.0,
        )
    if shipment.status == ShipmentStatus.RECEIVED_CORRESPONDENT or received_correspondent_at:
        started_at = (
            received_correspondent_at or boarding_ok_at or planned_at or shipment_created_at
        )
        return (
            CURRENT_SEGMENT_CORRESPONDENT_TO_DELIVERY,
            started_at,
            _hours_between(started_at, timezone.now()) or 0.0,
        )
    if shipment.status == ShipmentStatus.SHIPPED or boarding_ok_at:
        started_at = boarding_ok_at or planned_at or shipment_created_at
        return (
            CURRENT_SEGMENT_BOARDING_TO_CORRESPONDENT,
            started_at,
            _hours_between(started_at, timezone.now()) or 0.0,
        )
    if shipment.status == ShipmentStatus.PLANNED or planned_at:
        started_at = planned_at or shipment_created_at
        return (
            CURRENT_SEGMENT_PLANNED_TO_BOARDING,
            started_at,
            _hours_between(started_at, timezone.now()) or 0.0,
        )
    return (
        CURRENT_SEGMENT_CREATION_EXPEDITION,
        shipment_created_at,
        _hours_between(shipment_created_at, timezone.now()) or 0.0,
    )


def _delay_threshold_hours(*, current_segment, tracking_alert_hours, workflow_blockage_hours):
    if current_segment in _TRACKING_SEGMENTS:
        return float(tracking_alert_hours)
    if current_segment in {
        CURRENT_SEGMENT_CREATION_EXPEDITION,
        CURRENT_SEGMENT_DELIVERY_TO_CLOSE,
    }:
        return float(workflow_blockage_hours)
    return None


def _classify_delay(
    *, current_segment, segment_age_hours, tracking_alert_hours, workflow_blockage_hours
):
    threshold_hours = _delay_threshold_hours(
        current_segment=current_segment,
        tracking_alert_hours=tracking_alert_hours,
        workflow_blockage_hours=workflow_blockage_hours,
    )
    if current_segment == CURRENT_SEGMENT_CLOSED or threshold_hours is None:
        return DELAY_STATE_ON_TIME, 0.0
    if segment_age_hours > threshold_hours * 3:
        return DELAY_STATE_CRITICAL, round(max(segment_age_hours - threshold_hours, 0.0), 1)
    if segment_age_hours > threshold_hours * 2:
        return DELAY_STATE_PERSISTENT, round(max(segment_age_hours - threshold_hours, 0.0), 1)
    if segment_age_hours > threshold_hours:
        return DELAY_STATE_NEW, round(max(segment_age_hours - threshold_hours, 0.0), 1)
    return DELAY_STATE_ON_TIME, 0.0


def _active_blockage_category(*, current_segment, delay_state, has_open_dispute):
    if has_open_dispute:
        return "suivi"
    if delay_state == DELAY_STATE_ON_TIME:
        return ""
    if current_segment == CURRENT_SEGMENT_CREATION_EXPEDITION:
        return "creation_expedition"
    if current_segment in _TRACKING_SEGMENTS:
        return "suivi"
    if current_segment == CURRENT_SEGMENT_DELIVERY_TO_CLOSE:
        return "cloture"
    return ""


def build_shipment_workflow_projection_payload(
    *,
    shipment,
    tracking_alert_hours,
    workflow_blockage_hours,
):
    milestones = _tracking_milestones(shipment)
    current_segment, segment_started_at, segment_age_hours = _current_segment_state(
        shipment,
        milestones,
    )
    has_open_dispute = bool(getattr(shipment, "is_disputed", False))
    delay_state, current_delay_hours = _classify_delay(
        current_segment=current_segment,
        segment_age_hours=segment_age_hours,
        tracking_alert_hours=tracking_alert_hours,
        workflow_blockage_hours=workflow_blockage_hours,
    )
    dispute_opened_at = getattr(shipment, "dispute_opened_at", None) or getattr(
        shipment, "disputed_at", None
    )
    dispute_resolved_at = getattr(shipment, "dispute_resolved_at", None)
    destination = getattr(shipment, "destination", None)
    destination_label = (
        str(destination) if destination is not None else shipment.destination_address
    )

    return {
        "destination": destination,
        "reference": (getattr(shipment, "reference", "") or "").strip(),
        "tracking_token": getattr(shipment, "tracking_token", None),
        "destination_label": destination_label or "",
        "shipment_status": getattr(shipment, "status", "") or "",
        "shipment_created_at": getattr(shipment, "created_at", None),
        "planned_at": milestones["planned_at"],
        "boarding_ok_at": milestones["boarding_ok_at"],
        "received_correspondent_at": milestones["received_correspondent_at"],
        "delivered_at": milestones["delivered_at"],
        "closed_at": getattr(shipment, "closed_at", None),
        "current_segment": current_segment,
        "segment_started_at": segment_started_at,
        "segment_age_hours": segment_age_hours,
        "is_closed": bool(getattr(shipment, "closed_at", None)),
        "lead_hours_planned_to_boarding": _hours_between(
            milestones["planned_at"],
            milestones["boarding_ok_at"],
        ),
        "lead_hours_boarding_to_correspondent": _hours_between(
            milestones["boarding_ok_at"],
            milestones["received_correspondent_at"],
        ),
        "lead_hours_correspondent_to_delivery": _hours_between(
            milestones["received_correspondent_at"],
            milestones["delivered_at"],
        ),
        "lead_hours_delivery_to_close": _hours_between(
            milestones["delivered_at"],
            getattr(shipment, "closed_at", None),
        ),
        "lead_hours_total_to_delivery": _hours_between(
            getattr(shipment, "created_at", None),
            milestones["delivered_at"],
        ),
        "has_open_dispute": has_open_dispute,
        "dispute_reason": getattr(shipment, "dispute_reason", "") or "",
        "dispute_owner": getattr(shipment, "dispute_owner", "") or "",
        "dispute_opened_at": dispute_opened_at,
        "dispute_resolved_at": dispute_resolved_at,
        "dispute_resolution_hours": _hours_between(dispute_opened_at, dispute_resolved_at),
        "delay_state": delay_state,
        "current_delay_hours": current_delay_hours,
        "active_blockage_category": _active_blockage_category(
            current_segment=current_segment,
            delay_state=delay_state,
            has_open_dispute=has_open_dispute,
        ),
    }


def refresh_shipment_workflow_projection(
    shipment, *, tracking_alert_hours=None, workflow_blockage_hours=None
):
    runtime = get_runtime_config()
    payload = build_shipment_workflow_projection_payload(
        shipment=shipment,
        tracking_alert_hours=tracking_alert_hours or runtime.tracking_alert_hours,
        workflow_blockage_hours=workflow_blockage_hours or runtime.workflow_blockage_hours,
    )
    projection, _created = ShipmentWorkflowProjection.objects.update_or_create(
        shipment=shipment,
        defaults=payload,
    )
    return projection


def refresh_shipment_workflow_projection_by_id(shipment_id):
    if not shipment_id:
        return None
    shipment = (
        Shipment.objects.select_related("destination")
        .prefetch_related("tracking_events")
        .filter(pk=shipment_id)
        .first()
    )
    if shipment is None:
        ShipmentWorkflowProjection.objects.filter(shipment_id=shipment_id).delete()
        return None
    return refresh_shipment_workflow_projection(shipment)


def schedule_shipment_workflow_projection_refresh(shipment_id):
    if not shipment_id:
        return

    def _refresh():
        try:
            refresh_shipment_workflow_projection_by_id(shipment_id)
        except (OperationalError, ProgrammingError):
            return

    transaction.on_commit(_refresh)


def rebuild_shipment_workflow_projections():
    runtime = get_runtime_config()
    queryset = Shipment.objects.select_related("destination").prefetch_related("tracking_events")
    projected_count = 0
    for shipment in queryset.iterator(chunk_size=200):
        refresh_shipment_workflow_projection(
            shipment,
            tracking_alert_hours=runtime.tracking_alert_hours,
            workflow_blockage_hours=runtime.workflow_blockage_hours,
        )
        projected_count += 1
    return projected_count
