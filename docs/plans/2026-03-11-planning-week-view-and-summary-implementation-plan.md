# Planning Week View And Summary Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add two collapsible planning cards, `Vue Semaine` and `Bilan Planning`, to the legacy Django planning version page.

**Architecture:** Extend the existing `build_version_dashboard()` presenter with two new computed sections derived from run snapshots and version assignments, then render them through dedicated planning partials. Keep the feature fully server-rendered and consistent with current page reload mutation flows.

**Tech Stack:** Django templates, Django tests, legacy WMS planning presenter helpers.

---

### Task 1: Add failing dashboard presenter tests

**Files:**
- Modify: `wms/tests/planning/tests_version_dashboard.py`

**Steps:**
1. Add a failing test for `week_view` volunteer and flight tables.
2. Add a failing test for `planning_summary` volunteer metrics.
3. Run only these tests and confirm failure.

### Task 2: Implement dashboard week view computations

**Files:**
- Modify: `wms/planning/version_dashboard.py`
- Modify: `wms/planning/stats.py`

**Steps:**
1. Build helper functions to normalize week dates from the run.
2. Build volunteer availability matrix from `availability_summary`.
3. Build flight availability/usage matrix from `flight_snapshots` and current assignments.
4. Build volunteer planning summary rows from availability + assignments.
5. Run presenter tests and make them pass.

### Task 3: Add failing planning view tests

**Files:**
- Modify: `wms/tests/views/tests_views_planning.py`

**Steps:**
1. Add a failing test asserting `Vue Semaine` is rendered on the version page.
2. Add a failing test asserting `Bilan Planning` is rendered with expected values.
3. Run only these tests and confirm failure.

### Task 4: Render the two new collapsible cards

**Files:**
- Modify: `templates/planning/version_detail.html`
- Create: `templates/planning/_version_week_view_block.html`
- Create: `templates/planning/_version_planning_summary_block.html`

**Steps:**
1. Add `Vue Semaine` card under the header.
2. Add `Bilan Planning` card under `Vue Semaine`.
3. Use the current scan/planning card/table style.
4. Run planning view tests and make them pass.

### Task 5: Run regression verification

**Files:**
- No code changes expected unless regressions appear.

**Steps:**
1. Run presenter tests.
2. Run planning view tests.
3. Run broader planning regression.
4. Run `ruff` on touched files.

### Task 6: Commit and open PR

**Files:**
- Commit touched code and docs.

**Steps:**
1. Review diff for scope.
2. Commit with a focused message.
3. Push branch.
4. Open PR with summary and test plan.
