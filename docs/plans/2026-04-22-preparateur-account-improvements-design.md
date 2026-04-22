# Preparateur Account Improvements - Design

## Context

The scope stays on the legacy Django `scan` stack.

Translation parity and the paused Next/React migration stay out of scope. The current request targets
the preparateur account, shared scan UI primitives, product scan/creation behavior, order
preparation, carton visibility, and carton printing.

Existing repo anchors:

- preparateur shell and navigation in `templates/scan/base.html` and
  `templates/scan/includes/scan_sidebar_navigation.html`
- preparateur routes and helpers in `wms/views_scan_preparateur.py`,
  `wms/preparateur_session.py`, `wms/preparateur_orders.py`, and `wms/scan_permissions.py`
- pack runtime in `wms/pack_handlers.py`, `wms/forms.py`, `templates/scan/pack.html`,
  `templates/scan/includes/pack_unknown_product_modal.html`, and `wms/static/scan/scan.js`
- shared number input and date/input behavior in `wms/static/scan/modules/core.js` and
  `wms/static/scan/scan-bootstrap.css`
- carton and print routes in `wms/scan_urls.py`, `wms/views_scan_shipments.py`, and
  `wms/shipment_document_handlers.py`

## Goal

Make the preparateur account usable for the next operational wave by fixing visible mobile/tablet
and pack-flow issues, widening carton visibility/printing to all non-shipped cartons, improving
product scan and quick creation, and adding explicit controls for carton generation.

## Validated Decisions

- Mobile and tablet keep the preparateur masthead configured for the shared preparateur account.
- Desktop uses the standard scan masthead.
- `Voir dernier colis` becomes `Voir les colis`.
- `Voir les colis` opens all non-shipped cartons, not only cartons prepared by the active
  preparateur.
- Preparateurs may print any carton, not only cartons linked to their activity.
- The preparateur should only receive the extra access required for non-shipped carton list/detail
  and carton print actions; broad scan staff access stays blocked.
- After an active benevole is selected, the shell keeps only one greeting: `Bonjour Prenom`.
- Product camera scan must allow front/back camera choice.
- Product lookup must try barcode first, then EAN, then UDI.
- The unknown-product popup removes the SKU input, because SKU is generated later.
- The unknown-product popup adds brand and requires the three dimensions plus weight.
- The unknown-product popup includes the CN guidance:
  `Pour les CN, merci de noter le volume du produit (exemple : Sondalis Energy Fibre 500ML)`.
- Shared `+ / -` number inputs must be fixed in the core contract, not page by page.
- Expiration-date entry should move toward a reusable shared date control that works on iOS.
- Command preparation must verify that `Marquer pret` always attaches the carton to the correct
  order shipment.
- MM/CN automatically selects the matching standard carton format.
- Operators may force the number of cartons, with an explicit confirmation when the forced plan
  exceeds the standard packing recommendation.
- The UDI-on-box-only case is treated as a product-packaging problem, not as two unrelated product
  records.

## Design

### 1. Preparateur Shell And Navigation

The preparateur shell becomes responsive by breakpoint:

- mobile/tablet: keep the preparateur two-row masthead
- desktop: render the standard scan masthead

The duplicate greeting in the current preparateur shell is removed. Before active benevole
selection, the shell can fall back to the shared account name. After selection, it renders only
`Bonjour Prenom`.

The sidebar entry `Voir dernier colis` is renamed to `Voir les colis` and points to a non-shipped
carton list. The existing full scan carton list can be reused when the preparateur permission layer
limits access to the appropriate route/actions. If the full scan page exposes actions that should
remain staff-only, the implementation should hide or reject those actions for preparateurs while
keeping read/list/print/edit paths needed by the preparateur flow.

### 2. Carton Access And Printing

Preparateurs can see all cartons that are not shipped. This includes cartons prepared by other
benevoles or staff. The goal is operational continuity: the shared preparateur account must be able
to find and print the carton that is physically in front of the operator.

Printing access is also widened to all cartons. The permission change should stay route-specific:

- allow carton list for non-shipped cartons
- allow carton detail/edit when the carton is not shipped
- allow carton packing-list print surfaces for any carton
- do not grant dashboard, shipment management, admin, contacts, billing, or broad document
  management access

The 403 on the print button is treated as a permission/route contract bug.

### 3. Scan And Product Resolution

Camera choice is added to the scan overlay. The runtime stores the last selected camera mode in
browser storage and uses it for subsequent scans:

