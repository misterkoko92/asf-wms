from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from wms.models import (
    PlanningAssignment,
    PlanningAssignmentSource,
    PlanningVersion,
    PlanningVersionStatus,
)


def _assignment_key(assignment: PlanningAssignment) -> tuple[int | None, int]:
    return (
        assignment.shipment_snapshot_id,
        assignment.sequence,
    )


def _assignment_summary(assignment: PlanningAssignment) -> dict[str, object]:
    return {
        "shipment_reference": (
            assignment.shipment_snapshot.shipment_reference
            if assignment.shipment_snapshot_id
            else ""
        ),
        "volunteer": (
            assignment.volunteer_snapshot.volunteer_label
            if assignment.volunteer_snapshot_id
            else ""
        ),
        "flight": (
            assignment.flight_snapshot.flight_number if assignment.flight_snapshot_id else ""
        ),
        "cartons": assignment.assigned_carton_count,
        "notes": assignment.notes,
        "source": assignment.source,
    }


@transaction.atomic
def clone_version(
    original: PlanningVersion,
    *,
    created_by,
    change_reason: str,
) -> PlanningVersion:
    cloned_version = PlanningVersion.objects.create(
        run=original.run,
        status=PlanningVersionStatus.DRAFT,
        based_on=original,
        change_reason=change_reason,
        created_by=created_by,
    )
    cloned_assignments = [
        PlanningAssignment(
            version=cloned_version,
            shipment_snapshot=assignment.shipment_snapshot,
            volunteer_snapshot=assignment.volunteer_snapshot,
            flight_snapshot=assignment.flight_snapshot,
            assigned_carton_count=assignment.assigned_carton_count,
            assigned_weight_kg=assignment.assigned_weight_kg,
            status=assignment.status,
            source=PlanningAssignmentSource.COPIED,
            notes=assignment.notes,
            sequence=assignment.sequence,
        )
        for assignment in original.assignments.all().order_by("sequence", "id")
    ]
    if cloned_assignments:
        PlanningAssignment.objects.bulk_create(cloned_assignments)
    return cloned_version


@transaction.atomic
def publish_version(version: PlanningVersion) -> PlanningVersion:
    current_version = PlanningVersion.objects.select_for_update().get(pk=version.pk)
    if current_version.status != PlanningVersionStatus.DRAFT:
        raise ValidationError("Only draft planning versions can be published.")

    PlanningVersion.objects.filter(
        run=current_version.run,
        status=PlanningVersionStatus.PUBLISHED,
    ).exclude(pk=current_version.pk).update(status=PlanningVersionStatus.SUPERSEDED)

    current_version.status = PlanningVersionStatus.PUBLISHED
    current_version.save()
    return current_version


def diff_versions(
    previous_version: PlanningVersion,
    current_version: PlanningVersion,
) -> dict[str, list[dict[str, object]]]:
    previous_assignments = {
        _assignment_key(assignment): assignment
        for assignment in previous_version.assignments.select_related(
            "shipment_snapshot",
            "volunteer_snapshot",
            "flight_snapshot",
        )
    }
    current_assignments = {
        _assignment_key(assignment): assignment
        for assignment in current_version.assignments.select_related(
            "shipment_snapshot",
            "volunteer_snapshot",
            "flight_snapshot",
        )
    }

    changed: list[dict[str, object]] = []
    added: list[dict[str, object]] = []
    removed: list[dict[str, object]] = []

    for key, assignment in current_assignments.items():
        if key not in previous_assignments:
            added.append(_assignment_summary(assignment))
            continue

        previous_summary = _assignment_summary(previous_assignments[key])
        current_summary = _assignment_summary(assignment)
        comparable_previous = {
            field: value
            for field, value in previous_summary.items()
            if field != "shipment_reference"
        }
        comparable_current = {
            field: value
            for field, value in current_summary.items()
            if field != "shipment_reference"
        }
        if comparable_previous != comparable_current:
            changed.append(
                {
                    "shipment_reference": current_summary["shipment_reference"],
                    "from": comparable_previous,
                    "to": comparable_current,
                }
            )

    for key, assignment in previous_assignments.items():
        if key not in current_assignments:
            removed.append(_assignment_summary(assignment))

    return {
        "changed": changed,
        "added": added,
        "removed": removed,
    }
