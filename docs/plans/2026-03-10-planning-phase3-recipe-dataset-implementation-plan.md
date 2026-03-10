# Planning Phase 3 Recipe Dataset Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ajouter un jeu de recette planning jetable `phase3-s11-recipe` et sa purge sure pour tester la chaine operateur complete dans `asf-wms`.

**Architecture:** Introduire un service `recipe_dataset` qui porte le scenario operateur et ses helpers de seed/purge, puis l'exposer via deux commandes Django dediees. Encadrer le tout par des tests de commande et de scenario pour garantir la couverture des cas metier et la securite de la purge.

**Tech Stack:** Django management commands, services Python dans `wms/planning/`, tests `manage.py test`, documentation Markdown.

---

### Task 1: Poser le contrat du scenario et les tests rouges

**Files:**
- Create: `wms/tests/management/tests_management_planning_recipe_data.py`
- Create: `wms/planning/recipe_dataset.py`
- Test: `wms/tests/management/tests_management_planning_recipe_data.py`

**Step 1: Write the failing tests**

```python
def test_seed_planning_recipe_data_creates_expected_volumes():
    call_command("seed_planning_recipe_data", "--scenario=phase3-s11-recipe")

    assert PlanningParameterSet.objects.filter(name="RECIPE phase3-s11-recipe").exists()
    assert Flight.objects.filter(batch__source="recipe").count() == 5
    assert Shipment.objects.filter(reference__startswith="RECIPE-PHASE3-S11").count() >= 6
```

```python
def test_seed_recipe_covers_required_business_cases():
    call_command("seed_planning_recipe_data", "--scenario=phase3-s11-recipe", "--solve")

    run = PlanningRun.objects.latest("id")
    version = PlanningVersion.objects.get(run=run)

    assert version.assignments.filter(flight__routing="CDG-NSI-DLA").exists()
    assert version.unassigned_shipments.exists()
```

**Step 2: Run test to verify it fails**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.management.tests_management_planning_recipe_data -v 2
```

Expected:
- FAIL because the recipe dataset service and commands do not exist yet

**Step 3: Write minimal implementation**

- Create `wms/planning/recipe_dataset.py`
- Add scenario constants:
  - week start/end
  - destination rules
  - flight specs
  - volunteer specs
  - shipment specs
- Keep the service focused on scenario data composition only for now

**Step 4: Run test to verify it still fails on missing command layer**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.management.tests_management_planning_recipe_data -v 2
```

Expected:
- FAIL now because the command layer is still missing

**Step 5: Commit**

```bash
git add wms/planning/recipe_dataset.py wms/tests/management/tests_management_planning_recipe_data.py
git commit -m "test(planning): add recipe dataset scenario contract"
```

### Task 2: Implementer `seed_planning_recipe_data`

**Files:**
- Create: `wms/management/commands/seed_planning_recipe_data.py`
- Modify: `wms/planning/recipe_dataset.py`
- Modify: `wms/tests/management/tests_management_planning_recipe_data.py`
- Test: `wms/tests/management/tests_management_planning_recipe_data.py`

**Step 1: Write the failing command test**

```python
def test_seed_planning_recipe_data_can_solve_run():
    call_command(
        "seed_planning_recipe_data",
        "--scenario=phase3-s11-recipe",
        "--solve",
    )

    run = PlanningRun.objects.get()
    assert run.status == PlanningRunStatus.SOLVED
```

**Step 2: Run test to verify it fails**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.management.tests_management_planning_recipe_data -v 2
```

Expected:
- FAIL because `seed_planning_recipe_data` does not exist yet

**Step 3: Write minimal implementation**

- Create `wms/management/commands/seed_planning_recipe_data.py`
- Reuse/adapter patterns from `seed_planning_demo_data.py`
- Implement:
  - namespace `RECIPE phase3-s11`
  - destinations `NSI`, `DLA`, `ABJ`
  - flights including `CDG-NSI-DLA`
  - volunteer constraints and availabilities
  - shipments with enough load to trigger all required business cases
  - optional `--solve`

**Step 4: Run test to verify it passes**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.management.tests_management_planning_recipe_data -v 2
```

Expected:
- PASS with a solved run and recipe objects created

**Step 5: Commit**

```bash
git add wms/management/commands/seed_planning_recipe_data.py wms/planning/recipe_dataset.py wms/tests/management/tests_management_planning_recipe_data.py
git commit -m "feat(planning): add phase 3 recipe seed command"
```

### Task 3: Verrouiller les cas metier du scenario

**Files:**
- Modify: `wms/tests/management/tests_management_planning_recipe_data.py`
- Modify: `wms/planning/recipe_dataset.py`
- Test: `wms/tests/management/tests_management_planning_recipe_data.py`

**Step 1: Write the failing assertions for the required business cases**

```python
def test_seed_recipe_enforces_paramdest_day_rule():
    call_command("seed_planning_recipe_data", "--scenario=phase3-s11-recipe", "--solve")
    version = PlanningVersion.objects.latest("id")

    assert not version.assignments.filter(flight__flight_number="AF945").exists()
```

```python
def test_seed_recipe_exposes_multistop_single_destination_rule():
    call_command("seed_planning_recipe_data", "--scenario=phase3-s11-recipe", "--solve")
    version = PlanningVersion.objects.latest("id")

    destinations = set(
        version.assignments.filter(flight__flight_number="AF982")
        .values_list("shipment__destination__iata_code", flat=True)
    )
    assert destinations == {"NSI"}
```

