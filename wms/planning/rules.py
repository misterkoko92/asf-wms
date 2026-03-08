from __future__ import annotations

from datetime import time

from wms.models import PlanningRun
from wms.planning.validation import get_destination_rule_map


def _parse_time_value(value: str | None) -> time | None:
    if not value:
        return None
    parts = str(value).strip().split(":")
    if len(parts) < 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except (TypeError, ValueError):
        return None
    return time(hour=hour, minute=minute)


def _normalize_flight_number(value: str) -> str:
    normalized = "".join(ch for ch in str(value or "").strip().upper() if ch.isalnum())
    return normalized


def _infer_route_pos(*, routing: str, destination_iata: str) -> int:
    parts = [
        part.strip().upper() for part in str(routing or "").replace(",", "-").split("-") if part
    ]
    destination = str(destination_iata or "").strip().upper()
    for index, code in enumerate(parts[1:], start=1):
        if code == destination:
            return index
    return 1


def build_physical_flight_key(flight: dict) -> str:
    normalized_number = _normalize_flight_number(flight.get("flight_number", ""))
    departure_time = flight.get("departure_time") or ""
    return (
        f"{flight.get('departure_date', '')}|{departure_time}|"
        f"{normalized_number or flight.get('snapshot_id')}"
    )


def compile_run_solver_payload(run: PlanningRun) -> dict:
    destination_rule_map = get_destination_rule_map(run)
    destination_rules_by_iata = {}
    for rule in destination_rule_map.values():
        if rule.destination_id and rule.destination and rule.destination.iata_code:
            destination_rules_by_iata[rule.destination.iata_code.upper()] = {
                "priority": rule.priority,
                "weekly_frequency": rule.weekly_frequency,
                "max_cartons_per_flight": rule.max_cartons_per_flight,
            }

    shipments = [
        {
            "snapshot_id": snapshot.pk,
            "reference": snapshot.shipment_reference,
            "destination_iata": snapshot.destination_iata,
            "priority": snapshot.priority,
            "carton_count": snapshot.carton_count,
            "equivalent_units": snapshot.equivalent_units,
            "payload": snapshot.payload,
        }
        for snapshot in run.shipment_snapshots.order_by("-priority", "shipment_reference", "id")
    ]
    volunteers = [
        {
            "snapshot_id": snapshot.pk,
            "label": snapshot.volunteer_label,
            "max_colis_vol": snapshot.max_colis_vol,
            "availability_summary": snapshot.availability_summary,
            "payload": snapshot.payload,
        }
        for snapshot in run.volunteer_snapshots.order_by("volunteer_label", "id")
    ]
    flights = []
    for snapshot in run.flight_snapshots.order_by("departure_date", "flight_number", "id"):
        payload = snapshot.payload or {}
        departure_time = payload.get("departure_time") or ""
        routing = payload.get("routing") or ""
        route_pos = payload.get("route_pos")
        destination_rule = destination_rules_by_iata.get(snapshot.destination_iata.upper(), {})
        if route_pos in (None, ""):
            route_pos = _infer_route_pos(
                routing=routing,
                destination_iata=snapshot.destination_iata,
            )
        flight = {
            "snapshot_id": snapshot.pk,
            "flight_number": snapshot.flight_number,
            "departure_date": snapshot.departure_date.isoformat(),
            "departure_time": departure_time,
            "origin_iata": payload.get("origin_iata") or "",
            "destination_iata": snapshot.destination_iata,
            "routing": routing,
            "route_pos": int(route_pos or 1),
            "physical_flight_key": build_physical_flight_key(
                {
                    "snapshot_id": snapshot.pk,
                    "flight_number": snapshot.flight_number,
                    "departure_date": snapshot.departure_date.isoformat(),
                    "departure_time": departure_time,
                }
            ),
            "capacity_units": snapshot.capacity_units,
            "max_cartons_per_flight": destination_rule.get("max_cartons_per_flight"),
            "weekly_frequency": destination_rule.get("weekly_frequency"),
            "payload": payload,
        }
        flights.append(flight)
    return {
        "run_id": run.pk,
        "shipments": shipments,
        "volunteers": volunteers,
        "flights": flights,
        "destination_rules_by_iata": destination_rules_by_iata,
    }


