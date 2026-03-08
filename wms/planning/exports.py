from __future__ import annotations

import os
import tempfile
from pathlib import Path

from openpyxl import Workbook

from wms.models import PlanningArtifact, PlanningVersion


def _planning_output_dir() -> Path:
    base_dir = Path(os.getenv("ASF_TMP_DIR") or tempfile.gettempdir())
    output_dir = base_dir / "asf_wms_planning_exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def export_version_workbook(version: PlanningVersion) -> PlanningArtifact:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Planning"
    sheet.append(
        [
            "Shipment",
            "Volunteer",
            "Flight",
            "Cartons",
            "Status",
            "Source",
            "Notes",
        ]
    )
    for assignment in version.assignments.select_related(
        "shipment_snapshot",
        "volunteer_snapshot",
        "flight_snapshot",
    ).order_by("sequence", "id"):
        sheet.append(
            [
                assignment.shipment_snapshot.shipment_reference
                if assignment.shipment_snapshot_id
                else "",
                assignment.volunteer_snapshot.volunteer_label
                if assignment.volunteer_snapshot_id
                else "",
                assignment.flight_snapshot.flight_number if assignment.flight_snapshot_id else "",
                assignment.assigned_carton_count,
                assignment.status,
                assignment.source,
                assignment.notes,
            ]
        )

    file_path = _planning_output_dir() / f"planning-run-{version.run_id}-v{version.number}.xlsx"
    workbook.save(file_path)

    artifact = version.artifacts.filter(artifact_type="planning_workbook").order_by("id").first()
    if artifact is None:
        artifact = PlanningArtifact.objects.create(
            version=version,
            artifact_type="planning_workbook",
            label=f"Planning v{version.number}",
            file_path=str(file_path),
        )
    else:
        artifact.label = f"Planning v{version.number}"
        artifact.file_path = str(file_path)
        artifact.save(update_fields=["label", "file_path", "generated_at"])
    return artifact
