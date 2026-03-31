# W2.4 Workflow Projection Design

## Goal

Create a stable, queryable workflow read model for shipment dossiers so local pilotage no longer
depends on parsing JSON logs or recomputing everything ad hoc from scattered runtime fields.

## Scope

- legacy Django only
- local-first read model
- shipment dossier projection first
- API/reporting surface first
- no event-store rewrite in this wave

## Why This Wave Exists

Structured workflow logs already exist, but they are still audit-oriented. They are useful for
inspection, not for stable product/reporting queries. We need a read model that answers:

- where a dossier currently is
- how long each step took
- whether a dispute is open or resolved
- whether the dossier is delayed now
- which blockage category is active now

## Approaches Considered

### 1. Full workflow event store

Persist each workflow event in an application table, then build projections from that store.

Pros:

- strongest long-term event architecture
- best future fit for BI and replay

Cons:

- too heavy for the current local V2 phase
- adds double-write complexity everywhere
- backfill and correctness cost are not justified yet

### 2. Read everything live from shipment runtime models

Compute the reporting answer directly from `Shipment`, `ShipmentTrackingEvent`, dispute fields, and
close state on each request.

Pros:

- fastest initial delivery

Cons:

- unstable reporting contract
- repeated complex query logic across consumers
- weaker path toward future exports and external consumers

### 3. Dedicated shipment workflow read model

Recommended.

Persist one recalculable projection row per shipment dossier. The projection is derived from the
existing runtime sources and refreshed after meaningful workflow mutations.

Pros:

- stable API/reporting contract now
- simple local rebuild/backfill story
- keeps audit logs untouched
- clean bridge to future aggregates and exports

Cons:

- one more synchronization layer to maintain

## Recommended Architecture

Add a new model `ShipmentWorkflowProjection`.

It is a read model, not a business source of truth.

Sources:

- `Shipment`
- `ShipmentTrackingEvent`
- structured dispute fields on `Shipment`
- `closed_at`
- existing runtime delay thresholds via `tracking_alert_hours` and `workflow_blockage_hours`

Projection granularity:

- one row per shipment dossier

## Projection Contract

### Identity

- `shipment` FK unique
- `reference`
- `tracking_token`
- `destination_id`
- `destination_label`
- `shipment_status`

### Timeline markers

- `shipment_created_at`
- `planned_at`
- `boarding_ok_at`
- `received_correspondent_at`
- `delivered_at`
- `closed_at`

### Current workflow state

- `current_segment`
- `segment_started_at`
- `segment_age_hours`
- `is_closed`

### Lead times

- `lead_hours_planned_to_boarding`
- `lead_hours_boarding_to_correspondent`
- `lead_hours_correspondent_to_delivery`
- `lead_hours_delivery_to_close`
- `lead_hours_total_to_delivery`

### Dispute state

- `has_open_dispute`
- `dispute_reason`
- `dispute_owner`
- `dispute_opened_at`
- `dispute_resolved_at`
- `dispute_resolution_hours`

### Delay / blockage state

- `delay_state`
- `current_delay_hours`
- `active_blockage_category`

### Projection metadata

- `projected_at`

## Current Segment Rules

- `draft` / `picking` / `packed` without `planned_at` -> `creation_expedition`
- `planned` without `boarding_ok_at` -> `planned_to_boarding`
- `shipped` without `received_correspondent_at` -> `boarding_to_correspondent`
- `received_correspondent` without `delivered_at` -> `correspondent_to_delivery`
- `delivered` without `closed_at` -> `delivery_to_close`
- closed dossier -> `closed`

## Delay State Rules

Use existing runtime thresholds.

- `creation_expedition`
  - compare age since `shipment_created_at` to `workflow_blockage_hours`
- tracking segments
  - compare current segment age to `tracking_alert_hours`
- delivery-to-close
  - compare age since `delivered_at` to `workflow_blockage_hours`

States:

- `on_time`
- `new`
- `persistent`
- `critical`

Classification:

- `new` when age exceeds 1x threshold
- `persistent` when age exceeds 2x threshold
- `critical` when age exceeds 3x threshold

## Active Blockage Category Rules

- `creation_expedition`
- `suivi`
- `cloture`
- empty when no active blockage

This wave deliberately does not project order-only or queue-only blockers; it focuses on shipment
dossier workflow. That keeps the contract coherent and lets Wave 3 aggregates build on a clean
shipment base first.

## Synchronization Strategy

Projection is refreshed by application code, not by parsing logger output.

Refresh triggers in this wave:

- shipment create / edit
- shipment tracking event create
- shipment dispute open / resolve
- shipment case close

Operational rebuild:

- new management command `rebuild_workflow_projections`

Rules:

- recompute from runtime source of truth
- safe to rerun
- no async worker required in this local wave

## API Surface

Add a first reporting endpoint:

- `GET /api/v1/workflow-projections/shipments/`

Returned rows follow the read-model contract above.

Filters in this wave:

- `destination_id`
- `shipment_status`
- `current_segment`
- `delay_state`
- `has_open_dispute`
- `is_closed`
- `projected_since`

## Validation Strategy

- projection unit tests with representative dossiers
- endpoint tests for filters and payload shape
- rebuild command test
- coherence test between source shipment state and projected metrics

## Deferred From This Wave

- aggregate-by-destination endpoint
- time-series endpoint
- CSV export
- external BI contract
- true workflow event store
