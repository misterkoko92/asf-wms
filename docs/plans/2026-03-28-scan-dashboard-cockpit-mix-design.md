# Scan Dashboard Cockpit Mix Design

**Date:** 2026-03-28

## Goal

Reframe the legacy Django `/scan/dashboard/` page as a mixed cockpit that supports both immediate operational triage and short-horizon activity steering, without reopening Next/React migration scope or translation scope.

## Context

The current scan dashboard already exposes useful metrics, but the screen remains hard to read as a first-stop operational page because:
- almost every block uses the same visual weight
- the page is mostly a vertical stack of KPI sections
- filters are split across three separate forms
- urgent signals, weekly reading, and system-health details compete at the same level

The repository already contains the primitives needed to improve the page without creating a new shared UI contract:
- stable local composition around `ui-comp-card`, `ui-comp-panel`, and `ui-comp-actions`
- existing dashboard data groups in `wms/views_scan_dashboard.py`
- guidance from `docs/plans/2026-03-25-ui-lab-page-header-demo-design.md`
- stable usage rules from `docs/plans/2026-03-25-core-stable-usage-rules.md`

Validated product direction from discussion:
- the page must serve both `triage opérationnel` and `pilotage`
- the selected direction is a `mix des deux`
- the first screen should answer `what needs action now?`
- the next screen level should answer `how is activity moving this week / period?`
- lower sections can keep denser operational detail

## Scope

### In Scope

- legacy Django scan dashboard under `/scan/dashboard/`
- information hierarchy and section ordering
- local page header composition
- local dashboard toolbar composition
- regrouping of existing cards into `Priorités`, `Pilotage`, `Flux`, and `Santé système`
- responsive behavior for desktop, tablet, and mobile
- targeted dashboard view/template/CSS changes

### Out of Scope

- Next/React surfaces
- translation work
- new business metrics
- metric semantic changes in existing cards
- API/UI API work
- heavy JS interactions or client-side dashboard state
- promotion of `PageHeader` or `Toolbar` into shared stable primitives

## Approaches Considered

### 1. Light Reorganization

Idea:
- keep the current stacked page
- move alerts upward
- group sections more clearly
- add quick anchors

Pros:
- low implementation risk
- low template churn

Cons:
- keeps the page feeling like a widget stack
- does not solve the fragmented filter problem cleanly
- weak improvement in first-glance readability

### 2. Mixed Cockpit, Recommended

Idea:
- give the page a compact top header
- introduce one clear toolbar for the main reading controls
- place urgent cards first
- merge KPI and chart into one steering block
- move deeper operational and system sections lower

Pros:
- strongest hierarchy improvement
- fits the validated `triage + pilotage` intent
- reuses existing data groups and routes
- stays compatible with local legacy composition rules

Cons:
- requires a meaningful template restructure
- needs careful CSS to stay clean on mobile

### 3. Dense Command Center

Idea:
- turn the page into a persistent two-column desktop cockpit
- keep alerts in a sticky side rail
- place metrics and graph in the main rail

Pros:
- very strong for expert users on large screens

Cons:
- higher responsive risk
- more likely to feel over-designed in the current scan shell
- would push beyond the local convergence level of `PageHeader` and `Toolbar`

## Recommended Decision

Take approach 2.

The page should become a mixed cockpit with three reading levels:
1. `agir maintenant`
2. `comprendre la période`
3. `descendre dans le détail`

This preserves the existing backend dashboard value while giving the page a clearer operational rhythm.

## Information Architecture

Top to bottom, the target page structure is:
1. compact page header
2. unified dashboard toolbar
3. quick anchor navigation
4. `Priorités`
5. `Pilotage`
6. `Flux`
7. `Santé système`

The page should stop feeling like ten similar cards and start reading like an operator cockpit with explicit levels.

## Page Header

### Role

The header presents the page itself and exposes high-level scan actions.

It is not:
- a hero
- a KPI banner
- a breadcrumb zone
- a filter toolbar

### Content

Recommended content:
- title: `Tableau de bord scan`
- one short context sentence explaining that the page helps prioritize urgent work and monitor activity
- up to three page-level actions

Recommended actions:
- `Nouvelle expédition`
- `Suivi expéditions`
- `Vue stock`

### Tone Rules

The header must remain:
- compact
- work-oriented
- operational
- visually calmer than the priority strip below

It must not introduce decorative dashboard styling or onboarding copy.

## Unified Toolbar

### Goal

Replace the current feeling of three disconnected filter forms with one visible reading toolbar.

### Visible Controls

The first-line controls should be:
- `destination`
- `kpi_start`
- `kpi_end`
- `shipment_status`

### Advanced Controls

The chart-specific dates:
- `chart_start`
- `chart_end`

should move into a secondary collapsible area labelled as advanced graph-period controls.

Default rule:
- if no chart-specific period is given, the shipment chart keeps following the KPI date window

### Runtime Rule

