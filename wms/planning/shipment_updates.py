from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from wms.models import (
    PlanningVersion,
    PlanningVersionStatus,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
)

ALLOWED_SHIPMENT_UPDATE_STATUSES = {
    ShipmentStatus.PACKED,
    ShipmentStatus.PLANNED,
}
DEFAULT_ACTOR_STRUCTURE = "ASF WMS Planning"


@transaction.atomic
def apply_version_updates(
    version: PlanningVersion,
    *,
    actor_name: str,
    actor_structure: str = DEFAULT_ACTOR_STRUCTURE,
    user=None,
) -> dict[str, int]:
    if version.status != PlanningVersionStatus.PUBLISHED:
        raise ValidationError(
            "Shipment updates can only be applied from a published planning version."
        )

    summary = {
        "considered": 0,
        "updated": 0,
        "tracking_events_created": 0,
        "skipped_missing": 0,
        "skipped_locked": 0,
    }
    seen_shipments: set[int] = set()

    assignments = version.assignments.select_related("shipment_snapshot__shipment").order_by(
        "sequence",
        "id",
    )
    for assignment in assignments:
        shipment_snapshot = assignment.shipment_snapshot
        shipment = (
            shipment_snapshot.shipment
            if shipment_snapshot and shipment_snapshot.shipment_id
            else None
        )
        if shipment is None:
            summary["skipped_missing"] += 1
            continue
        if shipment.pk in seen_shipments:
            continue
        seen_shipments.add(shipment.pk)
        summary["considered"] += 1

        if shipment.status not in ALLOWED_SHIPMENT_UPDATE_STATUSES:
            summary["skipped_locked"] += 1
            continue

        if shipment.status != ShipmentStatus.PLANNED:
            shipment.status = ShipmentStatus.PLANNED
            shipment.save(update_fields=["status"])
            summary["updated"] += 1

        planned_event_exists = shipment.tracking_events.filter(
            status=ShipmentTrackingStatus.PLANNED
        ).exists()
        if not planned_event_exists:
            ShipmentTrackingEvent.objects.create(
                shipment=shipment,
                status=ShipmentTrackingStatus.PLANNED,
                actor_name=actor_name,
                actor_structure=actor_structure,
                comments=f"Planning version v{version.number}",
                created_by=user or version.created_by,
            )
            summary["tracking_events_created"] += 1

    return summary
