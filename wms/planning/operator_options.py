from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta

from wms.models import PlanningVersion
from wms.planning.rules import (
    compile_run_solver_payload,
    volunteer_is_compatible_with_flight,
)
from wms.planning.version_dashboard import (
    _format_flight_date,
    _format_flight_number,
    _format_flight_time,
)

CONFLICT_MARGIN_MINUTES = 150

TONE_STYLE = {
    "green": "background-color: #e6f6ea;",
    "orange": "background-color: #fff1db;",
    "red": "background-color: #f8d7da;",
    "none": "",
}

FLIGHT_REASON_LABELS = {
    "destination_mismatch": "Destination non compatible",
    "weekday_not_allowed": "Jour non autorise par ParamDest",
    "max_cartons_per_flight": "Limite colis destination depassee",
    "flight_capacity_insufficient": "Capacite du vol insuffisante",
    "remaining_capacity_insufficient": "Capacite restante insuffisante",
}

VOLUNTEER_REASON_LABELS = {
    "unavailable": "Benevole indisponible",
    "conflict": "Conflit horaire (marge 2h30)",
}


def build_operator_option_context(version: PlanningVersion) -> dict[str, object]:
    payload = compile_run_solver_payload(version.run)
    assignments = list(
        version.assignments.select_related(
            "shipment_snapshot",
            "volunteer_snapshot",
            "flight_snapshot",
        ).order_by("sequence", "id")
    )
    return {
        "payload": payload,
        "shipments": {int(item["snapshot_id"]): item for item in payload.get("shipments", [])},
        "volunteers": {int(item["snapshot_id"]): item for item in payload.get("volunteers", [])},
        "flights": {int(item["snapshot_id"]): item for item in payload.get("flights", [])},
        "assignments": assignments,
    }


def _option_style(tone: str) -> str:
    return TONE_STYLE.get(tone, "")


def _normalize_iata(value: str) -> str:
    return str(value or "").strip().upper()


