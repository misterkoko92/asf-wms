# W2.3 Workflow Blockage Queue Design

## Goal

Turn the existing `workflow_blockage_cards` KPI snapshot into an operator queue that can be
worked item by item from the local V2 cockpit.

## Scope

- legacy Django only
- local-only acknowledgement workflow
- shared HTML/API read contract
- no new business workflow state on `Shipment`, `Order`, or `IntegrationEvent`

## Current Gap

The dashboard already exposes blockage counts, but not the concrete rows an operator must open,
take over, and resolve. The user sees "how many" but not "which one", "who should act", or
"which blockage is already being handled".

## Design Choice

Keep the blockage queue derived at read time and persist only a lightweight operator claim table.

Why:

- keeps business entities unchanged
- avoids duplicating lifecycle state across several aggregates
- supports fast local calibration
- rows disappear naturally once the source issue is resolved

## Blockage Categories

The queue will expose five stable categories.

1. `creation_expedition`
   Old `draft` / `picking` shipments beyond `workflow_blockage_hours`
2. `commande`
   Approved orders without shipment beyond `workflow_blockage_hours`
3. `suivi`
   Open disputes plus persistent / critical SLA tracking alerts
4. `cloture`
   Delivered shipments still open
5. `queue`
   Failed or stale email / document-scan processing incidents

## Row Contract

Each row will expose:

- `blockage_key`
- `category`
- `category_label`
- `label`
- `reference`
- `owner`
- `priority`
- `started_at`
- `age_hours`
- `url`
- `cta_label`
- `is_claimed`
- `claimed_by`
- `claimed_at`
- `claim_state`
- `claim_state_label`

## Claim Persistence

Add a single local table, `WorkflowBlockageClaim`.

Stored fields:

- `blockage_key` unique
- `category`
- `label`
- `reference`
- `owner`
- `claimed_by`
- `claimed_at`
- `updated_at`

Rules:

- claim creates or refreshes the row for the derived blockage key
- release deletes the row
- no historical audit in this wave
- if the source blockage disappears, the claim is simply ignored by the dashboard/API

## Row Derivation Rules

### `creation_expedition`

- source: `Shipment`
- statuses: `draft`, `picking`
- age basis: `created_at`
- owner: `magasin`
- priority:
  - `high` for `picking`
  - `medium` for `draft`
- CTA:
  - `scan:scan_shipment_edit` when the shipment exists

### `commande`

- source: `Order`
- condition: `review_status=approved` and `shipment is null`
- age basis: `created_at`
- owner: `admin`
- priority: `high`
- CTA:
  - `scan:scan_orders_view`

### `suivi`

- sources:
  - open disputes from `Shipment`
  - persistent / critical SLA alerts from `build_sla_alert_rows(...)`
- age basis:
  - dispute: `dispute_opened_at` or `disputed_at` or `created_at`
  - SLA: existing `started_at`
- owner:
  - dispute: `shipment.dispute_owner` if present, else `qualite`
  - SLA: existing SLA owner
- priority:
  - dispute: `high`
  - persistent SLA: `high`
  - critical SLA: `high`
- CTA:
  - `scan:scan_shipment_track`

### `cloture`

- source: `Shipment`
- condition: `status=delivered` and `closed_at is null`
- age basis: `delivered_at`
- owner: `qualite`
- priority: `medium`
- CTA:
  - `scan:scan_shipment_track`

### `queue`

- sources:
  - email queue failed
  - email queue stale processing
  - document scan failed
  - document scan stale processing
- age basis:
  - oldest matching `IntegrationEvent.created_at`
- owner:
  - email queue: `admin`
  - document scan: `qualite`
- priority:
  - stale processing: `high`
  - failed queue incident: `medium`
- CTA:
  - `scan:scan_dashboard` with `#scan-dashboard-health`

## Dashboard Rendering

Keep existing blockage KPI cards. Add a dedicated table section `Blocages workflow` with:

- category
- action
- reference
- owner
- priority
- age
- claim state
- dossier CTA
- claim/release action

Sorting:

1. unclaimed first
2. priority `high` before `medium` before `low`
3. oldest first

The transverse `À traiter maintenant` queue will promote the top unclaimed blockage rows before
stock/order filler actions.

## HTML Actions

`scan_dashboard` will accept POST actions:

- `claim_workflow_blockage`
- `release_workflow_blockage`

Payload:

- `blockage_key`

No note field in this wave.

## API Contract

Mirror the derived queue in `api/v1/ui/dashboard/` with:

- `workflow_blockage_rows`
- `workflow_blockage_summary_cards`

Add a local UI mutation endpoint for parity:

- `POST /api/v1/ui/dashboard/workflow-blockages/claims/`

Payload:

- `action`: `claim` or `release`
- `blockage_key`

## Tests

Minimum proof:

- dashboard context includes the five categories and claim metadata
- POST claim toggles row state on HTML dashboard
- API payload exposes blockage rows and claim metadata
- API POST claim endpoint updates claim state
- queue category appears for stale/failed email and document-scan incidents

## Docs To Update With Implementation

- `docs/repo-reference/02-key-flows-and-living-tests.md`
- `docs/repo-reference/04-shared-contracts.md`
- `docs/operations.md`
- `docs/release_checklist.md`
