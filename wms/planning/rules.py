from wms.models import (
    PlanningFlightSnapshot,
    PlanningRun,
    PlanningShipmentSnapshot,
    PlanningVolunteerSnapshot,
)


def compile_run_solver_payload(run: PlanningRun) -> dict:
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
    flights = [
        {
            "snapshot_id": snapshot.pk,
            "flight_number": snapshot.flight_number,
            "departure_date": snapshot.departure_date.isoformat(),
            "destination_iata": snapshot.destination_iata,
            "capacity_units": snapshot.capacity_units,
            "payload": snapshot.payload,
        }
        for snapshot in run.flight_snapshots.order_by("departure_date", "flight_number", "id")
    ]
    return {
        "run_id": run.pk,
        "shipments": shipments,
        "volunteers": volunteers,
        "flights": flights,
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
