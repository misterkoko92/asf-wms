from __future__ import annotations

import re
from collections import defaultdict
from datetime import date

from django.utils import timezone

from wms.models import CommunicationDraft, PlanningVersion
from wms.planning.communication_plan import (
    CHANGE_STATUS_PRIORITY,
    build_version_communication_plan,
)
from wms.planning.stats import build_version_stats
from wms.planning.versioning import diff_versions

UNASSIGNED_REASON_LABELS = {
    "no_selected_candidate": "Non retenue par l'arbitrage solveur",
    "no_compatible_candidate": "Aucune compatibilite complete",
}

COMMUNICATION_CHANGE_LABELS = {
    "new": "Nouveau",
    "changed": "Modifie",
    "cancelled": "Annule",
    "unchanged": "Inchange",
}

VERSION_STATUS_BADGES = {
    "draft": "Brouillon",
    "published": "Publiee",
    "superseded": "Supplantee",
}

DAY_NAMES = (
    "Lundi",
    "Mardi",
    "Mercredi",
    "Jeudi",
    "Vendredi",
    "Samedi",
    "Dimanche",
)


def _display_datetime(value):
    if not value:
        return ""
    local_value = timezone.localtime(value) if timezone.is_aware(value) else value
    return local_value.strftime("%Y-%m-%d %H:%M")


def _format_short_date(value: date | None) -> str:
    value = _coerce_date(value)
    if value is None:
        return ""
    return value.strftime("%d/%m/%y")


def _format_flight_date(value: date | None) -> str:
    value = _coerce_date(value)
    if value is None:
        return ""
    return f"{DAY_NAMES[value.weekday()]} {value.strftime('%d/%m/%Y')}"


def _coerce_date(value):
    if isinstance(value, date):
        return value
    normalized = str(value or "").strip()
    if not normalized:
        return None
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        return None


