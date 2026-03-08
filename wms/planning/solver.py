from __future__ import annotations

from collections import defaultdict

from django.db import transaction

from wms.models import (
    PlanningAssignment,
    PlanningAssignmentSource,
    PlanningRunStatus,
    PlanningVersion,
)
from wms.planning.rules import (
    build_solver_diagnostics,
    compile_run_solver_payload,
    compute_compatibility,
    materialize_solver_snapshots,
)

try:
    from ortools.sat.python import cp_model
except ModuleNotFoundError:  # pragma: no cover - dependency guard
    cp_model = None


def _candidate_score(candidate: dict) -> int:
    priority = int(candidate.get("priority") or 0)
    route_pos = int(candidate.get("route_pos") or 1)
    route_bonus = max(0, 100 - route_pos)
    equivalent_units = int(candidate.get("equivalent_units") or 0)
    cartons = int(candidate.get("assigned_carton_count") or 0)
    return (
        (priority * 1_000_000_000)
        + (route_bonus * 1_000_000)
        + (equivalent_units * 1_000)
        + cartons
    )


def _build_empty_result(payload: dict, diagnostics: list[dict]) -> dict:
    return {
        "solver": "ortools_cp_sat_v1",
        "status": "OPTIMAL",
        "assignment_count": 0,
        "assigned_shipment_snapshot_ids": [],
        "unassigned_shipment_snapshot_ids": [
            shipment["snapshot_id"] for shipment in payload["shipments"]
        ],
        "flight_usage": {},
        "volunteer_usage": {},
        "candidate_count": 0,
        "vols_diagnostics": diagnostics,
        "nb_vols_total": len(payload["flights"]),
        "nb_vols_sans_be_compatible": sum(
            1 for item in diagnostics if item["shipment_compat_count"] == 0
        ),
        "nb_vols_sans_benevole_compatible": sum(
            1 for item in diagnostics if item["benevole_compat_count"] == 0
        ),
        "nb_vols_sans_compatibilite_complete": sum(
            1
            for item in diagnostics
            if item["shipment_compat_count"] == 0 or item["benevole_compat_count"] == 0
        ),
        "nb_vols_non_utilises_avec_compatibilite": sum(
            1
            for item in diagnostics
            if item["shipment_compat_count"] > 0 and item["benevole_compat_count"] > 0
        ),
    }


