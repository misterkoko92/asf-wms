# W3.2d Dashboard Destination Week Trend Design

## Goal

Enrich the existing `Destinations à risque` block on the legacy scan dashboard with a compact
current-week versus previous-week trend readout, so local ops can spot whether a destination is
worsening before opening the shipment queue.

## Scope

- legacy Django dashboard only
- mirrored contract in `api/v1/ui/dashboard`
- strict reuse of the existing destination and destination-week aggregate helpers
- compact comparative readout inside the existing block
- no new persistence layer and no new dashboard section

## Why This Lot Exists

`W3.2b` made destination risk visible in the dashboard.

`W3.2c` made destination-week aggregates queryable through the API.

The next useful step is not another endpoint and not a heavier dashboard table. Operators already
have the current top risky destinations. What is still missing is one compact answer:

- is this destination getting worse this week or stabilizing versus last week?

That answer belongs directly in the existing destination-risk block, not in a detached time-series
surface.

## Approaches Considered

### 1. Add a compact weekly comparison inside the existing destination-risk rows

Recommended.

Pros:

- keeps the dashboard readable
- reuses the existing ranking and block placement
- makes the weekly API aggregate operational immediately
- avoids opening a mini-BI surface too early

Cons:

- requires one more shared row contract to keep aligned between HTML and UI API

### 2. Add a second weekly table under `Destinations à risque`

Pros:

- more explicit historical readout

Cons:

- duplicates information already available through `destination-weeks`
- makes the dashboard denser and less cockpit-like

### 3. Keep weekly comparison API-only

Pros:

- smallest UI change

Cons:

- low operational value for day-to-day scan cockpit usage
- forces manual cross-reading of API payloads

## Recommended Architecture

Keep the `Destinations à risque` section where it is.

Do not add new cards and do not add a second table.

Instead, extend each existing row with a compact week-over-week trend payload derived from
`build_destination_week_workflow_projection_rows(...)`.

The existing destination-risk ranking remains the source of truth for which rows are visible.
The weekly trend layer only enriches those visible rows.

## Weekly Trend Contract

Each destination-risk row gains:

- `current_week_label`
- `current_week_score`
- `previous_week_label`
- `previous_week_score`
- `trend_delta`
- `trend_direction`
- `trend_label`

The UI API mirrors these same keys in `destination_risk_rows[]`.

## Weekly Score Rule

The score must stay explicit and product-readable.

Recommended formula:

- `weekly_score = delayed_shipment_count + open_dispute_count + critical_shipment_count`

This keeps the signal simple:

- delays matter
- disputes matter
- critical dossiers matter again, intentionally, so clearly severe weeks do not disappear into a
  flat additive score

No weighted settings or configurable scoring in this local phase.

## Week Mapping Rules

- `current_week_*` is computed from the current ISO week of the dashboard runtime date
- `previous_week_*` is computed from the previous ISO week
- when a destination has no bucket for one of those weeks, the score is `0`
- labels use the existing bucket notation: `YYYY-Www`

## Trend Rules

- `trend_delta = current_week_score - previous_week_score`
- `trend_direction = up` when delta > 0
- `trend_direction = down` when delta < 0
- `trend_direction = flat` when delta == 0
- `trend_label` is human-readable:
  - `+N`
  - `-N`
  - `stable`

## Rendering Rules

Keep the table compact.

Replace the single-column risk readout with:

- `Semaine`
- `S-1`
- `Tendance`

The rest of the row stays operational:

- destination
- current delays
- open disputes
- dominant blockage
- oldest open dossier
- dossier CTA

No sparkline, no chart, no badge system more complex than the current table needs.

## Filtering Behavior

The current dashboard destination filter still applies before computing the block.

This means:

- with no destination filter, the top risky destinations remain global
- with one destination selected, the same destination gets its current-week and previous-week trend

No extra period control is added in this lot.

## API Mirror

Extend `GET /api/v1/ui/dashboard/` only.

Do not add a new UI endpoint.

The legacy dashboard and the UI API must derive the trend payload from the same helper so the row
shape does not drift.

## Out Of Scope

- new summary cards
- second destination weekly table
- dashboard charting
- configurable trend scoring
- export/BI work
- adding weekly trend rows into `À traiter maintenant`

## Testing Strategy

Keep the lot narrow and TDD-driven.

Required proof:

- destination-risk rows expose current-week and previous-week scores plus delta
- missing weekly buckets fall back to `0`
- dashboard HTML renders the compact weekly comparison columns
- UI dashboard API mirrors the same trend fields
- the dashboard destination filter still applies to the enriched rows
