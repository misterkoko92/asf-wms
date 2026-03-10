# Planning Smoke Test Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ajouter un smoke test planning deterministe qui valide le chemin nominal `seed -> solve -> publish -> drafts -> export -> cockpit` sans dependance externe.

**Architecture:** Reposer sur le seed de demo planning existant pour construire un run resolu, puis enchaîner publication, generation des brouillons et export workbook via les services planning deja en place. Terminer le test par un `GET` staff sur la page de version afin de couvrir la surface HTTP operateur principale, tout en limitant les assertions a des invariants structurels.

**Tech Stack:** Django `TestCase`, `call_command`, services planning (`versioning`, `communications`, `exports`), client de test Django, `manage.py test`, `ruff`.

---

### Task 1: Poser le test de fumee nominal et le faire echouer

**Files:**
- Create: `wms/tests/planning/tests_smoke_planning_flow.py`
- Test: `wms/tests/planning/tests_smoke_planning_flow.py`

**Step 1: Write the failing test**

```python
from django.core.management import call_command


def test_planning_smoke_flow_seed_to_cockpit(self):
    call_command("seed_planning_demo_data", scenario="smoke-e2e", solve=True)

    run = PlanningRun.objects.get(parameter_set__name="DEMO smoke-e2e")
    version = run.versions.get(number=1)

    self.assertEqual(run.status, PlanningRun.Status.SOLVED)
    self.assertTrue(version.assignments.exists())
```

Add the rest of the intended flow in the same test body:
- publish the version
- generate drafts
- generate workbook export
- GET version detail as staff
- assert structural invariants

**Step 2: Run test to verify it fails**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_smoke_planning_flow -v 2
```

Expected: FAIL because the smoke test file does not exist yet or because the nominal flow is not fully wired in the test.

**Step 3: Write minimal implementation**

- Create `wms/tests/planning/tests_smoke_planning_flow.py`.
- Add a `TestCase` with:
  - a staff user setup
  - `call_command("seed_planning_demo_data", scenario="smoke-e2e", solve=True)`
  - retrieval of the `PlanningRun` and first `PlanningVersion`
- Keep the scenario name explicit and dedicated to this smoke path.
- Avoid any assertion on exact assignment identities.

**Step 4: Run test to verify it passes minimally**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_smoke_planning_flow -v 2
```

Expected: PASS for the initial nominal skeleton.

**Step 5: Commit**

```bash
git add wms/tests/planning/tests_smoke_planning_flow.py
git commit -m "test(planning): add smoke flow skeleton"
```

### Task 2: Couvrir publication, brouillons et export workbook

**Files:**
- Modify: `wms/tests/planning/tests_smoke_planning_flow.py`
- Test: `wms/tests/planning/tests_smoke_planning_flow.py`

**Step 1: Extend the failing test**

```python
publish_planning_version(version)
generate_version_drafts(version)
artifact = generate_planning_export(version)

self.assertEqual(version.status, PlanningVersion.Status.PUBLISHED)
self.assertTrue(version.communication_drafts.exists())
self.assertEqual(artifact.version_id, version.id)
```

**Step 2: Run test to verify it fails**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_smoke_planning_flow -v 2
```

Expected: FAIL until the test imports the right services and follows the current planning API correctly.

**Step 3: Write minimal implementation**

- Import and use the existing planning services already present in the codebase:
  - publication/versioning service
  - communication draft generation service
  - planning export service
- Refresh ORM objects after service calls where needed.
- Assert only:
  - published version status
  - at least one draft
  - at least one export artifact
  - same version linkage

**Step 4: Run test to verify it passes**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_smoke_planning_flow -v 2
```

Expected: PASS with the full nominal service chain.

**Step 5: Commit**

```bash
git add wms/tests/planning/tests_smoke_planning_flow.py
git commit -m "test(planning): cover smoke publication and outputs"
```

### Task 3: Couvrir la page cockpit finale et durcir les invariants

**Files:**
- Modify: `wms/tests/planning/tests_smoke_planning_flow.py`
- Modify: `wms/tests/views/tests_views_planning.py` (only if a helper is worth reusing)
- Test: `wms/tests/planning/tests_smoke_planning_flow.py`

**Step 1: Extend the failing test**

```python
response = self.client.get(reverse("planning:version_detail", args=[version.pk]))

self.assertEqual(response.status_code, 200)
self.assertContains(response, version.label)
self.assertTrue(version.assignments.exists())
self.assertTrue(version.communication_drafts.exists())
```

**Step 2: Run test to verify it fails**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_smoke_planning_flow -v 2
```

Expected: FAIL until the test client is authenticated as staff and the final page path is correctly exercised.

**Step 3: Write minimal implementation**

- Log in the test client as a staff user created in `setUp`.
- Hit `reverse("planning:version_detail", args=[version.pk])`.
- Keep the final assertions structural:
  - `200`
  - page references the tested version
  - assignments, drafts, and export artifact still exist after page load

Only reuse a helper from `wms/tests/views/tests_views_planning.py` if it meaningfully reduces duplication; otherwise keep the smoke test self-contained.

**Step 4: Run test to verify it passes**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_smoke_planning_flow -v 2
```

Expected: PASS with complete `seed -> solve -> publish -> drafts -> export -> cockpit`.

**Step 5: Commit**

```bash
git add wms/tests/planning/tests_smoke_planning_flow.py wms/tests/views/tests_views_planning.py
git commit -m "test(planning): finish smoke flow coverage"
```

### Task 4: Rejouer la regression planning et documenter le garde-fou

**Files:**
- Modify: `docs/plans/2026-03-08-planning-module-verification.md`
- Modify: `docs/plans/2026-03-10-planning-smoke-test-design.md`
- Modify: `docs/plans/2026-03-10-planning-smoke-test-implementation-plan.md`
- Test: `wms/tests/planning/tests_smoke_planning_flow.py`
- Test: `wms/tests/planning/`
- Test: `wms/tests/views/tests_views_planning.py`

**Step 1: Run focused test first**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_smoke_planning_flow -v 2
```

Expected: PASS.

**Step 2: Run broader planning regression**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning wms.tests.views.tests_views_planning wms.tests.management.tests_management_seed_planning_demo_data wms.tests.management.tests_management_makemigrations_check -v 1
```

Expected: PASS with no planning regression introduced by the smoke test.

**Step 3: Run lint**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/ruff check wms/tests/planning wms/tests/views/tests_views_planning.py
```

Expected: `All checks passed!`

**Step 4: Document the new guardrail**

- Update `docs/plans/2026-03-08-planning-module-verification.md` to mention the new smoke test and its role.
- Keep `docs/plans/2026-03-10-planning-smoke-test-design.md` and `docs/plans/2026-03-10-planning-smoke-test-implementation-plan.md` aligned with the delivered flow if a small wording adjustment is needed.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-08-planning-module-verification.md docs/plans/2026-03-10-planning-smoke-test-design.md docs/plans/2026-03-10-planning-smoke-test-implementation-plan.md wms/tests/planning/tests_smoke_planning_flow.py wms/tests/views/tests_views_planning.py
git commit -m "test(planning): add end-to-end smoke flow guardrail"
```