def materialize_solver_snapshots(run: PlanningRun) -> dict:
    return {
        "shipments": {
            snapshot.pk: snapshot
            for snapshot in run.shipment_snapshots.order_by("-priority", "shipment_reference", "id")
        },
        "volunteers": {
            snapshot.pk: snapshot
            for snapshot in run.volunteer_snapshots.order_by("volunteer_label", "id")
        },
        "flights": {
            snapshot.pk: snapshot
            for snapshot in run.flight_snapshots.order_by("departure_date", "flight_number", "id")
        },
    }


def volunteer_is_compatible_with_flight(volunteer: dict, flight: dict) -> bool:
    availability = volunteer.get("availability_summary") or {}
    unavailable_dates = set(availability.get("unavailable_dates") or [])
    departure_date = str(flight.get("departure_date") or "")
    if departure_date in unavailable_dates:
        return False

    slots = availability.get("slots") or []
    if not slots:
        return True

    departure_time = _parse_time_value(flight.get("departure_time"))
    for slot in slots:
        if slot.get("date") != departure_date:
            continue
        if departure_time is None:
            return True
        start_time = _parse_time_value(slot.get("start_time"))
        end_time = _parse_time_value(slot.get("end_time"))
        if start_time is None or end_time is None:
            return True
        if start_time <= departure_time <= end_time:
            return True
    return False


def shipment_is_compatible_with_flight(shipment: dict, flight: dict) -> bool:
    shipment_dest = str(shipment.get("destination_iata") or "").upper()
    flight_dest = str(flight.get("destination_iata") or "").upper()
    if shipment_dest and flight_dest and shipment_dest != flight_dest:
        return False
    max_cartons_per_flight = flight.get("max_cartons_per_flight")
    if max_cartons_per_flight is not None and shipment["carton_count"] > max_cartons_per_flight:
        return False
    capacity_units = flight.get("capacity_units")
    if capacity_units is not None and shipment["equivalent_units"] > capacity_units:
        return False
    return True


def build_solver_diagnostics(payload: dict) -> list[dict]:
    diagnostics = []
    for flight in payload["flights"]:
        shipment_compat_count = sum(
            1
            for shipment in payload["shipments"]
            if shipment_is_compatible_with_flight(shipment, flight)
        )
        benevole_compat_count = sum(
            1
            for volunteer in payload["volunteers"]
            if volunteer_is_compatible_with_flight(volunteer, flight)
        )
        diagnostics.append(
            {
                "flight_snapshot_id": flight["snapshot_id"],
                "flight_number": flight["flight_number"],
                "departure_date": flight["departure_date"],
                "departure_time": flight["departure_time"],
                "destination_iata": flight["destination_iata"],
                "physical_flight_key": flight["physical_flight_key"],
                "route_pos": flight["route_pos"],
                "shipment_compat_count": shipment_compat_count,
                "benevole_compat_count": benevole_compat_count,
                "candidate_assignment_count": 0,
                "used": False,
            }
        )
    return diagnostics


def compute_compatibility(payload: dict, diagnostics: list[dict] | None = None) -> list[dict]:
    candidates: list[dict] = []
    diagnostics_by_flight_id = {
        item["flight_snapshot_id"]: item
        for item in (diagnostics if diagnostics is not None else build_solver_diagnostics(payload))
    }
    for shipment in payload["shipments"]:
        for flight in payload["flights"]:
            if not shipment_is_compatible_with_flight(shipment, flight):
                continue
            for volunteer in payload["volunteers"]:
                if not volunteer_is_compatible_with_flight(volunteer, flight):
                    continue
                max_colis_vol = volunteer.get("max_colis_vol")
                if max_colis_vol is not None and shipment["carton_count"] > max_colis_vol:
                    continue
                candidates.append(
                    {
                        "shipment_snapshot_id": shipment["snapshot_id"],
                        "flight_snapshot_id": flight["snapshot_id"],
                        "volunteer_snapshot_id": volunteer["snapshot_id"],
                        "assigned_carton_count": shipment["carton_count"],
                        "equivalent_units": shipment["equivalent_units"],
                        "priority": shipment["priority"],
                        "route_pos": flight["route_pos"],
                        "physical_flight_key": flight["physical_flight_key"],
                    }
                )
                diagnostics_by_flight_id[flight["snapshot_id"]]["candidate_assignment_count"] += 1
    return candidates
