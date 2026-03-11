from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta

from wms.models import PlanningVersion
from wms.planning.rules import (
    compile_run_solver_payload,
    shipment_is_compatible_with_flight,
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
    base_compatible = shipment_is_compatible_with_flight(shipment, flight)
    remaining_capacity = _remaining_capacity(
        context,
        flight_snapshot_id=int(flight["snapshot_id"]),
        ignore_assignment_id=ignore_assignment_id,
    )
    remaining_ok = remaining_capacity is None or remaining_capacity >= int(
        shipment.get("equivalent_units") or 0
    )
    if not base_compatible or not remaining_ok:
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
        for flight in flights:
            tones_by_flight[str(flight["snapshot_id"])] = _volunteer_tone_for_flight(
                context,
                volunteer=volunteer,
                flight=flight,
                ignore_assignment_id=ignore_assignment_id,
            )
        tone = tones_by_flight.get(selected_flight_id, "none") if selected_flight else "none"
        options.append(
            {
                "value": str(volunteer["snapshot_id"]),
                "label": volunteer.get("label") or "",
                "tone": tone,
                "option_style": _option_style(tone),
                "tones_by_flight": tones_by_flight,
                "selected": int(volunteer["snapshot_id"]) == int(selected_volunteer_id or 0),
            }
        )
    options.sort(key=lambda item: item["label"].lower())
    return options


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
    selected_flight_option = (
        next(
            (item for item in flight_options if item["tone"] == "green"),
            None,
        )
        or next((item for item in flight_options if item["tone"] == "orange"), None)
        or (flight_options[0] if flight_options else None)
    )
    selected_flight = (
        context["flights"][int(selected_flight_option["value"])] if selected_flight_option else None
    )
    return {
        "flight_options": flight_options,
        "selected_flight_id": selected_flight_option["value"] if selected_flight_option else "",
        "volunteer_options": _build_volunteer_options(
            context,
            selected_flight=selected_flight,
            selected_volunteer_id=None,
        ),
    }
