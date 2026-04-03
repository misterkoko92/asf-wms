# Shipment Document-First, Carton Batch Actions, and Masthead Navigation Design

## Goal

Allow staff to create a shipment dossier before any physical carton exists, keep the shipment number definitive from the start, add true batch carton assignment and batch print actions in `Vue Colis`, and expose previous/next navigation buttons in the legacy mastheads for app usage.

## Working Constraints

- Stay on the legacy Django stack only.
- Translation scope remains paused.
- Keep the internal shipment status `draft` as the existing `Création` phase.
- Remove the user-facing temporary draft workflow built around `EXP-TEMP-*`.
- Preserve current locking rules for planned, shipped, delivered, and disputed shipments.

## Decisions

### 1. Shipment creation becomes document-first

- The minimum required data to create a shipment is:
  - destination
  - shipper contact
  - recipient contact
  - correspondent contact
- Cartons are no longer required at creation time.
- `Nombre de colis` can be empty or zero at creation time.
- `Poids total` stays empty when no carton is attached.
- The shipment is created immediately with a definitive reference from the normal shipment sequence.
- The shipment remains in internal status `Création` until later carton work advances it.
- No extra label such as `À compléter` is added; the existing `Création` label is sufficient.

### 2. The visible draft flow is removed

- The user-facing draft actions disappear from the shipment creation screen.
- The `EXP-TEMP-*` temporary reference flow is removed from the shipment creation UX.
- The multi-product carton action no longer creates a temporary draft first.
- Instead, the system creates the definitive shipment immediately, then redirects to the pack flow with that shipment already targeted.
- Existing save/edit behavior for a modifiable shipment stays in place once the shipment exists.

### 3. Shipment count and weight become derived values

- `Nombre de colis` and `Poids total` are treated as derived display values on the shipment form.
- When no carton is attached, both values render empty.
- When cartons are attached later, the UI recalculates the total weight and the shipment display reflects the actual attached carton count.
- The backend does not require a synthetic placeholder line just to satisfy the form.

### 4. Batch assignment is added to `Vue Colis`

- Multi-selection stays the entry point in `scan/cartons_ready`.
- A new batch action assigns selected cartons to one existing shipment.
- Eligible target shipments are limited to editable shipments only:
  - not planned
  - not shipped
  - not delivered
  - not disputed
- Eligible cartons are limited to cartons that are still mutable:
  - not shipped
  - not locked by a locked/disputed shipment
- The batch action updates:
  - carton `shipment`
  - carton preassignment destination, cleared when assignment succeeds
  - carton status if a transition is required for consistency
  - shipment readiness state through the existing synchronization path
- Mixed batches remain partially successful: eligible cartons are updated and the others are ignored with a clear feedback message.

### 5. Batch picking output becomes per-carton

- Multi-carton `Picking` no longer renders one aggregated list across all selected cartons.
- The grouped picking output renders one block per carton.
- Each block keeps the carton identity visible and isolates the picking content for warehouse usage.
- Existing single-carton picking routes stay unchanged.

### 6. Batch packing lists get global print actions

- The grouped packing-list page remains the batch entry point for multiple cartons.
- It gains two global actions:
  - print all packing lists in continuous-roll format
  - print all packing lists in A4 four-up format
- Per-carton actions can remain on the page, but the global actions become the primary workflow.
- Existing unit print routes remain valid.

### 7. Previous/next buttons are added to legacy mastheads

- Add two history navigation buttons to all legacy mastheads:
  - scan
  - portal
  - planning
  - benevole
- The buttons call browser/app history navigation:
  - previous page
  - next page
- The implementation should use a shared template partial and a lightweight shared JS hook rather than four divergent copies.
- The feature is intentionally generic and does not introduce route-order navigation logic.

## Runtime Areas Expected To Change

### Shipment creation and edit

- `wms/forms.py`
- `wms/scan_shipment_handlers.py`
- `wms/shipment_form_helpers.py`
- `wms/models_domain/shipment.py`
- `wms/views_scan_shipments.py`
- `templates/scan/shipment_create.html`
- `templates/scan/includes/shipment_create_details_panel.html`
- `wms/static/scan/scan.js`

### Carton batch actions and grouped documents

- `wms/carton_handlers.py`
- `wms/views_scan_shipments.py`
- `wms/views_print_docs.py`
- `wms/prepare_kits_helpers.py`
- `templates/scan/cartons_ready.html`
- `templates/scan/shipment_print_bundle_lot.html`
- grouped print templates used by carton bundle routes

### Shared masthead navigation

- `templates/scan/base.html`
- `templates/portal/base.html`
- `templates/planning/base.html`
- `templates/benevole/base.html`
- shared include under `templates/includes/`
- shared CSS and/or JS under `wms/static/scan/` and `wms/static/portal/` if needed

## Test Strategy

### Shipment creation

- add handler tests for zero-carton shipment creation
- replace draft-specific tests with definitive-reference tests
- add view tests for the updated create flow and multi-product redirect
- update bootstrap/UI contract tests that currently assert visible draft buttons

### Carton batch actions and grouped prints

- add carton handler tests for batch shipment assignment
- update scan shipment/carton page tests for the new bulk action controls
- add print/view tests for:
  - per-carton grouped picking output
  - grouped packing-list page global actions

### Masthead navigation

- add or update scan, portal, planning, and volunteer shell tests to assert the shared previous/next controls

## Documentation Propagation Planned During Implementation

- `docs/repo-reference/02-key-flows-and-living-tests.md`
- `docs/repo-reference/03-impact-map.md` if the maintained checklist wording needs to reflect the new batch assignment/print surfaces
- `docs/mvp_spec.md` if it still describes visible draft shipment creation
- `docs/release_checklist.md` and `docs/operations.md` if smoke wording or operator guidance changes
- `templates/scan/faq.html` for the removal of the visible temporary draft workflow

## Non-Goals

- no Next/React work
- no translation/parity work
- no redesign of shipment status vocabulary
- no route-order previous/next navigation system
