from wms.events.types import (
    EVENT_ORDER_STATUS_CHANGED,
    EVENT_PILOTAGE_REFRESH_REQUESTED,
    EVENT_PLANNING_ARTIFACT_EXPORTED,
    EVENT_SHIPMENT_STATUS_CHANGED,
    EVENT_TRACKING_EVENT_CREATED,
    EVENT_WORKFLOW_PROJECTION_REFRESH_REQUESTED,
    RuntimeEvent,
)


def build_shipment_status_changed_event(
    *, shipment_id: int, old_status: str, new_status: str
) -> RuntimeEvent:
    return RuntimeEvent(
        event_type=EVENT_SHIPMENT_STATUS_CHANGED,
        scope_type="shipment",
        scope_id=str(shipment_id),
        payload={
            "shipment_id": shipment_id,
            "old_status": old_status,
            "new_status": new_status,
        },
    )


def build_tracking_event_created_event(*, shipment_id: int, tracking_event_id: int) -> RuntimeEvent:
    return RuntimeEvent(
        event_type=EVENT_TRACKING_EVENT_CREATED,
        scope_type="shipment",
        scope_id=str(shipment_id),
        payload={
            "shipment_id": shipment_id,
            "tracking_event_id": tracking_event_id,
        },
    )


def build_order_status_changed_event(
    *, order_id: int, old_status: str, new_status: str
) -> RuntimeEvent:
    return RuntimeEvent(
        event_type=EVENT_ORDER_STATUS_CHANGED,
        scope_type="order",
        scope_id=str(order_id),
        payload={
            "order_id": order_id,
            "old_status": old_status,
            "new_status": new_status,
        },
    )


def build_workflow_projection_refresh_requested_event(*, shipment_id: int) -> RuntimeEvent:
    return RuntimeEvent(
        event_type=EVENT_WORKFLOW_PROJECTION_REFRESH_REQUESTED,
        scope_type="shipment",
        scope_id=str(shipment_id),
        payload={"shipment_id": shipment_id},
    )


def build_pilotage_refresh_requested_event(*, scope: str) -> RuntimeEvent:
    return RuntimeEvent(
        event_type=EVENT_PILOTAGE_REFRESH_REQUESTED,
        scope_type="pilotage",
        scope_id=scope,
        payload={"scope": scope},
    )


def build_planning_artifact_exported_event(
    *,
    version_id: int,
    artifact_type: str,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_type=EVENT_PLANNING_ARTIFACT_EXPORTED,
        scope_type="planning_version",
        scope_id=str(version_id),
        payload={
            "version_id": version_id,
            "artifact_type": artifact_type,
        },
    )
