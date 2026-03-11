# Planning Bilan Volunteer And Week Sort Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the two `Vue Semaine` tables and the volunteer `Bilan Planning` table sortable on every column, while updating volunteer summary labels and metrics.

**Architecture:** Keep the grouped expedition summary script local and add a second local planning script for simple tables only. Extend the dashboard volunteer summary data with assigned carton and equivalent totals, then update the planning templates to expose the new columns and titles.

**Tech Stack:** Django templates, Python dashboard builders, vanilla JavaScript, Django test suite

---

### Task 1: Add failing dashboard test for volunteer assigned totals

**Files:**
- Modify: `wms/tests/planning/tests_version_dashboard.py`
- Modify: `wms/planning/version_dashboard.py`

**Step 1: Write the failing test**

Add assertions to the volunteer planning summary test for:
- `assigned_carton_count`
- `assigned_equivalent_units`

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard.PlanningVersionDashboardTests.test_build_version_dashboard_exposes_planning_summary_per_volunteer -v 2`

Expected: FAIL because the new keys are not yet present.

**Step 3: Write minimal implementation**

Update the volunteer summary builder to expose the two new totals.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard.PlanningVersionDashboardTests.test_build_version_dashboard_exposes_planning_summary_per_volunteer -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/tests/planning/tests_version_dashboard.py wms/planning/version_dashboard.py
git commit -m "feat: add volunteer assigned totals to planning summary"
```

### Task 2: Add failing view tests for labels, columns, and simple-table hooks

**Files:**
- Modify: `wms/tests/views/tests_views_planning.py`
- Modify: `templates/planning/_version_week_view_block.html`
- Modify: `templates/planning/_version_planning_summary_block.html`

**Step 1: Write the failing tests**

Add assertions for:
- `Bilan Bénévoles`
- `Bilan Expéditions`
- absence of `Disponibilites` in the volunteer summary table section
- presence of `Nb Colis Affecté` and `Nb Equiv Affecté`
- three `data-planning-simple-table="1"` hooks across the two week-view tables and the volunteer summary table

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_planning.PlanningViewTests.test_version_detail_renders_week_view_and_planning_summary_cards -v 2`

Expected: FAIL because labels/columns/hooks are not in the templates yet.

**Step 3: Write minimal implementation**

Update the two templates with the requested titles, columns, and data hooks.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_planning.PlanningViewTests.test_version_detail_renders_week_view_and_planning_summary_cards -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_planning.py templates/planning/_version_week_view_block.html templates/planning/_version_planning_summary_block.html
git commit -m "feat: update planning volunteer and week table labels"
```

### Task 3: Add local simple-table sorting for planning cockpit tables

**Files:**
- Modify: `templates/planning/_version_week_view_block.html`
- Modify: `templates/planning/_version_planning_summary_block.html`
- Test: `wms/tests/views/tests_views_planning.py`

**Step 1: Write the failing test**

Add a rendering test that verifies the simple-table script hooks exist on:
- the two `Vue Semaine` tables;
- the volunteer `Bilan` table.

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_planning.PlanningViewTests.test_version_detail_week_view_tables_share_fixed_column_widths -v 2`

Expected: FAIL if the hooks or simple-table integration are incomplete.

**Step 3: Write minimal implementation**

Add or extend a local planning script that:
- finds `data-planning-simple-table="1"` tables;
- sorts rows by clicked column;
- never adds filter inputs;
- preserves stable ordering.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_planning.PlanningViewTests.test_version_detail_week_view_tables_share_fixed_column_widths -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add templates/planning/_version_week_view_block.html templates/planning/_version_planning_summary_block.html wms/tests/views/tests_views_planning.py
git commit -m "feat: add local sorting for planning simple tables"
```

### Task 4: Verify focused planning regressions

**Files:**
- Modify: `wms/planning/version_dashboard.py`
- Modify: `templates/planning/_version_week_view_block.html`
- Modify: `templates/planning/_version_planning_summary_block.html`
- Modify: `wms/tests/planning/tests_version_dashboard.py`
- Modify: `wms/tests/views/tests_views_planning.py`

**Step 1: Run focused suite**

Run: `.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2`

Expected: PASS

**Step 2: Fix regressions minimally**

If any test fails, add the smallest missing assertion first, then patch the corresponding file and rerun.

**Step 3: Final verification**

Run: `.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2`

Expected: PASS

**Step 4: Commit**

```bash
git add wms/planning/version_dashboard.py templates/planning/_version_week_view_block.html templates/planning/_version_planning_summary_block.html wms/tests/planning/tests_version_dashboard.py wms/tests/views/tests_views_planning.py
git commit -m "feat: complete planning volunteer and week table sorting"
```
