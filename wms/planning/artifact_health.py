from __future__ import annotations

from pathlib import Path

from wms.models import PlanningCommunicationArtifact, PlanningVersion

PLANNING_ARTIFACT_STATUS_READY = "ready"
PLANNING_ARTIFACT_STATUS_FAILED = "failed"
PLANNING_WORKBOOK_BACKEND = "openpyxl"


def record_planning_artifact_result(
    *,
    version: PlanningVersion,
    output_type: str,
    status: str,
    backend: str,
    file_name: str = "",
    error_message: str = "",
    payload: dict | None = None,
) -> PlanningCommunicationArtifact:
    return PlanningCommunicationArtifact.objects.create(
        planning_version=version,
        output_type=output_type,
        status=status,
        backend=backend,
        file_name=file_name,
        error_message=error_message,
        payload=payload or {},
    )


def artifact_file_name(file_path) -> str:
    if not file_path:
        return ""
    return Path(str(file_path)).name


def latest_planning_artifact_health(*, version: PlanningVersion, output_type: str):
    return (
        version.communication_artifacts.filter(output_type=output_type)
        .order_by("-generated_at", "-id")
        .first()
    )


def latest_ready_planning_artifact_health(*, version: PlanningVersion, output_type: str):
    return (
        version.communication_artifacts.filter(
            output_type=output_type,
            status=PLANNING_ARTIFACT_STATUS_READY,
        )
        .order_by("-generated_at", "-id")
        .first()
    )
