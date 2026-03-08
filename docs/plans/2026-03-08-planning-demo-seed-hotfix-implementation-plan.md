# Planning Demo Seed Hotfix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `seed_planning_demo_data` safe on shared databases where a destination already exists for the same city/country with a different IATA code.

**Architecture:** Keep the seed command deterministic, but resolve demo destinations through a fallback lookup that first tries the expected IATA and then reuses an existing destination by `city/country` without mutating it. Align seeded flights and shipments with the effective destination object returned by that resolver.

**Tech Stack:** Django management commands, legacy WMS destination model, Django TestCase.

---

### Task 1: Reproduce the PythonAnywhere failure

**Files:**
- Modify: `wms/tests/management/tests_management_seed_planning_demo_data.py`

**Step 1: Write the failing test**

Add a test creating a pre-existing `Destination(city="Dakar", country="Senegal", iata_code="XYZ")`, then assert `seed_planning_demo_data` reuses that destination instead of crashing.

**Step 2: Run test to verify it fails**

Run: `ASF_TMP_DIR=/tmp/asf_wms_planning /Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.management.tests_management_seed_planning_demo_data -v 2`
Expected: failure in the new test before the command is fixed.

### Task 2: Fix destination resolution in the seed command

**Files:**
- Modify: `wms/management/commands/seed_planning_demo_data.py`

**Step 1: Write minimal implementation**

Introduce a helper that resolves destinations by:
- exact `iata_code` first
- fallback on `city/country`
- creation only if neither exists

Then use the resolved destination object everywhere in the seeded dataset.

**Step 2: Run test to verify it passes**

Run: `ASF_TMP_DIR=/tmp/asf_wms_planning /Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.management.tests_management_seed_planning_demo_data -v 2`
Expected: PASS

### Task 3: Verify and commit

**Files:**
- Add the updated command, tests, and plan doc

**Step 1: Run targeted verification**

Run:
- `ASF_TMP_DIR=/tmp/asf_wms_planning /Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.management.tests_management_seed_planning_demo_data wms.tests.planning.tests_run_preparation wms.tests.planning.tests_solver_contracts -v 2`
- `/Users/EdouardGonnu/asf-wms/.venv/bin/ruff check /Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-demo-seed-hotfix/wms/management/commands/seed_planning_demo_data.py /Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-demo-seed-hotfix/wms/tests/management/tests_management_seed_planning_demo_data.py`

**Step 2: Commit**

```bash
git add docs/plans/2026-03-08-planning-demo-seed-hotfix-implementation-plan.md \
  wms/management/commands/seed_planning_demo_data.py \
  wms/tests/management/tests_management_seed_planning_demo_data.py
git commit -m "fix(planning): reuse existing destinations in demo seed"
```
