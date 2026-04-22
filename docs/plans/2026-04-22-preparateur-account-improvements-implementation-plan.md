# Preparateur Account Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver the agreed preparateur account fixes on the legacy Django scan stack: responsive shell, all non-shipped carton visibility and printing, product scan/creation improvements, shared input fixes, and safer command-preparation carton generation.

**Architecture:** Keep the work in legacy Django scan adapters and shared legacy UI assets. Start with permission/navigation/print regressions, then shared UI primitives, then product identification and popup validation, then order-preparation packing rules. Keep the packaging-alias model for UDI box/unit handling as a separate catalog task after the immediate operational fixes.

**Tech Stack:** Django views/forms/templates/handlers, Django ORM, legacy scan JavaScript/CSS, UI Lab shared contracts, Django test suite via `./.venv/bin/python manage.py test`.

---

### Task 1: Lock The Preparateur Carton Access Contract

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_scan_preparateur.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing tests**

Add tests proving:

- preparateur sidebar renders `Voir les colis`
- preparateur sidebar no longer renders `Voir dernier colis`
- the `Voir les colis` link points to the scan carton list route, or to a dedicated preparateur
  carton list route if implementation chooses one
- preparateurs can access the carton list
- shipped cartons are not actionable for preparateur edit/print paths
- non-shipped cartons prepared by another user are visible/actionable

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_views_scan_preparateur \
  wms.tests.views.tests_views_scan_shipments -v 2
```

Expected:
- FAIL because the menu still exposes `Voir dernier colis` and preparateur access is not widened
  to the all-non-shipped carton contract.

**Step 3: Implement the minimal permission/navigation change**

Modify:

- `templates/scan/includes/scan_sidebar_navigation.html`
- `wms/scan_permissions.py`
- `wms/views_scan_preparateur.py` if a redirect/helper is kept
- `wms/scan_urls.py` if a dedicated route is introduced
- `wms/views_scan_shipments.py` if carton-list filtering/action gating must become preparateur-aware

Implementation rules:

- rename visible label to `Voir les colis`
- show all non-shipped cartons
- do not filter by `prepared_by`
- keep unrelated scan routes blocked for preparateur users

**Step 4: Run tests to verify they pass**

Run the same command.

Expected:
- PASS.

### Task 2: Fix Preparateur Print 403 For All Cartons

**Files:**
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/scan_permissions.py`
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/shipment_document_handlers.py` only if the 403 is in document authorization
- Modify: `templates/scan/pack.html` or carton templates if the print button URL is wrong

**Step 1: Write the failing tests**

Add tests proving a preparateur can open the print endpoint for:

- a non-shipped carton prepared by the active volunteer
- a non-shipped carton prepared by another user
- a non-shipped carton with no preparateur activity

Add a negative test proving shipped cartons remain blocked if the route should not be operationally
available after shipping.

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2
```

Expected:
- FAIL with the current 403 or missing permission path.

**Step 3: Implement the permission fix**

Keep the permission specific to carton print routes. Do not add broad access to shipment documents,
admin routes, billing, or dashboard.

**Step 4: Run tests to verify they pass**

Run the same command.

Expected:
- PASS.

### Task 3: Make The Preparateur Masthead Responsive And Remove Duplicate Greeting

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `templates/scan/base.html`
- Modify: `wms/static/scan/scan-bootstrap.css`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Write the failing tests**

Add assertions that:

- preparateur pages contain only one user greeting after active volunteer selection
- the rendered greeting is `Bonjour <prenom>` from `request.scan_active_volunteer_greeting_name`
- mobile/tablet preparateur masthead markup remains available
- desktop uses the standard scan masthead classes/structure instead of the preparateur-only masthead
  presentation

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected:
- FAIL because the current template can render both account and volunteer greetings.

**Step 3: Implement the masthead change**

In `templates/scan/base.html`:

- render one preparateur greeting source
- prefer active volunteer first name when present
- keep the shared account fallback only before selection
- keep preparateur mobile/tablet structure
- expose standard desktop scan masthead via CSS/template branching at the relevant breakpoint

In CSS:

- use responsive display classes or media queries
- avoid changing non-preparateur scan masthead behavior

**Step 4: Update repo-reference**

Update the preparateur shell/sidebar section in `docs/repo-reference/04-shared-contracts.md`.

