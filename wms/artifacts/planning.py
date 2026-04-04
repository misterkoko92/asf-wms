from __future__ import annotations

from pathlib import Path

from tools.planning_comm_helper import excel_pdf, excel_runtime
from tools.planning_comm_helper.planning_pdf import (
    PlanningPdfConversionError,
    convert_workbook_to_pdf,
)
from wms.models import PlanningCommunicationArtifact, PlanningVersion
from wms.planning import exports as legacy_exports

PLANNING_WORKBOOK_ARTIFACT = legacy_exports.PLANNING_WORKBOOK_ARTIFACT
PLANNING_PDF_ARTIFACT = legacy_exports.PLANNING_PDF_ARTIFACT

PLANNING_ARTIFACT_STATUS_READY = "ready"
PLANNING_ARTIFACT_STATUS_FAILED = "failed"
PLANNING_ARTIFACT_STATUS_MISSING = "missing"
PLANNING_WORKBOOK_BACKEND = "openpyxl"

PLANNING_ARTIFACT_STATUS_LABELS = {
    PLANNING_ARTIFACT_STATUS_READY: "Pret",
    PLANNING_ARTIFACT_STATUS_FAILED: "Echec",
    PLANNING_ARTIFACT_STATUS_MISSING: "Aucune tentative",
}

PLANNING_RUNTIME_STATUS_LABELS = {
    excel_runtime.EXCEL_RUNTIME_READY: "Pret",
    excel_runtime.EXCEL_RUNTIME_PLATFORM_UNSUPPORTED: "Plateforme non supportee",
    excel_runtime.EXCEL_RUNTIME_NOT_INSTALLED: "Excel indisponible",
    excel_runtime.EXCEL_RUNTIME_AUTOMATION_UNAVAILABLE: "Automation Excel indisponible",
}

_EXPORT_PDF_ERRORS = (
    PlanningPdfConversionError,
    FileNotFoundError,
    OSError,
    PermissionError,
    RuntimeError,
    ValueError,
    TypeError,
)


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


def planning_artifact_status_label(status: str) -> str:
    return PLANNING_ARTIFACT_STATUS_LABELS.get(status, status or "")


def planning_runtime_status_label(status: str) -> str:
    return PLANNING_RUNTIME_STATUS_LABELS.get(status, status or "")


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


def _build_artifact_metadata(
    *,
    version: PlanningVersion,
    output_type: str,
    default_backend: str = "",
) -> dict[str, object]:
    latest_ready = latest_ready_planning_artifact_health(
        version=version,
        output_type=output_type,
    )
    latest_any = latest_planning_artifact_health(
        version=version,
        output_type=output_type,
    )
    health = latest_ready or latest_any
    return {
        "output_type": output_type,
        "status": health.status if health is not None else PLANNING_ARTIFACT_STATUS_MISSING,
        "backend": (health.backend if health is not None and health.backend else default_backend),
        "file_name": health.file_name if health is not None else "",
        "error_message": health.error_message if health is not None else "",
        "generated_at": health.generated_at if health is not None else None,
        "artifact_id": health.payload.get("artifact_id") if health is not None else None,
    }


def build_planning_artifacts(version: PlanningVersion) -> dict[str, dict[str, object]]:
    return {
        "workbook": _build_artifact_metadata(
            version=version,
            output_type=PLANNING_WORKBOOK_ARTIFACT,
            default_backend=PLANNING_WORKBOOK_BACKEND,
        ),
        "pdf": _build_artifact_metadata(
            version=version,
            output_type=PLANNING_PDF_ARTIFACT,
            default_backend=excel_pdf.pdf_backend_name(),
        ),
    }


def export_planning_workbook(version):
    template_path = legacy_exports._planning_template_path()
    output_path = (
        legacy_exports._planning_output_dir() / f"{legacy_exports._planning_basename(version)}.xlsx"
    )
    workbook = legacy_exports.load_workbook(template_path)
    try:
        try:
            ws_plan = legacy_exports._planning_sheet(workbook)
            legacy_exports._reset_planning_grid(ws_plan)
            legacy_exports._write_metadata(ws_plan, version=version)
            legacy_exports._populate_planning_sheet(
                ws_plan,
                rows=legacy_exports._build_export_rows(version),
            )
            legacy_exports._apply_planning_layout(ws_plan)
            workbook.save(output_path)
            artifact = legacy_exports._upsert_artifact(
                version=version,
                artifact_type=PLANNING_WORKBOOK_ARTIFACT,
                label=legacy_exports._artifact_label(version, suffix="XLSX"),
                file_path=output_path,
            )
            record_planning_artifact_result(
                version=version,
                output_type=PLANNING_WORKBOOK_ARTIFACT,
                status=PLANNING_ARTIFACT_STATUS_READY,
                backend=PLANNING_WORKBOOK_BACKEND,
                file_name=artifact_file_name(output_path),
                payload={"artifact_id": artifact.pk},
            )
            return artifact
        except Exception as exc:
            record_planning_artifact_result(
                version=version,
                output_type=PLANNING_WORKBOOK_ARTIFACT,
                status=PLANNING_ARTIFACT_STATUS_FAILED,
                backend=PLANNING_WORKBOOK_BACKEND,
                file_name=artifact_file_name(output_path),
                error_message=str(exc),
            )
            raise
    finally:
        workbook.close()


