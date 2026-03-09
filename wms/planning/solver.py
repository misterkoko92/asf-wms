from __future__ import annotations

from collections import defaultdict

from django.db import transaction

from wms.models import (
    PlanningAssignment,
    PlanningAssignmentSource,
    PlanningRunStatus,
    PlanningVersion,
)
from wms.planning.config import LEGACY_EQUIV_CAPACITY_PER_VOLUNTEER
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


def _build_candidates(payload: dict, compatibility: dict[int, list[tuple[int, int]]]) -> list[dict]:
    shipment_by_id = {
        shipment["snapshot_id"]: shipment for shipment in payload.get("shipments", [])
    }
    flight_by_id = {flight["snapshot_id"]: flight for flight in payload.get("flights", [])}
    candidates = []
    for shipment_id, pairs in compatibility.items():
        shipment = shipment_by_id[shipment_id]
        for flight_id, volunteer_id in pairs:
            flight = flight_by_id[flight_id]
            candidates.append(
                {
                    "shipment_snapshot_id": shipment_id,
                    "flight_snapshot_id": flight_id,
                    "volunteer_snapshot_id": volunteer_id,
                    "assigned_carton_count": shipment["carton_count"],
                    "equivalent_units": shipment["equivalent_units"],
                    "priority": shipment["priority"],
                    "route_pos": int(flight.get("route_pos") or 1),
                    "physical_flight_key": flight.get("physical_flight_key") or str(flight_id),
                    "reference": shipment.get("reference") or "",
                    "departure_date": flight.get("departure_date") or "",
                }
            )
    return candidates


def _solve_candidates(
    *,
    payload: dict,
    compatibility: dict[int, list[tuple[int, int]]],
    candidates: list[dict],
) -> tuple[list[dict], dict]:
    diagnostics = build_solver_diagnostics(payload)
    diagnostics_by_flight_id = {item["flight_snapshot_id"]: item for item in diagnostics}
    for candidate in candidates:
        diagnostics_by_flight_id[candidate["flight_snapshot_id"]]["candidate_assignment_count"] += 1

    if cp_model is None:
        raise RuntimeError("ortools is required to solve planning runs.")

    if not candidates:
        result = summarize_solver_result(
            payload=payload,
            assignments=[],
            unassigned=[shipment["snapshot_id"] for shipment in payload.get("shipments", [])],
            compatibility=compatibility,
            solver_name="ortools_cp_sat_v1",
        )
        result.update(
            {
                "status": "OPTIMAL",
                "assigned_shipment_snapshot_ids": [],
                "vols_diagnostics": diagnostics,
                "nb_vols_total": len(payload.get("flights", [])),
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
        )
        return [], result

    model = cp_model.CpModel()
    variables = {}
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

    flight_by_id = {flight["snapshot_id"]: flight for flight in payload.get("flights", [])}
    volunteer_by_id = {
        volunteer["snapshot_id"]: volunteer for volunteer in payload.get("volunteers", [])
    }

    for candidate_indexes in candidates_by_shipment.values():
        model.Add(sum(variables[index] for index in candidate_indexes) <= 1)

    flight_used_vars = {}
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
                    int(candidates[index]["equivalent_units"]) * variables[index]
                    for index in candidate_indexes
                )
                <= int(capacity_units)
            )

        max_cartons_per_flight = flight.get("max_cartons_per_flight")
        if max_cartons_per_flight is not None:
            model.Add(
                sum(
                    int(candidates[index]["assigned_carton_count"]) * variables[index]
                    for index in candidate_indexes
                )
                <= int(max_cartons_per_flight)
            )

    volunteer_flight_vars = {}
    for (volunteer_id, flight_id), candidate_indexes in candidates_by_volunteer_flight.items():
        link_var = model.NewBoolVar(f"volunteer_{volunteer_id}_flight_{flight_id}")
        volunteer_flight_vars[(volunteer_id, flight_id)] = link_var
        for index in candidate_indexes:
            model.Add(variables[index] <= link_var)
        model.Add(sum(variables[index] for index in candidate_indexes) >= link_var)

        volunteer_equiv_capacity = volunteer_by_id[volunteer_id].get("max_colis_vol")
        if volunteer_equiv_capacity is None:
            volunteer_equiv_capacity = LEGACY_EQUIV_CAPACITY_PER_VOLUNTEER
        model.Add(
            sum(
                int(candidates[index]["equivalent_units"]) * variables[index]
                for index in candidate_indexes
            )
            <= int(volunteer_equiv_capacity)
        )

    grouped_by_volunteer_and_physical = defaultdict(list)
    for (volunteer_id, flight_id), link_var in volunteer_flight_vars.items():
        physical_key = flight_by_id[flight_id].get("physical_flight_key") or str(flight_id)
        grouped_by_volunteer_and_physical[(volunteer_id, physical_key)].append(link_var)
    for link_vars in grouped_by_volunteer_and_physical.values():
        if len(link_vars) > 1:
            model.Add(sum(link_vars) <= 1)

    flights_by_destination = defaultdict(list)
    for flight_id, flight in flight_by_id.items():
        flights_by_destination[str(flight.get("destination_iata") or "")].append(flight_id)
    for destination_iata, flight_ids in flights_by_destination.items():
        rule = payload.get("destination_rules_by_iata", {}).get(destination_iata, {})
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
    selected.sort(
        key=lambda item: (
            -int(item.get("priority") or 0),
            str(item.get("departure_date") or ""),
            int(item.get("route_pos") or 1),
            str(item.get("reference") or ""),
        )
    )
    assigned_shipment_ids = [item["shipment_snapshot_id"] for item in selected]
    for candidate in selected:
        diagnostics_by_flight_id[candidate["flight_snapshot_id"]]["used"] = True
    result = summarize_solver_result(
        payload=payload,
        assignments=selected,
        unassigned=[
            shipment["snapshot_id"]
            for shipment in payload.get("shipments", [])
            if shipment["snapshot_id"] not in assigned_shipment_ids
        ],
        compatibility=compatibility,
        solver_name="ortools_cp_sat_v1",
    )
    result.update(
        {
            "status": status_name,
            "assigned_shipment_snapshot_ids": assigned_shipment_ids,
            "vols_diagnostics": list(diagnostics_by_flight_id.values()),
            "nb_vols_total": len(payload.get("flights", [])),
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
    )
    return selected, result


@transaction.atomic
def solve_run(run):
    if run.status != PlanningRunStatus.READY:
        raise ValueError("Planning run must be ready before solving.")

    run.status = PlanningRunStatus.SOLVING
    run.save(update_fields=["status", "updated_at"])

    payload = compile_run_solver_payload(run)
    compatibility = compute_compatibility(payload)
    assignments, solver_result = _solve_candidates(
        payload=payload,
        compatibility=compatibility,
        candidates=_build_candidates(payload, compatibility),
    )
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
    run.solver_result = solver_result
    run.status = PlanningRunStatus.SOLVED
    run.save(update_fields=["solver_payload", "solver_result", "status", "updated_at"])
    return version
