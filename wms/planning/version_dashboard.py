from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, timedelta

from django.utils import timezone

from wms.models import CommunicationDraft, PlanningVersion
from wms.planning.communication_plan import (
    CHANGE_STATUS_PRIORITY,
    build_version_communication_plan,
)
from wms.planning.legacy_communications import family_label, family_order_key
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

SHORT_DAY_NAMES = (
    "Lun",
    "Mar",
    "Mer",
    "Jeu",
    "Ven",
    "Sam",
    "Dim",
)

SHIPMENT_STATUS_PLANNED = "Planifié"
SHIPMENT_STATUS_NOT_DEPARTING = "Non partant"


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


def _format_ratio_label(numerator: int, denominator: int) -> str:
    return f"{numerator} / {denominator}"


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


def _build_week_dates(version: PlanningVersion) -> list[date]:
    start = _coerce_date(version.run.week_start)
    end = _coerce_date(version.run.week_end)
    if start is None:
        return []
    if end is None or end < start:
        end = start + timedelta(days=6)
    dates = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def _build_week_day_labels(week_dates: list[date]) -> list[dict[str, str]]:
    return [
        {
            "iso_date": value.isoformat(),
            "short_label": f"{SHORT_DAY_NAMES[value.weekday()]} {value.strftime('%d/%m')}",
            "long_label": _format_flight_date(value),
        }
        for value in week_dates
    ]


def _normalize_time_label(value: str) -> str:
    return _format_flight_time(value)


def _build_slot_map(volunteer_snapshot) -> dict[date, list[tuple[str, str]]]:
    slot_map: dict[date, list[tuple[str, str]]] = defaultdict(list)
    summary = volunteer_snapshot.availability_summary or {}
    for slot in summary.get("slots", []):
        slot_date = _coerce_date(slot.get("date"))
        if slot_date is None:
            continue
        start_time = _normalize_time_label(str(slot.get("start_time", "")).strip())
        end_time = _normalize_time_label(str(slot.get("end_time", "")).strip())
        if not start_time and not end_time:
            continue
        slot_map[slot_date].append((start_time, end_time))
    for value in slot_map.values():
        value.sort()
    return slot_map


def _format_slot_range(start_time: str, end_time: str) -> str:
    if start_time and end_time:
        return f"{start_time}-{end_time}"
    return start_time or end_time


def _build_week_view(version: PlanningVersion) -> dict[str, object]:
    week_dates = _build_week_dates(version)
    day_labels = _build_week_day_labels(week_dates)
    assignments = list(
        version.assignments.select_related(
            "flight_snapshot",
            "shipment_snapshot",
            "volunteer_snapshot",
        )
    )
    used_flight_ids = {
        assignment.flight_snapshot_id for assignment in assignments if assignment.flight_snapshot_id
    }

    volunteer_rows = []
    for volunteer_snapshot in version.run.volunteer_snapshots.all().order_by(
        "volunteer_label", "id"
    ):
        slot_map = _build_slot_map(volunteer_snapshot)
        availability_count = len(slot_map)
        cells = []
        for day in week_dates:
            day_slots = slot_map.get(day, [])
            if day_slots:
                cells.append(
                    {
                        "label": " / ".join(
                            _format_slot_range(start_time, end_time)
                            for start_time, end_time in day_slots
                        ),
                        "status": "available",
                    }
                )
            else:
                cells.append({"label": "", "status": "none"})
        volunteer_rows.append(
            {
                "volunteer_label": volunteer_snapshot.volunteer_label,
                "display_label": (
                    f"{volunteer_snapshot.volunteer_label} ({availability_count})"
                    if volunteer_snapshot.volunteer_label
                    else f"- ({availability_count})"
                ),
                "availability_count": availability_count,
                "cells": cells,
            }
        )

    destination_totals: dict[str, int] = defaultdict(int)
    for snapshot in version.run.shipment_snapshots.all():
        destination_totals[snapshot.destination_iata or "-"] += snapshot.carton_count

    flight_rows_by_destination: dict[str, dict[str, object]] = {}
    for flight_snapshot in version.run.flight_snapshots.all().order_by(
        "destination_iata",
        "departure_date",
        "flight_number",
        "id",
    ):
        destination = flight_snapshot.destination_iata or "-"
        row = flight_rows_by_destination.get(destination)
        if row is None:
            row = {
                "destination_iata": destination,
                "destination_label": f"{destination} ({destination_totals.get(destination, 0)})",
                "cells": [{"entries": [], "status": "none"} for _ in week_dates],
            }
            flight_rows_by_destination[destination] = row
        try:
            day_index = week_dates.index(flight_snapshot.departure_date)
        except ValueError:
            continue
        flight_label = " · ".join(
            part
            for part in [
                _format_flight_time((flight_snapshot.payload or {}).get("departure_time", "")),
                _format_flight_number(flight_snapshot.flight_number),
                (flight_snapshot.payload or {}).get("routing", ""),
            ]
            if part
        )
        entry_status = "used" if flight_snapshot.pk in used_flight_ids else "available"
        row["cells"][day_index]["entries"].append(
            {
                "label": flight_label or _format_flight_number(flight_snapshot.flight_number),
                "status": entry_status,
            }
        )
        row["cells"][day_index]["status"] = "used" if entry_status == "used" else "available"

    return {
        "day_labels": day_labels,
        "volunteer_rows": volunteer_rows,
        "flight_rows": list(flight_rows_by_destination.values()),
    }


