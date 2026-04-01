# W3.2b Dashboard Destination Risk Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** expose destination-level workflow risk directly in the legacy scan dashboard and in the UI dashboard API mirror

**Architecture:** the lot stays read-only and reuses the destination workflow aggregate helper added in `W3.2a`. The scan dashboard renders one new operational block with summary cards and top-risk rows, while `api/v1/ui/dashboard/` mirrors the same contract for local UI consumers.

**Tech Stack:** Django, DRF, legacy `wms/views_scan_dashboard.py`, `templates/scan/dashboard.html`, `api/v1/ui_views.py`, dashboard view tests, UI endpoint tests, repo-reference docs

---

### Task 1: Add failing dashboard tests for destination-risk context and rendering

**Files:**
- Modify: `wms/tests/views/tests_views_scan_dashboard.py`
- Test: `wms/tests/views/tests_views_scan_dashboard.py`

**Step 1: Write the failing context test**

Add a test asserting that `scan_dashboard` exposes:

- `destination_risk_summary_cards`
- `destination_risk_rows`
- the new anchor `scan-dashboard-destination-risk`

The test should create at least two risky destinations and assert that the most critical one appears first.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests.test_scan_dashboard_exposes_destination_risk_summary_and_rows -v 2`
Expected: FAIL because the context keys and anchor do not exist yet

**Step 3: Write the failing rendering test**

Add a second test asserting that the HTML renders:

- the section title `Destinations à risque`
- the risky destination reference row
- the CTA label for opening the filtered shipment tracking queue

**Step 4: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests.test_scan_dashboard_renders_destination_risk_panel -v 2`
Expected: FAIL because the section is not in the template yet

### Task 2: Add failing UI dashboard API tests for the mirror contract

**Files:**
- Modify: `api/tests/tests_ui_endpoints.py`
- Test: `api/tests/tests_ui_endpoints.py`

**Step 1: Write the failing API contract test**

Add a test asserting that `GET /api/v1/ui/dashboard/` returns:

- `destination_risk_summary_cards`
- `destination_risk_rows`

Assert the first row contains:

- `destination_id`
- `destination_label`
- `critical_shipment_count`
- `open_dispute_count`
- `top_blockage_category`
- `oldest_open_segment_age_hours`
- `url`
- `cta_label`

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiEndpointsTests.test_ui_dashboard_exposes_destination_risk_rows -v 2`
Expected: FAIL because the API payload does not include these keys yet

### Task 3: Implement the destination-risk builder in the scan dashboard view

**Files:**
- Modify: `wms/views_scan_dashboard.py`
- Test: `wms/tests/views/tests_views_scan_dashboard.py`

**Step 1: Add a small dashboard-specific adapter**

Build a helper that:

- calls the existing destination aggregate helper
- limits rows to the top 5
- formats summary cards for critical destinations, destinations with disputes, and oldest open dossier
- maps blockage categories to stable human-readable labels
- builds per-row filtered tracking URLs

**Step 2: Wire the new context keys**

Expose:

- `destination_risk_summary_cards`
- `destination_risk_rows`

Also insert the new dashboard anchor:

- `scan-dashboard-destination-risk`

**Step 3: Run focused dashboard tests**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests.test_scan_dashboard_exposes_destination_risk_summary_and_rows wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests.test_scan_dashboard_renders_destination_risk_panel -v 2`
Expected: still FAIL until the template is updated

### Task 4: Render the destination-risk section in the legacy dashboard template

**Files:**
- Modify: `templates/scan/dashboard.html`
- Test: `wms/tests/views/tests_views_scan_dashboard.py`

**Step 1: Add the new section**

Insert a section after `Blocages workflow` and before `Pilotage` that renders:

- the three summary cards
- a compact table for destination-risk rows
- a stable empty state when there are no risky destinations

**Step 2: Run focused dashboard tests**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard -v 2`
Expected: PASS

### Task 5: Mirror the contract in the UI dashboard API

**Files:**
- Modify: `api/v1/ui_views.py`
- Test: `api/tests/tests_ui_endpoints.py`

**Step 1: Reuse the same adapter rules**

Add the same destination-risk cards and rows to `GET /api/v1/ui/dashboard/`, aligned with the legacy dashboard behavior.

**Step 2: Run focused API tests**

Run: `./.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiEndpointsTests.test_ui_dashboard_exposes_destination_risk_rows -v 2`
Expected: PASS

### Task 6: Update repo-reference for the new dashboard/API contract

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Record the new shared contract**

Document:

- the `Destinations à risque` block on `scan/dashboard`
- the mirrored `api/v1/ui/dashboard` keys
- the reference tests that protect the lot

**Step 2: Re-check propagation**

Confirm that no extra page, export, or `pending_actions` feed is added in this lot.

### Task 7: Verification and commit

**Files:**
- Modify: any files touched above

**Step 1: Run focused verification**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard api.tests.tests_ui_endpoints -v 2
uv run ruff check wms/views_scan_dashboard.py templates/scan/dashboard.html api/v1/ui_views.py wms/tests/views/tests_views_scan_dashboard.py api/tests/tests_ui_endpoints.py docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md
```

Expected:

- tests PASS
- ruff PASS

**Step 2: Optional authenticated local smoke**

Check:

- `/scan/dashboard/`
- `/api/v1/ui/dashboard/`

Expected:

- `200`
- destination-risk block visible on the seeded local dataset

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: add destination risk dashboard block"
```
