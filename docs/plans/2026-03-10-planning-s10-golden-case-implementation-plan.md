# Planning S10 Golden Case Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Faire de `legacy_session_s10_2026` un golden case hebdomadaire complet, en egalite stricte avec le legacy sur toutes les affectations, sans casser `legacy_session_s11_2026`.

**Architecture:** Le harnais de reference existant est conserve. La phase renforce d'abord la fixture `s10` et le test de reference, puis corrige uniquement les causes structurelles dans le builder, le payload solveur ou le solveur lui-meme jusqu'a ce que `s10` et `s11` passent tous les deux en strict.

**Tech Stack:** Django 4.2, ORM Django, OR-Tools CP-SAT, fixtures JSON de reference, commande `build_legacy_planning_reference_case`, tests `manage.py test`.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:systematic-debugging`, `@superpowers:verification-before-completion`, `@superpowers:requesting-code-review`, `@superpowers:using-git-worktrees`.

### Task 1: Regenerer et figer la fixture hebdomadaire complete `s10`

**Files:**
- Modify: `wms/tests/planning/fixtures/solver_reference_cases/legacy_session_s10_2026.json`
- Read: `wms/management/commands/build_legacy_planning_reference_case.py`
- Read: `wms/planning/reference_case_builder.py`
- Read: `docs/plans/2026-03-09-planning-solver-parity-validation.md`

**Step 1: Write the failing test**

Transformer le test `s10` pour exiger une egalite stricte complete, sur le modele de `s11`.

```python
def test_reference_case_legacy_session_s10_2026_matches_expected_assignments(self):
    self._assert_reference_case("legacy_session_s10_2026")
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_solver_reference_cases -v 2`
Expected: FAIL because the current `s10` fixture or solver output does not yet match strictly.

**Step 3: Write minimal implementation**

- Regenerate `legacy_session_s10_2026.json` from the full legacy week session
- Ensure the fixture carries complete weekly data and strict `expected_assignments`
- Keep the builder generic; do not special-case `s10`

**Step 4: Run test to verify the new fixture is loaded**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_solver_reference_cases -v 2`

Expected: FAIL on a real strict diff, not on missing fixture structure.

**Step 5: Commit**

```bash
git add wms/tests/planning/fixtures/solver_reference_cases/legacy_session_s10_2026.json wms/tests/planning/tests_solver_reference_cases.py
git commit -m "test(planning): make s10 a strict golden case target"
```

### Task 2: Produire un diff solveur exploitable pour `s10`

**Files:**
- Modify: `wms/tests/planning/tests_solver_reference_cases.py`
- Optional create: `wms/tests/planning/tests_solver_reference_case_diffs.py`
- Read: `wms/planning/solver.py`

**Step 1: Write the failing test**

Ajouter un helper de comparaison qui expose clairement les manquants et les extras pour les cas de reference stricts.

```python
def test_reference_case_diff_lists_missing_and_extra_assignments(self):
    missing, extra = compute_assignment_diff(expected=[("A", "AF1", "X")], actual=[])
    self.assertEqual(missing, [("A", "AF1", "X")])
    self.assertEqual(extra, [])
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_solver_reference_cases -v 2`
Expected: FAIL because the diff helper does not exist yet.

**Step 3: Write minimal implementation**

- Add a small reusable diff helper for assignments
- Use it in the `s10` test failure path so debugging is readable
- Keep assertions strict; the helper is diagnostic only

