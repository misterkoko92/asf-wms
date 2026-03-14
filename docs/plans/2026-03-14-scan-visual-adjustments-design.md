# Scan Visual Adjustments Design

**Date:** 2026-03-14

**Goal:** Deliver a first visual-adjustments batch on the legacy Scan Django pages, grouped by page, without entering the separate FAQ/import audit batch.

## Scope

- Keep all work on the legacy Django stack only.
- Deliver the approved batch on these pages:
  - `scan/stock`
  - `scan/cartons_ready`
  - `scan/shipments_ready`
  - `scan/receive_pallet`
  - `scan/prepare_kits`
  - `scan/pack`
  - `scan/shipment_create`
  - `scan/shipments_tracking`
- Treat `scan/faq` and `scan/import` as a separate later batch.

## Non-Goals

- Do not touch paused Next/React migration files.
- Do not refactor the full Scan design system.
- Do not rewrite the shipment-create form flow from scratch.
- Do not fold the FAQ/import work into this batch.

## Constraints

- Preserve current legacy Scan routes and handlers.
- Prefer template/CSS changes when the request is purely visual.
- For shipment-ready equivalent-unit counts, reuse the exact planning equivalence rules instead of inventing a page-local computation.
- For shipment-create selects, preserve existing post payloads and progressive reveal behavior.

## Approaches Considered

### 1. Template/CSS-only changes everywhere

- Fastest approach for purely visual fixes.
- Rejected for the full batch because `scan/shipments_ready` needs a real equivalent-units computation and `scan/shipment_create` needs select grouping logic.

### 2. Hybrid per page

- Use template/CSS for presentational fixes.
- Use helper/view code only where the request needs data reshaping or calculated fields.
- Use targeted front-end JS only for the dynamic shipment-create selects.
- Approved because it keeps the blast radius small while meeting the requested behavior.

### 3. Shared-component refactor

- Would create reusable switch/select/radio abstractions.
- Rejected because the request is a focused correction batch and not a design-system refactor.

## Approved Design

### `scan/stock`

- Rework the `include_zero` switch markup to match the working `form-check form-switch` presentation already used on Scan admin contact forms.
- Remove the `Ajouter catégorie` and `Ajouter entrepôt` buttons from the page action row.
- Leave filtering behavior and context generation unchanged.

### `scan/cartons_ready`

- Keep the existing status update select but add an explicit dropdown affordance on the control so the choice list is visually obvious.
- Rename the displayed label for carton status `packed` from `Prêt` to `Disponible` on this page only.
- Reduce `Marquer étiqueté` to `btn-sm` and move it to tertiary styling.
- Make the status column content occupy the full column width and center the label/button content.
- Preserve current carton state values and existing update handlers.

### `scan/shipments_ready`

- Rename the first header to `NUMERO EXPEDITION` and allow a two-line header.
- Add a new `Nb Colis Equivalent` column immediately after `Nb colis`.
- Compute equivalent units in `shipment_view_helpers` with:
  - `ShipmentUnitInput`
  - `resolve_shipment_unit_count`
  - active `ShipmentUnitEquivalenceRule` records
- Format `ready_at` the same way as `created_at`: date then time on a new line.
- Apply more distinctive status styling per shipment state on this page without globally redefining every Scan badge.
- If width becomes tight, shrink `Date mise en disponible` and `Actions` first.

### `scan/receive_pallet`

- Realign radio controls in `Type de fichier` so each option is rendered inline as radio then label.
- Apply the same inline-radio cleanup to the PDF pages mode area while staying within the current page structure.
- Leave upload and import behavior unchanged.

### `scan/prepare_kits`

- Merge the two top cards into one consistent panel structure.
- Add left/right interior spacing so labels and controls are no longer flush against the border.
- Preserve the current kit data loading and preparation flow.

### `scan/pack`

- Add vertical spacing below `Ajouter un produit`.
- Rework the `confirm_defaults` switch to match the stable Scan switch style.
- Remove the `Scan` button from the shipment/location action row.
- Keep `Ajouter emplacement` on a single line.
- Remove the dynamic `Texte` scan button from product rows.
- Rename the row-level `Scan` button to `Scanner un code barre ou QR Code`.
- Leave the packing handlers and generated document links intact.

### `scan/shipment_create`

- Keep the existing progressive form sections and post actions.
- Update shipper select rendering into three blocks:
  - `AVIATION SANS FRONTIERES` first when present
  - destination-linked shippers
  - all remaining shippers
- Update recipient select rendering into three blocks:
  - recipient linked to the destination correspondent
  - recipients linked to the selected shipper + destination pair
  - other destination-linked recipients
- When only one correspondent choice is available, show the contact directly instead of exposing a meaningless dropdown, while still submitting the real field value.
- Add a second `Enregistrer un brouillon` button immediately above `Créer expédition`, reusing the same `save_draft` action as the existing top-of-page draft button.

### `scan/shipments_tracking`

- Change `Suivi/MAJ` to primary styling.
- Change `Clore le dossier` to secondary styling.
- Keep the existing enabled/disabled state logic intact.

## Data and Logic Touchpoints

- `wms/shipment_view_helpers.py`
  - extend shipments-ready rows with equivalent-unit counts and page-specific status styling hooks
- `wms/shipment_helpers.py`
  - enrich shipment contact payload data so JS can render the approved select groupings deterministically
- `wms/static/scan/scan.js`
  - adjust only the shipment-create contact filter rendering and pack line button labels

## Testing Strategy

- Add or update focused tests in:
  - `wms/tests/views/tests_scan_bootstrap_ui.py`
  - `wms/tests/views/tests_views_scan_shipments.py`
  - `wms/tests/views/tests_views_scan_stock.py`
  - `wms/tests/shipment/tests_shipment_view_helpers.py`
  - `wms/tests/scan/tests_scan_shipment_handlers.py` only if a Python-side action path changes
- Prefer assertion of HTML text/classes/context over introducing new browser tests unless the existing suite already covers the exact surface.

## Baseline Note

- The isolated worktree baseline is not fully green on `main`.
- Pre-existing failures observed before any changes in this batch:
  - `wms.tests.views.tests_views_scan_shipments.ScanShipmentsViewsTests.test_scan_shipment_pages_render_native_english`
  - `wms.tests.views.tests_views_scan_stock.ScanStockViewsTests.test_scan_stock_pages_render_native_english_when_runtime_disabled`
- These failures concern native English rendering expectations and are outside the requested visual batch.

## Validation

- Run targeted red/green tests for each affected page/helper area.
- Re-run the focused visual batch test suite after implementation.
- Run `git diff --check` before reporting completion.
