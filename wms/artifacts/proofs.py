from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings


def build_artifact_proof_payload(
    *,
    file_path=None,
    file_name: str = "",
    artifact_id: int | None = None,
    source: str = "",
) -> dict[str, object]:
    normalized_path = str(file_path or "")
    resolved_name = file_name or Path(normalized_path).name
    return {
        "artifact_id": artifact_id,
        "file_name": resolved_name,
        "file_path": normalized_path,
        "source": source,
    }


def print_artifact_filename(artifact) -> str:
    filename = os.path.basename((artifact.pdf_file.name or "").strip())
    if not filename:
        filename = f"print-pack-{artifact.pack_code}-{artifact.id}.pdf"
    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    return filename


def print_artifact_relative_dir(artifact) -> str:
    base_dir = (getattr(settings, "GRAPH_WORK_DIR", "") or "").strip().strip("/")
    parts = [base_dir] if base_dir else []
    if artifact.shipment and artifact.shipment.reference:
        parts.extend(["shipments", artifact.shipment.reference])
    elif artifact.carton and artifact.carton.code:
        parts.extend(["cartons", artifact.carton.code])
    else:
        parts.extend(["packs", (artifact.pack_code or "unknown").strip() or "unknown"])
    return "/".join(part for part in parts if part)


def build_print_artifact_proof_payload(artifact) -> dict[str, object]:
    relative_dir = print_artifact_relative_dir(artifact)
    file_name = print_artifact_filename(artifact)
    onedrive_path = f"{relative_dir}/{file_name}" if relative_dir else file_name
    payload = build_artifact_proof_payload(
        artifact_id=getattr(artifact, "id", None),
        file_path=getattr(getattr(artifact, "pdf_file", None), "name", ""),
        file_name=file_name,
        source="print_pack_sync",
    )
    payload.update(
        {
            "relative_dir": relative_dir,
            "onedrive_path": onedrive_path,
            "pack_code": getattr(artifact, "pack_code", "") or "",
            "shipment_reference": getattr(getattr(artifact, "shipment", None), "reference", "")
            or "",
            "carton_code": getattr(getattr(artifact, "carton", None), "code", "") or "",
        }
    )
    return payload


def build_print_artifact_sync_summary(
    *,
    artifact,
    result: str,
    onedrive_path: str = "",
    error_message: str = "",
) -> dict[str, object]:
    proof_payload = build_print_artifact_proof_payload(artifact)
    summary = {
        "artifact_id": proof_payload["artifact_id"],
        "file_name": proof_payload["file_name"],
        "relative_dir": proof_payload["relative_dir"],
        "onedrive_path": onedrive_path or proof_payload["onedrive_path"],
        "result": result,
    }
    if error_message:
        summary["error_message"] = str(error_message)
    return summary
