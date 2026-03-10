from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from functools import cache

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

LEGACY_MAX_BE_PER_FLIGHT = 5
LEGACY_MIN_HOURS_BETWEEN_FLIGHTS = 3.0


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
    equivalent_units = int(candidate.get("equivalent_units") or 0)
    priority = int(candidate.get("priority_rank") or candidate.get("priority") or 0)
    legacy_priority_bonus = max(0, 10 - priority)
    weighted_priority = equivalent_units * legacy_priority_bonus
    cartons = int(candidate.get("assigned_carton_count") or 0)
    return (weighted_priority * 1_000_000_000) + (equivalent_units * 1_000) + cartons


def _coerce_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _flight_datetime_key(flight: dict) -> datetime:
    departure_date = str(flight.get("departure_date") or "").strip()
    departure_time = str(flight.get("departure_time") or "").strip() or "00:00"
    try:
        return datetime.fromisoformat(f"{departure_date}T{departure_time}")
    except ValueError:
        return datetime.max


def _shipment_weight(shipment: dict) -> int:
    equivalent_units = int(shipment.get("equivalent_units") or 0)
    priority = int(shipment.get("priority_rank") or shipment.get("priority") or 0)
    legacy_priority_bonus = max(0, 10 - priority)
    return equivalent_units * legacy_priority_bonus


def _volunteer_availability_minutes(volunteer: dict) -> int:
    availability = volunteer.get("availability_summary") or {}
    total = 0
    for slot in availability.get("slots") or []:
        date_value = str(slot.get("date") or "").strip()
        start_value = str(slot.get("start_time") or "").strip()
        end_value = str(slot.get("end_time") or "").strip()
        if not date_value or not start_value or not end_value:
            continue
        try:
            start_dt = datetime.fromisoformat(f"{date_value}T{start_value}")
            end_dt = datetime.fromisoformat(f"{date_value}T{end_value}")
        except ValueError:
            continue
        delta = int((end_dt - start_dt).total_seconds() / 60)
        if delta > 0:
            total += delta
    return total


def _order_compatibility_pairs(
    payload: dict, compatibility: dict[int, list[tuple[int, int]]]
) -> dict:
    flight_order = {
        flight["snapshot_id"]: index for index, flight in enumerate(payload.get("flights", []))
    }
    volunteer_order = {
        volunteer["snapshot_id"]: index
        for index, volunteer in enumerate(payload.get("volunteers", []))
    }
    ordered = {}
    for shipment in payload.get("shipments", []):
        shipment_id = shipment["snapshot_id"]
        unique_pairs = list(dict.fromkeys(compatibility.get(shipment_id, [])))
        ordered[shipment_id] = sorted(
            unique_pairs,
            key=lambda pair: (
                flight_order.get(pair[0], 999999),
                volunteer_order.get(pair[1], 999999),
            ),
        )
    return ordered


def _volunteer_assignment_order_key(volunteer: dict) -> tuple:
    payload = volunteer.get("payload") or {}
    legacy_id = _coerce_int(payload.get("legacy_id"))
    label = str(volunteer.get("label") or "")
    snapshot_id = _coerce_int(volunteer.get("snapshot_id")) or 0
    if legacy_id is not None:
        return (0, legacy_id, label, snapshot_id)
    return (1, label, snapshot_id)


def _solve_lexicographic_flight_distribution(
    shipment_weights: tuple[int, ...],
    volunteer_capacities: tuple[int, ...],
) -> tuple[int, ...] | None:
    @cache
    def _assign(index: int, remaining_capacities: tuple[int, ...]) -> tuple[int, ...] | None:
        if index >= len(shipment_weights):
            return ()

        current_weight = shipment_weights[index]
        for volunteer_index, remaining_capacity in enumerate(remaining_capacities):
            if remaining_capacity < current_weight:
                continue
            next_remaining = list(remaining_capacities)
            next_remaining[volunteer_index] -= current_weight
            tail = _assign(index + 1, tuple(next_remaining))
            if tail is not None:
                return (volunteer_index,) + tail
        return None

    return _assign(0, volunteer_capacities)


