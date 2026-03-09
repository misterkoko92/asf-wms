# Planning Solver Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Adapter dans `asf-wms` le solveur OR-Tools et les regles critiques du repo planning historique afin d'obtenir un comportement proche du legacy sur des semaines de reference, tout en conservant le contrat applicatif du module planning WMS.

**Architecture:** La phase reste limitee a la pile Django legacy. Les services `wms/planning/rules.py`, `wms/planning/snapshots.py` et `wms/planning/solver.py` evoluent pour porter un payload plus riche, des contraintes CP-SAT et des diagnostics comparables au legacy. Les vues planning et le contrat `PlanningRun -> PlanningVersion -> PlanningAssignment` restent stables.

**Tech Stack:** Django 4.2, ORM Django, OR-Tools CP-SAT, tests Django `manage.py test`, repo de reference `../asf_scheduler/new_repo`.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:systematic-debugging`, `@superpowers:verification-before-completion`, `@superpowers:requesting-code-review`, `@superpowers:using-git-worktrees`.

### Task 1: Cartographier le solveur legacy contre le contrat WMS

**Files:**
- Modify: `docs/plans/2026-03-09-planning-solver-parity-design.md`
- Create: `docs/plans/2026-03-09-planning-solver-parity-mapping.md`
- Read: `../asf_scheduler/new_repo/scheduler/solver_ortools_common.py`
- Read: `../asf_scheduler/new_repo/scheduler/solver_ortools.py`
- Read: `../asf_scheduler/new_repo/scheduler/solver_ortools_v3.py`
- Read: `../asf_scheduler/new_repo/tests/test_solver_contracts.py`
- Read: `../asf_scheduler/new_repo/tests/test_solver_v3_strict_capacity.py`
- Read: `wms/planning/rules.py`
- Read: `wms/planning/solver.py`

**Step 1: Write the failing test**

Ajouter un premier test de contrat qui exprime le diagnostic cible absent aujourd'hui.

```python
from django.test import TestCase

from wms.tests.planning.factories import build_solver_payload
from wms.planning.solver import summarize_solver_result


class SolverParityContractTests(TestCase):
    def test_summary_exposes_candidate_and_unassigned_diagnostics(self):
        payload = build_solver_payload()
        summary = summarize_solver_result(
            payload=payload,
            selected_candidates=[],
            compatibility=[],
        )
        self.assertIn("candidate_count", summary)
        self.assertIn("unassigned_reasons", summary)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.planning.tests_solver_contracts -v 2`
Expected: FAIL because the summary helper and richer diagnostics do not exist yet.

**Step 3: Write minimal implementation**

- Produire `docs/plans/2026-03-09-planning-solver-parity-mapping.md` avec:
  - inventaire des inputs legacy
  - mapping vers snapshots et payload WMS
  - contraintes legacy ciblees pour la phase
  - ecarts connus a ne pas traiter dans ce lot
- Ajouter dans `wms/planning/solver.py` une facade minimale de resume de resultat qui prepare le contrat de diagnostic cible

**Step 4: Run test to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.planning.tests_solver_contracts -v 2`

Expected: PASS with a stable placeholder contract for the next tasks.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-09-planning-solver-parity-design.md docs/plans/2026-03-09-planning-solver-parity-mapping.md wms/planning/solver.py wms/tests/planning/tests_solver_contracts.py
git commit -m "docs(planning): map solver legacy inputs to WMS"
```

### Task 2: Enrichir le payload solveur et les snapshots WMS

**Files:**
- Modify: `wms/planning/rules.py`
- Modify: `wms/planning/snapshots.py`
- Modify: `wms/models_domain/planning.py`
- Modify: `wms/planning/flight_sources.py`
- Create: `wms/tests/planning/tests_solver_payload.py`
- Modify: `wms/tests/planning/tests_run_preparation.py`
- Modify: `wms/migrations/` via `makemigrations` if model fields are added

**Step 1: Write the failing test**

Ajouter un test qui verifie que le payload expose les metadonnees solveur critiques.

```python
from django.test import TestCase

from wms.planning.rules import compile_solver_payload
from wms.tests.planning.factories import make_ready_run


class SolverPayloadTests(TestCase):
    def test_payload_includes_route_frequency_and_capacity_fields(self):
        run = make_ready_run()
        payload = compile_solver_payload(run)
        flight = payload["flights"][0]
        self.assertIn("routing", flight)
        self.assertIn("route_pos", flight)
        self.assertIn("physical_flight_key", flight)
        self.assertIn("weekly_frequency", flight)
        self.assertIn("max_cartons_per_flight", flight)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.planning.tests_solver_payload -v 2`
Expected: FAIL because the current payload is too sparse.

**Step 3: Write minimal implementation**

- Porter dans `wms/planning/rules.py` les helpers utiles deja prototypes dans `codex/planning-ortools-solver`:
  - parsing heure
  - `build_physical_flight_key`
  - normalisation `route_pos`
  - extraction des regles destination
- Enrichir les snapshots et les vols avec les champs strictement necessaires:
  - `routing`
  - `route_pos`
  - `origin_iata`
  - heure de depart exploitable
  - capacite equivalente
  - `max_cartons_per_flight`
  - `weekly_frequency`
- Conserver le schema de sortie du payload compatible avec la persistance WMS

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.planning.tests_solver_payload -v 2`
- `./.venv/bin/python manage.py test wms.tests.planning.tests_run_preparation -v 2`
- `./.venv/bin/python manage.py test wms.tests.management.tests_management_makemigrations_check -v 2`

