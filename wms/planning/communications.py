from __future__ import annotations

from django.core.exceptions import ValidationError
from django.template import Context, Template

from wms.models import (
    CommunicationChannel,
    CommunicationDraft,
    CommunicationTemplate,
    PlanningVersion,
    PlanningVersionStatus,
)
from wms.planning.communication_plan import build_version_communication_plan


def _render_text(template_text: str, context: dict[str, object]) -> str:
    if not template_text:
        return ""
    return Template(template_text).render(Context(context)).strip()


def _format_assignment_summary(assignments) -> str:
    parts = []
    for assignment in assignments:
        flight = assignment.flight_number or "-"
        shipment_reference = assignment.shipment_reference or "-"
        cartons = assignment.cartons
        parts.append(f"{flight} pour {shipment_reference} ({cartons} colis)")
    return "; ".join(parts)


def _change_status_label(change_status: str) -> str:
    labels = {
        "new": "nouveau",
        "changed": "modifie",
        "cancelled": "annulation",
        "unchanged": "inchange",
    }
    return labels.get(change_status, change_status)


def _build_plan_item_context(version: PlanningVersion, plan_item) -> dict[str, object]:
    reference_assignments = plan_item.current_assignments or plan_item.previous_assignments
    primary_assignment = reference_assignments[0] if reference_assignments else None
    shipment_reference = primary_assignment.shipment_reference if primary_assignment else ""
    volunteer = plan_item.recipient_label
    flight = primary_assignment.flight_number if primary_assignment else ""
    cartons = primary_assignment.cartons if primary_assignment else 0
    return {
        "version_number": version.number,
        "week_start": version.run.week_start,
        "week_end": version.run.week_end,
        "shipment_reference": shipment_reference,
        "volunteer": volunteer,
        "recipient_label": volunteer,
        "flight": flight,
        "cartons": cartons,
        "notes": primary_assignment.notes if primary_assignment else "",
        "change_status": plan_item.change_status,
        "change_status_label": _change_status_label(plan_item.change_status),
        "change_summary": plan_item.change_summary,
        "assignment_count": len(plan_item.current_assignments),
        "current_assignments": plan_item.current_assignments,
        "previous_assignments": plan_item.previous_assignments,
    }


def _fallback_subject(version: PlanningVersion, plan_item) -> str:
    recipient = plan_item.recipient_label or "-"
    if plan_item.change_status == "cancelled":
        return f"Annulation planning v{version.number} pour {recipient}"
    if plan_item.change_status == "changed":
        return f"Mise a jour planning v{version.number} pour {recipient}"
    return f"Planning v{version.number} pour {recipient}"


def _fallback_body(plan_item) -> str:
    recipient = plan_item.recipient_label or "-"
    if plan_item.change_status == "cancelled":
        previous_summary = _format_assignment_summary(plan_item.previous_assignments)
        return f"Annulation pour {recipient}: {previous_summary}."

    current_summary = _format_assignment_summary(plan_item.current_assignments)
    if plan_item.change_status == "changed":
        previous_summary = _format_assignment_summary(plan_item.previous_assignments)
        return f"Mise a jour pour {recipient}: {current_summary}. Avant: {previous_summary}."
    if plan_item.change_status == "unchanged":
        return f"Aucun changement pour {recipient}: {current_summary}."
    return f"Planning pour {recipient}: {current_summary}."


def generate_version_drafts(version: PlanningVersion) -> list[CommunicationDraft]:
    if version.status != PlanningVersionStatus.PUBLISHED:
        raise ValidationError("Communication drafts can only be generated for published versions.")

    CommunicationDraft.objects.filter(version=version).delete()
    templates_by_channel: dict[str, list[CommunicationTemplate]] = {}
    for template in CommunicationTemplate.objects.filter(is_active=True).order_by("id"):
        templates_by_channel.setdefault(template.channel, []).append(template)
    plan = build_version_communication_plan(version)

    generated_drafts: list[CommunicationDraft] = []
    for plan_item in plan.items:
        context = _build_plan_item_context(version, plan_item)
        templates = templates_by_channel.get(plan_item.channel, [])
        if templates:
            for template in templates:
                generated_drafts.append(
                    CommunicationDraft(
                        version=version,
                        template=template,
                        channel=template.channel,
                        recipient_label=str(context["recipient_label"]),
                        recipient_contact="",
                        subject=_render_text(template.subject, context),
                        body=_render_text(template.body, context),
                    )
                )
            continue
        generated_drafts.append(
            CommunicationDraft(
                version=version,
                channel=CommunicationChannel.EMAIL,
                recipient_label=str(context["recipient_label"]),
                recipient_contact="",
                subject=_fallback_subject(version, plan_item),
                body=_fallback_body(plan_item),
            )
        )

    if generated_drafts:
        CommunicationDraft.objects.bulk_create(generated_drafts)
    return list(
        CommunicationDraft.objects.filter(version=version).order_by(
            "channel",
            "recipient_label",
            "id",
        )
    )