def _rebalance_assignments_by_flight(assignments: list[dict], payload: dict) -> list[dict]:
    if not assignments:
        return assignments

    volunteer_by_id = {
        volunteer["snapshot_id"]: volunteer for volunteer in payload.get("volunteers", [])
    }
    grouped_assignments = defaultdict(list)
    for assignment in assignments:
        grouped_assignments[assignment["flight_snapshot_id"]].append(assignment)

    rebalanced = []
    for flight_assignments in grouped_assignments.values():
        if len(flight_assignments) <= 1:
            rebalanced.extend(flight_assignments)
            continue

        ordered_shipments = sorted(
            flight_assignments,
            key=lambda item: (
                str(item.get("reference") or ""),
                int(item.get("shipment_snapshot_id") or 0),
            ),
        )
        volunteer_ids = sorted(
            {item["volunteer_snapshot_id"] for item in ordered_shipments},
            key=lambda volunteer_id: _volunteer_assignment_order_key(
                volunteer_by_id.get(volunteer_id, {"snapshot_id": volunteer_id})
            ),
        )
        if len(volunteer_ids) <= 1:
            rebalanced.extend(ordered_shipments)
            continue

        volunteer_capacities = []
        for volunteer_id in volunteer_ids:
            volunteer = volunteer_by_id.get(volunteer_id, {})
            max_colis_vol = volunteer.get("max_colis_vol")
            if max_colis_vol is None:
                max_colis_vol = LEGACY_EQUIV_CAPACITY_PER_VOLUNTEER
            volunteer_capacities.append(int(max_colis_vol))

        distribution = _solve_lexicographic_flight_distribution(
            tuple(int(item["equivalent_units"]) for item in ordered_shipments),
            tuple(volunteer_capacities),
        )
        if distribution is None:
            rebalanced.extend(ordered_shipments)
            continue

        for assignment, volunteer_index in zip(ordered_shipments, distribution):
            updated_assignment = dict(assignment)
            updated_assignment["volunteer_snapshot_id"] = volunteer_ids[volunteer_index]
            rebalanced.append(updated_assignment)

    return rebalanced


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
                    "priority_rank": shipment.get("priority_rank", shipment["priority"]),
                    "route_pos": int(flight.get("route_pos") or 1),
                    "physical_flight_key": flight.get("physical_flight_key") or str(flight_id),
                    "reference": shipment.get("reference") or "",
                    "departure_date": flight.get("departure_date") or "",
                }
            )
    candidates_by_physical_key = defaultdict(list)
    for candidate in candidates:
        candidates_by_physical_key[candidate["physical_flight_key"]].append(candidate)

    filtered_candidates = []
    for physical_key, physical_candidates in candidates_by_physical_key.items():
        if not physical_key:
            filtered_candidates.extend(physical_candidates)
            continue
        min_route_pos = min(int(item.get("route_pos") or 1) for item in physical_candidates)
        filtered_candidates.extend(
            item for item in physical_candidates if int(item.get("route_pos") or 1) == min_route_pos
        )
    return filtered_candidates


