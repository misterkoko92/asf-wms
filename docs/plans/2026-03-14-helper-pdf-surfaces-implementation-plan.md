# Helper PDF Surfaces Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend legacy scan pages so all helper-compatible PDF download buttons consistently use the local helper UX.

**Architecture:** Reuse the existing local helper root/panel/script pattern from `scan/cartons_ready` and `scan/shipments_ready`. Limit the rollout to routes that already support helper jobs in `views_print_docs.py` or `views_print_labels.py`.

**Tech Stack:** Django templates, Django views, unittest-based Django tests, legacy scan helper JavaScript.

---

### Task 1: Add failing helper-surface tests

**Files:**
- Modify: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing tests**

- Add tests asserting that:
  - `scan_prepare_kits` exposes `helper_install` metadata in the response context and HTML helper root.
  - `scan_prepare_kits` marks only the single-carton picking link for helper interception.
  - `scan_pack` exposes `helper_install` metadata in the response context and HTML helper root when a packing result is present.
  - `scan_shipment_create` exposes helper metadata and marks generated-document links with `data-local-document-helper-link="1"`.

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments.ScanShipmentsViewsTests \
  -v 2
```

**Step 3: Commit**

```bash
git add wms/tests/views/tests_views_scan_shipments.py
git commit -m "test(helper): cover missing scan pdf surfaces"
```

### Task 2: Add helper context to the missing scan views

**Files:**
- Modify: `wms/views_scan_shipments.py`

**Step 1: Implement minimal view changes**

- Add the same `helper_install` and `local_document_helper_origin` context used by the existing scan helper-enabled pages to:
  - `scan_prepare_kits`
  - `scan_pack`
  - `scan_shipment_create`

**Step 2: Run targeted tests**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments.ScanShipmentsViewsTests \
  -v 2
```

**Step 3: Commit**

```bash
git add wms/views_scan_shipments.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat(helper): expose scan helper metadata on pdf surfaces"
```

### Task 3: Wire the templates to the helper

**Files:**
- Modify: `templates/scan/prepare_kits.html`
- Modify: `templates/scan/pack.html`
- Modify: `templates/scan/shipment_create.html`

**Step 1: Add helper root and install panel**

- Wrap the page body with `data-local-document-helper-root` and related metadata.
- Include `templates/wms/_local_document_helper_install_panel.html`.
- Load `wms/static/wms/local_document_helper.js`.

**Step 2: Mark only helper-compatible links**

- Add `data-local-document-helper-link="1"` only to:
  - single-carton `prepare_kits` picking downloads
  - pack-generated packing list / picking links
  - shipment create generated document links
  - shipment create carton document / label links
- Do not mark uploaded `document.file.url` links.
- Do not mark the multi-carton `scan_prepare_kits_picking` HTML print route.

**Step 3: Run targeted tests**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments.ScanShipmentsViewsTests \
  -v 2
```

**Step 4: Commit**

```bash
git add templates/scan/prepare_kits.html templates/scan/pack.html templates/scan/shipment_create.html
git commit -m "feat(helper): wire scan pdf buttons to local helper"
```

### Task 4: Final verification

**Files:**
- Modify: none

**Step 1: Run the helper-related regression suite**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_views_planning.PlanningViewTests.test_version_detail_exposes_helper_bridge_hooks \
  wms.tests.views.tests_views_planning.PlanningViewTests.test_version_detail_helper_installer_allows_signed_anonymous_request \
  wms.tests.admin.tests_admin_extra.ShipmentAndStockMovementAdminTests.test_shipment_change_form_exposes_local_helper_metadata \
  wms.tests.core.tests_helper_install \
  -v 2
```

**Step 2: Run diff hygiene**

```bash
git diff --check
```

**Step 3: Commit**

```bash
git add -A
git commit -m "docs: record helper pdf surface rollout"
```