**Step 5: Run tests to verify they pass**

Run the same command.

Expected:
- PASS.

### Task 4: Lock And Fix Shared Number Input Overlap

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Modify: `wms/tests/core/tests_ui.py`
- Modify: `wms/static/scan/modules/core.js`
- Modify: `wms/static/scan/scan-bootstrap.css`
- Modify: `templates/scan/ui_lab.html`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Write the failing tests**

Add/extend tests proving:

- the shared number input reserves value padding derived from actual control width
- compact and default variants expose enough reserved space for readable values
- core runtime keeps the input padding synchronized after enhancement
- UI Lab documents both default and compact examples

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_portal_bootstrap_ui \
  wms.tests.core.tests_ui -v 2
```

Expected:
- FAIL on the new overlap contract assertions.

**Step 3: Implement the shared primitive fix**

Modify only the shared runtime/CSS contract:

- keep `enhanceNumberInput(...)` as the single enhancement point
- compute or reserve padding so text cannot sit behind `+ / -`
- keep `min`, `max`, `step`, `disabled`, `readonly`, `input`, and `change` semantics
- avoid local page-specific padding fixes

**Step 4: Update docs/UI Lab**

Update `templates/scan/ui_lab.html` and the shared number-input section in
`docs/repo-reference/04-shared-contracts.md`.

**Step 5: Run tests to verify they pass**

Run the same command.

Expected:
- PASS.

### Task 5: Introduce A Shared Date Input Contract For Expiration Dates

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py` if portal shares the runtime
- Modify: `wms/static/scan/modules/core.js`
- Modify: `wms/static/scan/scan-bootstrap.css`
- Modify: `templates/scan/includes/pack_unknown_product_modal.html`
- Modify: `templates/scan/includes/receive_add_line_card.html` if adopting the shared date marker there
- Modify: `templates/scan/ui_lab.html`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Write the failing tests**

Add tests that:

- expiration-date fields render a shared `ui-date-input` marker or data attribute
- the shared runtime initializes a reusable date control
- the control keeps a plain `YYYY-MM-DD` form value for Django forms

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_portal_bootstrap_ui -v 2
```

Expected:
- FAIL because no shared date-input contract exists yet.

**Step 3: Implement the minimal shared date control**

Implementation target:

- keep native `input[type=date]` where it behaves correctly
- add a shared fallback/control path that lets iOS users change year, month, and day without being
  stuck after year changes
- preserve submitted value format as `YYYY-MM-DD`

Avoid adding a page-local calendar only for pack.

**Step 4: Update docs/UI Lab**

Add the date control to UI Lab and document it in `docs/repo-reference/04-shared-contracts.md`.

**Step 5: Run tests to verify they pass**

Run the same command.

Expected:
- PASS.

### Task 6: Improve Pack Row Layout For Product Name, Quantity, And Scan Button

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `templates/scan/pack.html`
- Modify: `wms/static/scan/scan-bootstrap.css`

**Step 1: Write the failing test**

Add assertions that the preparateur pack row exposes a stable layout contract:

- product-name cell/input spans the available width before quantity
- quantity stays in its own fixed column
- scan button is rendered below or inside the quantity/action stack, not next to a cramped product
  name field

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected:
- FAIL because the current pack row does not expose the new layout contract.

**Step 3: Implement the layout change**

Prefer CSS grid/flex adjustments in the existing pack template and shared scan CSS. Keep existing
input names and JS hooks stable.

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS.

### Task 7: Add Front/Rear Camera Choice To Scan

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `templates/scan/base.html`
- Modify: `wms/static/scan/scan.js`
- Modify: `wms/static/scan/scan-bootstrap.css`

**Step 1: Write the failing tests**

Add static/template tests proving:

- the scan overlay renders a camera choice control
- the JS defines and uses a stored facing-mode preference
- BarcodeDetector and ZXing paths both read the selected facing mode

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected:
- FAIL because the scan overlay hard-codes rear/environment camera.

**Step 3: Implement camera choice**

In `templates/scan/base.html`, add an accessible segmented/select control for rear/front camera.

In `wms/static/scan/scan.js`:

- default to rear/environment
- store user choice in `localStorage`
- use `facingMode: { ideal: selectedMode }` when possible
- keep fallback behavior when the browser ignores the constraint

**Step 4: Run tests to verify they pass**

Run the same command.

Expected:
- PASS.

### Task 8: Add UDI Fallback To Product Resolution

**Files:**
- Modify: `wms/tests/scan/tests_scan_product_helpers.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/models_domain/catalog.py` if UDI already exists there
- Modify: `wms/models.py` facade only if a model field/export changes
- Modify: `wms/scan_product_helpers.py`
- Modify: `wms/static/scan/scan.js`
- Modify: `templates/scan/pack.html`
- Create migration if `Product.udi` does not exist yet

**Step 1: Write the failing backend tests**

Add tests proving exact-match priority:

1. barcode wins
2. EAN wins when barcode missing
3. UDI wins when barcode/EAN missing

**Step 2: Write the failing frontend/static tests**

Add tests or static assertions proving the product matcher checks barcode before EAN before UDI.

**Step 3: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.scan.tests_scan_product_helpers \
  wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected:
- FAIL because UDI is not part of the shared lookup contract.

**Step 4: Implement UDI support**

If `Product.udi` exists, add it to helper queries, product option payloads, template data, and JS
matching.

If it does not exist, add a nullable indexed field through the catalog domain model and create a
focused migration. Keep it optional for legacy data.

**Step 5: Run tests to verify they pass**

Run the same command.

Expected:
- PASS.

### Task 9: Update Unknown-Product Popup Fields And Validation

**Files:**
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/forms.py`
- Modify: `wms/pack_handlers.py`
- Modify: `templates/scan/includes/pack_unknown_product_modal.html`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Write the failing tests**

