from __future__ import annotations

from urllib.parse import quote

from django.core.exceptions import ValidationError

from wms.artifacts.attachments import (
    attachments_for_draft,
    planning_pdf_delivery_state,
)
from wms.artifacts.planning import (
    build_planning_artifacts as build_planning_artifacts_runtime,
)
from wms.models import CommunicationChannel
from wms.planning.communication_plan import build_version_communication_plan


def _plan_item_key(
    *, family: str, recipient_label: str, recipient_contact: str
) -> tuple[str, str, str]:
    return (family, recipient_label, recipient_contact)


def _plan_item_by_draft(draft):
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


def _assignments_for_draft(draft):
    plan_item = _plan_item_by_draft(draft)
    return plan_item.current_assignments or plan_item.previous_assignments


def _wa_me_url(contact: str, body: str) -> str:
    digits = "".join(char for char in str(contact or "") if char.isdigit())
    if not digits:
        return ""
    return f"https://wa.me/{digits}?text={quote(body)}"


def build_planning_artifacts(version):
    return build_planning_artifacts_runtime(version)


def build_draft_helper_action_payload(draft) -> dict[str, object]:
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
        "attachments": attachments_for_draft(
            draft=draft,
            assignments=_assignments_for_draft(draft),
        ),
        "blocked": False,
        "blocking_reason": "",
    }
    if draft.family in {"email_asf", "email_airfrance"}:
        payload.update(planning_pdf_delivery_state(draft.version))
    return payload


def build_family_helper_action_payload(*, version, family: str) -> dict[str, object]:
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
