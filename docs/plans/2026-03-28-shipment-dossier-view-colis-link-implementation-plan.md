# Shipment Dossier View Colis Link Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `Voir les colis` action on the shipment dossier and make `Vue Colis` open already filtered on the current shipment reference.

**Architecture:** Keep the legacy Django shipment dossier and carton list routes unchanged. Add one dossier navigation link, add one server-side filter in `scan_cartons_ready`, and expose the active shipment filter back to the carton template so the scoped view remains explicit and reversible.

**Tech Stack:** Django views/templates, legacy scan runtime in `wms/views_scan_shipments.py`, Django template partials under `templates/scan/`, Django test suite via `./.venv/bin/python manage.py test`

---

### Task 1: Lock Down The New Navigation Through Failing View Tests

**Files:**
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Reference: `templates/scan/includes/shipment_dossier_header.html`
- Reference: `templates/scan/cartons_ready.html`

**Step 1: Write the failing tests**

Add test coverage for:

```python
def test_scan_shipment_edit_renders_view_colis_link_for_current_shipment(self):
    ...


def test_scan_cartons_ready_filters_by_shipment_reference_querystring(self):
    ...
```

The dossier test should assert that the rendered action bar contains:
- `Voir les colis`
- the `scan:scan_cartons_ready` URL with `shipment_reference=<shipment.reference>`

The carton list test should assert that:
- only cartons belonging to the matching shipment are rendered
- the active filter reminder is visible
- the fallback `Voir tous les colis` link is visible

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments.ScanShipmentsViewsTests.test_scan_shipment_edit_renders_view_colis_link_for_current_shipment \
  wms.tests.views.tests_views_scan_shipments.ScanShipmentsViewsTests.test_scan_cartons_ready_filters_by_shipment_reference_querystring \
  -v 2
```

Expected:
- FAIL because the dossier does not expose the new action yet
- FAIL because `scan_cartons_ready` ignores `shipment_reference`

**Step 3: Write minimal implementation**

Do not widen the scope. Only add:
- the dossier link
- the query-string filter in `scan_cartons_ready`
- the active filter banner in `cartons_ready.html`

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS for both new behaviors

**Step 5: Commit**

```bash
git add \
  wms/tests/views/tests_views_scan_shipments.py \
  wms/views_scan_shipments.py \
  templates/scan/includes/shipment_dossier_header.html \
  templates/scan/cartons_ready.html
git commit -m "feat: link shipment dossier to filtered carton view"
```

### Task 2: Implement Server-Side Carton Filtering

**Files:**
- Modify: `wms/views_scan_shipments.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Use the carton list test from Task 1 as the failing proof:

```python
response = self.client.get(
    reverse("scan:scan_cartons_ready"),
    {"shipment_reference": shipment.reference},
)
assertContains(response, "C-MATCH")
assertNotContains(response, "C-OTHER")
```

**Step 2: Run test to verify it fails**

Run the carton list test only.

Expected:
- FAIL because both cartons are still rendered

**Step 3: Write minimal implementation**

In `scan_cartons_ready`:

```python
shipment_reference_filter = (request.GET.get("shipment_reference") or "").strip()
...
if shipment_reference_filter:
    cartons_qs = cartons_qs.filter(
        shipment__reference__iexact=shipment_reference_filter,
    )
```

Also add the filter string into the template context.

**Step 4: Run test to verify it passes**

Run the same test.

Expected:
- PASS and only the targeted shipment cartons remain

**Step 5: Commit**

```bash
git add wms/views_scan_shipments.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: filter carton view by shipment reference"
```

### Task 3: Add Explicit Filter Feedback In The Carton Template

**Files:**
- Modify: `templates/scan/cartons_ready.html`
- Modify: `templates/scan/includes/shipment_dossier_header.html`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Assert:

```python
self.assertContains(response, f"Expédition filtrée : {shipment.reference}")
self.assertContains(response, "Voir tous les colis")
self.assertContains(
    response,
    f'{reverse("scan:scan_cartons_ready")}?shipment_reference={shipment.reference}',
)
```

**Step 2: Run test to verify it fails**

Run the two Task 1 tests again.

Expected:
- FAIL because the filter reminder and dossier link are still missing

**Step 3: Write minimal implementation**

Add:
- a tertiary `Voir les colis` link in the dossier header
- a small active-filter block above the carton list title or toolbar
- an unfiltered fallback link to `scan:scan_cartons_ready`

**Step 4: Run test to verify it passes**

Run the same tests again.

Expected:
- PASS with explicit filter feedback

**Step 5: Commit**

```bash
git add \
  templates/scan/includes/shipment_dossier_header.html \
  templates/scan/cartons_ready.html \
  wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: surface active shipment filter in carton view"
```
