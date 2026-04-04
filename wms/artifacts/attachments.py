from __future__ import annotations

from wms.artifacts.planning import (
    latest_planning_artifact_health,
    latest_ready_planning_artifact_health,
)

EXCEL_WORKBOOK_ATTACHMENT = "excel_workbook"
PLANNING_WORKBOOK_ATTACHMENT = EXCEL_WORKBOOK_ATTACHMENT
LEGACY_PLANNING_WORKBOOK_ATTACHMENT = "planning_workbook"
PLANNING_PDF_ATTACHMENT = "planning_pdf"
PACKING_LIST_ATTACHMENT = "packing_list_pdf"
PLANNING_PDF_NOT_READY_BLOCKING_REASON = "planning_pdf_not_ready"


def planning_pdf_attachments(version) -> list[dict[str, object]]:
    attachment = {
        "attachment_type": PLANNING_PDF_ATTACHMENT,
        "version_id": version.pk,
        "filename": f"planning-v{version.number}.pdf",
        "optional": False,
    }
    latest_ready = latest_ready_planning_artifact_health(
        version=version,
        output_type=PLANNING_PDF_ATTACHMENT,
    )
    latest_any = latest_planning_artifact_health(
        version=version,
        output_type=PLANNING_PDF_ATTACHMENT,
    )
    health = latest_ready or latest_any
    if health is not None:
        attachment["artifact_status"] = health.status
        attachment["backend"] = health.backend
        if health.file_name:
            attachment["filename"] = health.file_name
    return [attachment]


def planning_pdf_delivery_state(version) -> dict[str, object]:
    latest_ready = latest_ready_planning_artifact_health(
        version=version,
        output_type=PLANNING_PDF_ATTACHMENT,
    )
    return {
        "attachments": planning_pdf_attachments(version),
        "blocked": latest_ready is None,
        "blocking_reason": (
            "" if latest_ready is not None else PLANNING_PDF_NOT_READY_BLOCKING_REASON
        ),
    }


def packing_list_attachments(assignments) -> list[dict[str, object]]:
    attachments: list[dict[str, object]] = []
    seen_snapshot_ids: set[int] = set()
    for assignment in assignments:
        shipment_snapshot_id = assignment.shipment_snapshot_id
        if shipment_snapshot_id is None or shipment_snapshot_id in seen_snapshot_ids:
            continue
        seen_snapshot_ids.add(shipment_snapshot_id)
        shipment_reference = assignment.shipment_reference
        attachments.append(
            {
                "attachment_type": PACKING_LIST_ATTACHMENT,
                "shipment_snapshot_id": shipment_snapshot_id,
                "shipment_reference": shipment_reference,
                "filename": f"packing-list-{shipment_reference}.pdf",
                "optional": True,
            }
        )
    return attachments


def attachments_for_draft(*, draft, assignments) -> list[dict[str, object]]:
    if draft.family in {"email_asf", "email_airfrance"}:
        return planning_pdf_attachments(draft.version)
    if draft.family in {"email_correspondant", "email_expediteur", "email_destinataire"}:
        return packing_list_attachments(assignments)
    return []