def export_planning_pdf(version):
    workbook_artifact = export_planning_workbook(version)
    return _export_pdf_artifact(version=version, workbook_artifact=workbook_artifact)


def export_planning_artifacts(version):
    workbook_artifact = export_planning_workbook(version)
    pdf_artifact = _export_pdf_artifact(version=version, workbook_artifact=workbook_artifact)
    return {
        PLANNING_WORKBOOK_ARTIFACT: workbook_artifact,
        PLANNING_PDF_ARTIFACT: pdf_artifact,
    }


def _export_pdf_artifact(*, version, workbook_artifact):
    workbook_path = Path(workbook_artifact.file_path)
    pdf_path = (
        legacy_exports._planning_output_dir() / f"{legacy_exports._planning_basename(version)}.pdf"
    )
    runtime_status = excel_runtime.get_excel_runtime_status()
    if not runtime_status["available"]:
        runtime_message = excel_runtime.build_runtime_unavailable_message(runtime_status)
        record_planning_artifact_result(
            version=version,
            output_type=PLANNING_PDF_ARTIFACT,
            status=PLANNING_ARTIFACT_STATUS_FAILED,
            backend=excel_pdf.pdf_backend_name(),
            file_name=artifact_file_name(pdf_path),
            error_message=runtime_message,
            payload={
                "workbook_artifact_id": workbook_artifact.pk,
                "error_code": runtime_status["status"],
                "runtime_status": runtime_status["status"],
                "runtime_detail": runtime_status["detail"],
            },
        )
        raise legacy_exports.PlanningExportError("Planning PDF indisponible.")
    try:
        generated = Path(convert_workbook_to_pdf(workbook_path, pdf_path, strict=True))
    except _EXPORT_PDF_ERRORS as exc:
        error_code = runtime_status["status"]
        if error_code == excel_runtime.EXCEL_RUNTIME_READY:
            error_code = excel_runtime.EXCEL_RUNTIME_AUTOMATION_UNAVAILABLE
        record_planning_artifact_result(
            version=version,
            output_type=PLANNING_PDF_ARTIFACT,
            status=PLANNING_ARTIFACT_STATUS_FAILED,
            backend=excel_pdf.pdf_backend_name(),
            file_name=artifact_file_name(pdf_path),
            error_message=str(exc),
            payload={
                "workbook_artifact_id": workbook_artifact.pk,
                "error_code": error_code,
                "runtime_status": runtime_status["status"],
                "runtime_detail": runtime_status["detail"],
            },
        )
        raise legacy_exports.PlanningExportError("Planning PDF indisponible.") from exc
    if not generated.exists():
        record_planning_artifact_result(
            version=version,
            output_type=PLANNING_PDF_ARTIFACT,
            status=PLANNING_ARTIFACT_STATUS_FAILED,
            backend=excel_pdf.pdf_backend_name(),
            file_name=artifact_file_name(pdf_path),
            error_message="Generated PDF file is missing.",
            payload={
                "workbook_artifact_id": workbook_artifact.pk,
                "error_code": excel_runtime.EXCEL_RUNTIME_AUTOMATION_UNAVAILABLE,
                "runtime_status": runtime_status["status"],
                "runtime_detail": runtime_status["detail"],
            },
        )
        raise legacy_exports.PlanningExportError("Planning PDF indisponible.")
    artifact = legacy_exports._upsert_artifact(
        version=version,
        artifact_type=PLANNING_PDF_ARTIFACT,
        label=legacy_exports._artifact_label(version, suffix="PDF"),
        file_path=generated,
    )
    record_planning_artifact_result(
        version=version,
        output_type=PLANNING_PDF_ARTIFACT,
        status=PLANNING_ARTIFACT_STATUS_READY,
        backend=excel_pdf.pdf_backend_name(),
        file_name=artifact_file_name(generated),
        payload={
            "artifact_id": artifact.pk,
            "workbook_artifact_id": workbook_artifact.pk,
        },
    )
    return artifact
