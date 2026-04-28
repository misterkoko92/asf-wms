# Rangement Préparateur Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a preparateur-only rangement scan flow that updates stock and shows a five-product recap.

**Architecture:** Add a legacy Django `/scan/preparateur/rangement/` route, a small helper module for session batch and stock updates, a template using existing scan controls, and focused view tests. Reuse existing product resolution, `receive_stock`, and preparateur unknown-product creation.

**Tech Stack:** Django views/templates, existing scan JS `data-scan-target`, Django TestCase.

---

### Task 1: Route And Home Entry

**Files:**
- Modify: `wms/scan_urls.py`
- Modify: `wms/views_scan.py`
- Modify: `wms/views.py`
- Modify: `wms/scan_permissions.py`
- Modify: `wms/views_scan_preparateur.py`
- Modify: `templates/scan/preparateur_home.html`
- Test: `wms/tests/views/tests_views_scan_preparateur.py`

**Steps:**
1. Add failing tests for the home button, redirect action, route accessibility, and preparateur allowlist.
2. Run the focused test file and confirm the new tests fail.
3. Add the route, exports, allowlist entry, and home action.
4. Run the focused tests and confirm those route/home tests pass.

### Task 2: Rangement Helper And Stock Behavior

**Files:**
- Create: `wms/preparateur_rangement.py`
- Test: `wms/tests/views/tests_views_scan_preparateur.py`

**Steps:**
1. Add failing tests for known product stock update, missing location message, duplicate scan quantity merge, and five-product limit.
2. Run the focused test file and confirm the new tests fail.
3. Implement session batch helpers and stock update behavior with `receive_stock`.
4. Run the focused tests and confirm they pass.

### Task 3: Rangement Page And Unknown Product Modal

**Files:**
- Modify: `wms/views_scan_preparateur.py`
- Create: `templates/scan/preparateur_rangement.html`
- Test: `wms/tests/views/tests_views_scan_preparateur.py`

**Steps:**
1. Add failing tests for unknown product stop, recap display, modal fields, finish action, and create-new-product action.
2. Run the focused test file and confirm the new tests fail.
3. Implement the page, modal open context, finish action, and create-product path.
4. Run the focused tests and confirm they pass.

### Task 4: Governance, Changelog, And Verification

**Files:**
- Modify: `wms/faq_changelog.py`
- Modify if needed: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify if needed: `docs/repo-reference/04-shared-contracts/03-scan-operations.md`

**Steps:**
1. Add the FAQ changelog entry with `pr_number=None`.
2. Re-check scan impact and shared-contract docs for drift.
3. Run nearest tests:
   `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_preparateur wms.tests.views.tests_scan_bootstrap_ui -v 2`
4. Report verification output and any remaining PR-number follow-up.
