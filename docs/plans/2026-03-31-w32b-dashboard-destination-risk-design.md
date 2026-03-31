# W3.2b Dashboard Destination Risk Design

## Goal

Expose the destination-level workflow aggregates directly in the legacy scan dashboard so local ops can
spot which destinations require intervention before drilling into individual shipment dossiers.

## Scope

- legacy Django dashboard only
- mirrored contract in `api/v1/ui/dashboard`
- read-only reuse of the existing destination aggregate helper
- local-first pilotage surface
- no new persistence layer and no new global dashboard filter

## Why This Lot Exists

`W3.2a` made destination risk queryable through the API.

That contract is useful, but still too far from day-to-day operations. The scan dashboard is now the
main local cockpit for urgent work, SLA alerts, disputes, and workflow blockages. Destination-level
risk needs to appear in the same surface, with a short action-oriented list instead of another detached
endpoint.

## Approaches Considered

### 1. Add a dedicated dashboard block driven by the aggregate helper

Recommended.

Pros:

- reuses the already-stabilized destination aggregate contract
- keeps the dashboard operational and readable
- avoids another persistence or synchronization layer
- gives the UI API the same reusable readout

Cons:

- introduces one more dashboard section to keep aligned with the API mirror

### 2. Add destination aggregate cards only, without rows

Pros:

- smallest UI footprint

Cons:

- not actionable enough
- forces operators to switch endpoints or inspect raw API payloads

### 3. Add a full destination cockpit page first

Pros:

- richer pilotage potential

Cons:

- premature for the local optimization phase
- duplicates navigation before the core dashboard contract is stable

## Recommended Architecture

Add a new dashboard section:

- `Destinations à risque`

The section sits after `Blocages workflow` and before `Pilotage`.

It is backed by the existing destination aggregate helper and exposes:

- three summary cards
- a top-5 action table

The legacy HTML view and the UI API return the same data shape, with the API acting as the explicit
shared contract.

## Summary Cards

The block exposes exactly three cards:

- `Destinations critiques`: count of destination rows with at least one critical shipment
- `Destinations avec litiges`: count of destination rows with at least one open dispute
- `Plus ancien dossier ouvert`: max `oldest_open_segment_age_hours` across visible destinations

Each card links to the new dashboard anchor so the operator lands directly on the detailed block.

## Table Contract

Show at most five rows ordered by operational urgency, reusing the aggregate sort order.

Each row exposes:

- `destination_id`
- `destination_label`
- `critical_shipment_count`
- `open_dispute_count`
- `top_blockage_category`
- `oldest_open_segment_age_hours`
- `url`
- `cta_label`

`url` should point to `scan_shipments_tracking` filtered by the destination id so the operator lands on
the concrete shipment queue for that destination.

## Formatting Rules

- `top_blockage_category` must stay human-readable in both HTML and API payloads
- `oldest_open_segment_age_hours` is displayed as an hour value with one decimal place
- if a destination has no active blockage category, show a stable fallback label rather than an empty cell

## Filtering Behavior

The existing dashboard destination filter continues to apply before computing the block.

This means:

- with no filter, the block shows the top risky destinations globally
- with one destination selected, the block narrows to that destination only

No new filter control is added in this lot.

## Pending Action Policy

This block is informative and navigational, but it should not feed `À traiter maintenant` yet.

Reason:

- shipment-level pending actions already represent concrete work items
- pushing destination aggregates into the same queue would duplicate urgency signals and reduce clarity

## API Mirror

Add two new keys to `GET /api/v1/ui/dashboard/`:

- `destination_risk_summary_cards`
- `destination_risk_rows`

This keeps the destination-risk contract aligned between the legacy dashboard and future local UI
consumers.

## Out Of Scope

- new dashboard filters
- time-series destination trends
- CSV or BI export
- destination-specific settings or thresholds
- adding destination aggregates into `pending_actions`

## Testing Strategy

Keep the lot narrow and TDD-driven.

Required proof:

- the dashboard context exposes the new summary cards and rows
- the HTML renders the new section and top risky destination rows
- the UI API mirrors the same keys and content
- the dashboard destination filter applies to the new block
