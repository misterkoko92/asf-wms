# Cartons Ready Status Skip Confirmation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add guarded status-jump confirmations to `/scan/cartons/`, require shipment assignment when jumping directly to `Étiqueté`, add a `Tout sélectionner` control, and replace the list summary columns with a concrete `Produits` column.

**Architecture:** Keep the legacy Django `/scan/cartons/` route and existing bulk toolbar, but add explicit helper functions for visible-status progression and skipped-step calculation, extend the POST contract to accept a final target status plus optional shipment assignment, and add a page-local scan module that intercepts bulk submits and drives the confirmation modal. Reuse the existing editable-shipment dataset so the toolbar and modal stay aligned.

**Tech Stack:** Django views/templates/helpers, legacy scan static modules, Django test suite via `./.venv/bin/python manage.py test`

---

### Task 1: Lock The New Helper Contracts Through Failing Unit Tests

**Files:**
- Modify: `wms/tests/carton/tests_carton_view_helpers.py`
- Modify: `wms/carton_view_helpers.py`

**Step 1: Write the failing tests**

Add unit coverage for:

- the formatted `product_rows` payload built from carton items
- shipment-option-like row data staying stable after the table change
- helper functions that resolve visible workflow order and skipped intermediate labels

Example assertions:

```python
self.assertEqual(
    row["product_rows"],
    [
        {"label": "Compresses", "quantity": 50, "display": "Compresses x 50"},
        {"label": "Gants", "quantity": 2, "display": "Gants x 2"},
    ],
)
self.assertEqual(resolve_visible_carton_step(CartonStatus.PACKED), CartonStatus.PACKED)
self.assertEqual(
    build_skipped_visible_status_labels(CartonStatus.DRAFT, CartonStatus.ASSIGNED),
    ["En préparation", "Disponible"],
)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.carton.tests_carton_view_helpers -v 2
```

Expected:
- FAIL because the row payload and skip helpers do not exist yet

**Step 3: Write minimal implementation**

In `wms/carton_view_helpers.py`:

- add visible-order helpers for the list workflow
- add skipped-step label resolution
- expose `product_rows` and per-line `display`
- keep current badge/status payload intact

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 2: Add Failing Handler Tests For Confirmed Status Jumps

**Files:**
- Modify: `wms/tests/carton/tests_carton_handlers.py`
- Modify: `wms/carton_handlers.py`

**Step 1: Write the failing tests**

Add handler coverage for:

- direct bulk `PACKED -> LABELED` without skip confirmation metadata staying ignored
- confirmed jump to `LABELED` assigning the chosen editable shipment and marking the carton labeled
- confirmed jump to `LABELED` failing when the shipment id is missing
- confirmed jump to `ASSIGNED` from `DRAFT` applying the final status directly
- unconfirmed skip requests being ignored

Example:

```python
request = self.factory.post(
    "/scan/cartons/",
    {
        "action": "bulk_mark_cartons_labeled",
        "selected_carton_ids": [str(carton.id)],
        "confirm_skipped_statuses": "1",
        "bulk_shipment_id": str(target_shipment.id),
    },
)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.carton.tests_carton_handlers -v 2
```

Expected:
- FAIL because the handler cannot distinguish guarded skip requests yet

**Step 3: Write minimal implementation**

In `wms/carton_handlers.py`:

- add helpers that resolve current and target visible steps
- require `confirm_skipped_statuses=1` when intermediate steps are skipped
- require `bulk_shipment_id` for confirmed jumps to `LABELED`
- when confirmed, assign shipment first if needed, then persist the final status
- keep editable/locked shipment safeguards and success messaging

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 3: Add Failing View Tests For The Updated Cartons Table

**Files:**
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `templates/scan/cartons_ready.html`
- Modify: `wms/views_scan_shipments.py`

**Step 1: Write the failing tests**

Add view assertions for:

- `Tout sélectionner` button presence in the selection header
- `Produits` header presence
- absence of `Emplacement`, `Remplissage`, and `Contenu`
- rendering of one product line per row using `Nom x quantité`
- shipment selector labels shown as `REFERENCE - IATA - SHIPPER`

Example:

```python
self.assertContains(response, "Tout sélectionner")
self.assertContains(response, "Produits")
self.assertNotContains(response, "Emplacement")
self.assertNotContains(response, "Remplissage")
self.assertNotContains(response, "Contenu")
self.assertContains(response, "Compresses x 50")
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments.ScanShipmentViewsTests -v 2
```

Expected:
- FAIL because the current template still renders the old columns and shipment labels

**Step 3: Write minimal implementation**

Update:

- `templates/scan/cartons_ready.html` to render the new table structure and modal shell
- `wms/views_scan_shipments.py` shipment-option builder to format labels as `REFERENCE - IATA - SHIPPER`

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS for the updated list contract

### Task 4: Add The Page-Local Confirmation Module

**Files:**
- Create: `wms/static/scan/modules/cartons-ready.js`
- Modify: `templates/scan/cartons_ready.html`
- Modify: `wms/static/scan/scan.css`

**Step 1: Write the failing tests**

Extend view tests to assert the page now includes:

- modal DOM ids for skip confirmation
- hidden input used to carry confirmation state
- page-local script include for `scan/modules/cartons-ready.js`

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments.ScanShipmentViewsTests.test_scan_cartons_ready_uses_bulk_toolbar_and_open_action -v 2
```

Expected:
- FAIL because the modal shell and script include are missing

**Step 3: Write minimal implementation**

In `wms/static/scan/modules/cartons-ready.js`:

- bind the `Tout sélectionner` button
- inspect selected cartons, current bulk action, and target shipment
- compute whether the request skips one or more steps
- open the confirmation modal when required
- for `LABELED` skip requests, require a shipment selection inside the modal
- on validate, set the hidden confirmation input and submit the form

In the template/CSS:

- render the modal shell and shipment selector
- expose carton row status metadata through `data-*` attributes
- add compact styling for the product-lines column and modal error state

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 5: Re-Verify Focused Flows And Doc Impact

**Files:**
- Modify if needed: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify if needed: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Run focused verification**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.carton.tests_carton_view_helpers \
  wms.tests.carton.tests_carton_handlers \
  wms.tests.views.tests_views_scan_shipments \
  -v 2
```

Expected:
- PASS with no failures in the directly impacted helper, handler, and view suites

**Step 2: Re-check repo reference impact**

Confirm whether the `/scan/cartons/` flow description or shared contract notes now need a short update for:

- skip-confirmation behavior
- required shipment selection when jumping to `Étiqueté`
- `Produits` list-column contract

**Step 3: Make only the minimal doc update required**

Update the matching repo-reference file only if the implementation changed the durable contract rather than a purely local presentation detail.

**Step 4: Re-run the focused verification if docs touched tests or references**

Run the same test command if any runtime file changed during doc-alignment follow-up.
