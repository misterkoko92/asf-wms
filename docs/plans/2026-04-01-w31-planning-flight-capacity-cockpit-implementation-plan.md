# W3.1 Planning Flight Capacity Cockpit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** add a flight-centric capacity cockpit inside the planning version detail so operators can see tension, critical load, overload, and remaining capacity before editing assignments.

**Architecture:** extend the existing planning stats layer in `wms/planning/stats.py`, propagate the new capacity breakdown through `wms/planning/version_dashboard.py`, and render it through the existing planning partials. Keep the lot read-only and local-first, with no new persistence and no assignment-rule changes.

**Tech Stack:** Django, legacy planning templates, planning dashboard helpers, planning snapshot models, Django test suite

---

### Task 1: Add failing stats tests for flight capacity breakdown

**Files:**
- Modify: `wms/tests/planning/tests_version_dashboard.py`
- Modify: `wms/planning/stats.py`

**Step 1: Write the failing stats test**

Add a test asserting that flight capacity rows expose:

- `remaining_units`
- `utilization_pct`
- `load_state`
- `load_state_label`

Cover at least:

- one `ok` flight
- one `critical` flight
- one `overload` flight

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard.PlanningVersionDashboardTests.test_build_version_dashboard_exposes_flight_capacity_states -v 2
```

Expected:

- FAIL because the capacity fields are not present yet

### Task 2: Implement flight-capacity computation in planning stats

**Files:**
- Modify: `wms/planning/stats.py`

**Step 1: Write minimal implementation**

Extend `flight_load_breakdown` rows so each row computes:

- `remaining_units`
- `utilization_pct`
- `load_state`
- `load_state_label`

Add stable sorting by:

- load severity
- departure date/time
- flight number

**Step 2: Run the focused test**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard.PlanningVersionDashboardTests.test_build_version_dashboard_exposes_flight_capacity_states -v 2
```

Expected:

- PASS on the new stats assertions

### Task 3: Add cockpit summary rows to the planning dashboard payload

**Files:**
- Modify: `wms/planning/version_dashboard.py`
- Modify: `wms/tests/planning/tests_version_dashboard.py`

**Step 1: Write the failing dashboard test**

Add a test asserting that `build_version_dashboard(version)` exposes:

- summary counts for `tension`, `critical`, `overload`
- `remaining_capacity_total`
- the enriched flight-capacity rows

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard.PlanningVersionDashboardTests.test_build_version_dashboard_exposes_capacity_summary -v 2
```

Expected:

- FAIL because the dashboard payload does not include the summary yet

**Step 3: Write minimal implementation**

Propagate the enriched flight rows and derived summary into the version dashboard payload.

### Task 4: Render the capacity cockpit in planning templates

**Files:**
- Modify: `templates/planning/_version_stats_block.html`
- Modify: `templates/planning/_version_planning_block.html`
- Modify: `wms/tests/views/tests_views_planning.py`

**Step 1: Write the failing view test**

Add a test asserting that version detail renders:

- `Vols en tension`
- `Vols critiques`
- `Vols en surcharge`
- `Capacité restante totale`
- `Charge vols`

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_planning.PlanningViewsTests.test_version_detail_renders_capacity_cockpit -v 2
```

Expected:

- FAIL because the planning templates do not render the new block yet

**Step 3: Write minimal template implementation**

Render:

- the four summary cards in the stats block
- a compact `Charge vols` table before the detailed per-flight assignment cards

Keep the detailed assignment list intact.

### Task 5: Update repo-reference and planning notes

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Create: `docs/plans/2026-04-01-w31-planning-flight-capacity-cockpit-design.md`
- Create: `docs/plans/2026-04-01-w31-planning-flight-capacity-cockpit-implementation-plan.md`

**Step 1: Document the new cockpit contract**

Record:

- the flight-capacity row fields
- the load-state thresholds
- the template blocks that now consume the contract
- the reference tests that protect the lot

### Task 6: Verification and commit

**Files:**
- Modify: any files touched above

**Step 1: Run targeted verification**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2
uv run ruff check wms/planning/stats.py wms/planning/version_dashboard.py wms/tests/planning/tests_version_dashboard.py wms/tests/views/tests_views_planning.py
```

Expected:

- tests PASS
- lint PASS

**Step 2: Smoke the planning cockpit**

Run the local planning smoke or inspect one version detail page to confirm:

- capacity cards visible
- `Charge vols` table visible
- detailed planning assignments still present

**Step 3: Commit**

```bash
git add wms/planning/stats.py wms/planning/version_dashboard.py templates/planning/_version_stats_block.html templates/planning/_version_planning_block.html wms/tests/planning/tests_version_dashboard.py wms/tests/views/tests_views_planning.py docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md docs/plans/2026-04-01-w31-planning-flight-capacity-cockpit-design.md docs/plans/2026-04-01-w31-planning-flight-capacity-cockpit-implementation-plan.md
git commit -m "feat: add planning flight capacity cockpit"
```
