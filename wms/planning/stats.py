from __future__ import annotations

from wms.models import PlanningAssignmentSource, PlanningVersion


def build_version_stats(version: PlanningVersion) -> dict[str, int]:
    assignments = list(
        version.assignments.select_related(
            "volunteer_snapshot",
            "flight_snapshot",
        )
    )
    return {
        "assignment_count": len(assignments),
        "carton_total": sum(assignment.assigned_carton_count for assignment in assignments),
        "volunteer_count": len(
            {
                assignment.volunteer_snapshot_id
                for assignment in assignments
                if assignment.volunteer_snapshot_id
            }
        ),
        "flight_count": len(
            {
                assignment.flight_snapshot_id
                for assignment in assignments
                if assignment.flight_snapshot_id
            }
        ),
        "manual_adjustment_count": sum(
            1 for assignment in assignments if assignment.source == PlanningAssignmentSource.MANUAL
        ),
    }
