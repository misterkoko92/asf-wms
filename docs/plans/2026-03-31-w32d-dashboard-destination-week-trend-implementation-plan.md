# W3.2d Dashboard Destination Week Trend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** enrich the existing `Destinations à risque` dashboard block and its UI API mirror with a compact current-week versus previous-week trend readout.

**Architecture:** keep the current destination-risk ranking as the visible top list, then enrich each visible row by looking up the current and previous ISO-week buckets from `build_destination_week_workflow_projection_rows(...)`. The lot stays read-only and reuses the existing dashboard adapter in `wms/scan_dashboard_destination_risk.py`, plus the legacy dashboard template and the UI API mirror.

**Tech Stack:** Django, DRF, legacy `wms/views_scan_dashboard.py`, `templates/scan/dashboard.html`, `api/v1/ui_views.py`, workflow projection helpers, dashboard/API tests, repo-reference docs

---

### Task 1: Add failing dashboard tests for compact weekly comparison

**Files:**
- Modify: `wms/tests/views/tests_views_scan_dashboard.py`

**Step 1: Write the failing context test**

Add a test asserting that dashboard `destination_risk_rows` now expose:

- `current_week_label`
- `current_week_score`
- `previous_week_label`
- `previous_week_score`
- `trend_delta`
- `trend_direction`
- `trend_label`

Create projections for the current ISO week and previous ISO week so the delta is non-zero.

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests.test_scan_dashboard_exposes_destination_risk_week_trend -v 2
```

Expected:

- FAIL because the weekly fields are not in the dashboard row contract yet

**Step 3: Write the failing rendering test**

Add a second test asserting that the HTML renders:

- `Semaine`
- `S-1`
- `Tendance`
- one visible week label such as `2026-W14`

**Step 4: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests.test_scan_dashboard_renders_destination_risk_week_trend_columns -v 2
```

Expected:

- FAIL because the template does not render the compact weekly columns yet

### Task 2: Add failing UI API tests for the mirrored weekly trend contract

**Files:**
- Modify: `api/tests/tests_ui_endpoints.py`

**Step 1: Write the failing API test**

Add a test asserting that `GET /api/v1/ui/dashboard/` returns the weekly comparison fields inside
`destination_risk_rows[]`.

Assert:

- `current_week_score`
- `previous_week_score`
- `trend_delta`
- `trend_direction`
- `trend_label`

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiEndpointsTests.test_ui_dashboard_exposes_destination_risk_week_trend -v 2
```

Expected:

- FAIL because the API mirror has not been extended yet

### Task 3: Implement the weekly trend enrichment helper

**Files:**
- Modify: `wms/scan_dashboard_destination_risk.py`

**Step 1: Write minimal implementation**

Extend the helper so it:

- computes the current ISO week and previous ISO week
- reads weekly rows via `build_destination_week_workflow_projection_rows(...)`
- builds one lookup per destination
- enriches visible destination-risk rows with current/previous scores and trend metadata

Keep the visible ranking driven by the existing destination-risk aggregate, not by the weekly score.

**Step 2: Run focused tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests.test_scan_dashboard_exposes_destination_risk_week_trend api.tests.tests_ui_endpoints.UiEndpointsTests.test_ui_dashboard_exposes_destination_risk_week_trend -v 2
```

Expected:

- FAIL on rendering or mirror details until the dashboard/template/API are wired

### Task 4: Wire the legacy dashboard block

**Files:**
- Modify: `wms/views_scan_dashboard.py`
- Modify: `templates/scan/dashboard.html`

**Step 1: Reuse the enriched destination-risk snapshot**

Expose the extended row contract in dashboard context without changing the existing section order.

**Step 2: Render the compact weekly columns**

Update the `Destinations à risque` table to render:

- `Semaine`
- `S-1`
- `Tendance`

Keep the CTA and the rest of the operational columns unchanged.

**Step 3: Run focused dashboard tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard -v 2
```

Expected:

- PASS

### Task 5: Mirror the trend fields in the UI dashboard API

**Files:**
- Modify: `api/v1/ui_views.py`

**Step 1: Reuse the same enriched snapshot**

Expose the exact same weekly trend fields in `destination_risk_rows[]` from `GET /api/v1/ui/dashboard/`.

**Step 2: Run focused API tests**

Run:

```bash
./.venv/bin/python manage.py test api.tests.tests_ui_endpoints -v 2
```

Expected:

- PASS

### Task 6: Update repo-reference for the enriched shared contract

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Create: `docs/plans/2026-03-31-w32d-dashboard-destination-week-trend-design.md`
- Create: `docs/plans/2026-03-31-w32d-dashboard-destination-week-trend-implementation-plan.md`

**Step 1: Document the shared trend contract**

Record:

- the enriched destination-risk row fields
- the current-week / previous-week mapping rule
- the simple weekly score formula
- the reference tests that protect the lot

### Task 7: Verification and commit

**Files:**
- Modify: any files touched above

**Step 1: Run targeted verification**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard api.tests.tests_ui_endpoints -v 2
uv run ruff check wms/scan_dashboard_destination_risk.py wms/views_scan_dashboard.py templates/scan/dashboard.html api/v1/ui_views.py wms/tests/views/tests_views_scan_dashboard.py api/tests/tests_ui_endpoints.py docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md
```

Expected:

- tests PASS
- lint PASS

**Step 2: Optional authenticated local smoke**

Check:

- `/scan/dashboard/`
- `/api/v1/ui/dashboard/`

Expected:

- `200`
- compact weekly comparison visible in `Destinations à risque`

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: add destination risk week trends to scan dashboard"
```
