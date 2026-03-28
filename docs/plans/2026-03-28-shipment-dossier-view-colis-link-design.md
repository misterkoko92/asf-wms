# Shipment Dossier View Colis Link Design

**Date:** 2026-03-28

## Goal

Add a `Voir les colis` action on the legacy `Dossier expédition` page so operators can jump directly to `Vue Colis` already filtered on the current shipment reference.

## Context

The shipment dossier is now the main operational entry point after clicking `Ouvrir` from the shipment lists. It already centralizes administration, documents, and tracking, but it does not provide a direct way to inspect only the cartons attached to the current shipment.

`Vue Colis` already exists as the legacy carton list under `/scan/cartons/`, but it currently opens as the full list. That forces operators to switch screens and manually re-find the shipment context they just opened.

Validated product direction from discussion:
- add a `Voir les colis` button on the dossier page
- place it next to the existing dossier navigation actions
- open `Vue Colis` already filtered on the shipment number
- keep the work on the legacy Django stack

## Scope

### In Scope

- legacy `Dossier expédition` header action bar
- legacy `/scan/cartons/` server-side filtering by shipment reference
- visible reminder in `Vue Colis` when a shipment filter is active
- targeted scan view tests covering the new navigation and filter behavior

### Out Of Scope

- Next/React surfaces
- translation parity work
- new carton routes or a dedicated shipment-carton screen
- carton business status changes
- changes to shipment tracking, documents, or close rules

## Approaches Considered

### 1. Server-side filter on the existing carton list, recommended

Idea:
- add a dossier button linking to `/scan/cartons/?shipment_reference=<reference>`
- make `scan_cartons_ready` filter the queryset on that query parameter
- show the active filter in the page chrome

Pros:
- simplest mental model
- shareable URL
- reliable result count and empty state
- no new route or JS dependency

Cons:
- requires a small view change and a small template change

### 2. Client-side pre-filled table filter

Idea:
- keep the existing full queryset
- use JS or the table filter row to pre-fill the shipment column filter

Pros:
- little or no backend change

Cons:
- weaker contract because the page still loads unrelated cartons
- filtered count and empty states are less explicit
- more fragile because it depends on frontend table behavior

### 3. Dedicated “cartons of this shipment” route

Idea:
- add a new route dedicated to cartons linked to one shipment

Pros:
- explicit route name and semantics

Cons:
- unnecessary new surface for a narrow navigation improvement
- extra maintenance cost for very little product value

## Recommended Decision

Take approach 1.

Use the current shipment dossier as the origin surface and the existing `Vue Colis` page as the destination surface. The dossier button should simply carry the shipment reference into the carton list query string. The carton list should then enforce the filter server-side and explain clearly that the page is currently scoped to one shipment.

## UX Behavior

### Shipment Dossier

Add a `Voir les colis` button in the action bar of `templates/scan/includes/shipment_dossier_header.html`.

Expected placement:
- near `Retour aux dossiers`
- same secondary visual weight as navigation actions
- available whenever the dossier itself is available

Expected target:
- `scan:scan_cartons_ready?shipment_reference=<shipment.reference>`

### Vue Colis

When `shipment_reference` is present in the query string:
- filter the carton queryset to cartons linked to a shipment whose reference matches the provided value
- keep the page title and table structure unchanged
- add a visible reminder that the page is filtered on one shipment
- add a simple `Voir tous les colis` link back to the unfiltered carton view

If the reference matches no carton:
- render the normal page
- show the filter reminder
- show the existing empty state with zero results

## Runtime Design

### View Layer

`wms/views_scan_shipments.py::scan_cartons_ready` should:
- read `shipment_reference` from `request.GET`
- trim the value
- apply a queryset filter on `shipment__reference__iexact` when the value is non-empty
- pass the active filter string into template context

No new handler module is needed. The behavior is local to the existing legacy scan view.

### Template Layer

`templates/scan/includes/shipment_dossier_header.html` should render the new dossier action.

`templates/scan/cartons_ready.html` should render a small informational block when the filter is active, for example:
- `Expédition filtrée : EXP-123`
- `Voir tous les colis`

This should stay local to the carton page rather than becoming a shared UI primitive.

## Testing

Minimum proof for the change:
- a view test covering dossier rendering of the new `Voir les colis` link
- a view test covering `/scan/cartons/?shipment_reference=...` and asserting that only cartons from the matching shipment appear
- a view test asserting that the active filter reminder and the unfiltered fallback link render on `Vue Colis`

## Docs Impact

No repo-reference update is required for this change.

Reasoning:
- no route contract changes
- no shipment business rule changes
- no shared UI primitive contract changes
- no release-smoke wording changes
