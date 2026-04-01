from __future__ import annotations

from collections import defaultdict

from wms.models import PlanningAssignmentSource, PlanningVersion
from wms.policies.planning import (
    FLIGHT_LOAD_STATE_LABELS,
    FLIGHT_LOAD_STATE_ORDER,
    classify_planning_load_state,
)


def _build_flight_load_metrics(
    capacity_units,
    equivalent_total: int,
    *,
    tension_pct: int = 80,
    critical_pct: int = 95,
) -> dict[str, object]:
    if not capacity_units:
        load_state = "unknown"
        return {
            "remaining_units": None,
            "utilization_pct": None,
            "load_state": load_state,
            "load_state_label": FLIGHT_LOAD_STATE_LABELS[load_state],
        }
    utilization_pct = round((equivalent_total / capacity_units) * 100)
    remaining_units = capacity_units - equivalent_total
    load_state = classify_planning_load_state(
        utilization_pct,
        tension_pct=tension_pct,
        critical_pct=critical_pct,
    )
    return {
        "remaining_units": remaining_units,
        "utilization_pct": utilization_pct,
        "load_state": load_state,
        "load_state_label": FLIGHT_LOAD_STATE_LABELS[load_state],
    }


def build_version_stats(
    version: PlanningVersion,
    *,
    tension_pct: int = 80,
    critical_pct: int = 95,
) -> dict[str, int]:
    assignments = list(
        version.assignments.select_related(
            "volunteer_snapshot",
            "flight_snapshot",
            "shipment_snapshot",
        )
    )
    assigned_snapshot_ids = {
        assignment.shipment_snapshot_id
        for assignment in assignments
        if assignment.shipment_snapshot_id
    }
    destination_totals: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "destination_iata": "",
            "assignment_count": 0,
            "carton_total": 0,
            "equivalent_total": 0,
        }
    )
    volunteer_totals: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "volunteer_label": "",
            "assignment_count": 0,
            "carton_total": 0,
            "equivalent_total": 0,
        }
    )
    flight_load: dict[int, dict[str, object]] = {
        flight.pk: {
            "flight_snapshot_id": flight.pk,
            "flight_number": flight.flight_number,
            "departure_date": flight.departure_date,
            "departure_time": (flight.payload or {}).get("departure_time", ""),
            "destination_iata": flight.destination_iata,
            "capacity_units": flight.capacity_units,
            "assignment_count": 0,
            "carton_total": 0,
            "equivalent_total": 0,
        }
        for flight in version.run.flight_snapshots.all()
    }

    for assignment in assignments:
        shipment = assignment.shipment_snapshot
        volunteer = assignment.volunteer_snapshot
        flight = assignment.flight_snapshot
        destination_iata = ""
        equivalent_units = 0
        if shipment is not None:
            destination_iata = shipment.destination_iata
            equivalent_units = shipment.equivalent_units
        if not destination_iata and flight is not None:
            destination_iata = flight.destination_iata

        destination_bucket = destination_totals[destination_iata or "-"]
        destination_bucket["destination_iata"] = destination_iata or "-"
        destination_bucket["assignment_count"] += 1
        destination_bucket["carton_total"] += assignment.assigned_carton_count
        destination_bucket["equivalent_total"] += equivalent_units

        volunteer_label = volunteer.volunteer_label if volunteer is not None else "-"
        volunteer_bucket = volunteer_totals[volunteer_label]
        volunteer_bucket["volunteer_label"] = volunteer_label
        volunteer_bucket["assignment_count"] += 1
        volunteer_bucket["carton_total"] += assignment.assigned_carton_count
        volunteer_bucket["equivalent_total"] += equivalent_units

        if flight is not None:
            flight_bucket = flight_load.get(flight.pk)
            if flight_bucket is None:
                flight_bucket = {
                    "flight_snapshot_id": flight.pk,
                    "flight_number": flight.flight_number,
                    "departure_date": flight.departure_date,
                    "departure_time": (flight.payload or {}).get("departure_time", ""),
                    "destination_iata": flight.destination_iata,
                    "capacity_units": flight.capacity_units,
                    "assignment_count": 0,
                    "carton_total": 0,
                    "equivalent_total": 0,
                }
                flight_load[flight.pk] = flight_bucket
            flight_bucket["assignment_count"] += 1
            flight_bucket["carton_total"] += assignment.assigned_carton_count
            flight_bucket["equivalent_total"] += equivalent_units

    destination_breakdown = sorted(
        destination_totals.values(),
        key=lambda item: (-item["carton_total"], item["destination_iata"]),
    )
    volunteer_breakdown = sorted(
        volunteer_totals.values(),
        key=lambda item: (-item["carton_total"], item["volunteer_label"]),
    )
    for item in flight_load.values():
        item.update(
            _build_flight_load_metrics(
                item["capacity_units"],
                item["equivalent_total"],
                tension_pct=tension_pct,
                critical_pct=critical_pct,
            )
        )
    flight_load_breakdown = sorted(
        flight_load.values(),
        key=lambda item: (
            FLIGHT_LOAD_STATE_ORDER.get(item["load_state"], 99),
            item["departure_date"],
            item["departure_time"] or "",
            item["flight_number"],
        ),
    )
    return {
        "assignment_count": len(assignments),
        "carton_total": sum(assignment.assigned_carton_count for assignment in assignments),
        "volunteer_count": len(
            {
                assignment.volunteer_snapshot_id
                for assignment in assignments
                if assignment.volunteer_snapshot_id
            }
        ),
        "flight_count": len(
            {
                assignment.flight_snapshot_id
                for assignment in assignments
                if assignment.flight_snapshot_id
            }
        ),
        "manual_adjustment_count": sum(
            1 for assignment in assignments if assignment.source == PlanningAssignmentSource.MANUAL
        ),
        "unassigned_count": version.run.shipment_snapshots.exclude(
            pk__in=assigned_snapshot_ids
        ).count(),
        "destination_breakdown": destination_breakdown,
        "volunteer_breakdown": volunteer_breakdown,
        "flight_load_breakdown": flight_load_breakdown,
    }
