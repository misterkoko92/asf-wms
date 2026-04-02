from dataclasses import dataclass, field
from typing import Any

EVENT_ORDER_STATUS_CHANGED = "order.status_changed"
EVENT_DEFAULT_SHIPPER_LINKS_FOR_DESTINATION = (
    "shipment_parties.default_shipper_links_for_destination"
)
EVENT_DEFAULT_SHIPPER_LINKS_FOR_RECIPIENT_ORGANIZATION = (
    "shipment_parties.default_shipper_links_for_recipient_organization"
)
EVENT_DESTINATION_CORRESPONDENT_RECIPIENT_SUPPORT = (
    "destination.correspondent_recipient_support_requested"
)
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