Add tests that:

- the unknown-product popup does not render SKU input
- the popup renders brand
- dimensions `length_cm`, `width_cm`, `height_cm` are required
- `weight_g` is required
- CN guidance text is rendered
- a valid form creates an incomplete product with brand, dimensions, and weight
- SKU is generated by existing backend generation behavior instead of user input

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected:
- FAIL because the current popup still exposes SKU and does not require all requested physical
  fields.

**Step 3: Implement the form/template/handler changes**

In `ScanPackUnknownProductForm`:

- remove user-submitted SKU field
- add/require brand if not already present
- add required dimensions and weight
- keep at least one scannable identifier rule across barcode/EAN/UDI/source scan as applicable

In `create_preparateur_unknown_product_from_pack(...)`:

- pass dimensions and weight to `Product`
- use existing SKU generation path or add a small helper if needed
- keep `is_incomplete=True`

**Step 4: Update repo-reference**

Update the preparateur pack contract in `docs/repo-reference/04-shared-contracts.md`.

**Step 5: Run tests to verify they pass**

Run the same command.

Expected:
- PASS.

### Task 10: Auto-Select MM/CN Standard Carton Formats

**Files:**
- Modify: `wms/tests/scan/tests_scan_pack_helpers.py`
- Modify: `wms/tests/scan/tests_scan_pack_helpers_extra.py`
- Modify: `wms/tests/views/tests_views_scan_preparateur.py`
- Modify: `wms/preparateur_orders.py`
- Modify: `wms/pack_handlers.py`
- Modify: `templates/scan/pack.html` if the selected format is visible/editable

**Step 1: Write the failing tests**

Add tests proving:

- MM uses the `MM Standard` format when it exists
- CN uses the `CN Standard` format when it exists
- existing fallback format behavior still applies when the named format is missing
- both free-pack and order-preparation planning use the same resolver

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.scan.tests_scan_pack_helpers \
  wms.tests.scan.tests_scan_pack_helpers_extra \
  wms.tests.views.tests_views_scan_preparateur -v 2
```

Expected:
- FAIL because current logic mostly uses default/fallback format selection.

**Step 3: Implement a shared format resolver**

Add a small resolver that maps:

- `MM` -> `MM Standard`
- `CN` -> `CN Standard`

Use it from both `wms/preparateur_orders.py` and `wms/pack_handlers.py`.

**Step 4: Run tests to verify they pass**

Run the same command.

Expected:
- PASS.

### Task 11: Verify `Marquer Pret` Uses The Correct Shipment

**Files:**
- Modify: `wms/tests/views/tests_views_scan_preparateur.py`
- Modify: `wms/tests/orders/tests_pack_handlers.py` if handler-level coverage is closer
- Modify: `wms/preparateur_orders.py`

**Step 1: Write the failing or locking tests**

Add tests for:

- order with existing shipment: `Marquer pret` packs into that shipment
- order without shipment: `Marquer pret` creates exactly one shipment and links it to that order
- two orders in session/history: marking one plan ready cannot attach cartons to the other order's
  shipment
- stale plan/order mismatch is rejected with an operator-visible error

**Step 2: Run tests to verify behavior**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_preparateur \
  wms.tests.orders.tests_pack_handlers -v 2
```

