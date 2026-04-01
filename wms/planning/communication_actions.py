from __future__ import annotations

from urllib.parse import quote

from django.core.exceptions import ValidationError

from wms.models import CommunicationChannel, CommunicationDraft, PlanningVersion
from wms.planning.artifact_health import (
    latest_planning_artifact_health,
    latest_ready_planning_artifact_health,
)
from wms.planning.communication_plan import build_version_communication_plan

EXCEL_WORKBOOK_ATTACHMENT = "excel_workbook"
PLANNING_WORKBOOK_ATTACHMENT = EXCEL_WORKBOOK_ATTACHMENT
LEGACY_PLANNING_WORKBOOK_ATTACHMENT = "planning_workbook"
PLANNING_PDF_ATTACHMENT = "planning_pdf"
PACKING_LIST_ATTACHMENT = "packing_list_pdf"
PLANNING_PDF_NOT_READY_BLOCKING_REASON = "planning_pdf_not_ready"


def _plan_item_key(
    *, family: str, recipient_label: str, recipient_contact: str
) -> tuple[str, str, str]:
    return (family, recipient_label, recipient_contact)


def _plan_item_by_draft(draft: CommunicationDraft):
    plan = build_version_communication_plan(draft.version)
    plan_items = {
        _plan_item_key(
            family=item.family,
            recipient_label=item.recipient_label,
            recipient_contact=item.recipient_contact,
        ): item
        for item in plan.items
    }
    plan_item = plan_items.get(
        _plan_item_key(
            family=draft.family,
            recipient_label=draft.recipient_label,
            recipient_contact=draft.recipient_contact,
        )
    )
    if plan_item is None:
        raise ValidationError("Draft helper payload requires a matching communication plan item.")
    return plan_item


def _assignments_for_draft(draft: CommunicationDraft):
    plan_item = _plan_item_by_draft(draft)
    return plan_item.current_assignments or plan_item.previous_assignments


def _planning_pdf_attachments(version: PlanningVersion) -> list[dict[str, object]]:
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


def _planning_pdf_delivery_state(version: PlanningVersion) -> dict[str, object]:
    latest_ready = latest_ready_planning_artifact_health(
        version=version,
        output_type=PLANNING_PDF_ATTACHMENT,
    )
    return {
        "attachments": _planning_pdf_attachments(version),
        "blocked": latest_ready is None,
        "blocking_reason": ""
        if latest_ready is not None
        else PLANNING_PDF_NOT_READY_BLOCKING_REASON,
    }


def _packing_list_attachments(draft: CommunicationDraft) -> list[dict[str, object]]:
    attachments: list[dict[str, object]] = []
    seen_snapshot_ids: set[int] = set()
    for assignment in _assignments_for_draft(draft):
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


def _attachments_for_draft(draft: CommunicationDraft) -> list[dict[str, object]]:
    if draft.family in {"email_asf", "email_airfrance"}:
        return _planning_pdf_attachments(draft.version)
    if draft.family in {"email_correspondant", "email_expediteur", "email_destinataire"}:
        return _packing_list_attachments(draft)
    return []


def _wa_me_url(contact: str, body: str) -> str:
    digits = "".join(char for char in str(contact or "") if char.isdigit())
    if not digits:
        return ""
    return f"https://wa.me/{digits}?text={quote(body)}"


def build_draft_helper_action_payload(draft: CommunicationDraft) -> dict[str, object]:
    if draft.channel == CommunicationChannel.WHATSAPP:
        return {
            "draft_id": draft.pk,
            "action": "whatsapp",
            "family": draft.family,
            "recipient_label": draft.recipient_label,
            "recipient_contact": draft.recipient_contact,
            "body": draft.body,
            "wa_url": _wa_me_url(draft.recipient_contact, draft.body),
            "attachments": [],
            "blocked": False,
            "blocking_reason": "",
        }

    payload = {
        "draft_id": draft.pk,
        "action": "email",
        "family": draft.family,
        "recipient_label": draft.recipient_label,
        "recipient_contact": draft.recipient_contact,
        "subject": draft.subject,
        "body_html": draft.body,
        "attachments": _attachments_for_draft(draft),
        "blocked": False,
        "blocking_reason": "",
    }
    if draft.family in {"email_asf", "email_airfrance"}:
        payload.update(_planning_pdf_delivery_state(draft.version))
    return payload


def build_family_helper_action_payload(
    *, version: PlanningVersion, family: str
) -> dict[str, object]:
    drafts = list(
        version.communication_drafts.filter(family=family).order_by("recipient_label", "id")
    )
    if not drafts:
        raise ValidationError("No communication drafts found for this family.")

    return {
        "version_id": version.pk,
        "family": family,
        "action": "whatsapp" if drafts[0].channel == CommunicationChannel.WHATSAPP else "email",
        "drafts": [build_draft_helper_action_payload(draft) for draft in drafts],
    }
