# Scan Operational Cockpit Refresh Design

**Date:** 2026-03-30

## Goal

Improve the operator clarity of three legacy Django scan pages:
- `/scan/dashboard/`
- `/scan/shipments-tracking/`
- `/scan/orders-view/`

The target is not a visual redesign for its own sake. The target is faster operational reading:
- remove low-signal visualization on the dashboard
- surface exceptions and next actions on shipment tracking
- turn the orders page into an action-oriented review cockpit

## Context

Recent scan work already introduced clearer legacy Django cockpit patterns on:
- `templates/scan/cartons_ready.html`
- `templates/scan/shipments_ready.html`
- `templates/scan/shipment_dossier.html`

Those pages now read better because they prioritize:
- explicit status pills
- compact action blocks
- density that still remains scannable

The three pages in scope still lag behind that direction:
- the dashboard keeps a destination bar chart that does not materially help decision-making
- shipment tracking spends too much table width on raw dates and not enough on exception visibility
- orders view reads like an administrative list rather than a decision surface

Validated direction from discussion:
- remove the dashboard chart instead of replacing it
- keep `shipments-tracking` and `orders-view` as table-backed pages
- add a light cockpit layer above the tables
- make disputes/litiges visually unavoidable

## Scope

### In Scope

- legacy Django view/template/CSS changes for the three scan pages
- presenter/helper changes needed to expose clearer page context
- targeted tests for the new view contracts and UI shell
- local scan styling only

### Out of Scope

- Next/React migration scope
- translation work
- business-rule changes for shipment progression, dispute handling, order approval, or shipment creation
- API/UI API payload changes
- shared UI primitive promotion unless strictly necessary

## Problem Summary

### Dashboard

Current problems:
- the chart occupies prime space without improving decision quality
- chart-specific filters add visual noise
- `Pilotage` is split between KPI reading and a weak chart

Operator need:
- read the page once
- identify priorities
- navigate into the right operational view

### Shipment Tracking

Current problems:
- the table is dominated by historical timestamps
- dispute state is easy to miss because it appears as small inline text
- the screen does not tell the operator what to do next

Operator need:
- spot disputes and overdue dossiers immediately
- know the next expected step without decoding five tracking columns
- jump into `Suivi/MAJ` or closure fast

### Orders View

Current problems:
- the page shows data but not workload shape
- status review is visible, but action priority is weak
- refusal/change-request guidance is pushed into long secondary table rows

Operator need:
- see the review queue and backlog shape immediately
- know whether to validate, recontact, or create a shipment
- keep contact details close to the action decision

## Approaches Considered

### 1. Minimal Cleanup

Idea:
- keep current page structures
- tweak wording and styling only

Pros:
- lowest implementation risk

Cons:
- does not fix the information hierarchy
- keeps disputes and pending actions too subtle

### 2. Light Cockpit Overlay, Recommended

Idea:
- keep table-based workflows
- add small high-signal summary cards above each operational table
- refocus each table on status and next action

Pros:
- matches recent `scan` cockpit direction
- improves first-glance readability without losing density
- avoids reopening broader UI governance

Cons:
- requires reshaping both presenters and templates
- needs careful CSS so mobile remains readable

### 3. Full Card-Based Cockpit

Idea:
- replace operational tables with lists/cards only

Pros:
- strong visual simplification

Cons:
- too much density loss for operator workflows
- high regression risk
- less consistent with the current legacy scan shell

## Recommended Decision

Take approach 2.

Each page should keep its operational table, but the page should start with a compact cockpit summary that highlights what matters now.

## Target Design

## 1. Dashboard

### Decision

Remove the shipment chart entirely.

Do not replace it with another chart. The existing KPI cards already cover the useful reading. Another graph would likely reintroduce visual noise without adding operational value.

### Layout

Keep the current high-level section structure:
- `Priorités`
- `Pilotage`
- `Flux`
- `Santé système`

Reshape `Pilotage` into a single full-width KPI panel.

### Filters

Keep only:
- `Destination`
- `Date de début`
- `Date de fin`

Remove:
- `Date de début graphique`
- `Date de fin graphique`
- `État expédition`

### Content Rule

`Pilotage` should become a straightforward period-reading block:
- command volume
- orders in treatment
- orders pending validation/correction
- cartons created
- cartons assigned
- shipments ready

The page header, priority cards, flow sections, and system-health sections remain valid and should stay in place.

### Non-Goals

Do not invent new metrics.
Do not move dashboard semantics into a new shared component.

## 2. Shipment Tracking

### Reading Goal

This page should answer:
- which dossiers are blocked?
- which dossiers need an action now?
- what is the next expected tracking step?

### Page Structure

Top to bottom:
1. page header with total count
2. existing filters for planned week and closed dossiers
3. a summary strip with four clickable operational cards
4. a condensed action-oriented tracking table

### Summary Cards

Recommended cards:
- `Litiges ouverts`
- `Dossiers clôturables`
- `En attente escale`
- `En attente livraison`

