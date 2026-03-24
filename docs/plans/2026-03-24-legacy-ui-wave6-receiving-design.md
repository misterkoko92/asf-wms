# Legacy UI Wave 6 Receiving Design

**Date:** 2026-03-24

## Goal

Simplify and harmonize the legacy receiving surfaces by splitting the remaining dense templates into workflow-local sections while preserving the current Django handlers, form names, IDs, stage logic, and local JavaScript behavior.

## Scope

### Target Screens

- `templates/scan/receive_pallet.html`
- `templates/scan/receive.html`
- `templates/scan/receive_association.html`

### Out of Scope

- any Next/React surface,
- any translation/parity work,
- any shared `wms_ui` promotion,
- any refactor of receipt handlers or domain logic.

## Governance Position

### Core Stable Reused As-Is

- `ui-comp-card`
- `ui-comp-title`
- `ui-comp-form`
- `ui-comp-actions`
- Bootstrap table and button levels already in use

### En Convergence To Observe Only

- `Table`
- `EmptyState`
- upload/review card motifs

### Workflow-Local And Explicitly Not Shared

- pallet listing upload,
- column mapping,
- listing review/import confirmation,
- receiving line entry,
- hors-format generation,
- allocation entry.

## Recommended Structure

### `receive_pallet`

Keep the route template as the shell and script host, but move the content into workflow-local includes:

- pallet creation card,
- listing upload card,
- optional mapping card,
- optional review card.

The mapping and review stages stay local to receiving. The file-type and listing-match scripts remain route-local and keep the current `id_*`, `data-field`, `data-lock`, and `pending_token` contracts untouched.

### `receive`

Split the screen into named cards:

- receipt selection,
- receipt creation,
- active receipt summary,
- add line,
- receipt lines,
- empty state when no receipt is selected.

The product datalist and `products_json` payload remain tied to the add-line workflow. No receipt action names or line form field IDs change.

### `receive_association`

Split the screen into:

- association receipt creation card,
- optional allocations card.

The hors-format subsection stays inside the creation card because it is driven by the same form and local JS. The `association-lines-data` and `association-lines-errors` JSON payloads remain route-local.

## Testing Strategy

Add structure-focused assertions in `wms/tests/views/tests_scan_bootstrap_ui.py` for the new section IDs and for preservation of the current hook markers already used by the receiving pages.

Keep `wms/tests/views/tests_views_scan_receipts.py` as the primary regression suite for:

- route rendering,
- context propagation,
- handler response passthrough,
- line error propagation.

Also retain broader receipt creation smoke coverage in `wms/tests/views/tests_views.py`.

## Risks And Controls

- Risk: over-abstracting receiving-specific blocks.
  Control: only route-local includes, no shared component promotion.
- Risk: breaking local JavaScript by moving markup away from expected IDs.
  Control: keep scripts in the route shells and preserve all existing IDs/data attributes.
- Risk: changing form semantics while splitting large cards.
  Control: keep each current form boundary intact unless the design explicitly uses one existing form across multiple visual cards.

## Expected Outcome

Wave 6 should leave the three receiving screens easier to read and maintain, with explicit section boundaries similar to waves 4B and 5, while keeping all receiving behavior unchanged.