```python
def test_seed_recipe_leaves_at_least_one_unassigned_shipment():
    call_command("seed_planning_recipe_data", "--scenario=phase3-s11-recipe", "--solve")
    run = PlanningRun.objects.latest("id")

    assert run.solver_result["unassigned_count"] >= 1
```

**Step 2: Run test to verify it fails**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.management.tests_management_planning_recipe_data -v 2
```

Expected:
- FAIL until the seeded scenario is tuned to trigger the exact expected behavior

**Step 3: Tune the scenario minimally**

- Adjust `PlanningDestinationRule`
- Adjust capacities
- Adjust volunteer availability windows
- Adjust shipment equivalent units
- Keep the scenario small and readable

**Step 4: Run test to verify it passes**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.management.tests_management_planning_recipe_data -v 2
```

Expected:
- PASS with all required recipe cases covered

**Step 5: Commit**

```bash
git add wms/planning/recipe_dataset.py wms/tests/management/tests_management_planning_recipe_data.py
git commit -m "test(planning): lock phase 3 recipe business cases"
```

### Task 4: Implementer `purge_planning_recipe_data`

**Files:**
- Create: `wms/management/commands/purge_planning_recipe_data.py`
- Modify: `wms/planning/recipe_dataset.py`
- Modify: `wms/tests/management/tests_management_planning_recipe_data.py`
- Test: `wms/tests/management/tests_management_planning_recipe_data.py`

**Step 1: Write the failing purge tests**

```python
def test_purge_planning_recipe_data_dry_run_only_reports_counts():
    call_command("seed_planning_recipe_data", "--scenario=phase3-s11-recipe")
    output = StringIO()

    call_command("purge_planning_recipe_data", "--scenario=phase3-s11-recipe", stdout=output)

    assert "dry-run" in output.getvalue().lower()
    assert PlanningParameterSet.objects.filter(name="RECIPE phase3-s11-recipe").exists()
```

```python
def test_purge_planning_recipe_data_deletes_only_recipe_namespace():
    call_command("seed_planning_recipe_data", "--scenario=phase3-s11-recipe")
    keep = PlanningParameterSet.objects.create(name="Keep me")

    call_command("purge_planning_recipe_data", "--scenario=phase3-s11-recipe", "--yes")

    assert not PlanningParameterSet.objects.filter(name="RECIPE phase3-s11-recipe").exists()
    assert PlanningParameterSet.objects.filter(pk=keep.pk).exists()
```

**Step 2: Run test to verify it fails**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.management.tests_management_planning_recipe_data -v 2
```

Expected:
- FAIL because the purge command does not exist yet

**Step 3: Write minimal implementation**

- Create `wms/management/commands/purge_planning_recipe_data.py`
- Add dry-run output
- Require `--yes` for deletion
- Delete only namespace-bound objects in dependency-safe order

**Step 4: Run test to verify it passes**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.management.tests_management_planning_recipe_data -v 2
```

Expected:
- PASS with dry-run and real purge both behaving safely

**Step 5: Commit**

```bash
git add wms/management/commands/purge_planning_recipe_data.py wms/planning/recipe_dataset.py wms/tests/management/tests_management_planning_recipe_data.py
git commit -m "feat(planning): add phase 3 recipe purge command"
```

### Task 5: Document usage and run verification

**Files:**
- Modify: `docs/plans/2026-03-10-planning-phase3-recipe-runbook.md`
- Modify: `docs/plans/2026-03-10-planning-phase3-isolated-result.md`
- Modify: `docs/plans/2026-03-10-planning-phase3-pythonanywhere-result.md`
- Modify: `docs/plans/2026-03-10-planning-phase3-recipe-dataset-design.md`
- Modify: `docs/plans/2026-03-10-planning-phase3-recipe-dataset-implementation-plan.md`
- Test: `wms/tests/management/tests_management_planning_recipe_data.py`

**Step 1: Add usage snippets**

Document:

```bash
python manage.py seed_planning_recipe_data --scenario phase3-s11-recipe --solve
python manage.py purge_planning_recipe_data --scenario phase3-s11-recipe
python manage.py purge_planning_recipe_data --scenario phase3-s11-recipe --yes
```

**Step 2: Run focused verification**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.management.tests_management_planning_recipe_data -v 2
```

Expected:
- PASS

**Step 3: Run broader regression**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning wms.tests.management.tests_management_seed_planning_demo_data wms.tests.management.tests_management_makemigrations_check -v 1
```

Expected:
- PASS without planning regression

**Step 4: Run lint**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/ruff check wms/planning/recipe_dataset.py wms/management/commands/seed_planning_recipe_data.py wms/management/commands/purge_planning_recipe_data.py wms/tests/management/tests_management_planning_recipe_data.py
```

Expected:
- `All checks passed!`

**Step 5: Commit**

```bash
git add docs/plans/2026-03-10-planning-phase3-recipe-runbook.md docs/plans/2026-03-10-planning-phase3-isolated-result.md docs/plans/2026-03-10-planning-phase3-pythonanywhere-result.md docs/plans/2026-03-10-planning-phase3-recipe-dataset-design.md docs/plans/2026-03-10-planning-phase3-recipe-dataset-implementation-plan.md wms/planning/recipe_dataset.py wms/management/commands/seed_planning_recipe_data.py wms/management/commands/purge_planning_recipe_data.py wms/tests/management/tests_management_planning_recipe_data.py
git commit -m "docs(planning): wire recipe dataset into phase 3"
```