def _format_flight_time(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    return normalized.replace(":", "h")


def _format_flight_number(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if not normalized:
        return ""
    match = re.fullmatch(r"([A-Z]+)\s*([0-9]+[A-Z]?)", normalized)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return normalized


def _build_header(version: PlanningVersion, *, stats: dict[str, object]) -> dict[str, object]:
    run = version.run
    week_start = _coerce_date(run.week_start)
    week_end = _coerce_date(run.week_end)
    week_number = week_start.isocalendar().week if week_start else ""
    period_label = f"{_format_short_date(week_start)} au {_format_short_date(week_end)}"
    return {
        "run_label": str(run),
        "week_start": week_start,
        "week_end": week_end,
        "week_number": week_number,
        "period_label": period_label,
        "title": f"Planning Semaine {week_number} (du {period_label})",
        "version_number": version.number,
        "status": version.status,
        "status_label": version.get_status_display(),
        "status_badge": VERSION_STATUS_BADGES.get(version.status, version.get_status_display()),
        "flight_mode": run.flight_mode,
        "parameter_set_name": run.parameter_set.name if run.parameter_set_id else "",
        "created_by": version.created_by.get_username() if version.created_by_id else "",
        "created_at": _display_datetime(version.created_at),
        "published_at": _display_datetime(version.published_at),
        "summary": {
            "flight_mode": run.flight_mode,
            "used_flight_count": stats["flight_count"],
            "available_carton_count": run.shipment_snapshots.count()
            and sum(
                snapshot.carton_count
                for snapshot in run.shipment_snapshots.all().only("carton_count")
            )
            or 0,
            "assigned_carton_count": stats["carton_total"],
            "available_volunteer_count": run.volunteer_snapshots.count(),
            "assigned_volunteer_count": stats["volunteer_count"],
        },
    }


def _assignment_row(assignment) -> dict[str, object]:
    shipment = assignment.shipment_snapshot
    volunteer = assignment.volunteer_snapshot
    flight = assignment.flight_snapshot
    shipment_payload = shipment.payload if shipment else {}
    flight_payload = flight.payload if flight else {}
    return {
        "assignment_id": assignment.pk,
        "flight_date_label": _format_flight_date(flight.departure_date if flight else None),
        "flight_time_label": _format_flight_time((flight_payload or {}).get("departure_time", "")),
        "flight_number_label": _format_flight_number(flight.flight_number if flight else ""),
        "shipment_reference": shipment.shipment_reference if shipment else "",
        "shipper_name": shipment.shipper_name if shipment else "",
        "destination_iata": shipment.destination_iata if shipment else "",
        "routing": flight_payload.get("routing", ""),
        "equivalent_units": shipment.equivalent_units if shipment else 0,
        "volunteer_label": volunteer.volunteer_label if volunteer else "",
        "flight_number": flight.flight_number if flight else "",
        "cartons": assignment.assigned_carton_count,
        "assigned_carton_count": assignment.assigned_carton_count,
        "shipment_type": shipment_payload.get("legacy_type", ""),
        "recipient_label": shipment_payload.get("legacy_destinataire", ""),
        "status": assignment.status,
        "notes": assignment.notes,
        "source": assignment.source,
        "sequence": assignment.sequence,
    }


def _build_flight_groups(version: PlanningVersion) -> list[dict[str, object]]:
    grouped: dict[tuple[int | None, str, str, str], dict[str, object]] = {}
    assignments = version.assignments.select_related(
        "shipment_snapshot",
        "volunteer_snapshot",
        "flight_snapshot",
    ).order_by(
        "flight_snapshot__departure_date",
        "flight_snapshot__flight_number",
        "sequence",
        "id",
    )
    for assignment in assignments:
        flight = assignment.flight_snapshot
        if flight is None:
            continue
        key = (
            flight.pk,
            str(flight.departure_date),
            flight.flight_number,
            flight.destination_iata,
        )
        group = grouped.get(key)
        if group is None:
            group = {
                "flight_snapshot_id": flight.pk,
                "flight_number": flight.flight_number,
                "departure_date": flight.departure_date,
                "departure_time": (flight.payload or {}).get("departure_time", ""),
                "destination_iata": flight.destination_iata,
                "capacity_units": flight.capacity_units,
                "used_cartons": 0,
                "used_equivalent_units": 0,
                "volunteer_labels": [],
                "assignments": [],
            }
            grouped[key] = group
        row = _assignment_row(assignment)
        group["assignments"].append(row)
        group["used_cartons"] += assignment.assigned_carton_count
        if assignment.shipment_snapshot_id:
            group["used_equivalent_units"] += assignment.shipment_snapshot.equivalent_units
        if row["volunteer_label"] and row["volunteer_label"] not in group["volunteer_labels"]:
            group["volunteer_labels"].append(row["volunteer_label"])

    flight_groups = list(grouped.values())
    flight_groups.sort(
        key=lambda item: (
            item["departure_date"],
            item["departure_time"] or "",
            item["flight_number"],
            item["destination_iata"],
        )
    )
    return flight_groups


def _build_planning_rows(version: PlanningVersion) -> list[dict[str, object]]:
    assignments = version.assignments.select_related(
        "shipment_snapshot",
        "volunteer_snapshot",
        "flight_snapshot",
    ).order_by(
        "flight_snapshot__departure_date",
        "flight_snapshot__flight_number",
        "sequence",
        "id",
    )
    rows = [_assignment_row(assignment) for assignment in assignments]
    rows.sort(
        key=lambda item: (
            item["flight_date_label"],
            item["flight_time_label"],
            item["flight_number_label"],
            item["shipment_reference"],
        )
    )
    return rows


def _build_unassigned_shipments(version: PlanningVersion) -> list[dict[str, object]]:
    assigned_ids = {
        shipment_id
        for shipment_id in version.assignments.values_list("shipment_snapshot_id", flat=True)
        if shipment_id
    }
    unassigned_reasons = version.run.solver_result.get("unassigned_reasons", {})
    rows = []
    for snapshot in version.run.shipment_snapshots.exclude(pk__in=assigned_ids).order_by(
        "priority",
        "shipment_reference",
        "id",
    ):
        reason_code = str(unassigned_reasons.get(str(snapshot.pk)) or "").strip()
        rows.append(
            {
                "shipment_snapshot_id": snapshot.pk,
                "shipment_reference": snapshot.shipment_reference,
                "shipper_name": snapshot.shipper_name,
                "destination_iata": snapshot.destination_iata,
                "priority": snapshot.priority,
                "carton_count": snapshot.carton_count,
                "equivalent_units": snapshot.equivalent_units,
                "reason_code": reason_code,
                "reason": UNASSIGNED_REASON_LABELS.get(
                    reason_code,
                    "Non affectee dans cette version",
                ),
            }
        )
    return rows


def _build_history(version: PlanningVersion) -> dict[str, object]:
    versions = [
        {
            "id": item.pk,
            "number": item.number,
            "status": item.status,
            "status_label": item.get_status_display(),
            "is_current": item.pk == version.pk,
            "change_reason": item.change_reason,
            "created_at": _display_datetime(item.created_at),
            "published_at": _display_datetime(item.published_at),
        }
        for item in version.run.versions.all().order_by("number", "id")
    ]
    if version.based_on_id is None:
        return {
            "has_parent": False,
            "based_on_version_number": None,
            "change_reason": version.change_reason,
            "versions": versions,
            "assignment_changes": {
                "changed_count": 0,
                "added_count": 0,
                "removed_count": 0,
                "changed": [],
                "added": [],
                "removed": [],
            },
        }

    comparison = diff_versions(version.based_on, version)
    return {
        "has_parent": True,
        "based_on_version_number": version.based_on.number,
        "change_reason": version.change_reason,
        "versions": versions,
        "assignment_changes": {
            "changed_count": len(comparison["changed"]),
            "added_count": len(comparison["added"]),
            "removed_count": len(comparison["removed"]),
            "changed": comparison["changed"],
            "added": comparison["added"],
            "removed": comparison["removed"],
        },
    }


def _draft_payload(draft) -> dict[str, object]:
    return {
        "draft_id": draft.pk,
        "subject": draft.subject,
        "body": draft.body,
        "status": draft.status,
        "template_label": draft.template.label if draft.template_id else "",
    }


def _build_legacy_draft_group(key, drafts: list[dict[str, object]]) -> dict[str, object]:
    channel, recipient_label = key
    return {
        "channel": channel,
        "channel_label": _channel_label(channel),
        "recipient_label": recipient_label,
        "recipient_contact": "",
        "change_status": "unchanged",
        "change_status_label": COMMUNICATION_CHANGE_LABELS["unchanged"],
        "change_summary": "Aucun changement",
        "changed_since_parent": False,
        "is_priority": False,
        "is_collapsed": True,
        "drafts": drafts,
    }


def _channel_label(channel: str) -> str:
    field = CommunicationDraft._meta.get_field("channel")
    return dict(field.choices).get(channel, channel)


def _build_communications(version: PlanningVersion) -> dict[str, object]:
    drafts_by_key: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for draft in version.communication_drafts.select_related("template").order_by(
        "channel",
        "recipient_label",
        "id",
    ):
        drafts_by_key[(draft.channel, draft.recipient_label or "")].append(_draft_payload(draft))

    plan = build_version_communication_plan(version)
    groups: list[dict[str, object]] = []
    for item in plan.items:
        key = (item.channel, item.recipient_label)
        groups.append(
            {
                "channel": item.channel,
                "channel_label": _channel_label(item.channel),
                "recipient_label": item.recipient_label,
                "recipient_contact": "",
                "change_status": item.change_status,
                "change_status_label": COMMUNICATION_CHANGE_LABELS.get(
                    item.change_status,
                    item.change_status,
                ),
                "change_summary": item.change_summary,
                "changed_since_parent": item.change_status != "unchanged",
                "is_priority": item.change_status != "unchanged",
                "is_collapsed": item.change_status == "unchanged",
                "drafts": drafts_by_key.pop(key, []),
            }
        )

    for key, drafts in drafts_by_key.items():
        groups.append(_build_legacy_draft_group(key, drafts))

    groups.sort(
        key=lambda item: (
            CHANGE_STATUS_PRIORITY.get(item["change_status"], 99),
            item["recipient_label"].lower(),
            item["channel"],
        )
    )
    return {
        "draft_count": sum(len(group["drafts"]) for group in groups),
        "groups": groups,
    }


def _build_exports(version: PlanningVersion) -> dict[str, object]:
    artifacts = [
        {
            "artifact_id": artifact.pk,
            "artifact_type": artifact.artifact_type,
            "label": artifact.label or artifact.artifact_type,
            "file_path": artifact.file_path,
            "generated_at": _display_datetime(artifact.generated_at),
        }
        for artifact in version.artifacts.all().order_by("artifact_type", "id")
    ]
    return {
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }


def build_version_dashboard(version: PlanningVersion) -> dict[str, object]:
    stats = build_version_stats(version)
    history = _build_history(version)
    return {
        "header": _build_header(version, stats=stats),
        "planning_rows": _build_planning_rows(version),
        "flight_groups": _build_flight_groups(version),
        "unassigned_shipments": _build_unassigned_shipments(version),
        "communications": _build_communications(version),
        "stats": stats,
        "exports": _build_exports(version),
        "history": history,
    }
