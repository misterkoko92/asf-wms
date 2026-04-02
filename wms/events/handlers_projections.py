from wms.events.types import RuntimeEvent
from wms.workflow_projection import schedule_shipment_workflow_projection_refresh


def handle_workflow_projection_refresh_requested_event(*, event: RuntimeEvent) -> None:
    shipment_id = int(event.scope_id)
    schedule_shipment_workflow_projection_refresh(shipment_id)
