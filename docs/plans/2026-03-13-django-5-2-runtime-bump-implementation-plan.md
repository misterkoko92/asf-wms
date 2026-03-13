# Django 5.2 Runtime Bump Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update the repository’s real dependency pins from Django 4.2 / DRF 3.15 to Django 5.2 / DRF 3.16 and verify the legacy Django stack on the bumped runtime.

**Architecture:** Keep the already-landed compatibility fixes in place, treat `pyproject.toml` as the dependency source of truth, regenerate exported requirements, then validate the repository from narrow checks to full suite. Use a small regression guard to lock the expected framework versions into tests so the bump cannot silently drift.

**Tech Stack:** Django 5.2, Django REST framework 3.16, uv, pip requirements export, legacy Django test suite

---

### Task 1: Add a failing runtime-version regression guard

**Files:**
- Modify: `wms/tests/management/tests_management_runtime_dependencies.py`
- Test: `wms/tests/management/tests_management_runtime_dependencies.py`

**Step 1: Write the failing test**

Add a focused test that asserts:

- `django.get_version()` starts with `5.2`
- `rest_framework.VERSION` starts with `3.16`

Name it clearly, for example `test_runtime_dependency_versions_match_supported_baseline`.

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.management.tests_management_runtime_dependencies -v 2
```

Expected: FAIL because the branch still uses Django 4.2 / DRF 3.15 before the pin update.

**Step 3: Write minimal implementation**

Implement the regression guard only. Do not update production code yet.

**Step 4: Run test to verify the failure is the expected one**

Run the same command and confirm the failing assertion points to the pinned versions, not to a broken import or unrelated error.

**Step 5: Commit**

```bash
git add wms/tests/management/tests_management_runtime_dependencies.py
git commit -m "test: guard Django 5.2 runtime baseline"
```

### Task 2: Bump dependency pins and exported requirement files

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Modify: `requirements-dev.txt`

**Step 1: Update the source-of-truth pins**

Change:

- `Django==4.2.11` -> `Django==5.2.12` (or latest validated 5.2 patch available in this branch context)
- `djangorestframework==3.15.2` -> `djangorestframework==3.16.1`

Keep the rest unchanged unless the export process forces lockfile-level updates.

**Step 2: Regenerate exported requirements**

Run:

```bash
make export-requirements
```

Expected: `requirements.txt` and `requirements-dev.txt` update to match `pyproject.toml`.

**Step 3: Install the bumped runtime into the working environment**

Run the repo-approved install path that matches local verification needs. Prefer explicit installs over ad hoc environment mutation.

**Step 4: Run the version-guard test**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.management.tests_management_runtime_dependencies -v 2
```

Expected: PASS

**Step 5: Commit**

```bash
git add pyproject.toml requirements.txt requirements-dev.txt \
  wms/tests/management/tests_management_runtime_dependencies.py
git commit -m "build: bump Django runtime to 5.2"
```

### Task 3: Verify repository compatibility on the bumped runtime

**Files:**
- Modify if needed: any legacy Django file required to satisfy failing verification
- Test: `wms/tests/management/tests_management_makemigrations_check.py`
- Test: `wms/tests/planning/tests_outputs.py`
- Test: `wms/tests/views/tests_views.py`
- Test: `wms/tests/views/tests_views_print_docs.py`
- Test: `wms/tests/views/tests_views_print_labels.py`
- Test: `wms/tests/views/tests_views_planning.py`
- Test: `wms/tests/admin/tests_admin_extra.py`
- Test: `wms/tests/portal/`

**Step 1: Run structural checks**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py check
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py makemigrations --check --dry-run
```

Expected: both pass with no new model drift.

**Step 2: Run targeted regression suites**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python -Wa manage.py test \
  wms.tests.management.tests_management_makemigrations_check \
  wms.tests.planning.tests_outputs \
  wms.tests.portal \
  wms.tests.views.tests_views \
  wms.tests.views.tests_views_portal \
  wms.tests.views.tests_views_print_docs \
  wms.tests.views.tests_views_print_labels \
  wms.tests.views.tests_views_planning \
  wms.tests.admin.tests_admin_extra -v 2
```

Expected: PASS

**Step 3: Fix the minimal failing issues**

If verification fails, apply the smallest possible legacy Django fix, rerun the narrowest failing command first, then rerun the targeted suite.

**Step 4: Run the full suite**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python -Wa manage.py test
```

Expected: PASS on the bumped environment.

**Step 5: Commit**

```bash
git add <exact files changed by verification fallout>
git commit -m "fix: finish Django 5.2 runtime bump"
```

### Task 4: Document the real bump outcome

**Files:**
- Modify: `docs/plans/2026-03-13-django-5-2-upgrade-spike-results.md`
- Or create: `docs/plans/2026-03-13-django-5-2-runtime-bump-results.md`

**Step 1: Record actual versions and commands**

Write down:

- final Django version
- final DRF version
- exact commands run
- pass/fail outcomes
- any remaining follow-up risk

**Step 2: Run a final sanity diff check**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace issues, only intended files changed.

**Step 3: Commit**

```bash
git add docs/plans/2026-03-13-django-5-2-runtime-bump-results.md
git commit -m "docs: record Django 5.2 runtime bump results"
```
