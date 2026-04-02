from dataclasses import dataclass, field
from typing import Any

EVENT_ORDER_STATUS_CHANGED = "order.status_changed"
EVENT_PLANNING_ARTIFACT_EXPORTED = "planning.artifact_exported"
EVENT_PILOTAGE_REFRESH_REQUESTED = "pilotage.refresh_requested"
EVENT_SHIPMENT_STATUS_CHANGED = "shipment.status_changed"
EVENT_TRACKING_EVENT_CREATED = "shipment_tracking.event_created"
EVENT_WORKFLOW_PROJECTION_REFRESH_REQUESTED = "workflow_projection.refresh_requested"


@dataclass(frozen=True)
class RuntimeEvent:
    event_type: str
    scope_type: str
    scope_id: str
    payload: dict[str, Any] = field(default_factory=dict)