These cards are page-local cockpit summaries. They do not replace the table.

If implementation stays simple, cards can link back to the same page without local filtering. If low-risk local filtering is easy, card links may prefilter the table.

### Table Model

Replace the current raw timestamp-heavy table with five columns:
- `Dossier`
- `Parties`
- `Avancement`
- `À faire`
- `Actions`

#### Dossier

Show:
- shipment reference
- visible dispute badge when `is_disputed`
- closed badge when `is_closed`

Dispute must be visible at first glance.

#### Parties

Show:
- shipper name
- recipient name
- carton count

#### Avancement

Show:
- a shipment status pill using existing shipment status tone rules
- one compact date line for the latest relevant completed milestone

The page should stop trying to present the full tracking timeline inline.

#### À faire

Expose a short explicit next action label:
- `Traiter le litige`
- `Confirmer reçu escale`
- `Confirmer livraison`
- `Clore le dossier`
- `Aucune action`

The rule is presentational only. It should be computed from current shipment/dispute/closure/tracking state without changing workflow logic.

#### Actions

Keep:
- `Suivi / MAJ`
- `Clore le dossier`

Existing closure availability logic stays unchanged.

### Priority Rule: Litige

Dispute visibility is the main requirement on this page.

It must appear through three cues:
- a red badge in the `Dossier` column
- a row-level stronger visual treatment
- `À faire = Traiter le litige`

### Non-Goals

Do not embed a full timeline widget.
Do not change dispute or closure business rules.

## 3. Orders View

### Reading Goal

This page should answer:
- what is waiting for ASF review?
- what needs recontact with the association?
- what can be converted into a shipment now?

### Page Structure

Top to bottom:
1. page header with total count
2. summary strip with review/workload cards
3. a denser but more action-oriented table

### Summary Cards

Recommended cards:
- `À valider`
- `Modifications demandées`
- `Validées sans expédition`
- `Refusées`

These cards summarize operator backlog and should link back to the page.

### Table Model

Recommended columns:
- `Commande`
- `Contact`
- `Statut revue`
- `Action attendue`
- `Suite`
- `Documents`

#### Commande

Show:
- creation date
- association name

This identifies the demand first.

#### Contact

Show:
- contact name
- phone
- email

Keep this compact, readable, and directly adjacent to the decision context.

#### Statut revue

Show:
- existing review status pill
- the existing review-status update form in the same cell or directly under the badge

#### Action attendue

Replace long inline explanatory rows with a short explicit action:
- `Valider ou demander des modifications`
- `Recontacter l’association`
- `Créer l’expédition`
- `Aucune action`

#### Suite

Primary contextual action only:
- if approved and no shipment: `Créer l’expédition`
- otherwise no fake CTA

#### Documents

Keep current document links, but present them as a compact action cluster.

### Copy Rule

Remove the extra follow-up rows currently rendered for:
- rejected
- changes requested

Those messages create vertical noise and repeat information that should be summarized in the action column.

## Data / Presenter Changes

The view layer should expose compact presenter-friendly fields instead of pushing all interpretation into templates.

Recommended additions:
- shipment tracking summary card data
- per-tracking-row `status_display`, `priority_badges`, `last_step_label`, `last_step_at`, `next_action_label`, `row_tone`
- orders summary card data
- per-order-row `review_status_display`, `next_action_label`, `can_create_shipment`, `follow_up_tone`

These should live in local helpers/view modules already responsible for those pages:
- `wms/views_scan_dashboard.py`
- `wms/shipment_view_helpers.py`
- `wms/views_scan_orders.py`
- `wms/order_view_helpers.py`

## Styling Direction

Use existing scan patterns:
- `ui-comp-card`
- `ui-comp-panel`
- `ui-comp-actions`
- `ui-comp-status-pill`
- existing scan table wrappers

Add page-local classes where needed instead of creating new shared primitives.

The styling goal is:
- stronger hierarchy
- clearer table cells
- no chart chrome
- explicit dispute emphasis

## Testing Strategy

Add or update targeted tests for:
- dashboard no longer rendering chart panel and chart-specific controls
- shipment tracking exposing summary cards and action-oriented table markers
- shipment tracking dispute visibility in the first column / next-action area
- orders view exposing summary cards and compact next-action content
- bootstrap/UI tests for new shell hooks and class names

Primary test areas:
- `wms/tests/views/tests_views_scan_dashboard.py`
- `wms/tests/views/tests_views_scan_shipments.py`
- `wms/tests/views/tests_views_scan_orders.py`
- `wms/tests/views/tests_scan_bootstrap_ui.py`

## Propagation / Repo Reference Check

This change stays local to scan HTML surfaces, but before closing the work we still need to re-check:
- `docs/repo-reference/03-impact-map.md` section `Change On A Scan Page`
- `docs/repo-reference/04-shared-contracts.md` shared UI contract guidance

Expected propagation surface:
- scan views
- scan templates
- scan CSS
- scan view tests

No business-rule or route contract change is expected.
