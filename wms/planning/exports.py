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
    try:
        sheet = workbook.active
        sheet.title = "Planning"
        sheet.append(
            [
                "Date",
                "Flight",
                "Destination",
                "DepartureTime",
                "Volunteer",
                "Shipment",
                "Shipper",
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
            flight = assignment.flight_snapshot
            shipment = assignment.shipment_snapshot
            volunteer = assignment.volunteer_snapshot
            sheet.append(
                [
                    str(flight.departure_date) if flight else "",
                    flight.flight_number if flight else "",
                    flight.destination_iata if flight else "",
                    ((flight.payload or {}).get("departure_time", "") if flight else ""),
                    volunteer.volunteer_label if volunteer else "",
                    shipment.shipment_reference if shipment else "",
                    shipment.shipper_name if shipment else "",
                    assignment.assigned_carton_count,
                    assignment.status,
                    assignment.source,
                    assignment.notes,
                ]
            )

        file_path = _planning_output_dir() / f"planning-run-{version.run_id}-v{version.number}.xlsx"
        workbook.save(file_path)
    finally:
        workbook.close()

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