**Step 4: Run tests to verify it passes**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_solver_reference_cases -v 2`

Expected: PASS for the helper, while the strict `s10` case still fails with a useful diff.

**Step 5: Commit**

```bash
git add wms/tests/planning/tests_solver_reference_cases.py
git commit -m "test(planning): add strict reference diff helpers"
```

### Task 3: Corriger le builder ou le payload de reference si `s10` est incomplet

**Files:**
- Modify: `wms/planning/reference_case_builder.py`
- Modify: `wms/tests/planning/reference_cases.py`
- Modify: `wms/tests/planning/fixtures/solver_reference_cases/legacy_session_s10_2026.json`
- Read: `wms/tests/planning/fixtures/solver_reference_cases/legacy_session_s11_2026.json`

**Step 1: Write the failing test**

Ajouter un test qui verrouille les champs de contexte legacy indispensables au chargement strict de `s10`.

```python
def test_legacy_session_s10_fixture_keeps_reference_context_fields(self):
    case = load_reference_case("legacy_session_s10_2026")
    self.assertTrue(case.run.shipment_snapshots.filter(payload__legacy_case_name="legacy_session_s10_2026").exists())
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_solver_reference_cases -v 2`
Expected: FAIL if the fixture or loader still drops context needed for strict parity.

**Step 3: Write minimal implementation**

- Carry any still-missing legacy metadata through the builder and loader
- Regenerate `s10` if needed
- Avoid changing `s11` semantics unless the change is generic

**Step 4: Run tests to verify it passes**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_solver_reference_cases -v 2`

Expected: The fixture loads with the full context needed; remaining failure should now point to solver behavior only.

**Step 5: Commit**

```bash
git add wms/planning/reference_case_builder.py wms/tests/planning/reference_cases.py wms/tests/planning/fixtures/solver_reference_cases/legacy_session_s10_2026.json
git commit -m "feat(planning): complete s10 legacy reference payload"
```

### Task 4: Aligner le solveur pour faire passer `s10` en strict sans casser `s11`

**Files:**
- Modify: `wms/planning/rules.py`
- Modify: `wms/planning/solver.py`
- Modify: `wms/tests/planning/tests_solver_reference_cases.py`
- Modify: `wms/tests/planning/tests_solver_ortools.py`
- Read: `docs/plans/2026-03-09-planning-solver-parity-validation.md`

**Step 1: Write the failing test**

Use the strict `s10` golden test as the red test. Do not add a weaker alternate assertion.

**Step 2: Run test to verify it fails**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_solver_reference_cases -v 2`

Expected: FAIL with exact missing and extra assignments for `s10`.

**Step 3: Write minimal implementation**

- Fix only structural causes:
  - missing payload fields
  - missing legacy rule
  - missing tie-break
  - wrong priority semantics
- Re-run `s10` and `s11` after each change
- Reject any change that introduces a week-specific exception

**Step 4: Run tests to verify it passes**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_solver_reference_cases -v 2`
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_solver_ortools -v 2`

Expected: `s10` and `s11` both pass strictly.

**Step 5: Commit**

```bash
git add wms/planning/rules.py wms/planning/solver.py wms/tests/planning/tests_solver_reference_cases.py wms/tests/planning/tests_solver_ortools.py
git commit -m "feat(planning): align s10 weekly golden case parity"
```

### Task 5: Final verification and parity documentation update

**Files:**
- Modify: `docs/plans/2026-03-09-planning-solver-parity-validation.md`

**Step 1: Write the failing test**

No new application test. The failing gate here is the strict parity suite.

**Step 2: Run verification commands**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_solver_reference_cases wms.tests.planning.tests_solver_ortools wms.tests.planning wms.tests.views.tests_views_planning wms.tests.management.tests_management_makemigrations_check -v 1`
- `/Users/EdouardGonnu/asf-wms/.venv/bin/ruff check wms/planning wms/tests/planning wms/views_planning.py`

Expected: PASS, with `s10` and `s11` both strict-green.

**Step 3: Write minimal documentation updates**

- Update the parity validation note to state that `legacy_session_s10_2026` is now a full golden case
- Remove language that still presents `s10` as partial or non-conclusive
- Document the exact residual gap status as zero for `s10`

**Step 4: Re-run verification if code changed during documentation cleanup**

Run the same commands again only if code was touched while finalizing the note.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-09-planning-solver-parity-validation.md
git commit -m "docs(planning): mark s10 as full golden case"
```
