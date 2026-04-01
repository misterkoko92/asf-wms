# W3.1 Planning Flight Capacity Cockpit Design

## Goal

Enrich the existing planning version cockpit with a preventive flight-capacity view, so local ops can
spot tension, critical load, and overload before changing assignments.

## Scope

- legacy Django planning cockpit only
- no new page and no public API in this lot
- read-only capacity indicators on top of existing planning snapshots
- flight-centric presentation with destination as context
- no mutation rule change and no new persistence layer

## Why This Lot Exists

The current planning cockpit already shows assignments grouped by flight and exposes raw capacity as
`used_equivalent_units / capacity_units`.

That is useful, but still too weak for fast operator arbitration. The cockpit does not yet answer
clearly:

- which flights are close to saturation
- which flights are already critical
- which flights are overloaded
- how much remaining capacity is still available in the version as a whole

The next useful step is therefore not export, not BI, and not another surface. It is a stronger
capacity readout inside the existing version cockpit.

## Approaches Considered

### 1. Integrate a flight-capacity block directly in the version cockpit

Recommended.

Pros:

- matches the existing operator workflow
- reuses current planning dashboard and snapshots
- keeps local tuning fast
- no navigation split

Cons:

- adds one more planning contract to keep aligned between stats and templates

### 2. Add a separate planning capacity page

Pros:

- clearer isolation

Cons:

- unnecessary navigation cost
- premature for local optimization

### 3. Export-only capacity data

Pros:

- easy to inspect externally

Cons:

- weak operator value
- does not improve the planning cockpit itself

## Recommended Architecture

Keep the main planning surface unchanged:

- `templates/planning/version_detail.html`

Extend the existing dashboard payload produced by:

- `wms/planning/stats.py`
- `wms/planning/version_dashboard.py`

Render the new capacity information through the existing planning partials, primarily:

- `templates/planning/_version_stats_block.html`
- `templates/planning/_version_planning_block.html`

## Data Model And Computation

No new model and no new table.

Computation stays derived from:

- `PlanningAssignment`
- `PlanningFlightSnapshot`
- `PlanningShipmentSnapshot`

Each flight row should expose:

- `flight_snapshot_id`
- `flight_number`
- `departure_date`
- `departure_time`
- `destination_iata`
- `capacity_units`
- `equivalent_total`
- `remaining_units`
- `utilization_pct`
- `load_state`
- `load_state_label`

## Load-State Rules

Keep thresholds explicit and local-phase simple:

- `ok` when utilization `< 80%`
- `tension` when utilization `>= 80%` and `< 95%`
- `critical` when utilization `>= 95%` and `<= 100%`
- `overload` when utilization `> 100%`

`remaining_units` can become negative in overload, and that is intentional because it makes
over-capacity explicit instead of hiding it.

## Cockpit Summary

Add four summary cards to the version cockpit:

- `Vols en tension`
- `Vols critiques`
- `Vols en surcharge`
- `Capacité restante totale`

These cards are informative only in this lot. They do not block publication or assignment changes.

## Flight Table

Add a compact `Charge vols` table ordered by operator urgency.

Recommended columns:

- vol
- destination
- capacité
- charge
- reste
- taux
- état

Ordering:

1. overload
2. critical
3. tension
4. ok
5. departure date/time
6. flight number

This keeps the most urgent flights at the top while preserving operator chronology inside each state.

## Placement In The Existing Cockpit

Recommended placement:

- keep the current `Planning` block as the main assignment detail area
- surface the capacity summary in `Stats`
- add the compact `Charge vols` table before the detailed per-flight assignment cards

This preserves the current reading order:

- header
- priorities
- section nav
- capacity summary and flight load
- detailed flight assignments
- secondary summaries

## Constraints

- no automatic assignment warning modal
- no hard validation on solve or publish
- no configurable thresholds in runtime settings yet
- no destination-first regrouping in this lot

## Out Of Scope

- export/BI
- public or DRF planning endpoint
- automatic blocking of overloaded flights
- per-destination planning rollups
- rebalancing suggestions

## Testing Strategy

Keep the lot narrow and operator-facing.

Required proof:

- `build_version_stats` exposes remaining capacity, utilization, and load state per flight
- `build_version_dashboard` carries the enriched flight rows to the template layer
- version detail HTML renders the new summary cards and `Charge vols` table
- planning smoke still reaches the cockpit with the new block in place
