# Planning Demo Seed Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a management command that seeds coherent fictive planning data and can optionally prepare and solve a planning run end-to-end.

**Architecture:** Implement a legacy Django management command that creates a self-contained demo dataset spanning portal contacts, volunteer constraints/availabilities, shipments, equivalence rules, destination planning rules, flights, and a planning run. Keep the seed deterministic and idempotent by keying demo records with a scenario slug, then verify the operational flow with targeted tests and a smoke solve.

**Tech Stack:** Django management commands, legacy WMS domain models, planning snapshots/solver services, Django TestCase.

---

### Task 1: Cover the command contract with tests

**Files:**
- Create: `wms/tests/management/tests_management_seed_planning_demo_data.py`

**Step 1: Write the failing test**

Add tests asserting that `seed_planning_demo_data` creates the minimal coherent planning dataset and, with `--solve`, produces a solved `PlanningRun` plus a draft `PlanningVersion`.

**Step 2: Run test to verify it fails**

Run: `ASF_TMP_DIR=/tmp/asf_wms_planning /Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.management.tests_management_seed_planning_demo_data -v 2`
Expected: failure because the command does not exist yet.

### Task 2: Implement the demo seed command

**Files:**
- Create: `wms/management/commands/seed_planning_demo_data.py`

**Step 1: Write minimal implementation**

Add a management command that:
- creates deterministic demo contacts, destination, association portal contacts, volunteers, shipments, cartons, lots, equivalence rules, flights, parameter set, and run
- supports `--scenario` to namespace the dataset
- supports `--solve` to call `prepare_run_inputs()` and `solve_run()`
- prints a short summary with created object ids/counts

**Step 2: Run test to verify it passes**

Run: `ASF_TMP_DIR=/tmp/asf_wms_planning /Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.management.tests_management_seed_planning_demo_data -v 2`
Expected: PASS

### Task 3: Validate the flow on the planning domain

**Files:**
- Modify: `docs/plans/2026-03-08-planning-module-verification.md`

**Step 1: Run targeted verification**

Run:
- `ASF_TMP_DIR=/tmp/asf_wms_planning /Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.management.tests_management_seed_planning_demo_data wms.tests.planning.tests_run_preparation wms.tests.planning.tests_solver_contracts -v 2`
- `ASF_TMP_DIR=/tmp/asf_wms_planning /Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py seed_planning_demo_data --scenario smoke --solve`

Expected: tests pass and the command reports a solved run with at least one assignment.

### Task 4: Commit the lot

**Files:**
- Add the new command, tests, and doc updates

**Step 1: Commit**

```bash
git add docs/plans/2026-03-08-planning-demo-seed-implementation-plan.md \
  wms/management/commands/seed_planning_demo_data.py \
  wms/tests/management/tests_management_seed_planning_demo_data.py \
  docs/plans/2026-03-08-planning-module-verification.md
git commit -m "feat(planning): add demo planning seed command"
```