The backend may keep the current GET parameter structure in `wms/views_scan_dashboard.py`.

The visible UI can be unified even if the view still parses:
- `destination`
- `kpi_start`
- `kpi_end`
- `shipment_status`
- `chart_start`
- `chart_end`

The objective is UI clarity, not a backend query redesign.

## Quick Anchor Navigation

Add one compact local anchor row after the toolbar:
- `Priorités`
- `Pilotage`
- `Flux`
- `Santé`

This is a scan aid, not a secondary navigation system.

It should remain visually light and collapse cleanly on mobile.

## Priorités

### Role

`Priorités` is the first operational block and answers:
- what requires attention now?
- what can block the team if left untouched?

### Composition Rule

Limit this strip to six cards maximum.

Recommended cards:
- `Expéditions prêtes`
- `Blocages workflow`
- `Suivi en retard`
- `Litiges ouverts`
- `Stock bas`
- `Queue email en échec / bloquée`

### Data Sources

These cards should be assembled from existing dashboard groups rather than from new metrics:
- `shipment_cards`
- `workflow_blockage_cards`
- `tracking_cards`
- `stock_cards`
- `technical_cards`

### Interaction Rule

Each priority card should expose:
- a short label
- a dominant value
- one short help text
- an explicit action label or destination meaning

The operator should understand the next click, not just see a number.

### Visual Rule

Reserve strong tones for real operational attention:
- `danger` for blocking or failing conditions
- `warn` for near-term attention
- neutral or success for everything else

Do not make all cards visually loud.

## Pilotage

### Role

`Pilotage` answers:
- how is the current period moving?
- where is shipment activity concentrated?

### Layout

On desktop:
- one two-column section
- KPI grid on the left
- shipment chart on the right

On mobile:
- stack KPI first
- chart second

### KPI Block

Keep the existing six KPI cards, but treat them as neutral information cards, not alert cards.

The KPI grid should remain readable as a compact `2 x 3` steering panel on desktop.

### Shipment Chart Block

The shipment chart should gain more visual space than it has today.

It remains a server-rendered destination aggregation view with:
- shipment count
- equivalent units
- optional shipment status filter

The graph stays in the same conceptual period block as the KPI view, not as an isolated widget later in the page.

## Flux

### Role

`Flux` contains the denser operational sections that matter after the urgent read and the steering read.

### Section Order

Within `Flux`, use this order:
1. `Stock`
2. `Colis`
3. `Réceptions / Commandes`

### Stock

`Stock` should be the richest sub-section in this block because it already contains:
- stock summary cards
- the low-stock table

The low-stock table must stay attached to the stock section and should not appear as a detached table between unrelated blocks.

### Colis

`Colis` remains a compact operational summary grid.

### Réceptions / Commandes

`Réceptions / Commandes` also remains a compact summary grid, calmer than `Priorités`.

## Santé Système

### Role

`Santé système` closes the page and answers:
- is the platform queueing / processing behaving normally?
- are SLA segments drifting?

### Composition

This section should group:
- `Technique / Queue email`
- `Suivi SLA`

It stays visible, but lower in the hierarchy than operational work and activity steering.

Only true failures should use strong tones here.

## Responsive Rules

### Desktop

- header in two zones: copy left, actions right
- toolbar laid out as a readable control strip
- anchor row under toolbar
- priority cards in one high-signal grid
- pilotage in two columns

### Tablet

- header actions wrap below the copy if needed
- toolbar may spread over two clean rows
- priorities remain above pilotage
- pilotage may collapse to one column if space is too tight

### Mobile

Exact page order:
1. header
2. toolbar
3. anchors
4. priorities
5. pilotage
6. stock
7. colis
8. réceptions / commandes
9. santé système

Additional rules:
- no persistent side rail
- no permanent two-column dashboard shell
- actions can become full width when readability improves
- anchor row may scroll horizontally if needed

## Runtime And Contract Notes

- Keep the feature entirely in the legacy Django stack.
- Reuse existing dashboard card computations where possible.
- Compose locally with stable primitives:
  - `ui-comp-card`
  - `ui-comp-panel`
  - `ui-comp-actions`
- Do not promote the page header or toolbar into shared primitives in this ticket.
- Keep the dashboard implementation aligned with `docs/repo-reference/03-impact-map.md` section `Change On A Scan Page`.

## Testing Strategy

Update or add focused coverage for:
- the new top-level dashboard structure
- the unified toolbar shell
- the new section ordering
- presence of the anchor row
- responsive/stable class hooks used by scan bootstrap layout
- continued rendering of existing metric groups inside the new hierarchy

Primary test files:
- `wms/tests/views/tests_views_scan_dashboard.py`
- `wms/tests/views/tests_scan_bootstrap_ui.py`

Primary runtime files:
- `templates/scan/dashboard.html`
- `wms/views_scan_dashboard.py`
- `wms/static/scan/scan-bootstrap.css`
