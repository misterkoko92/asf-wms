# Scan Visual Adjustments Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Apply the approved first batch of legacy Scan visual adjustments while keeping logic changes narrowly scoped to shipment ready metrics and shipment create select grouping.

**Architecture:** Use a hybrid approach. Purely visual requests stay in templates and Scan CSS, shipment-ready equivalent counts are added in Python helpers to stay aligned with planning rules, and shipment-create select grouping stays in the existing `scan.js` dynamic flow with enriched helper payloads.

**Tech Stack:** Django templates, Django view/helpers, legacy Scan JavaScript, unittest-based Django tests, Bootstrap-flavored Scan CSS.

---

### Task 1: Record the page-level HTML expectations in failing tests

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_scan_stock.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

- Add assertions covering:
  - stock page no longer renders `Ajouter catégorie` or `Ajouter entrepôt`
  - stock and pack pages still render the expected switch structure
  - receive-pallet renders the radio controls with the expected inline classes
  - shipments-tracking renders the requested button classes
  - shipment-create renders both draft buttons

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_views_scan_stock \
  wms.tests.views.tests_views_scan_shipments \
  -v 2
```

Expected: new assertions fail on current templates. Ignore the known pre-existing native-English baseline failures unless they expand.

**Step 3: Write minimal implementation**

- Do not implement production code in this task.

**Step 4: Run test to verify it still fails for the new assertions**

Run the same command and confirm the failures point to the new expectations.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_stock.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "test(scan): cover visual adjustment batch"
```

### Task 2: Implement the stock, receive-pallet, prepare-kits, pack, and shipments-tracking template/CSS changes

**Files:**
- Modify: `templates/scan/stock.html`
- Modify: `templates/scan/receive_pallet.html`
- Modify: `templates/scan/prepare_kits.html`
- Modify: `templates/scan/pack.html`
- Modify: `templates/scan/shipments_tracking.html`
- Modify: `wms/static/scan/scan.css`
- Modify: `wms/static/scan/scan-bootstrap.css`

**Step 1: Write the failing test**

- Use the view-level tests from Task 1 as the red bar.

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_views_scan_stock \
  wms.tests.views.tests_views_scan_shipments \
  -v 2
```

**Step 3: Write minimal implementation**

- Update stock switch markup and remove the two admin-add links.
- Rework receive-pallet radio wrappers for inline alignment.
- Merge the prepare-kits top cards into one padded panel.
- Add pack spacing, remove the row-level top `Scan` action, rename the product scan button, and remove the text-scan button.
- Change shipments-tracking button classes as requested.
- Add only the CSS needed to support these renders.

**Step 4: Run test to verify it passes**

Run the same command and confirm the new visual assertions pass, aside from any unchanged known baseline failures.

**Step 5: Commit**

```bash
git add templates/scan/stock.html templates/scan/receive_pallet.html templates/scan/prepare_kits.html templates/scan/pack.html templates/scan/shipments_tracking.html wms/static/scan/scan.css wms/static/scan/scan-bootstrap.css
git commit -m "feat(scan): apply first visual template batch"
```

### Task 3: Add carton page coverage and ship the cartons-ready adjustments

**Files:**
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/tests/carton/tests_carton_view_helpers.py`
- Modify: `templates/scan/cartons_ready.html`
- Modify: `wms/carton_view_helpers.py`
- Modify: `wms/static/scan/scan.css`

**Step 1: Write the failing test**

- Add tests asserting:
  - cartons-ready displays `Disponible` for packed cartons on this page
  - the status column exposes the expected class hooks for full-width centered rendering
  - the `Marquer étiqueté` action uses tertiary/small styling

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.carton.tests_carton_view_helpers \
  -v 2
```

**Step 3: Write minimal implementation**

- Override the packed label in the cartons-ready helper/context only for this page.
- Update the cartons-ready template to add the dropdown affordance wrapper and full-width centered status layout.
- Change `Marquer étiqueté` button classes to tertiary + small.

**Step 4: Run test to verify it passes**

Run the same command and confirm the new cartons-ready assertions pass.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_scan_shipments.py wms/tests/carton/tests_carton_view_helpers.py templates/scan/cartons_ready.html wms/carton_view_helpers.py wms/static/scan/scan.css
git commit -m "feat(scan): refine cartons ready status column"
```

### Task 4: Add failing shipment-ready helper tests for equivalent units and status presentation

