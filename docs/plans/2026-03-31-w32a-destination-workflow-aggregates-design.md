# W3.2a Destination Workflow Aggregates Design

## Goal

Add a first aggregated pilotage endpoint by destination on top of the shipment workflow read model,
so local ops can identify which destinations concentrate delays, disputes, and workflow blockages.

## Scope

- legacy Django and DRF only
- local-first reporting contract
- no new persistence layer in this lot
- no dashboard HTML surface in this lot
- no period/time-series aggregation yet

## Why This Lot Exists

`W2.4` stabilized one queryable row per shipment dossier.

The next useful layer is not another shipment view. It is a destination-level readout answering:

- which destinations are currently the most critical
- where disputes are concentrated
- where workflow is blocked at creation, tracking, or closure
- where lead times already look structurally weak

This gives ops a pilotage lens before opening a broader API v2 or BI/export wave.

## Approaches Considered

### 1. Aggregate directly from `ShipmentWorkflowProjection`

Recommended.

Pros:

- no new write path
- no synchronization burden
- stable enough for local pilotage
- reusable later by dashboard and exports

Cons:

- query cost grows with dataset size
- not yet ideal for heavy external BI traffic

### 2. Add a new persisted destination aggregate table

Pros:

- best long-term for large datasets and repeated reads

Cons:

- premature now
- duplicates synchronization before real scale pressure exists

### 3. Render destination summaries directly on `scan/dashboard`

Pros:

- immediate visual payoff

Cons:

- UI-first would duplicate logic before the aggregate contract is stable
- makes later API consumers depend on dashboard-specific logic

## Recommended Architecture

Add one read-only endpoint:

- `GET /api/v1/workflow-projections/destinations/`

The endpoint aggregates the existing `ShipmentWorkflowProjection` rows grouped by destination.

No new model is added in this lot.

## Response Contract

One row represents one destination.

Fields:

- `destination_id`
- `destination_label`
- `shipment_count`
- `open_shipment_count`
- `closed_shipment_count`
- `open_dispute_count`
- `delayed_shipment_count`
- `critical_shipment_count`
- `creation_blockage_count`
- `tracking_blockage_count`
- `closure_blockage_count`
- `avg_total_to_delivery_hours`
- `avg_delivery_to_close_hours`
- `oldest_open_segment_age_hours`
- `top_delay_state`
- `top_blockage_category`
- `projected_at_max`

## Aggregation Rules

- `shipment_count`: total projected rows in the destination group
- `open_shipment_count`: rows with `is_closed=false`
- `closed_shipment_count`: rows with `is_closed=true`
- `open_dispute_count`: rows with `has_open_dispute=true`
- `delayed_shipment_count`: rows with `delay_state in (new, persistent, critical)`
- `critical_shipment_count`: rows with `delay_state=critical`
- `creation_blockage_count`: rows with `active_blockage_category=creation_expedition`
- `tracking_blockage_count`: rows with `active_blockage_category=suivi`
- `closure_blockage_count`: rows with `active_blockage_category=cloture`
- `avg_total_to_delivery_hours`: average on non-null `lead_hours_total_to_delivery`
- `avg_delivery_to_close_hours`: average on non-null `lead_hours_delivery_to_close`
- `oldest_open_segment_age_hours`: max `segment_age_hours` among open rows
- `projected_at_max`: max `projected_at` in the group

## Dominant Status Rules

`top_delay_state` and `top_blockage_category` should stay product-readable, not mathematically opaque.

Recommended tie-breaking:

- count the values on open rows only
- when counts are tied, prefer the most severe value

Delay-state severity order:

- `critical`
- `persistent`
- `new`
- `on_time`

Blockage-category severity order:

- `suivi`
- `cloture`
- `creation_expedition`
- empty

This keeps the destination row oriented toward the most urgent operational risk.

## Filters

Filters are applied before grouping:

- `delay_state`
- `has_open_dispute`
- `current_segment`
- `active_blockage_category`
- `is_closed`
- `projected_since`

This keeps the contract aligned with the shipment-projection endpoint and makes the aggregate reusable
for later dashboard slices.

## Sorting

Default ordering should prioritize operational urgency:

1. `critical_shipment_count` desc
2. `open_dispute_count` desc
3. `oldest_open_segment_age_hours` desc
4. `destination_label` asc

## Out Of Scope

- time buckets by day/week
- destination+period materialized tables
- CSV export
- dashboard UI block
- external BI auth/permissions beyond the existing authenticated API surface

## Testing Strategy

Keep the lot TDD and narrow.

Required proof:

- destination rows aggregate counts and averages correctly
- filters are applied before grouping
- default sorting reflects criticity and age

The first tests should live in API-level contract tests.