def _solve_candidates(
    payload: dict, candidates: list[dict], diagnostics: list[dict]
) -> tuple[list[dict], dict]:
    if cp_model is None:
        raise RuntimeError("ortools is required to solve planning runs.")
    if not candidates:
        return [], _build_empty_result(payload, diagnostics)

    model = cp_model.CpModel()
    variables = {}
    volunteer_flight_vars = {}
    flight_used_vars = {}

    candidates_by_shipment = defaultdict(list)
    candidates_by_flight = defaultdict(list)
    candidates_by_volunteer_flight = defaultdict(list)

    for index, candidate in enumerate(candidates):
        variables[index] = model.NewBoolVar(
            "assign_"
            f"{candidate['shipment_snapshot_id']}_"
            f"{candidate['flight_snapshot_id']}_"
            f"{candidate['volunteer_snapshot_id']}"
        )
        candidates_by_shipment[candidate["shipment_snapshot_id"]].append(index)
        candidates_by_flight[candidate["flight_snapshot_id"]].append(index)
        candidates_by_volunteer_flight[
            (candidate["volunteer_snapshot_id"], candidate["flight_snapshot_id"])
        ].append(index)

    flight_by_id = {flight["snapshot_id"]: flight for flight in payload["flights"]}
    volunteer_by_id = {volunteer["snapshot_id"]: volunteer for volunteer in payload["volunteers"]}

    for shipment_id, candidate_indexes in candidates_by_shipment.items():
        del shipment_id
        model.Add(sum(variables[index] for index in candidate_indexes) <= 1)

    for flight_id, candidate_indexes in candidates_by_flight.items():
        flight = flight_by_id[flight_id]
        flight_used = model.NewBoolVar(f"flight_used_{flight_id}")
        flight_used_vars[flight_id] = flight_used
        for index in candidate_indexes:
            model.Add(variables[index] <= flight_used)
        model.Add(sum(variables[index] for index in candidate_indexes) >= flight_used)

        capacity_units = flight.get("capacity_units")
        if capacity_units is not None:
            model.Add(
                sum(
                    candidates[index]["equivalent_units"] * variables[index]
                    for index in candidate_indexes
                )
                <= int(capacity_units)
            )

        max_cartons_per_flight = flight.get("max_cartons_per_flight")
        if max_cartons_per_flight is not None:
            model.Add(
                sum(
                    candidates[index]["assigned_carton_count"] * variables[index]
                    for index in candidate_indexes
                )
                <= int(max_cartons_per_flight)
            )

    for (volunteer_id, flight_id), candidate_indexes in candidates_by_volunteer_flight.items():
        link_var = model.NewBoolVar(f"volunteer_{volunteer_id}_flight_{flight_id}")
        volunteer_flight_vars[(volunteer_id, flight_id)] = link_var
        for index in candidate_indexes:
            model.Add(variables[index] <= link_var)
        model.Add(sum(variables[index] for index in candidate_indexes) >= link_var)

        max_colis_vol = volunteer_by_id[volunteer_id].get("max_colis_vol")
        if max_colis_vol is not None:
            model.Add(
                sum(
                    candidates[index]["assigned_carton_count"] * variables[index]
                    for index in candidate_indexes
                )
                <= int(max_colis_vol)
            )

    grouped_by_volunteer_and_physical = defaultdict(list)
    for (volunteer_id, flight_id), link_var in volunteer_flight_vars.items():
        physical_key = flight_by_id[flight_id]["physical_flight_key"]
        grouped_by_volunteer_and_physical[(volunteer_id, physical_key)].append(link_var)
    for link_vars in grouped_by_volunteer_and_physical.values():
        if len(link_vars) > 1:
            model.Add(sum(link_vars) <= 1)

    flights_by_destination = defaultdict(list)
    for flight_id, flight in flight_by_id.items():
        flights_by_destination[flight["destination_iata"]].append(flight_id)
    for destination_iata, flight_ids in flights_by_destination.items():
        rule = payload["destination_rules_by_iata"].get(destination_iata, {})
        weekly_frequency = rule.get("weekly_frequency")
        if weekly_frequency:
            available_vars = [
                flight_used_vars[flight_id]
                for flight_id in flight_ids
                if flight_id in flight_used_vars
            ]
            if available_vars:
                model.Add(sum(available_vars) <= int(weekly_frequency))

    model.Maximize(
        sum(_candidate_score(candidates[index]) * variables[index] for index in variables)
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    status_name = solver.StatusName(status)

    selected = [
        candidates[index] for index, variable in variables.items() if solver.Value(variable)
    ]

    diagnostics_by_flight_id = {item["flight_snapshot_id"]: item for item in diagnostics}
    assignment_count_by_flight = defaultdict(int)
    assignment_count_by_volunteer = defaultdict(int)
    for candidate in selected:
        flight_id = candidate["flight_snapshot_id"]
        volunteer_id = candidate["volunteer_snapshot_id"]
        diagnostics_by_flight_id[flight_id]["used"] = True
        assignment_count_by_flight[flight_id] += 1
        assignment_count_by_volunteer[volunteer_id] += 1

    assigned_shipment_ids = [item["shipment_snapshot_id"] for item in selected]
    result = {
        "solver": "ortools_cp_sat_v1",
        "status": status_name,
        "assignment_count": len(selected),
        "assigned_shipment_snapshot_ids": assigned_shipment_ids,
        "unassigned_shipment_snapshot_ids": [
            shipment["snapshot_id"]
            for shipment in payload["shipments"]
            if shipment["snapshot_id"] not in assigned_shipment_ids
        ],
        "flight_usage": {str(key): value for key, value in assignment_count_by_flight.items()},
        "volunteer_usage": {
            str(key): value for key, value in assignment_count_by_volunteer.items()
        },
        "candidate_count": len(candidates),
        "vols_diagnostics": list(diagnostics_by_flight_id.values()),
        "nb_vols_total": len(payload["flights"]),
        "nb_vols_sans_be_compatible": sum(
            1 for item in diagnostics if item["shipment_compat_count"] == 0
        ),
        "nb_vols_sans_benevole_compatible": sum(
            1 for item in diagnostics if item["benevole_compat_count"] == 0
        ),
        "nb_vols_sans_compatibilite_complete": sum(
            1
            for item in diagnostics
            if item["shipment_compat_count"] == 0 or item["benevole_compat_count"] == 0
        ),
        "nb_vols_non_utilises_avec_compatibilite": sum(
            1
            for item in diagnostics_by_flight_id.values()
            if (
                item["shipment_compat_count"] > 0
                and item["benevole_compat_count"] > 0
                and not item["used"]
            )
        ),
    }
    return selected, result


@transaction.atomic
def solve_run(run):
    if run.status != PlanningRunStatus.READY:
        raise ValueError("Planning run must be ready before solving.")

    run.status = PlanningRunStatus.SOLVING
    run.save(update_fields=["status", "updated_at"])

    payload = compile_run_solver_payload(run)
    diagnostics = build_solver_diagnostics(payload)
    candidates = compute_compatibility(payload, diagnostics)
    assignments, solver_result = _solve_candidates(payload, candidates, diagnostics)
    snapshots = materialize_solver_snapshots(run)
    version = PlanningVersion.objects.create(
        run=run,
        created_by=run.created_by,
    )

    def _assignment_sort_key(item: dict):
        shipment = snapshots["shipments"][item["shipment_snapshot_id"]]
        flight = snapshots["flights"][item["flight_snapshot_id"]]
        flight_payload = flight.payload or {}
        return (
            -item.get("priority", 0),
            str(getattr(flight, "departure_date", "")),
            int(flight_payload.get("route_pos") or 1),
            shipment.shipment_reference,
        )

    for sequence, item in enumerate(sorted(assignments, key=_assignment_sort_key), start=1):
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
    run.solver_result = solver_result
    run.status = PlanningRunStatus.SOLVED
    run.save(update_fields=["solver_payload", "solver_result", "status", "updated_at"])
    return version