def _build_availability_label(volunteer_snapshot) -> tuple[int, str]:
    slot_map = _build_slot_map(volunteer_snapshot)
    labels = []
    for slot_date in sorted(slot_map):
        for start_time, end_time in slot_map[slot_date]:
            labels.append(
                f"{slot_date.strftime('%d/%m/%y')} {_format_slot_range(start_time, end_time)}"
            )
    return len(slot_map), ", ".join(labels)


def _build_planning_summary(version: PlanningVersion) -> dict[str, object]:
    assignments = list(
        version.assignments.select_related(
            "volunteer_snapshot",
            "flight_snapshot",
            "shipment_snapshot",
        )
    )
    assignments_by_volunteer: dict[int, list[object]] = defaultdict(list)
    assignment_by_shipment: dict[int, object] = {}
    for assignment in assignments:
        if assignment.volunteer_snapshot_id:
            assignments_by_volunteer[assignment.volunteer_snapshot_id].append(assignment)
        if (
            assignment.shipment_snapshot_id
            and assignment.shipment_snapshot_id not in assignment_by_shipment
        ):
            assignment_by_shipment[assignment.shipment_snapshot_id] = assignment

    volunteer_rows = []
    for volunteer_snapshot in version.run.volunteer_snapshots.all().order_by(
        "volunteer_label", "id"
    ):
        volunteer_assignments = assignments_by_volunteer.get(volunteer_snapshot.pk, [])
        availability_count, availability_label = _build_availability_label(volunteer_snapshot)
        assigned_day_count = len(
            {
                assignment.flight_snapshot.departure_date
                for assignment in volunteer_assignments
                if assignment.flight_snapshot_id and assignment.flight_snapshot is not None
            }
        )
        assigned_flight_count = len(
            {
                assignment.flight_snapshot_id
                for assignment in volunteer_assignments
                if assignment.flight_snapshot_id
            }
        )
        assigned_shipment_count = len(
            {
                assignment.shipment_snapshot_id
                for assignment in volunteer_assignments
                if assignment.shipment_snapshot_id
            }
        )
        assigned_carton_count = sum(
            assignment.assigned_carton_count for assignment in volunteer_assignments
        )
        assigned_equivalent_units = sum(
            assignment.shipment_snapshot.equivalent_units
            for assignment in volunteer_assignments
            if assignment.shipment_snapshot_id and assignment.shipment_snapshot is not None
        )
        volunteer_rows.append(
            {
                "volunteer_label": volunteer_snapshot.volunteer_label or "-",
                "availability_count": availability_count,
                "assigned_day_count": assigned_day_count,
                "assigned_flight_count": assigned_flight_count,
                "assigned_shipment_count": assigned_shipment_count,
                "assigned_carton_count": assigned_carton_count,
                "assigned_equivalent_units": assigned_equivalent_units,
                "availability_label": availability_label,
            }
        )

    grouped_shipments: dict[str, dict[str, object]] = {}
    shipment_snapshots = version.run.shipment_snapshots.all().order_by(
        "destination_iata",
        "priority",
        "shipment_reference",
        "id",
    )
    for snapshot in shipment_snapshots:
        destination = snapshot.destination_iata or "-"
        group = grouped_shipments.get(destination)
        if group is None:
            group = {
                "destination_iata": destination,
                "planned_count": 0,
                "total_count": 0,
                "planned_carton_count": 0,
                "total_carton_count": 0,
                "planned_equivalent_units": 0,
                "total_equivalent_units": 0,
                "shipment_rows": [],
            }
            grouped_shipments[destination] = group

        assignment = assignment_by_shipment.get(snapshot.pk)
        is_planned = assignment is not None
        status_label = SHIPMENT_STATUS_PLANNED if is_planned else SHIPMENT_STATUS_NOT_DEPARTING
        shipment_payload = snapshot.payload or {}
        shipment_row = {
            "destination_iata": destination,
            "shipment_reference": snapshot.shipment_reference or "-",
            "status_label": status_label,
            "carton_count": snapshot.carton_count,
            "equivalent_units": snapshot.equivalent_units,
            "shipment_type": shipment_payload.get("legacy_type", ""),
            "shipper_name": snapshot.shipper_name or "",
            "recipient_label": shipment_payload.get("legacy_destinataire", ""),
            "is_planned": is_planned,
        }
        group["shipment_rows"].append(shipment_row)
        group["total_count"] += 1
        group["total_carton_count"] += snapshot.carton_count
        group["total_equivalent_units"] += snapshot.equivalent_units
        if is_planned:
            group["planned_count"] += 1
            group["planned_carton_count"] += snapshot.carton_count
            group["planned_equivalent_units"] += snapshot.equivalent_units

    destination_groups = []
    for destination in sorted(grouped_shipments):
        group = grouped_shipments[destination]
        group["shipment_rows"].sort(
            key=lambda item: (
                item["shipment_reference"],
                item["shipper_name"],
                item["recipient_label"],
            )
        )
        group["summary_row"] = {
            "destination_iata": destination,
            "shipment_reference": _format_ratio_label(group["planned_count"], group["total_count"]),
            "status_label": _format_ratio_label(group["planned_count"], group["total_count"]),
            "carton_count_label": _format_ratio_label(
                group["planned_carton_count"], group["total_carton_count"]
            ),
            "equivalent_units_label": _format_ratio_label(
                group["planned_equivalent_units"], group["total_equivalent_units"]
            ),
            "shipment_type": "",
            "shipper_name": "",
            "recipient_label": "",
        }
        destination_groups.append(group)

    return {
        "volunteer_rows": volunteer_rows,
        "destination_groups": destination_groups,
    }


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
                "shipment_type": (snapshot.payload or {}).get("legacy_type", ""),
                "recipient_label": (snapshot.payload or {}).get("legacy_destinataire", ""),
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
        "family": draft.family,
        "subject": draft.subject,
        "body": draft.body,
        "status": draft.status,
        "template_label": draft.template.label if draft.template_id else "",
        "recipient_label": draft.recipient_label,
        "recipient_contact": draft.recipient_contact,
    }


