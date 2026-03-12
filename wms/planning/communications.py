from __future__ import annotations

import re
from datetime import date

from django.core.exceptions import ValidationError
from django.template import Context, Template

from wms.models import (
    CommunicationDraft,
    CommunicationTemplate,
    PlanningVersion,
    PlanningVersionStatus,
)
from wms.planning.communication_plan import build_version_communication_plan
from wms.planning.legacy_communications import (
    DEFAULT_BODY_AIRFRANCE,
    DEFAULT_BODY_ASF,
    DEFAULT_BODY_DEST,
    DEFAULT_BODY_EXPEDITEUR,
    CommunicationFamily,
    LegacyCommRow,
    build_comm_table_html,
    build_subject_airfrance,
    build_subject_asf,
    build_subject_destination,
    build_subject_expediteur,
    build_whatsapp_message,
    family_order_key,
)


def _render_text(template_text: str, context: dict[str, object]) -> str:
    if not template_text:
        return ""
    return Template(template_text).render(Context(context)).strip()


def _rows_for_plan_item(plan_item) -> list[LegacyCommRow]:
    assignments = plan_item.current_assignments or plan_item.previous_assignments
    rows = [
        LegacyCommRow(
            flight_date=assignment.departure_date,
            destination_city=assignment.destination_city,
            destination_iata=assignment.destination_iata,
            flight_number=assignment.flight_number,
            departure_time=assignment.departure_time,
            shipment_reference=assignment.shipment_reference,
            cartons=assignment.cartons,
            shipment_type=assignment.shipment_type,
            shipper_name=assignment.shipper_name,
            recipient_name=assignment.recipient_name,
            volunteer_label=assignment.volunteer_label,
            volunteer_first_name=assignment.volunteer_first_name,
            volunteer_phone=assignment.volunteer_phone,
            correspondent_label=assignment.correspondent_label,
            correspondent_contact=assignment.correspondent_contact_details,
            shipper_contact=assignment.shipper_contact,
            recipient_contact=assignment.recipient_contact,
        )
        for assignment in assignments
    ]
    rows.sort(
        key=lambda row: (
            row.flight_date,
            row.destination_city,
            row.flight_number,
            row.departure_time,
            row.shipment_reference,
        )
    )
    return rows


def _coerce_date(value):
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    return date.fromisoformat(text)


def _run_week(version: PlanningVersion) -> tuple[int, int]:
    week_start = _coerce_date(version.run.week_start)
    if week_start is None:
        return (0, 0)
    return (week_start.isocalendar().week, week_start.year)


def _default_subject(version: PlanningVersion, plan_item) -> str:
    week, year = _run_week(version)
    rows = _rows_for_plan_item(plan_item)
    if plan_item.family == CommunicationFamily.WHATSAPP_BENEVOLE:
        return ""
    if plan_item.family == CommunicationFamily.EMAIL_ASF:
        return build_subject_asf(week=week, year=year)
    if plan_item.family == CommunicationFamily.EMAIL_AIRFRANCE:
        return build_subject_airfrance(week=week)
    if not rows:
        return ""
    if plan_item.family == CommunicationFamily.EMAIL_CORRESPONDANT:
        return build_subject_destination(destination_city=rows[0].destination_city, week=week)
    if plan_item.family == CommunicationFamily.EMAIL_EXPEDITEUR:
        return build_subject_expediteur(
            party_name=plan_item.recipient_label,
            destination_city=rows[0].destination_city,
            week=week,
        )
    if plan_item.family == CommunicationFamily.EMAIL_DESTINATAIRE:
        return build_subject_expediteur(
            party_name=plan_item.recipient_label,
            destination_city=rows[0].destination_city,
            week=week,
        )
    return ""


def _default_body(version: PlanningVersion, plan_item) -> str:
    week, _ = _run_week(version)
    rows = _rows_for_plan_item(plan_item)
    if plan_item.family == CommunicationFamily.WHATSAPP_BENEVOLE:
        return build_whatsapp_message(rows=rows)
    if plan_item.family == CommunicationFamily.EMAIL_ASF:
        return DEFAULT_BODY_ASF.format(week=week)
    if plan_item.family == CommunicationFamily.EMAIL_AIRFRANCE:
        return DEFAULT_BODY_AIRFRANCE.format(week=week)
    if not rows:
        return ""

    table_html = build_comm_table_html(rows)
    if plan_item.family == CommunicationFamily.EMAIL_CORRESPONDANT:
        return DEFAULT_BODY_DEST.format(
            destination=rows[0].destination_city,
            table_html=table_html,
        )
    if plan_item.family in {
        CommunicationFamily.EMAIL_EXPEDITEUR,
        CommunicationFamily.EMAIL_DESTINATAIRE,
    }:
        return DEFAULT_BODY_EXPEDITEUR.format(
            table_html=table_html,
            coord_correspondant=rows[0].correspondent_contact,
        )
    return ""


def _template_for_family(plan_item) -> CommunicationTemplate | None:
    return (
        CommunicationTemplate.objects.filter(
            is_active=True,
            scope=plan_item.family,
            channel=plan_item.channel,
        )
        .order_by("id")
        .first()
    )


def _build_plan_item_context(version: PlanningVersion, plan_item) -> dict[str, object]:
    rows = _rows_for_plan_item(plan_item)
    primary = rows[0] if rows else None
    week, year = _run_week(version)
    return {
        "version_number": version.number,
        "week": week,
        "year": year,
        "recipient_label": plan_item.recipient_label,
        "recipient_contact": plan_item.recipient_contact,
        "destination": primary.destination_city if primary else "",
        "correspondent_contact": primary.correspondent_contact if primary else "",
        "table_html": build_comm_table_html(rows),
        "rows": rows,
    }


def _subject_with_version_suffix(subject: str, version: PlanningVersion, *, channel: str) -> str:
    if channel != "email":
        return subject
    normalized = str(subject or "").strip()
    if not normalized:
        return ""
    suffix = f"v{version.number}"
    if re.search(rf"(?:^|\s){re.escape(suffix)}$", normalized):
        return normalized
    return f"{normalized} {suffix}"


def generate_version_drafts(version: PlanningVersion) -> list[CommunicationDraft]:
    if version.status != PlanningVersionStatus.PUBLISHED:
        raise ValidationError("Communication drafts can only be generated for published versions.")

    CommunicationDraft.objects.filter(version=version).delete()
    plan = build_version_communication_plan(version)
    generated_drafts: list[CommunicationDraft] = []

    for plan_item in plan.items:
        template = _template_for_family(plan_item)
        if template is not None:
            context = _build_plan_item_context(version, plan_item)
            subject = _render_text(template.subject, context)
            body = _render_text(template.body, context)
        else:
            subject = _default_subject(version, plan_item)
            body = _default_body(version, plan_item)
        subject = _subject_with_version_suffix(subject, version, channel=plan_item.channel)
        generated_drafts.append(
            CommunicationDraft(
                version=version,
                template=template,
                channel=plan_item.channel,
                family=plan_item.family,
                recipient_label=plan_item.recipient_label,
                recipient_contact=plan_item.recipient_contact,
                subject=subject,
                body=body,
            )
        )

    if generated_drafts:
        CommunicationDraft.objects.bulk_create(generated_drafts)
    return list(
        CommunicationDraft.objects.filter(version=version).order_by(
            "family",
            "channel",
            "recipient_label",
            "id",
        )
    )
