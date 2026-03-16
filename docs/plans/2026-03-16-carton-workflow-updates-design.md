# Carton Workflow Updates Design

**Date:** 2026-03-16

**Goal:** Update legacy Django carton workflows so carton numbering becomes linear by family, cartons can be edited or deleted until shipped, carton creation captures per-product expiry input, and cartons can be preassigned to a destination before real shipment assignment.

## Scope

- Keep all work on the legacy Django stack only.
- Cover carton creation from:
  - `scan/pack`
  - `scan/shipment/create`
  - `scan/shipment/<id>/edit`
- Cover carton list visibility in `scan/cartons/`.
- Cover carton assignment into real shipments, including destination mismatch confirmation.
- Cover carton packing documents that display expiry dates.

## Non-Goals

- Do not touch paused Next/React migration files.
- Do not redesign the stock receipt flow or actual `ProductLot` FEFO reservation logic.
- Do not redesign shipment tracking, planning, or portal order workflows outside carton-related display changes.
- Do not introduce a separate reservation entity for carton destination preassignment.

## Constraints

- Preserve the current legacy shipment and stock workflows as much as possible.
- Keep carton edits and deletes safe by restoring stock before destructive actions.
- Do not overwrite real stock lot expiry values with manual carton-level input.
- Keep backend validation authoritative even when the UI shows client-side confirmation popups.
- Allow carton modification and deletion while the carton is not shipped, including cartons linked to draft, picking, packed, or planned shipments.
- Keep shipment dispute protection in place.

## Approaches Considered

### 1. Extend `Carton` and carton-item flows in place

- Add the missing carton-level business data directly to the existing carton flow.
- Rework numbering generation, add destination preassignment on `Carton`, and add manual expiry display data on carton items.
- Approved because it fits the current legacy Django flow with minimal structural churn.

### 2. Introduce a dedicated carton reservation model

- Store preassignment and carton preparation metadata in a separate reservation table.
- Rejected because it adds unnecessary persistence and workflow complexity for a narrow feature set.

### 3. Model preassignment as temporary shipments

- Preassign cartons by linking them to fake draft shipments per destination.
- Rejected because it conflates reservation intent with real shipment lifecycle and makes carton edit/delete rules harder to reason about.

## Approved Design

### Numbering

- Replace the current date-based carton auto-numbering with linear family sequences:
  - `MM-00001`, `MM-00002`, ...
  - `CN-00001`, `CN-00002`, ...
- Maintain an independent persistent sequence per family.
- Keep existing carton codes unchanged when editing an existing carton.
- Ensure carton creation from both pack and shipment flows always resolves to one of the supported families and never falls back to `XX-*`.

### Expiry Input

- Do not store expiry on `Carton`.
- Capture manual expiry input per product line during carton creation.
- Recommended persistence:
  - store a nullable display expiry date on carton items
  - keep `ProductLot.expires_on` unchanged as stock truth
- When one product line consumes multiple lots, propagate the same manual expiry value to the created carton items from that line.
- When carton displays aggregate repeated product rows, use the nearest available manual expiry date for that product.
- Packing and shipment documents should prefer the manual carton-item expiry when present and fall back to the lot expiry otherwise.

### Destination Preassignment

- Add `preassigned_destination` on `Carton` as a nullable foreign key to `Destination`.
- Allow preassignment only while no real shipment is linked.
- Show preassignment in the carton list `N° expédition` column as `(IATA)`.
- Once a carton is assigned to a real shipment, clear `preassigned_destination`.
- When assigning a preassigned carton to a shipment with another destination:
  - show a client-side confirmation popup
  - require an explicit confirmation flag in the submitted payload
  - reject the assignment in backend validation if that flag is absent

### Editing and Deleting Cartons

- Add visible `Modifier` and `Supprimer` actions from the carton list for non-shipped cartons.
- Editing flow:
  - open a single-carton edit mode reusing the preparation UI
  - prefill existing carton contents, including manual expiry values
  - atomically unpack the carton, then repack into the same carton record
  - preserve the carton code
  - preserve shipment linkage when the linked shipment remains editable
- Delete flow:
  - confirm with the user
  - unpack the carton to restore stock
  - delete the carton record after successful unpack
- Authorization:
  - allowed while carton status is not `SHIPPED`
  - allowed for cartons linked to shipment statuses `draft`, `picking`, `packed`, or `planned`
  - blocked when the linked shipment is disputed

### UI Surfaces

- `scan/pack`
  - add optional `Destination pre-affectee` field in the top controls
  - add `Date de peremption` beside `Quantite` on each product line
  - disable or hide preassignment when a real shipment reference is supplied
- `scan/shipment/create` and `scan/shipment/<id>/edit`
  - add `Date de peremption` beside `Quantite` for mono-product carton creation lines
  - show preassigned carton destination in carton select labels, for example `MM-00012 (NKC)`
  - trigger mismatch confirmation when selected preassigned cartons target a different destination
- `scan/cartons/`
  - show real shipment reference if present
  - otherwise show `(IATA)` for preassigned cartons
  - otherwise show `-`
  - expose `Modifier` and `Supprimer` only when allowed

## Data and Logic Touchpoints

- `wms/models_domain/shipment.py`
  - carton fields for preassignment and manual expiry support
- `wms/domain/stock.py`
  - numbering generation
  - carton preparation and unpack/repack behavior
- `wms/pack_handlers.py`
  - pack form parsing, destination preassignment, expiry propagation
- `wms/forms.py`
  - pack and shipment forms
- `wms/shipment_helpers.py`
  - shipment line parsing, confirmation flag handling
- `wms/scan_carton_helpers.py`
  - available carton payload labels
- `wms/carton_view_helpers.py`
  - carton list display rules and action visibility
- `wms/carton_handlers.py`
  - carton delete and status action handling
- `wms/views_scan_shipments.py`
  - carton edit route and pack/carton list views
- `wms/static/scan/scan.js`
  - new line fields
  - mismatch confirmation popup
  - carton select labels
- `wms/print_context.py`
  - document expiry display fallback behavior
- `templates/scan/pack.html`
- `templates/scan/shipment_create.html`
- `templates/scan/cartons_ready.html`
- print templates already rendering expiry values through existing context keys

## Testing Strategy

- Add domain tests for:
  - linear `MM` / `CN` numbering
  - preserving code across carton edit
  - delete flow restoring stock
- Add handler tests for:
  - pack creation with preassignment
  - clearing preassignment on real shipment assignment
  - backend rejection of destination mismatch without confirmation
  - acceptance with confirmation
- Add form/helper tests for:
  - expiry line parsing
  - preassigned carton labels in payload helpers
- Add view/template tests for:
  - expiry fields on pack and shipment pages
  - `(IATA)` display in carton list shipment column
  - edit/delete action visibility
- Add document tests for:
  - manual expiry preferred over lot expiry
  - fallback to lot expiry when manual expiry is absent

## Validation

- Run focused carton domain, shipment handler, form, view, and print tests.
- Re-run UI tests covering pack and shipment pages where expiry fields and confirmation behavior are visible.
- Keep implementation scoped to carton workflows and carton-related document output.
