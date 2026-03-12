from __future__ import annotations

from urllib.parse import quote

from django.core.exceptions import ValidationError

from wms.models import CommunicationChannel, CommunicationDraft, PlanningVersion
from wms.planning.communication_plan import build_version_communication_plan

PLANNING_WORKBOOK_ATTACHMENT = "planning_workbook"
PACKING_LIST_ATTACHMENT = "packing_list_pdf"


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


def _planning_workbook_attachments(version: PlanningVersion) -> list[dict[str, object]]:
    return [
        {
            "attachment_type": PLANNING_WORKBOOK_ATTACHMENT,
            "version_id": version.pk,
            "filename": f"planning-v{version.number}.xlsx",
        }
    ]


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
            }
        )
    return attachments


def _attachments_for_draft(draft: CommunicationDraft) -> list[dict[str, object]]:
    if draft.family in {"email_asf", "email_airfrance"}:
        return _planning_workbook_attachments(draft.version)
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
        }

    return {
        "draft_id": draft.pk,
        "action": "email",
        "family": draft.family,
        "recipient_label": draft.recipient_label,
        "recipient_contact": draft.recipient_contact,
        "subject": draft.subject,
        "body_html": draft.body,
        "attachments": _attachments_for_draft(draft),
    }


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