Expected: PASS with no migration drift.

**Step 5: Commit**

```bash
git add wms/planning/rules.py wms/planning/snapshots.py wms/models_domain/planning.py wms/planning/flight_sources.py wms/tests/planning/tests_solver_payload.py wms/tests/planning/tests_run_preparation.py wms/migrations
git commit -m "feat(planning): enrich solver payload for parity"
```

### Task 3: Porter les contraintes de compatibilite du legacy

**Files:**
- Modify: `wms/planning/rules.py`
- Create: `wms/tests/planning/tests_solver_constraints.py`
- Modify: `wms/tests/planning/tests_solver_contracts.py`
- Read: `../asf_scheduler/new_repo/tests/test_solver_v3_strict_capacity.py`
- Read: `../asf_scheduler/new_repo/tests/test_solver_contracts.py`

**Step 1: Write the failing test**

Ajouter des tests qui verrouillent les contraintes prioritaires.

```python
from django.test import TestCase

from wms.planning.rules import compute_compatibility
from wms.tests.planning.factories import build_candidate_payload


class SolverConstraintTests(TestCase):
    def test_same_physical_flight_keeps_one_assignment_per_volunteer(self):
        payload = build_candidate_payload(same_physical_flight=True)
        compatibility = compute_compatibility(payload)
        self.assertTrue(any(row["physical_flight_key"] for row in compatibility))

    def test_departure_time_outside_volunteer_slot_is_incompatible(self):
        payload = build_candidate_payload(slot_miss=True)
        compatibility = compute_compatibility(payload)
        self.assertFalse(
            any(
                row["shipment_snapshot_id"] == payload["shipments"][0]["id"]
                for row in compatibility
            )
        )
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.planning.tests_solver_constraints -v 2`
Expected: FAIL because time window and physical flight constraints are not modeled yet.

**Step 3: Write minimal implementation**

- Porter dans `wms/planning/rules.py`:
  - compatibilite temporelle benevole/vol
  - contrainte `max_colis_par_vol`
  - contrainte capacite equivalente
  - exclusivite sur vol physique multi-stop
  - frequence hebdomadaire destination si necessaire au filtrage
- Exposer des diagnostics de compatibilite pour expliquer pourquoi un candidat est exclu

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.planning.tests_solver_constraints -v 2`
- `./.venv/bin/python manage.py test wms.tests.planning.tests_solver_contracts -v 2`

Expected: PASS with explicit coverage of the main blocking rules.

**Step 5: Commit**

```bash
git add wms/planning/rules.py wms/tests/planning/tests_solver_constraints.py wms/tests/planning/tests_solver_contracts.py
git commit -m "feat(planning): port legacy solver compatibility rules"
```

### Task 4: Remplacer `greedy_v1` par le solveur OR-Tools CP-SAT

**Files:**
- Modify: `wms/planning/solver.py`
- Modify: `requirements.txt`
- Modify: `pyproject.toml`
- Modify: `wms/tests/planning/tests_solver_contracts.py`
- Create: `wms/tests/planning/tests_solver_ortools.py`
- Read: `../asf_scheduler/new_repo/scheduler/solver_ortools_v3.py`

**Step 1: Write the failing test**

Ajouter un test qui verrouille l'utilisation du solveur OR-Tools et la persistance des affectations.

```python
from django.test import TestCase

from wms.models import PlanningRun
from wms.planning.solver import solve_run
from wms.tests.planning.factories import make_ready_run_with_candidates


class SolverOrtoolsTests(TestCase):
    def test_solve_run_uses_ortools_and_persists_a_version(self):
        run = make_ready_run_with_candidates()
        version = solve_run(run)
        run.refresh_from_db()
        self.assertEqual(run.solver_result["solver"], "ortools_cp_sat_v1")
        self.assertEqual(version.run_id, run.id)
        self.assertGreaterEqual(version.assignments.count(), 1)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.planning.tests_solver_ortools -v 2`
Expected: FAIL because `greedy_v1` is still in use.

**Step 3: Write minimal implementation**

- Ajouter `ortools` dans `requirements.txt` et `pyproject.toml`
- Porter le coeur CP-SAT dans `wms/planning/solver.py` en conservant:
  - `solve_run(run)`
  - creation de `PlanningVersion`
  - creation de `PlanningAssignment`
  - mise a jour de `run.solver_result`
- Reprendre du prototype `codex/planning-ortools-solver` uniquement les parties necessaires au contrat WMS

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.planning.tests_solver_ortools -v 2`
- `./.venv/bin/python manage.py test wms.tests.planning.tests_solver_contracts -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_planning -v 2`

