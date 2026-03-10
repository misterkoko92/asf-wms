# Planning Phase 3 Export Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ajouter un export limite et pseudonymise des donnees planning pour la semaine `2026-03-09 -> 2026-03-15`, afin de preparer une base locale rejouable pour la recette phase 3.

**Architecture:** Introduire une commande Django `planning_recipe_export` qui selectionne les objets utiles a partir de la semaine cible, applique une pseudonymisation deterministe sur les donnees identifiantes, et produit un artefact JSON exploitable par une future recharge locale. Encadrer le tout par des tests de selection, d'anonymisation et de cohérence de sortie.

**Tech Stack:** Django management commands, services Python dans `wms/planning/`, tests `manage.py test`, documentation Markdown.

---

### Task 1: Poser le contrat de sortie et les tests de selection

**Files:**
- Create: `wms/planning/recipe_export.py`
- Create: `wms/tests/planning/tests_recipe_export.py`
- Test: `wms/tests/planning/tests_recipe_export.py`

**Step 1: Write the failing tests**

```python
def test_build_planning_recipe_export_selects_only_week_scope():
    export = build_planning_recipe_export(
        week_start=date(2026, 3, 9),
        week_end=date(2026, 3, 15),
    )

    assert export.selection["week_start"] == "2026-03-09"
    assert export.selection["week_end"] == "2026-03-15"
    assert export.summary["flights"] >= 1
```

```python
def test_build_planning_recipe_export_excludes_unrelated_history():
    export = build_planning_recipe_export(
        week_start=date(2026, 3, 9),
        week_end=date(2026, 3, 15),
    )

    assert "planning_versions" not in export.fixtures
```

**Step 2: Run test to verify it fails**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_recipe_export -v 2
```

Expected:
- FAIL because the recipe export builder does not exist yet

**Step 3: Write minimal implementation**

- Create `wms/planning/recipe_export.py`
- Add a builder function that:
  - accepts `week_start` and `week_end`
  - collects the minimum queryset set for flights, shipments, volunteers, destinations, contacts and rules
  - returns a structured payload object/dict with:
    - `meta`
    - `selection`
    - `summary`
    - `fixtures`

**Step 4: Run test to verify it passes**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_recipe_export -v 2
```

Expected:
- PASS with a minimal but coherent selection payload

**Step 5: Commit**

```bash
git add wms/planning/recipe_export.py wms/tests/planning/tests_recipe_export.py
git commit -m "feat(planning): add phase 3 recipe export selection"
```

### Task 2: Ajouter la pseudonymisation deterministe

**Files:**
- Modify: `wms/planning/recipe_export.py`
- Modify: `wms/tests/planning/tests_recipe_export.py`
- Test: `wms/tests/planning/tests_recipe_export.py`

**Step 1: Write the failing tests**

```python
def test_recipe_export_pseudonymizes_volunteers_stably():
    export = build_planning_recipe_export(
        week_start=date(2026, 3, 9),
        week_end=date(2026, 3, 15),
    )

    volunteers = export.fixtures["volunteer_profiles"]
    assert volunteers[0]["display_name"].startswith("VOL-")
```

```python
def test_recipe_export_keeps_same_alias_for_same_source_object():
    export = build_planning_recipe_export(
        week_start=date(2026, 3, 9),
        week_end=date(2026, 3, 15),
    )

    alias_a = export.alias_map["volunteer"][123]
    alias_b = export.alias_map["volunteer"][123]
    assert alias_a == alias_b
```

**Step 2: Run test to verify it fails**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_recipe_export -v 2
```

Expected:
- FAIL because anonymization is not implemented yet

**Step 3: Write minimal implementation**

- Add deterministic pseudonymization helpers for:
  - volunteer display names and emails
  - shipper/contact labels and emails
- Keep operational fields intact:
  - IATA
  - dates
  - quantities
  - rules
  - constraints

**Step 4: Run test to verify it passes**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_recipe_export -v 2
```

Expected:
- PASS with stable aliases and preserved business structure

**Step 5: Commit**

```bash
git add wms/planning/recipe_export.py wms/tests/planning/tests_recipe_export.py
git commit -m "feat(planning): pseudonymize phase 3 recipe export"
```

### Task 3: Exposer la commande `planning_recipe_export`

**Files:**
- Create: `wms/management/commands/planning_recipe_export.py`
- Modify: `wms/tests/planning/tests_recipe_export.py`
- Test: `wms/tests/planning/tests_recipe_export.py`

**Step 1: Write the failing test**

```python
def test_planning_recipe_export_command_writes_json_file(tmp_path):
    output = tmp_path / "planning_recipe.json"

    call_command(
        "planning_recipe_export",
        week_start="2026-03-09",
        week_end="2026-03-15",
        output=str(output),
    )

    assert output.exists()
```

**Step 2: Run test to verify it fails**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_recipe_export -v 2
```

Expected:
- FAIL because the command does not exist

**Step 3: Write minimal implementation**

- Create `wms/management/commands/planning_recipe_export.py`
- Support:
  - `--week-start`
  - `--week-end`
  - `--output`
  - optional `--no-anonymize`
- Write JSON payload to disk
- Print a short summary:
  - output path
  - volumes exported

**Step 4: Run test to verify it passes**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_recipe_export -v 2
```

Expected:
- PASS with a created JSON export file

**Step 5: Commit**

```bash
git add wms/management/commands/planning_recipe_export.py wms/tests/planning/tests_recipe_export.py
git commit -m "feat(planning): add recipe export command"
```

### Task 4: Document usage and run focused verification

**Files:**
- Modify: `docs/plans/2026-03-10-planning-phase3-recipe-runbook.md`
- Modify: `docs/plans/2026-03-10-planning-phase3-isolated-result.md`
- Modify: `docs/plans/2026-03-10-planning-phase3-export-design.md`
- Modify: `docs/plans/2026-03-10-planning-phase3-export-implementation-plan.md`
- Test: `wms/tests/planning/tests_recipe_export.py`

**Step 1: Add the usage snippet**

Document the command in the runbook with a concrete example:

```bash
python manage.py planning_recipe_export \
  --week-start 2026-03-09 \
  --week-end 2026-03-15 \
  --output /tmp/planning_recipe_s11_2026.json
```

**Step 2: Run focused verification**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_recipe_export -v 2
```

Expected:
- PASS

**Step 3: Run broader regression**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning wms.tests.management.tests_management_makemigrations_check -v 1
```

Expected:
- PASS without planning regression

**Step 4: Run lint**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/ruff check wms/planning/recipe_export.py wms/management/commands/planning_recipe_export.py wms/tests/planning/tests_recipe_export.py
```

Expected:
- `All checks passed!`

**Step 5: Commit**

```bash
git add docs/plans/2026-03-10-planning-phase3-recipe-runbook.md docs/plans/2026-03-10-planning-phase3-isolated-result.md docs/plans/2026-03-10-planning-phase3-export-design.md docs/plans/2026-03-10-planning-phase3-export-implementation-plan.md wms/planning/recipe_export.py wms/management/commands/planning_recipe_export.py wms/tests/planning/tests_recipe_export.py
git commit -m "docs(planning): wire recipe export into phase 3"
```