def _solve_candidates(
    *,
    payload: dict,
    compatibility: dict[int, list[tuple[int, int]]],
    candidates: list[dict],
) -> tuple[list[dict], dict]:
    del candidates
    diagnostics = build_solver_diagnostics(payload)
    diagnostics_by_flight_id = {item["flight_snapshot_id"]: item for item in diagnostics}

    if cp_model is None:
        raise RuntimeError("ortools is required to solve planning runs.")

    ordered_compatibility = _order_compatibility_pairs(payload, compatibility)
    candidate_count = sum(len(pairs) for pairs in ordered_compatibility.values())
    for pairs in ordered_compatibility.values():
        for flight_id, _ in pairs:
            diagnostics_by_flight_id[flight_id]["candidate_assignment_count"] += 1

    if candidate_count == 0:
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
    shipment_by_id = {
        shipment["snapshot_id"]: shipment for shipment in payload.get("shipments", [])
    }
    flight_by_id = {flight["snapshot_id"]: flight for flight in payload.get("flights", [])}
    volunteer_by_id = {
        volunteer["snapshot_id"]: volunteer for volunteer in payload.get("volunteers", [])
    }
    flight_order = {
        flight["snapshot_id"]: index
        for index, flight in enumerate(payload.get("flights", []), start=1)
    }

    shipment_flights = defaultdict(list)
    volunteer_flights = defaultdict(list)
    volunteers_by_shipment_flight = defaultdict(list)
    shipments_by_volunteer_flight = defaultdict(list)

    for shipment in payload.get("shipments", []):
        shipment_id = shipment["snapshot_id"]
        seen_flights = set()
        for flight_id, volunteer_id in ordered_compatibility.get(shipment_id, []):
            if flight_id not in seen_flights:
                shipment_flights[shipment_id].append(flight_id)
                seen_flights.add(flight_id)
            if flight_id not in volunteer_flights[volunteer_id]:
                volunteer_flights[volunteer_id].append(flight_id)
            if volunteer_id not in volunteers_by_shipment_flight[(shipment_id, flight_id)]:
                volunteers_by_shipment_flight[(shipment_id, flight_id)].append(volunteer_id)
            shipments_by_volunteer_flight[(volunteer_id, flight_id)].append(shipment_id)

    x_vars = {}
    x_by_shipment = defaultdict(list)
    x_by_flight = defaultdict(list)
    for shipment in payload.get("shipments", []):
        shipment_id = shipment["snapshot_id"]
        for flight_id in shipment_flights.get(shipment_id, []):
            var = model.NewBoolVar(f"x_{shipment_id}_{flight_id}")
            x_vars[(shipment_id, flight_id)] = var
            x_by_shipment[shipment_id].append(var)
            x_by_flight[flight_id].append(var)

    y_vars = {}
    y_by_flight = defaultdict(list)
    y_by_volunteer = defaultdict(list)
    for volunteer in payload.get("volunteers", []):
        volunteer_id = volunteer["snapshot_id"]
        for flight_id in volunteer_flights.get(volunteer_id, []):
            var = model.NewBoolVar(f"y_{volunteer_id}_{flight_id}")
            y_vars[(volunteer_id, flight_id)] = var
            y_by_flight[flight_id].append(var)
            y_by_volunteer[volunteer_id].append((flight_id, var))

    z_vars = {}
    z_order = {}
    z_by_flight = defaultdict(list)
    z_by_shipment_flight = defaultdict(list)
    z_by_volunteer_flight = defaultdict(list)
    z_counter = 0
    for shipment in payload.get("shipments", []):
        shipment_id = shipment["snapshot_id"]
        for flight_id in shipment_flights.get(shipment_id, []):
            for volunteer_id in volunteers_by_shipment_flight.get((shipment_id, flight_id), []):
                var = model.NewBoolVar(f"z_{shipment_id}_{volunteer_id}_{flight_id}")
                z_vars[(shipment_id, volunteer_id, flight_id)] = var
                z_counter += 1
                z_order[(shipment_id, volunteer_id, flight_id)] = z_counter
                z_by_flight[flight_id].append(var)
                z_by_shipment_flight[(shipment_id, flight_id)].append(var)
                z_by_volunteer_flight[(volunteer_id, flight_id)].append((shipment_id, var))

    flight_used_vars = {
        flight["snapshot_id"]: model.NewBoolVar(f"flight_used_{flight['snapshot_id']}")
        for flight in payload.get("flights", [])
    }
    nb_be_vars = {
        flight["snapshot_id"]: model.NewIntVar(
            0, LEGACY_MAX_BE_PER_FLIGHT, f"nb_be_{flight['snapshot_id']}"
        )
        for flight in payload.get("flights", [])
    }
    charge_vars = {
        flight["snapshot_id"]: model.NewIntVar(0, 10_000, f"charge_{flight['snapshot_id']}")
        for flight in payload.get("flights", [])
    }

    for shipment_vars in x_by_shipment.values():
        model.Add(sum(shipment_vars) <= 1)

    for flight in payload.get("flights", []):
        flight_id = flight["snapshot_id"]
        flight_used = flight_used_vars[flight_id]
        shipment_vars = x_by_flight.get(flight_id, [])
        volunteer_vars = y_by_flight.get(flight_id, [])

        if shipment_vars:
            model.Add(nb_be_vars[flight_id] == sum(shipment_vars))
            model.Add(sum(shipment_vars) >= 1).OnlyEnforceIf(flight_used)
            model.Add(sum(shipment_vars) == 0).OnlyEnforceIf(flight_used.Not())
            model.Add(nb_be_vars[flight_id] <= LEGACY_MAX_BE_PER_FLIGHT)
            model.Add(
                charge_vars[flight_id]
                == sum(
                    int(shipment_by_id[shipment_id]["equivalent_units"])
                    * x_vars[(shipment_id, flight_id)]
                    for shipment_id in shipment_flights
                    if (shipment_id, flight_id) in x_vars
                )
            )
            capacity_units = flight.get("capacity_units")
            if capacity_units is not None:
                model.Add(charge_vars[flight_id] <= int(capacity_units))
            max_cartons_per_flight = flight.get("max_cartons_per_flight")
            if max_cartons_per_flight is not None:
                model.Add(
                    sum(
                        int(shipment_by_id[shipment_id]["carton_count"])
                        * x_vars[(shipment_id, flight_id)]
                        for shipment_id in shipment_flights
                        if (shipment_id, flight_id) in x_vars
                    )
                    <= int(max_cartons_per_flight)
                )
            for shipment_id in shipment_flights:
                if (shipment_id, flight_id) in x_vars:
                    model.Add(x_vars[(shipment_id, flight_id)] <= flight_used)
        else:
            model.Add(flight_used == 0)
            model.Add(nb_be_vars[flight_id] == 0)
            model.Add(charge_vars[flight_id] == 0)

        if volunteer_vars:
            model.Add(sum(volunteer_vars) >= 1).OnlyEnforceIf(flight_used)
            model.Add(sum(volunteer_vars) == 0).OnlyEnforceIf(flight_used.Not())
        else:
            model.Add(flight_used == 0)

    for (shipment_id, flight_id), x_var in x_vars.items():
        z_list = z_by_shipment_flight.get((shipment_id, flight_id), [])
        if z_list:
            model.Add(sum(z_list) == x_var)
        else:
            model.Add(x_var == 0)

    for (volunteer_id, flight_id), y_var in y_vars.items():
        z_items = z_by_volunteer_flight.get((volunteer_id, flight_id), [])
        z_vars_for_pair = [item[1] for item in z_items]
        if z_vars_for_pair:
            for z_var in z_vars_for_pair:
                model.Add(z_var <= y_var)
            model.Add(sum(z_vars_for_pair) >= y_var)
            volunteer_equiv_capacity = volunteer_by_id[volunteer_id].get("max_colis_vol")
            if volunteer_equiv_capacity is None:
                volunteer_equiv_capacity = LEGACY_EQUIV_CAPACITY_PER_VOLUNTEER
            model.Add(
                sum(
                    int(shipment_by_id[shipment_id]["equivalent_units"]) * z_var
                    for shipment_id, z_var in z_items
                )
                <= int(volunteer_equiv_capacity) * y_var
            )
        else:
            model.Add(y_var == 0)

    grouped_by_volunteer_and_physical = defaultdict(list)
    for (volunteer_id, flight_id), y_var in y_vars.items():
        physical_key = flight_by_id[flight_id].get("physical_flight_key") or str(flight_id)
        grouped_by_volunteer_and_physical[(volunteer_id, physical_key)].append(y_var)
    for y_list in grouped_by_volunteer_and_physical.values():
        if len(y_list) > 1:
            model.Add(sum(y_list) <= 1)

    for volunteer_id, entries in y_by_volunteer.items():
        ordered_entries = sorted(
            entries,
            key=lambda item: _flight_datetime_key(flight_by_id[item[0]]),
        )
        for index, (flight_id_a, var_a) in enumerate(ordered_entries):
            dt_a = _flight_datetime_key(flight_by_id[flight_id_a])
            for flight_id_b, var_b in ordered_entries[index + 1 :]:
                dt_b = _flight_datetime_key(flight_by_id[flight_id_b])
                if abs((dt_b - dt_a).total_seconds()) < LEGACY_MIN_HOURS_BETWEEN_FLIGHTS * 3600:
                    model.Add(var_a + var_b <= 1)

    flights_by_destination = defaultdict(list)
    for flight in payload.get("flights", []):
        flights_by_destination[str(flight.get("destination_iata") or "")].append(
            flight["snapshot_id"]
        )
    for destination_iata, flight_ids in flights_by_destination.items():
        rule = payload.get("destination_rules_by_iata", {}).get(destination_iata, {})
        weekly_frequency = _coerce_int(rule.get("weekly_frequency"))
        if weekly_frequency and weekly_frequency > 0:
            model.Add(
                sum(flight_used_vars[flight_id] for flight_id in flight_ids) <= weekly_frequency
            )

    grouped_by_physical_flight = defaultdict(list)
    for flight in payload.get("flights", []):
        physical_key = flight.get("physical_flight_key") or ""
        if physical_key:
            grouped_by_physical_flight[physical_key].append(flight["snapshot_id"])

    for flight_ids in grouped_by_physical_flight.values():
        if len(flight_ids) > 1:
            model.Add(sum(flight_used_vars[flight_id] for flight_id in flight_ids) <= 1)
        candidate_flights = [
            flight_id
            for flight_id in flight_ids
            if x_by_flight.get(flight_id) and y_by_flight.get(flight_id)
        ]
        if len(candidate_flights) < 2:
            continue
        min_route_pos = min(
            int(flight_by_id[flight_id].get("route_pos") or 1) for flight_id in candidate_flights
        )
        for flight_id in candidate_flights:
            if int(flight_by_id[flight_id].get("route_pos") or 1) <= min_route_pos:
                continue
            model.Add(flight_used_vars[flight_id] == 0)
            for var in x_by_flight.get(flight_id, []):
                model.Add(var == 0)
            for var in y_by_flight.get(flight_id, []):
                model.Add(var == 0)
            for var in z_by_flight.get(flight_id, []):
                model.Add(var == 0)

    weighted_expr = sum(
        _shipment_weight(shipment_by_id[shipment_id]) * x_var
        for (shipment_id, _flight_id), x_var in x_vars.items()
    )
    mission_vars = {}
    volunteer_availability_weights = {}
    for volunteer in payload.get("volunteers", []):
        volunteer_id = volunteer["snapshot_id"]
        entries = y_by_volunteer.get(volunteer_id, [])
        max_missions = len(entries)
        mission_var = model.NewIntVar(0, max_missions, f"missions_{volunteer_id}")
        mission_vars[volunteer_id] = mission_var
        if entries:
            model.Add(mission_var == sum(var for _, var in entries))
        else:
            model.Add(mission_var == 0)
        volunteer_availability_weights[volunteer_id] = max(
            1,
            _volunteer_availability_minutes(volunteer),
        )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    solver.parameters.num_search_workers = 8

    model.Maximize(weighted_expr)
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("Planning solver found no feasible solution.")
    model.Add(weighted_expr >= int(round(solver.ObjectiveValue())))

    model.Minimize(sum(flight_used_vars.values()))
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("Planning solver failed during flight minimization.")
    model.Add(sum(flight_used_vars.values()) <= int(round(solver.ObjectiveValue())))

    model.Minimize(sum(y_vars.values()))
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("Planning solver failed during volunteer minimization.")
    model.Add(sum(y_vars.values()) <= int(round(solver.ObjectiveValue())))

    excess_vars = []
    for volunteer_id, mission_var in mission_vars.items():
        excess = model.NewIntVar(
            0, len(y_by_volunteer.get(volunteer_id, [])), f"excess_{volunteer_id}"
        )
        model.Add(excess >= mission_var - 1)
        model.Add(excess >= 0)
        excess_vars.append(excess)
    if excess_vars:
        model.Minimize(sum(excess_vars))
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise RuntimeError("Planning solver failed during excess mission minimization.")
        model.Add(sum(excess_vars) <= int(round(solver.ObjectiveValue())))

    compatibility_option_expr = sum(
        len(volunteers_by_shipment_flight.get((shipment_id, flight_id), [])) * x_var
        for (shipment_id, flight_id), x_var in x_vars.items()
    )
    model.Maximize(compatibility_option_expr)
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("Planning solver failed during compatibility option maximization.")
    model.Add(compatibility_option_expr >= int(round(solver.ObjectiveValue())))

    weighted_availability_terms = [
        mission_vars[volunteer_id] * volunteer_availability_weights[volunteer_id]
        for volunteer_id in mission_vars
    ]
    if weighted_availability_terms:
        model.Minimize(sum(weighted_availability_terms))
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise RuntimeError("Planning solver failed during availability minimization.")

    chronological_assignment_expr = sum(
        flight_order[flight_id] * x_var for (_shipment_id, flight_id), x_var in x_vars.items()
    )
    model.Minimize(chronological_assignment_expr)
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("Planning solver failed during chronological tie-break.")
    model.Add(chronological_assignment_expr <= int(round(solver.ObjectiveValue())))

    z_selection_order_expr = sum(z_order[key] * z_var for key, z_var in z_vars.items())
    model.Maximize(z_selection_order_expr)
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("Planning solver failed during assignment tie-break.")
    model.Add(z_selection_order_expr >= int(round(solver.ObjectiveValue())))

    model.Minimize(sum(flight_used_vars.values()))
    status = solver.Solve(model)
    status_name = solver.StatusName(status)

    selected = []
    for (shipment_id, volunteer_id, flight_id), z_var in z_vars.items():
        if solver.Value(z_var) != 1:
            continue
        shipment = shipment_by_id[shipment_id]
        flight = flight_by_id[flight_id]
        selected.append(
            {
                "shipment_snapshot_id": shipment_id,
                "flight_snapshot_id": flight_id,
                "volunteer_snapshot_id": volunteer_id,
                "assigned_carton_count": shipment["carton_count"],
                "equivalent_units": shipment["equivalent_units"],
                "priority": shipment["priority"],
                "priority_rank": shipment.get("priority_rank", shipment["priority"]),
                "route_pos": int(flight.get("route_pos") or 1),
                "physical_flight_key": flight.get("physical_flight_key") or str(flight_id),
                "reference": shipment.get("reference") or "",
                "departure_date": flight.get("departure_date") or "",
            }
        )
    selected = _rebalance_assignments_by_flight(selected, payload)
    selected.sort(
        key=lambda item: (
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
