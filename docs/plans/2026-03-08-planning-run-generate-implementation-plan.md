# Planning Run Generate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the planning UI generate a planning version from a draft run with a single operator action.

**Architecture:** Keep preparation and solving as separate services, but orchestrate them behind the existing planning run action. The view should first call `prepare_run_inputs(run)`, stop on validation errors, and only call `solve_run(run)` when the run becomes `ready`.

**Tech Stack:** Django legacy views/templates, planning snapshot and solver services, Django TestCase.

---

### Task 1: Cover the combined run action with tests

**Files:**
- Modify: `wms/tests/views/tests_views_planning.py`

**Step 1: Write the failing tests**

Add tests asserting that posting the run action on a draft run:
- prepares then solves when inputs are valid
- stays on the run detail page with issues when validation fails

**Step 2: Run tests to verify they fail**

Run: `ASF_TMP_DIR=/tmp/asf_wms_planning /Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_planning -v 2`
Expected: failure before the view is updated.

### Task 2: Implement the combined generate action

**Files:**
- Modify: `wms/views_planning.py`
- Modify: `templates/planning/run_detail.html`

**Step 1: Write minimal implementation**

Update the run action so it:
- calls `prepare_run_inputs(run)` unless already `ready`
- redirects to the version detail if solving succeeds
- redirects back to the run detail with an error message if validation fails

Rename the button in the template to reflect the operator action.

**Step 2: Run tests to verify they pass**

Run: `ASF_TMP_DIR=/tmp/asf_wms_planning /Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_planning -v 2`
Expected: PASS

### Task 3: Verify and commit

**Files:**
- Add the plan doc and modified view/template/tests

**Step 1: Run targeted verification**

Run:
- `ASF_TMP_DIR=/tmp/asf_wms_planning /Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_planning wms.tests.planning.tests_run_preparation wms.tests.planning.tests_solver_contracts -v 2`
- `/Users/EdouardGonnu/asf-wms/.venv/bin/ruff check /Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-run-generate/wms/views_planning.py /Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-run-generate/wms/tests/views/tests_views_planning.py`

**Step 2: Commit**

```bash
git add docs/plans/2026-03-08-planning-run-generate-implementation-plan.md \
  templates/planning/run_detail.html \
  wms/views_planning.py \
  wms/tests/views/tests_views_planning.py
git commit -m "feat(planning): prepare runs from the generate action"
```