def _channel_label(channel: str) -> str:
    field = CommunicationDraft._meta.get_field("channel")
    return dict(field.choices).get(channel, channel)


def _build_communications(version: PlanningVersion) -> dict[str, object]:
    plan = build_version_communication_plan(version)
    plan_items_by_key = {
        (item.family, item.recipient_label, item.recipient_contact): item for item in plan.items
    }
    drafts_by_key: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for draft in version.communication_drafts.select_related("template").order_by(
        "family",
        "channel",
        "recipient_label",
        "id",
    ):
        plan_item = plan_items_by_key.get(
            (draft.family or "", draft.recipient_label or "", draft.recipient_contact or "")
        )
        payload = _draft_payload(draft)
        if plan_item is not None:
            payload.update(
                {
                    "change_status": plan_item.change_status,
                    "change_status_label": COMMUNICATION_CHANGE_LABELS.get(
                        plan_item.change_status,
                        plan_item.change_status,
                    ),
                    "change_summary": plan_item.change_summary,
                }
            )
        else:
            payload.update(
                {
                    "change_status": "unchanged",
                    "change_status_label": COMMUNICATION_CHANGE_LABELS["unchanged"],
                    "change_summary": "Aucun changement",
                }
            )
        drafts_by_key[(draft.family or "", draft.channel, draft.recipient_label or "")].append(
            payload
        )

    groups_by_family: dict[str, dict[str, object]] = {}
    for item in plan.items:
        group = groups_by_family.get(item.family)
        if group is None:
            group = {
                "family_key": item.family,
                "family_label": item.family_label,
                "channel": item.channel,
                "channel_label": _channel_label(item.channel),
                "change_status": item.change_status,
                "change_status_label": COMMUNICATION_CHANGE_LABELS.get(
                    item.change_status,
                    item.change_status,
                ),
                "change_summary": item.change_summary,
                "changed_since_parent": item.change_status != "unchanged",
                "is_priority": item.change_status != "unchanged",
                "is_collapsed": item.change_status == "unchanged",
                "drafts": [],
            }
            groups_by_family[item.family] = group
        elif CHANGE_STATUS_PRIORITY.get(item.change_status, 99) < CHANGE_STATUS_PRIORITY.get(
            group["change_status"], 99
        ):
            group["change_status"] = item.change_status
            group["change_status_label"] = COMMUNICATION_CHANGE_LABELS.get(
                item.change_status,
                item.change_status,
            )
            group["change_summary"] = item.change_summary
            group["changed_since_parent"] = item.change_status != "unchanged"
            group["is_priority"] = item.change_status != "unchanged"
            group["is_collapsed"] = item.change_status == "unchanged"

        key = (item.family, item.channel, item.recipient_label)
        family_drafts = drafts_by_key.pop(key, [])
        if family_drafts:
            group["drafts"].extend(family_drafts)
        else:
            group["drafts"].append(
                {
                    "draft_id": None,
                    "family": item.family,
                    "recipient_label": item.recipient_label,
                    "recipient_contact": item.recipient_contact,
                    "subject": "",
                    "body": "",
                    "status": "generated",
                    "template_label": "",
                    "change_status": item.change_status,
                    "change_status_label": COMMUNICATION_CHANGE_LABELS.get(
                        item.change_status,
                        item.change_status,
                    ),
                    "change_summary": item.change_summary,
                }
            )

    for (family, channel, recipient_label), drafts in drafts_by_key.items():
        group = groups_by_family.setdefault(
            family,
            {
                "family_key": family,
                "family_label": family_label(family) if family else _channel_label(channel),
                "channel": channel,
                "channel_label": _channel_label(channel),
                "change_status": "unchanged",
                "change_status_label": COMMUNICATION_CHANGE_LABELS["unchanged"],
                "change_summary": "Aucun changement",
                "changed_since_parent": False,
                "is_priority": False,
                "is_collapsed": True,
                "drafts": [],
            },
        )
        group["drafts"].extend(drafts)

    groups = list(groups_by_family.values())
    for group in groups:
        group["drafts"].sort(
            key=lambda draft: (
                (draft.get("recipient_label") or "").lower(),
                draft.get("subject") or "",
            )
        )
    groups.sort(key=lambda item: family_order_key(item["family_key"]))
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
        "week_view": _build_week_view(version),
        "planning_summary": _build_planning_summary(version),
        "planning_rows": _build_planning_rows(version),
        "flight_groups": _build_flight_groups(version),
        "unassigned_shipments": _build_unassigned_shipments(version),
        "communications": _build_communications(version),
        "stats": stats,
        "exports": _build_exports(version),
        "history": history,
    }