def _normalize_flight_number(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").strip().upper())


def _flight_sort_key(flight: dict) -> tuple[str, str, str]:
    return (
        str(flight.get("departure_date") or ""),
        str(flight.get("departure_time") or ""),
        str(flight.get("flight_number") or ""),
    )


def _flight_departure_dt(flight: dict) -> datetime | None:
    departure_date = str(flight.get("departure_date") or "").strip()
    departure_time = str(flight.get("departure_time") or "").strip()
    if not departure_date or not departure_time:
        return None
    try:
        return datetime.fromisoformat(f"{departure_date}T{departure_time}")
    except ValueError:
        return None


def _flight_physical_key(flight: dict) -> str:
    return "{date}|{time}|{number}".format(
        date=str(flight.get("departure_date") or ""),
        time=str(flight.get("departure_time") or ""),
        number=_normalize_flight_number(flight.get("flight_number") or ""),
    )


def _assignments_for_flight(context: dict[str, object], *, flight_snapshot_id: int) -> list:
    return [
        assignment
        for assignment in context["assignments"]
        if assignment.flight_snapshot_id == flight_snapshot_id
    ]


def _remaining_capacity(
    context: dict[str, object],
    *,
    flight_snapshot_id: int,
    ignore_assignment_id: int | None = None,
) -> int | None:
    flight = context["flights"][int(flight_snapshot_id)]
    capacity = flight.get("capacity_units")
    if capacity is None:
        return None
    used_equivalent_units = 0
    for assignment in _assignments_for_flight(context, flight_snapshot_id=int(flight_snapshot_id)):
        if ignore_assignment_id is not None and assignment.pk == ignore_assignment_id:
            continue
        if assignment.shipment_snapshot_id:
            used_equivalent_units += assignment.shipment_snapshot.equivalent_units
    return int(capacity) - int(used_equivalent_units)


def explain_flight_rejection(
    context: dict[str, object],
    *,
    shipment: dict,
    flight: dict,
    ignore_assignment_id: int | None = None,
) -> str | None:
    if _normalize_iata(flight.get("destination_iata")) != _normalize_iata(
        shipment.get("destination_iata")
    ):
        return "destination_mismatch"

    allowed_weekdays = [
        str(value or "").strip().lower() for value in flight.get("allowed_weekdays") or []
    ]
    if allowed_weekdays:
        departure_date = str(flight.get("departure_date") or "").strip()
        if departure_date:
            weekday_code = datetime.fromisoformat(departure_date).strftime("%a").lower()[:3]
            if weekday_code not in allowed_weekdays:
                return "weekday_not_allowed"

    shipment_carton_count = int(shipment.get("carton_count") or 0)
    max_cartons_per_flight = flight.get("max_cartons_per_flight")
    if max_cartons_per_flight is not None and shipment_carton_count > int(max_cartons_per_flight):
        return "max_cartons_per_flight"

    shipment_equivalent_units = int(shipment.get("equivalent_units") or 0)
    capacity_units = flight.get("capacity_units")
    if capacity_units is not None and shipment_equivalent_units > int(capacity_units):
        return "flight_capacity_insufficient"

    remaining_capacity = _remaining_capacity(
        context,
        flight_snapshot_id=int(flight["snapshot_id"]),
        ignore_assignment_id=ignore_assignment_id,
    )
    if remaining_capacity is not None and remaining_capacity < shipment_equivalent_units:
        return "remaining_capacity_insufficient"

    return None


def _flight_tone_for_shipment(
    context: dict[str, object],
    *,
    shipment: dict,
    flight: dict,
    ignore_assignment_id: int | None = None,
) -> str | None:
    if _normalize_iata(flight.get("destination_iata")) != _normalize_iata(
        shipment.get("destination_iata")
    ):
        return None
    if explain_flight_rejection(
        context,
        shipment=shipment,
        flight=flight,
        ignore_assignment_id=ignore_assignment_id,
    ):
        return "red"
    if _assignments_for_flight(context, flight_snapshot_id=int(flight["snapshot_id"])):
        return "orange"
    return "green"


def _has_availability_info(volunteer: dict) -> bool:
    availability = volunteer.get("availability_summary") or {}
    return bool((availability.get("slots") or []) or (availability.get("unavailable_dates") or []))


def _volunteer_has_conflict(
    context: dict[str, object],
    *,
    volunteer_snapshot_id: int,
    flight: dict,
    ignore_assignment_id: int | None = None,
) -> bool:
    candidate_dt = _flight_departure_dt(flight)
    if candidate_dt is None:
        return False
    candidate_key = _flight_physical_key(flight)
    for assignment in context["assignments"]:
        if assignment.volunteer_snapshot_id != volunteer_snapshot_id:
            continue
        if ignore_assignment_id is not None and assignment.pk == ignore_assignment_id:
            continue
        other_flight = context["flights"].get(int(assignment.flight_snapshot_id or 0))
        if not other_flight:
            continue
        if _flight_physical_key(other_flight) == candidate_key:
            continue
        other_dt = _flight_departure_dt(other_flight)
        if other_dt is None:
            continue
        if abs(candidate_dt - other_dt) < timedelta(minutes=CONFLICT_MARGIN_MINUTES):
            return True
    return False


def _volunteer_tone_for_flight(
    context: dict[str, object],
    *,
    volunteer: dict,
    flight: dict,
    ignore_assignment_id: int | None = None,
) -> str:
    if not _has_availability_info(volunteer):
        return "none"
    if not volunteer_is_compatible_with_flight(volunteer, flight):
        return "red"
    if _volunteer_has_conflict(
        context,
        volunteer_snapshot_id=int(volunteer["snapshot_id"]),
        flight=flight,
        ignore_assignment_id=ignore_assignment_id,
    ):
        return "orange"
    return "green"


def explain_volunteer_rejection(
    context: dict[str, object],
    *,
    volunteer: dict,
    flight: dict,
    ignore_assignment_id: int | None = None,
) -> str | None:
    if not _has_availability_info(volunteer):
        return None
    if not volunteer_is_compatible_with_flight(volunteer, flight):
        return "unavailable"
    if _volunteer_has_conflict(
        context,
        volunteer_snapshot_id=int(volunteer["snapshot_id"]),
        flight=flight,
        ignore_assignment_id=ignore_assignment_id,
    ):
        return "conflict"
    return None


def _build_date_options(*, flights: list[dict], selected_date: str) -> list[dict[str, object]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for flight in flights:
        grouped[str(flight["date_value"])].append(flight)
    tone_priority = {"green": 3, "orange": 2, "red": 1}
    options = []
    for date_value in sorted(grouped):
        flights_for_date = grouped[date_value]
        tone = max(
            flights_for_date,
            key=lambda item: tone_priority.get(item["tone"], 0),
        )["tone"]
        options.append(
            {
                "value": date_value,
                "label": flights_for_date[0]["date_label"],
                "tone": tone,
                "option_style": _option_style(tone),
                "selected": date_value == selected_date,
            }
        )
    return options


def _build_flight_options(
    context: dict[str, object],
    *,
    shipment: dict,
    selected_flight_id: int | None,
    ignore_assignment_id: int | None = None,
) -> list[dict[str, object]]:
    options = []
    for flight in sorted(context["flights"].values(), key=_flight_sort_key):
        tone = _flight_tone_for_shipment(
            context,
            shipment=shipment,
            flight=flight,
            ignore_assignment_id=ignore_assignment_id,
        )
        if tone is None:
            continue
        reason_code = explain_flight_rejection(
            context,
            shipment=shipment,
            flight=flight,
            ignore_assignment_id=ignore_assignment_id,
        )
        options.append(
            {
                "value": str(flight["snapshot_id"]),
                "label": "{time} · {number} · {routing}".format(
                    time=_format_flight_time(flight.get("departure_time") or ""),
                    number=_format_flight_number(flight.get("flight_number") or ""),
                    routing=flight.get("routing") or "-",
                ),
                "date_value": str(flight.get("departure_date") or ""),
                "date_label": _format_flight_date(flight.get("departure_date")),
                "tone": tone,
                "reason_code": reason_code or "",
                "reason_label": FLIGHT_REASON_LABELS.get(reason_code or "", ""),
                "option_style": _option_style(tone),
                "selected": int(flight["snapshot_id"]) == int(selected_flight_id or 0),
            }
        )
    return options


def _build_volunteer_options(
    context: dict[str, object],
    *,
    selected_flight: dict | None,
    selected_volunteer_id: int | None,
    ignore_assignment_id: int | None = None,
) -> list[dict[str, object]]:
    options = []
    selected_flight_id = str(selected_flight["snapshot_id"]) if selected_flight else ""
    flights = sorted(context["flights"].values(), key=_flight_sort_key)
    for volunteer in context["volunteers"].values():
        tones_by_flight = {}
        reasons_by_flight = {}
        for flight in flights:
            flight_key = str(flight["snapshot_id"])
            tones_by_flight[flight_key] = _volunteer_tone_for_flight(
                context,
                volunteer=volunteer,
                flight=flight,
                ignore_assignment_id=ignore_assignment_id,
            )
            reason_code = explain_volunteer_rejection(
                context,
                volunteer=volunteer,
                flight=flight,
                ignore_assignment_id=ignore_assignment_id,
            )
            reasons_by_flight[flight_key] = reason_code or ""
        tone = tones_by_flight.get(selected_flight_id, "none") if selected_flight else "none"
        options.append(
            {
                "value": str(volunteer["snapshot_id"]),
                "label": volunteer.get("label") or "",
                "tone": tone,
                "option_style": _option_style(tone),
                "tones_by_flight": tones_by_flight,
                "reasons_by_flight": reasons_by_flight,
                "selected": int(volunteer["snapshot_id"]) == int(selected_volunteer_id or 0),
            }
        )
    options.sort(key=lambda item: item["label"].lower())
    return options


def _volunteer_selection_rank(tone: str) -> int:
    if tone == "green":
        return 2
    if tone == "none":
        return 1
    return 0


def _pick_preferred_volunteer_id(
    context: dict[str, object],
    *,
    flight: dict | None,
    ignore_assignment_id: int | None = None,
) -> int | None:
    if flight is None:
        return None
    ranked_candidates: list[tuple[int, str, int]] = []
    for volunteer in context["volunteers"].values():
        tone = _volunteer_tone_for_flight(
            context,
            volunteer=volunteer,
            flight=flight,
            ignore_assignment_id=ignore_assignment_id,
        )
        rank = _volunteer_selection_rank(tone)
        if rank <= 0:
            continue
        ranked_candidates.append(
            (
                rank,
                str(volunteer.get("label") or "").lower(),
                int(volunteer["snapshot_id"]),
            )
        )
    if not ranked_candidates:
        return None
    ranked_candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    return ranked_candidates[0][2]


def _pick_preferred_unassigned_flight_option(
    context: dict[str, object],
    *,
    flight_options: list[dict[str, object]],
) -> tuple[dict[str, object] | None, int | None]:
    selectable_flights = [item for item in flight_options if item["tone"] in {"green", "orange"}]
    for preferred_tone in ("green", "orange"):
        for option in selectable_flights:
            if option["tone"] != preferred_tone:
                continue
            volunteer_id = _pick_preferred_volunteer_id(
                context,
                flight=context["flights"][int(option["value"])],
            )
            if volunteer_id is not None:
                return option, volunteer_id
    if selectable_flights:
        return selectable_flights[0], None
    if flight_options:
        return flight_options[0], None
    return None, None


def build_assignment_editor_options(
    version: PlanningVersion,
    *,
    assignment,
    context: dict[str, object] | None = None,
) -> dict[str, object]:
    context = context or build_operator_option_context(version)
    shipment = context["shipments"][int(assignment.shipment_snapshot_id)]
    selected_flight = context["flights"][int(assignment.flight_snapshot_id)]
    flight_options = _build_flight_options(
        context,
        shipment=shipment,
        selected_flight_id=assignment.flight_snapshot_id,
        ignore_assignment_id=assignment.pk,
    )
    return {
        "selected_date": str(selected_flight.get("departure_date") or ""),
        "date_options": _build_date_options(
            flights=flight_options,
            selected_date=str(selected_flight.get("departure_date") or ""),
        ),
        "flight_options": flight_options,
        "volunteer_options": _build_volunteer_options(
            context,
            selected_flight=selected_flight,
            selected_volunteer_id=assignment.volunteer_snapshot_id,
            ignore_assignment_id=assignment.pk,
        ),
    }


def build_unassigned_editor_options(
    version: PlanningVersion,
    *,
    shipment_snapshot,
    context: dict[str, object] | None = None,
) -> dict[str, object]:
    context = context or build_operator_option_context(version)
    shipment = context["shipments"][int(shipment_snapshot.pk)]
    flight_options = _build_flight_options(
        context,
        shipment=shipment,
        selected_flight_id=None,
    )
    has_assignable_flight = any(item["tone"] in {"green", "orange"} for item in flight_options)
    selected_flight_option, selected_volunteer_id = _pick_preferred_unassigned_flight_option(
        context,
        flight_options=flight_options,
    )
    selected_flight = (
        context["flights"][int(selected_flight_option["value"])] if selected_flight_option else None
    )
    has_assignable_pair = selected_volunteer_id is not None and selected_flight is not None
    return {
        "flight_options": flight_options,
        "selected_flight_id": selected_flight_option["value"] if selected_flight_option else "",
        "has_assignable_flight": has_assignable_flight,
        "has_assignable_pair": has_assignable_pair,
        "blocking_reason": _summarize_unassigned_blocking_reason(
            flight_options,
            has_assignable_pair=has_assignable_pair,
        ),
        "volunteer_options": _build_volunteer_options(
            context,
            selected_flight=selected_flight,
            selected_volunteer_id=selected_volunteer_id,
        ),
    }


def _summarize_unassigned_blocking_reason(
    flight_options: list[dict[str, object]],
    *,
    has_assignable_pair: bool,
) -> str:
    if has_assignable_pair:
        return ""
    if not flight_options:
        return "Aucun vol disponible pour cette destination."
    reason_labels = [
        str(item.get("reason_label") or "").strip()
        for item in flight_options
        if item.get("tone") == "red" and item.get("reason_label")
    ]
    unique_reason_labels = list(dict.fromkeys(label for label in reason_labels if label))
    if len(unique_reason_labels) == 1:
        return f"Aucun vol actuellement assignable: {unique_reason_labels[0].lower()}."
    if unique_reason_labels:
        return "Aucun vol actuellement assignable: plusieurs contraintes bloquent cette expedition."
    return "Aucun couple vol/benevole actuellement assignable pour cette expedition."