Expected:
- Either FAIL on a real bug or PASS as locking coverage before the next change.

**Step 3: Implement only if needed**

If tests expose a bug, fix `_ensure_preparateur_shipment(...)`,
`mark_preparateur_plan_carton_ready(...)`, or the view/session guard so the selected order remains
the source of truth.

**Step 4: Run tests to verify they pass**

Run the same command.

Expected:
- PASS.

### Task 12: Add Forced Carton Count For Order Preparation

**Files:**
- Modify: `wms/tests/views/tests_views_scan_preparateur.py`
- Modify: `wms/tests/scan/tests_scan_pack_helpers.py`
- Modify: `wms/preparateur_orders.py`
- Modify: `wms/views_scan_orders.py` or `wms/views_scan_preparateur.py` depending where the POST lives
- Modify: `templates/scan/preparateur_order_prepare.html`

**Step 1: Write the failing tests**

Add tests proving:

- generated plan still defaults to automatic carton count
- operator can set a forced carton count
- `53` units can be forced into one carton
- forced plan displays warnings when capacity/weight constraints are exceeded
- stock is not mutated until `Marquer pret`
- forced count is stored in the preparateur order plan session

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_preparateur \
  wms.tests.scan.tests_scan_pack_helpers -v 2
```

Expected:
- FAIL because the current plan is generated automatically without operator override.

**Step 3: Implement the override**

Add a small form/control to the order-preparation workbench:

- default blank/auto
- minimum `1`
- clear warning when forced count differs from auto count
- preserve the plan in session

Keep all stock movement inside `Marquer pret`.

**Step 4: Run tests to verify they pass**

Run the same command.

Expected:
- PASS.

### Task 13: Document Packaging Alias Follow-Up For Box-Only UDI

**Files:**
- Create: `docs/plans/2026-04-22-product-packaging-aliases-follow-up.md`
- Modify: `docs/deferred-follow-ups.md` if this repo tracks deferred work there

**Step 1: Write the follow-up note**

Document:

- one canonical product
- packaging aliases with barcode/EAN/UDI identifiers
- unit multiplier
- scan behavior when a box alias maps to multiple units
- stock/order math remains in canonical units

**Step 2: Do not implement the model in this wave**

This is intentionally split from the immediate preparateur fixes because it touches catalog identity,
stock quantities, import matching, and possibly receipt/listing flows.

### Task 14: Final Repo-Reference And Verification Pass

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/03-impact-map.md` only if a checklist changes
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Re-read relevant reference sections**

Re-check:

- scan page impact map
- print/document behavior
- shared UI primitives
- scan preparateur pack contract

**Step 2: Update docs**

Update repo-reference docs for any changed route, permission, shared UI primitive, or named
reference test.

**Step 3: Run focused verification**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_portal_bootstrap_ui \
  wms.tests.views.tests_views_scan_preparateur \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.orders.tests_pack_handlers \
  wms.tests.scan.tests_scan_pack_helpers \
  wms.tests.scan.tests_scan_pack_helpers_extra \
  wms.tests.scan.tests_scan_product_helpers \
  wms.tests.core.tests_ui -v 2
```

Expected:
- PASS.

**Step 4: Run broader smoke if time allows**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.core.tests_flow \
  wms.tests.views.tests_views_scan_orders \
  wms.tests.views.tests_views_imports -v 2
```

Expected:
- PASS.

---

## Execution Notes

- Use TDD for each task: write the failing test, run it, implement, rerun.
- Keep commits or review chunks grouped by task where practical.
- Do not touch `frontend-next/`, `wms/views_next_frontend.py`, `wms/ui_mode.py`, or paused
  translation scope.
- Do not add FR/EN parity work or translation-specific tests.
- Keep product-packaging aliases as a documented follow-up unless explicitly re-scoped.
