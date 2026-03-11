# Planning Bilan Destination Summary Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a second `Bilan Planning` table that summarizes destinations in collapsed mode and expands to shipment-level rows with sortable columns.

**Architecture:** Extend the legacy Django planning dashboard builder with a destination/shipment summary dataset, render it in the existing `Bilan Planning` template, and attach a small dedicated script that handles expand/collapse and grouped sorting without affecting other planning tables. Keep the first volunteer summary table unchanged.

**Tech Stack:** Django templates, Python dashboard builders, legacy scan table styles, vanilla JavaScript, Django test suite

---

### Task 1: Add failing dashboard tests for destination summary data

**Files:**
- Modify: `wms/tests/planning/tests_version_dashboard.py`
- Modify: `wms/planning/version_dashboard.py`

**Step 1: Write the failing test**

Add a test that creates one destination with both planned and unplanned shipments and asserts:
- one destination summary group exists;
- the destination row exposes `planned_count`, `total_count`;
- `BE_Numero` and `Etat` summary values are `planned / total`;
- carton and equivalent displays are `planned_sum / total_sum`;
- shipment rows expose `Planifie` and `Non partant`.

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard.PlanningVersionDashboardTests.test_build_version_dashboard_exposes_destination_summary_rows -v 2`

Expected: FAIL because `destination_rows` is missing or incomplete.

**Step 3: Write minimal implementation**

Add a destination summary builder in `wms/planning/version_dashboard.py` and include it under `dashboard["planning_summary"]`.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard.PlanningVersionDashboardTests.test_build_version_dashboard_exposes_destination_summary_rows -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/tests/planning/tests_version_dashboard.py wms/planning/version_dashboard.py
git commit -m "feat: add planning destination summary data"
```

### Task 2: Add failing view test for second bilan planning table

**Files:**
- Modify: `wms/tests/views/tests_views_planning.py`
- Modify: `templates/planning/_version_planning_summary_block.html`

**Step 1: Write the failing test**

Add a view test that renders `planning:version_detail` and asserts:
- the second table headers are present;
- the page contains `Tout developper`;
- the page renders aggregate values such as `1 / 2` for `BE_Numero`, `Etat`, `BE_Nb_Colis`, and `BE_Nb_Equiv`.

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_planning.PlanningViewsTests.test_version_detail_renders_destination_bilan_table -v 2`

Expected: FAIL because the template does not render the new table yet.

**Step 3: Write minimal implementation**

Update the summary block template to render the second table beneath the volunteer table using the new dashboard data.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_planning.PlanningViewsTests.test_version_detail_renders_destination_bilan_table -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_planning.py templates/planning/_version_planning_summary_block.html
git commit -m "feat: render planning destination summary table"
```

### Task 3: Add failing UI hook test for grouped expand/collapse controls

**Files:**
- Modify: `wms/tests/views/tests_views_planning.py`
- Modify: `templates/planning/_version_planning_summary_block.html`

**Step 1: Write the failing test**

Add assertions that the rendered HTML includes:
- a global toggle button;
- one per-destination toggle button;
- `data-*` attributes identifying the destination summary table, groups, parent rows, and child rows.

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_planning.PlanningViewsTests.test_version_detail_renders_destination_bilan_expand_controls -v 2`

Expected: FAIL because these hooks do not exist yet.

**Step 3: Write minimal implementation**

Add the necessary `data-*` hooks and accessible button labels in the template.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_planning.PlanningViewsTests.test_version_detail_renders_destination_bilan_expand_controls -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_planning.py templates/planning/_version_planning_summary_block.html
git commit -m "feat: add planning destination summary controls"
```

### Task 4: Implement grouped sorting and expand/collapse behavior

**Files:**
- Modify: `templates/planning/_version_planning_summary_block.html`

**Step 1: Write the failing test**

No new automated JS test is planned here; use the existing rendering hooks from Task 3 as the guardrail.

**Step 2: Run focused server-side tests before JS changes**

Run: `.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2`

Expected: PASS before adding the inline script.

**Step 3: Write minimal implementation**

Add a dedicated inline script scoped to the destination summary table that:
- initializes all groups collapsed;
- toggles one destination at a time;
- toggles all destinations;
- sorts destination groups by any column;
- sorts shipment child rows inside each destination by the same column;
- preserves stable order when values are equal.

**Step 4: Run test to verify server-side behavior still passes**

Run: `.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add templates/planning/_version_planning_summary_block.html
git commit -m "feat: add grouped planning destination table interactions"
```

### Task 5: Verify full planning detail coverage

**Files:**
- Modify: `wms/tests/planning/tests_version_dashboard.py`
- Modify: `wms/tests/views/tests_views_planning.py`
- Modify: `wms/planning/version_dashboard.py`
- Modify: `templates/planning/_version_planning_summary_block.html`

**Step 1: Run targeted regression tests**

Run: `.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2`

Expected: PASS for all planning dashboard and planning view tests.

**Step 2: Run any necessary follow-up fixes**

If a regression appears, add the smallest failing test first, then patch the relevant file and rerun the focused suite.

**Step 3: Final verification**

Run: `.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2`

Expected: PASS

**Step 4: Commit**

```bash
git add wms/tests/planning/tests_version_dashboard.py wms/tests/views/tests_views_planning.py wms/planning/version_dashboard.py templates/planning/_version_planning_summary_block.html
git commit -m "feat: complete planning destination bilan summary"
```
