from wms.models import (
    PlanningFlightSnapshot,
    PlanningRun,
    PlanningShipmentSnapshot,
    PlanningVolunteerSnapshot,
)
from wms.planning.validation import get_destination_rule_map


def _normalize_flight_number(value: str) -> str:
    return "".join(ch for ch in str(value or "").strip().upper() if ch.isalnum())


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
        flights.append(
            {
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
        )
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


def _has_availability_for_date(volunteer_payload, departure_date: str) -> bool:
    slots = (volunteer_payload.get("availability_summary") or {}).get("slots") or []
    if not slots:
        return True
    return any(slot.get("date") == departure_date for slot in slots)


def compute_compatibility(payload: dict) -> dict[int, list[tuple[int, int]]]:
    compatibility = {}
    for shipment in payload["shipments"]:
        pairs = []
        for flight in payload["flights"]:
            if (
                shipment["destination_iata"]
                and flight["destination_iata"]
                and shipment["destination_iata"] != flight["destination_iata"]
            ):
                continue
            for volunteer in payload["volunteers"]:
                max_colis_vol = volunteer.get("max_colis_vol")
                if max_colis_vol is not None and shipment["carton_count"] > max_colis_vol:
                    continue
                if not _has_availability_for_date(volunteer, flight["departure_date"]):
                    continue
                pairs.append((flight["snapshot_id"], volunteer["snapshot_id"]))
        compatibility[shipment["snapshot_id"]] = pairs
    return compatibility
