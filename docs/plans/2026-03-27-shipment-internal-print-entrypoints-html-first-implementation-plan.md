# Shipment Internal Print Entrypoints HTML-First Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Route internal shipment print buttons in `scan` and `admin` to HTML/CSS documents by default without changing explicit PDF exports or public/legacy PDF-first contracts.

**Architecture:** Reuse the existing `delivery` contract already present in `scan`. Internal UI links either target HTML-first routes directly or append `delivery=html` to legacy-compatible routes. Admin adopts the same rule by switching its default internal delivery mode to HTML while still honoring helper and explicit PDF flows.

**Tech Stack:** Django views, Django templates, Django tests

---

### Task 1: Lock dossier and bundle carton actions to HTML

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/shipment_view_helpers.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print_docs.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/shipment/tests_shipment_view_helpers.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_docs.py`

**Steps:**
1. Add failing assertions for carton document and single-label URLs ending with `delivery=html`.
2. Run the targeted tests and verify they fail.
3. Add a shared HTML-delivery URL helper in the relevant modules.
4. Update dossier and bundle row actions to append `delivery=html`.
5. Re-run the targeted tests and verify they pass.

### Task 2: Align admin print buttons and handlers with HTML-first internal delivery

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/admin.py`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/admin/wms/shipment/change_form.html`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/admin/tests_admin_extra.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/admin/tests_admin_bootstrap_ui.py`

**Steps:**
1. Add failing tests showing admin shipment/carton print endpoints should render HTML by default and stay PDF/XLSX when `delivery=pdf`.
2. Run those tests and confirm the current PDF-first behavior fails them.
3. Import and use the shared delivery helper in admin views.
4. Make admin print handlers return HTML on default internal requests.
5. Remove helper-only button markers from internal admin print buttons.
6. Re-run the admin tests and verify they pass.

### Task 3: Realign the legacy generated-doc panel in scan

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/templates/scan/includes/shipment_create_generated_documents_panel.html`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views.py`

**Steps:**
1. Add or update assertions so internal links on the shipment edit/form surface no longer behave like helper-only PDF links and expose HTML-first URLs for carton packing list and single label actions.
2. Run the targeted view test and confirm the old links fail.
3. Repoint the template to HTML-first routes or append `delivery=html` where needed.
4. Remove helper-only markers from internal buttons.
5. Re-run the targeted view test and verify it passes.

### Task 4: Verify the full targeted regression slice

**Files:**
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/shipment/tests_shipment_view_helpers.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_docs.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/admin/tests_admin_bootstrap_ui.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/admin/tests_admin_extra.py`

**Steps:**
1. Run the full targeted suite covering the modified scan/admin entrypoints.
2. Run `git diff --check`.
3. Review the remaining diff to ensure only internal entrypoint routing changed.