**Files:**
- Modify: `wms/tests/shipment/tests_shipment_view_helpers.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

- Add tests asserting:
  - `build_shipments_ready_rows` exposes an `equivalent_carton_count`
  - the helper uses active equivalence rules to compute that count
  - the view/template renders the new `Nb Colis Equivalent` column
  - the ready date is rendered as date + time on separate lines
  - the page exposes page-local status styling hooks for shipment states

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.shipment.tests_shipment_view_helpers \
  wms.tests.views.tests_views_scan_shipments \
  -v 2
```

**Step 3: Commit**

```bash
git add wms/tests/shipment/tests_shipment_view_helpers.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "test(scan): cover shipments ready equivalents"
```

### Task 5: Implement the shipment-ready data and template changes

**Files:**
- Modify: `wms/shipment_view_helpers.py`
- Modify: `templates/scan/shipments_ready.html`
- Modify: `wms/static/scan/scan.css`

**Step 1: Write minimal implementation**

- Build shipment equivalence inputs from carton items.
- Load active `ShipmentUnitEquivalenceRule` values and compute equivalent units in `build_shipments_ready_rows`.
- Expose page-local status style hooks and the equivalent-unit count in row data.
- Update the template with:
  - two-line `NUMERO EXPEDITION`
  - `Nb Colis Equivalent`
  - date/time split rendering
  - width hooks for the requested columns

**Step 2: Run test to verify it passes**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.shipment.tests_shipment_view_helpers \
  wms.tests.views.tests_views_scan_shipments \
  -v 2
```

**Step 3: Commit**

```bash
git add wms/shipment_view_helpers.py templates/scan/shipments_ready.html wms/static/scan/scan.css wms/tests/shipment/tests_shipment_view_helpers.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat(scan): add shipment ready equivalents"
```

### Task 6: Add failing shipment-create payload/render tests

**Files:**
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/tests/shipment/tests_shipment_form_helpers.py`
- Modify: `wms/tests/scan/tests_scan_shipment_handlers.py`

**Step 1: Write the failing test**

- Add tests asserting:
  - shipment-create renders a second draft button above the create button
  - context payloads include the extra metadata needed for grouped shipper/recipient ordering
  - single-option correspondent rendering remains submittable

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.shipment.tests_shipment_form_helpers \
  wms.tests.scan.tests_scan_shipment_handlers \
  -v 2
```

**Step 3: Commit**

```bash
git add wms/tests/views/tests_views_scan_shipments.py wms/tests/shipment/tests_shipment_form_helpers.py wms/tests/scan/tests_scan_shipment_handlers.py
git commit -m "test(scan): cover shipment create grouping"
```

### Task 7: Implement shipment-create payload enrichment and JS grouping

**Files:**
- Modify: `wms/shipment_helpers.py`
- Modify: `templates/scan/shipment_create.html`
- Modify: `wms/static/scan/scan.js`
- Modify: `wms/static/scan/scan.css`

**Step 1: Write minimal implementation**

- Enrich the shipment contact payload with the metadata needed to identify:
  - the canonical ASF shipper
  - destination-linked shippers
  - destination-correspondent-linked recipient
  - shipper+destination recipient bindings
- Update the shipment-create template to add the second draft button and the single-correspondent display hook.
- Update `setupShipmentContactFilters()` in `scan.js` to render the approved three-block ordering and the single-correspondent display mode without changing submitted values.

**Step 2: Run test to verify it passes**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.shipment.tests_shipment_form_helpers \
  wms.tests.scan.tests_scan_shipment_handlers \
  -v 2
```

**Step 3: Commit**

```bash
git add wms/shipment_helpers.py templates/scan/shipment_create.html wms/static/scan/scan.js wms/static/scan/scan.css wms/tests/views/tests_views_scan_shipments.py wms/tests/shipment/tests_shipment_form_helpers.py wms/tests/scan/tests_scan_shipment_handlers.py
git commit -m "feat(scan): group shipment create contact choices"
```

### Task 8: Run the focused regression suite and diff hygiene

**Files:**
- Modify: none

**Step 1: Run the focused regression suite**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_views_scan_stock \
  wms.tests.shipment.tests_shipment_view_helpers \
  wms.tests.carton.tests_carton_view_helpers \
  wms.tests.shipment.tests_shipment_form_helpers \
  wms.tests.scan.tests_scan_shipment_handlers \
  -v 2
```

Expected: all new visual-batch assertions pass. Pre-existing native-English failures on stock/shipments pages may still need explicit disposition if still present and unrelated.

**Step 2: Run diff hygiene**

```bash
git diff --check
```

**Step 3: Commit**

```bash
git add -A
git commit -m "feat(scan): deliver first visual adjustment batch"
```