Expected: PASS and stable planning UI workflow.

**Step 5: Commit**

```bash
git add wms/planning/solver.py requirements.txt pyproject.toml wms/tests/planning/tests_solver_ortools.py wms/tests/planning/tests_solver_contracts.py
git commit -m "feat(planning): switch planning solver to ortools"
```

### Task 5: Porter les diagnostics et le diff legacy vs WMS

**Files:**
- Modify: `wms/planning/solver.py`
- Modify: `wms/planning/rules.py`
- Create: `wms/tests/planning/tests_solver_diagnostics.py`
- Create: `docs/plans/2026-03-09-planning-solver-parity-validation.md`

**Step 1: Write the failing test**

Ajouter un test qui verrouille les diagnostics minimum exposes apres resolution.

```python
from django.test import TestCase

from wms.planning.solver import solve_run
from wms.tests.planning.factories import make_ready_run_with_candidates


class SolverDiagnosticsTests(TestCase):
    def test_solver_result_exposes_unassigned_reasons_and_flight_usage(self):
        run = make_ready_run_with_candidates()
        solve_run(run)
        run.refresh_from_db()
        result = run.solver_result
        self.assertIn("candidate_count", result)
        self.assertIn("assignment_count_by_flight", result)
        self.assertIn("unassigned_reasons", result)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.planning.tests_solver_diagnostics -v 2`
Expected: FAIL because the richer diagnostics are not fully persisted yet.

**Step 3: Write minimal implementation**

- Enrichir `run.solver_result` avec:
  - `candidate_count`
  - usage vol et benevole
  - expeditions non affectees et raison principale
  - eventuels diagnostics de vols sans benevole compatible
- Documenter dans `2026-03-09-planning-solver-parity-validation.md` le format de comparaison attendu contre le legacy

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.planning.tests_solver_diagnostics -v 2`
- `./.venv/bin/python manage.py test wms.tests.planning -v 2`

Expected: PASS with richer diagnostics and no planning regression.

**Step 5: Commit**

```bash
git add wms/planning/solver.py wms/planning/rules.py wms/tests/planning/tests_solver_diagnostics.py docs/plans/2026-03-09-planning-solver-parity-validation.md
git commit -m "feat(planning): add solver parity diagnostics"
```

### Task 6: Valider sur un corpus de reference et documenter les ecarts

**Files:**
- Create: `wms/tests/planning/tests_solver_reference_cases.py`
- Create: `wms/tests/planning/fixtures/solver_reference_cases/`
- Modify: `docs/plans/2026-03-09-planning-solver-parity-validation.md`
- Read: corpus exports from `../asf_scheduler/new_repo`

**Step 1: Write the failing test**

Ajouter au moins un cas de reference qui compare une solution WMS a un resultat legacy fige.

```python
from django.test import TestCase

from wms.planning.solver import solve_run
from wms.tests.planning.reference_cases import load_reference_case


class SolverReferenceCaseTests(TestCase):
    def test_reference_case_nominal_week_matches_expected_assignments(self):
        case = load_reference_case("nominal_week")
        version = solve_run(case.run)
        assignments = sorted(
            version.assignments.values_list(
                "shipment_snapshot__shipment_reference",
                "flight_snapshot__flight_number",
                "volunteer_snapshot__display_name",
            )
        )
        self.assertEqual(assignments, case.expected_assignments)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.planning.tests_solver_reference_cases -v 2`
Expected: FAIL until the fixtures and parity comparison harness exist.

**Step 3: Write minimal implementation**

- Introduire au moins un cas de reference rejouable
- Construire un petit loader ou une fixture qui instancie le run avec snapshots attendus
- Documenter les ecarts residuels acceptes entre legacy et WMS

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.planning.tests_solver_reference_cases -v 2`
- `./.venv/bin/python manage.py test wms.tests.planning wms.tests.views.tests_views_planning -v 2`

Expected: PASS with at least one golden reference week and documented residual gaps.

**Step 5: Commit**

```bash
git add wms/tests/planning/tests_solver_reference_cases.py wms/tests/planning/fixtures/solver_reference_cases docs/plans/2026-03-09-planning-solver-parity-validation.md
git commit -m "test(planning): add solver reference parity cases"
```

## Final Verification
Run:
- `./.venv/bin/python manage.py test wms.tests.planning -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_planning wms.tests.views.tests_views_volunteer -v 2`
- `./.venv/bin/python manage.py test wms.tests.management.tests_management_makemigrations_check -v 2`
- `./.venv/bin/ruff check wms/planning wms/tests/planning wms/views_planning.py`

Expected:
- tests planning verts
- vues planning encore vertes
- pas de drift migration
- lint cible vert

## Sequencing Notes
- Commencer par les entrees solveur avant de brancher CP-SAT
- Ne pas ouvrir le scope API vols concret pendant cette phase
- Ne pas enrichir `Planning.xlsx` tant que le solveur n'a pas une parite minimale prouvee

Plan complete and saved to `docs/plans/2026-03-09-planning-solver-parity-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
