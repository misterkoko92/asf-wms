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


def _render_text(template_text: str, context: dict[str, object]) -> str:
    if not template_text:
        return ""
    return Template(template_text).render(Context(context)).strip()


def _build_assignment_context(version: PlanningVersion, assignment) -> dict[str, object]:
    shipment_reference = (
        assignment.shipment_snapshot.shipment_reference if assignment.shipment_snapshot_id else ""
    )
    volunteer = (
        assignment.volunteer_snapshot.volunteer_label if assignment.volunteer_snapshot_id else ""
    )
    flight = assignment.flight_snapshot.flight_number if assignment.flight_snapshot_id else ""
    return {
        "version_number": version.number,
        "week_start": version.run.week_start,
        "week_end": version.run.week_end,
        "shipment_reference": shipment_reference,
        "volunteer": volunteer,
        "flight": flight,
        "cartons": assignment.assigned_carton_count,
        "notes": assignment.notes,
    }


def generate_version_drafts(version: PlanningVersion) -> list[CommunicationDraft]:
    if version.status != PlanningVersionStatus.PUBLISHED:
        raise ValidationError("Communication drafts can only be generated for published versions.")

    CommunicationDraft.objects.filter(version=version).delete()
    templates = list(CommunicationTemplate.objects.filter(is_active=True).order_by("id"))
    assignments = version.assignments.select_related(
        "shipment_snapshot",
        "volunteer_snapshot",
        "flight_snapshot",
    ).order_by("sequence", "id")

    generated_drafts: list[CommunicationDraft] = []
    for assignment in assignments:
        context = _build_assignment_context(version, assignment)
        if templates:
            for template in templates:
                generated_drafts.append(
                    CommunicationDraft(
                        version=version,
                        template=template,
                        channel=template.channel,
                        recipient_label=str(context["volunteer"]),
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
                recipient_label=str(context["volunteer"]),
                recipient_contact="",
                subject=f"Planning v{version.number} pour {context['volunteer']}",
                body=(
                    f"Vol {context['flight']} pour {context['shipment_reference']} "
                    f"({context['cartons']} colis)."
                ),
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