- rear camera by default for product/barcode work
- front camera available explicitly

Product matching becomes deterministic and shared:

1. exact barcode
2. exact EAN
3. exact UDI
4. existing fallback behavior such as SKU/name only where already supported

The backend helper and frontend product matcher should agree on this priority to avoid an operator
seeing one result client-side and another result after submit.

### 4. Unknown-Product Popup

The preparateur unknown-product popup becomes a quick incomplete-product creation form, not a full
catalog editor.

Changes:

- remove SKU input
- keep SKU auto-generation in the backend/catalog path
- add brand
- require product name
- require MM/CN family
- require initial quantity and structured location as before
- require length, width, height, and weight
- keep barcode/EAN/UDI/source scan fields as the scannable identifiers
- add the CN instruction text near MM/CN or dimensions

The product remains `is_incomplete=True` after creation and still enters the reviewer workflow.

### 5. Shared UI Core

The recurrent number-input overlap is a shared UI primitive bug. The fix belongs in:

- `wms/static/scan/modules/core.js`
- `wms/static/scan/scan-bootstrap.css`
- UI Lab/tests that document the shared number-input contract

The goal is that values never sit under the `+ / -` controls, including narrow quantity cells.

The iOS expiration-date issue should be handled as a shared date-input contract. The first delivery
can use a shared wrapper around native date inputs with a text fallback or calendar trigger, as long
as the behavior is reusable by scan, portal, benevole, and future account types.

### 6. Command Preparation And Carton Generation

The `Marquer pret` path must be locked by tests around the exact selected order and shipment. A
prepared carton should attach to the order's shipment or create/reuse the correct shipment through
the existing order-shipment link.

MM/CN format selection should be automatic:

- MM products default to `MM Standard`
- CN products default to `CN Standard`

When the generated packing plan recommends multiple cartons, the operator can force a lower or
higher carton count. For example, `53` units may be forced into one carton instead of `50 + 3`.
This must show an explicit warning if the forced carton exceeds known format capacity or weight.
The system should keep an audit-friendly trace by preserving warnings in the plan/session and by
not silently changing stock until `Marquer pret`.

### 7. UDI Box Versus Unit Packaging

The box-only UDI case should not be solved by creating two unrelated products with one hidden
relationship. The cleaner model is:

- one canonical product
- one or more packaging aliases or pack units
- each packaging alias can hold barcode/EAN/UDI/SKU-like identifiers
- each alias defines a unit multiplier, for example `box of 50 -> 50 units`

Operator behavior:

- if the scan matches a packaging alias, the UI can show the matched packaging and quantity factor
- the preparateur can confirm whether the action should count boxes or individual units when
  ambiguity exists
- stock and order preparation continue to reason in canonical units

This is intentionally a separate later task because it touches catalog identity and stock math.

## Alternatives Considered

### A. Keep `Voir dernier colis` And Fix Only The Wrong Redirect

Rejected. It solves the immediate wrong-carton bug but does not match the operational need to view
all open cartons.

### B. Give Preparateurs Full Scan Staff Access

Rejected. It would solve printing/listing quickly but would expose unrelated staff surfaces.

### C. Fix Number Inputs Locally In Pack Only

Rejected. The bug is already recurring across screens and accounts, so local CSS would leave the
shared primitive broken.

### D. Duplicate Products For Box And Unit UDI Cases

Rejected as the long-term model. It risks stock drift and makes product equivalence implicit. A
packaging-alias layer is more explicit and safer.

## Tests

Implementation should add focused tests before production changes:

- preparateur shell breakpoint/greeting/navigation tests
- preparateur permission tests for carton list/detail/print routes
- print-button 403 regression test
- product creation form tests for SKU removal, brand, required dimensions/weight, CN help text
- product lookup priority tests for barcode, EAN, UDI
- frontend/static contract tests for camera choice and product matcher order
- shared number-input CSS/runtime tests
- shared date-input/iOS regression coverage where feasible
- order preparation tests for `Marquer pret` shipment assignment
- packing-plan tests for automatic MM/CN format and forced carton count warnings

## Docs Impact During Implementation

Update `docs/repo-reference/04-shared-contracts.md` when the preparateur sidebar, preparateur pack
contract, shared number-input contract, shared date-input contract, or product identifier contract
changes.

Update `docs/repo-reference/02-key-flows-and-living-tests.md` if the preparateur flow summary or
named reference tests change.
