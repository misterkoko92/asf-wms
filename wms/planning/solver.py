from collections import defaultdict

from django.db import transaction

from wms.models import (
    PlanningAssignment,
    PlanningAssignmentSource,
    PlanningRunStatus,
    PlanningVersion,
)
from wms.planning.rules import (
    compile_run_solver_payload,
    compute_compatibility,
    materialize_solver_snapshots,
)


def summarize_solver_result(
    *,
    payload: dict,
    assignments: list[dict],
    unassigned: list[int],
    compatibility: dict[int, list[tuple[int, int]]],
    solver_name: str = "greedy_v1",
) -> dict:
    assignment_count_by_flight = defaultdict(int)
    flight_usage = {str(flight["snapshot_id"]): 0 for flight in payload.get("flights", [])}
    volunteer_usage = {
        str(volunteer["snapshot_id"]): 0 for volunteer in payload.get("volunteers", [])
    }
    assigned_shipment_ids = {item["shipment_snapshot_id"] for item in assignments}

    for item in assignments:
        flight_id = item["flight_snapshot_id"]
        volunteer_id = item["volunteer_snapshot_id"]
        assignment_count_by_flight[flight_id] += 1
        flight_usage[str(flight_id)] = flight_usage.get(str(flight_id), 0) + 1
        volunteer_usage[str(volunteer_id)] = volunteer_usage.get(str(volunteer_id), 0) + 1

    unassigned_reasons = {}
    for shipment_id in unassigned:
        if shipment_id in assigned_shipment_ids:
            continue
        if compatibility.get(shipment_id):
            reason = "no_selected_candidate"
        else:
            reason = "no_compatible_candidate"
        unassigned_reasons[str(shipment_id)] = reason

    return {
        "solver": solver_name,
        "candidate_count": sum(len(pairs) for pairs in compatibility.values()),
        "assignment_count": len(assignments),
        "unassigned_shipment_snapshot_ids": unassigned,
        "unassigned_reasons": unassigned_reasons,
        "compatibility": {str(key): value for key, value in compatibility.items()},
        "assignment_count_by_flight": dict(assignment_count_by_flight),
        "flight_usage": flight_usage,
        "volunteer_usage": volunteer_usage,
    }


def _build_assignments(
    payload: dict, compatibility: dict[int, list[tuple[int, int]]]
) -> tuple[list, list]:
    flight_remaining_capacity = {
        flight["snapshot_id"]: flight.get("capacity_units") for flight in payload["flights"]
    }
    volunteer_remaining_cartons = {
        volunteer["snapshot_id"]: volunteer.get("max_colis_vol")
        for volunteer in payload["volunteers"]
    }
    assignments = []
    unassigned = []

    for shipment in payload["shipments"]:
        matched = False
        for flight_id, volunteer_id in compatibility.get(shipment["snapshot_id"], []):
            remaining_capacity = flight_remaining_capacity.get(flight_id)
            if remaining_capacity is not None and shipment["equivalent_units"] > remaining_capacity:
                continue
            remaining_cartons = volunteer_remaining_cartons.get(volunteer_id)
            if remaining_cartons is not None and shipment["carton_count"] > remaining_cartons:
                continue
            assignments.append(
                {
                    "shipment_snapshot_id": shipment["snapshot_id"],
                    "flight_snapshot_id": flight_id,
                    "volunteer_snapshot_id": volunteer_id,
                    "assigned_carton_count": shipment["carton_count"],
                }
            )
            if remaining_capacity is not None:
                flight_remaining_capacity[flight_id] = (
                    remaining_capacity - shipment["equivalent_units"]
                )
            if remaining_cartons is not None:
                volunteer_remaining_cartons[volunteer_id] = (
                    remaining_cartons - shipment["carton_count"]
                )
            matched = True
            break
        if not matched:
            unassigned.append(shipment["snapshot_id"])

    return assignments, unassigned


@transaction.atomic
def solve_run(run):
    if run.status != PlanningRunStatus.READY:
        raise ValueError("Planning run must be ready before solving.")

    run.status = PlanningRunStatus.SOLVING
    run.save(update_fields=["status", "updated_at"])

    payload = compile_run_solver_payload(run)
    compatibility = compute_compatibility(payload)
    assignments, unassigned = _build_assignments(payload, compatibility)
    snapshots = materialize_solver_snapshots(run)
    version = PlanningVersion.objects.create(
        run=run,
        created_by=run.created_by,
    )

    for sequence, item in enumerate(assignments, start=1):
        PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=snapshots["shipments"][item["shipment_snapshot_id"]],
            volunteer_snapshot=snapshots["volunteers"][item["volunteer_snapshot_id"]],
            flight_snapshot=snapshots["flights"][item["flight_snapshot_id"]],
            assigned_carton_count=item["assigned_carton_count"],
            source=PlanningAssignmentSource.SOLVER,
            sequence=sequence,
        )

    run.solver_payload = payload
    run.solver_result = summarize_solver_result(
        payload=payload,
        assignments=assignments,
        unassigned=unassigned,
        compatibility=compatibility,
    )
    run.status = PlanningRunStatus.SOLVED
    run.save(update_fields=["solver_payload", "solver_result", "status", "updated_at"])
    return version
