# W3.2c Destination Week Workflow Aggregates Design

## Goal

Add a first time-bucketed pilotage endpoint by destination and ISO week on top of the
shipment workflow read model, so local ops can see where planned shipment waves are degrading
over time without introducing a new persistence layer.

## Scope

- legacy Django and DRF only
- local-first reporting contract
- read-only aggregation on top of `ShipmentWorkflowProjection`
- ISO week buckets anchored on `planned_at`
- no dashboard HTML surface in this lot
- no new materialized aggregate table

## Why This Lot Exists

`W3.2a` gave one current aggregate row per destination.

That is enough to rank current risk, but not enough to answer:

- whether a destination is getting worse week over week
- whether delays are concentrated on one planned wave or spread across many
- whether disputes and critical dossiers are isolated spikes or recurring patterns

The next useful step is therefore not a new UI block. It is a stable API contract for
`destination x ISO week`, still derived from the same shipment-level read model.

## Approaches Considered

### 1. Add a dedicated endpoint grouped by destination and ISO week

Recommended.

Pros:

- contract stays explicit and stable
- no ambiguity with the current destination aggregate shape
- no new write path
- easy to reuse later for dashboard slices or export

Cons:

- one more endpoint to maintain

### 2. Extend `GET /api/v1/workflow-projections/destinations/` with `group_by=iso_week`

Pros:

- fewer routes

Cons:

- one endpoint would expose two row shapes
- filter and sorting rules would become harder to reason about
- makes client code more fragile

### 3. Persist a `destination x week` read model

Pros:

- strongest long-term scaling story

Cons:

- premature for the local phase
- adds synchronization burden before the contract is validated

## Recommended Architecture

Add one read-only endpoint:

- `GET /api/v1/workflow-projections/destination-weeks/`

The endpoint aggregates existing `ShipmentWorkflowProjection` rows grouped by:

- `destination_id`
- ISO week-year of `planned_at`
- ISO week number of `planned_at`

Rows without `planned_at` are excluded from this aggregate in the local phase.

## Response Contract

One row represents one `(destination, ISO week)` bucket.

Fields:

- `bucket_key`
- `iso_year`
- `iso_week`
- `bucket_label`
- `bucket_start`
- `bucket_end`
- `destination_id`
- `destination_label`
- `shipment_count`
- `open_shipment_count`
- `open_dispute_count`
- `delayed_shipment_count`
- `critical_shipment_count`
- `oldest_open_segment_age_hours`
- `top_blockage_category`
- `projected_at_max`

## Aggregation Rules

- `bucket_key`: `<destination_id>:<iso_year>-W<iso_week>`
- `bucket_label`: `YYYY-Www`
- `bucket_start` / `bucket_end`: Monday / Sunday bounds of the ISO week in local date format
- `shipment_count`: total projected rows in the bucket
- `open_shipment_count`: rows with `is_closed=false`
- `open_dispute_count`: rows with `has_open_dispute=true`
- `delayed_shipment_count`: rows with `delay_state in (new, persistent, critical)`
- `critical_shipment_count`: rows with `delay_state=critical`
- `oldest_open_segment_age_hours`: max `segment_age_hours` among open rows
- `projected_at_max`: max `projected_at` in the bucket

## Dominant Blockage Rule

`top_blockage_category` should stay product-readable.

Recommended tie-breaking:

- count blockage categories on open rows only
- when counts are tied, prefer the most severe value

Severity order:

- `suivi`
- `cloture`
- `creation_expedition`
- empty

## Filters

Filters are applied before grouping.

Keep the existing shipment-projection filters where they still make sense:

- `destination_id`
- `shipment_status`
- `current_segment`
- `delay_state`
- `has_open_dispute`
- `active_blockage_category`
- `is_closed`
- `projected_since`

Add period-specific filters:

- `iso_year`
- `iso_week`
- `limit`

## Sorting

Default ordering should prioritize recent operational risk:

1. `iso_year` desc
2. `iso_week` desc
3. `critical_shipment_count` desc
4. `open_dispute_count` desc
5. `oldest_open_segment_age_hours` desc
6. `destination_label` asc

## Out Of Scope

- dashboard HTML rendering
- charting or sparkline contracts
- CSV export
- persisted `destination x week` projections
- aggregation on anchors other than `planned_at`

## Testing Strategy

Keep the lot TDD and API-first.

Required proof:

- ISO-week rows aggregate counts correctly from `planned_at`
- rows without `planned_at` are excluded
- filters are applied before grouping
- default ordering is week-first then risk-first

The first tests should live in `api/tests/tests_views_extra.py`.
