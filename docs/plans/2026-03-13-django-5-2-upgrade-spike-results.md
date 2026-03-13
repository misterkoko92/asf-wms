# Django 4.2 -> 5.2 upgrade spike results

Date: 2026-03-13
Branch: `codex/django-5-2-upgrade-spike`
Scope: legacy Django only (`wms/`, `scan/`, `portal/`, `templates/`)

## Outcome

The legacy Django codebase is compatible with Django 5.2 in this spike setup.

Validated points:

- Django 5.0.14 + djangorestframework 3.16.1: full suite previously passed in the spike environment.
- Django 5.1.15 + djangorestframework 3.16.1: targeted upgrade suites passed after removing `CheckConstraint(check=...)` deprecation noise from live models and historical migrations.
- Django 5.2.12 + djangorestframework 3.16.1: full suite passed on the final code state.

## Code changes in the spike

### 1. Close workbook resources explicitly

- `wms/planning/exports.py`
- `wms/tests/planning/tests_outputs.py`
- `wms/tests/views/tests_views_planning.py`

`export_version_workbook()` now closes the `openpyxl` workbook in a `finally` block, and affected tests now close opened workbooks and file responses explicitly.

### 2. Make `CheckConstraint` definitions work on both Django 4.2 and 5.1+

- `wms/models_domain/portal.py`
- `wms/migrations/0042_associationportalcontact.py`
- `wms/migrations/0069_destinationcorrespondentoverride_and_more.py`

The spike adds a small compatibility helper that maps to:

- `check=` on Django < 5.1
- `condition=` on Django >= 5.1

This removes the Django 5.1 `RemovedInDjango60Warning` while keeping Django 4.2 compatibility and preserving `makemigrations --check`.

### 3. Close generated PDF files before returning responses

- `wms/views_print_docs.py`
- `wms/views_print_labels.py`
- `wms/admin.py`
- `wms/tests/views/tests_views.py`

Generated artifact PDF helpers now read the file into `BytesIO` and close the storage file handle immediately before building the `FileResponse`. This removes the remaining file-handle warning path observed in print/admin tests under the spike environment.

## Verification

### Django 4.2 baseline in the worktree

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python -Wa manage.py test \
  wms.tests.management.tests_management_makemigrations_check \
  wms.tests.planning.tests_outputs \
  wms.tests.views.tests_views \
  wms.tests.views.tests_views_print_docs \
  wms.tests.views.tests_views_print_labels \
  wms.tests.views.tests_views_planning \
  wms.tests.admin.tests_admin_extra -v 2
```

Result: `Ran 152 tests in 183.671s` -> `OK`

### Django 5.2 targeted verification on final code

```bash
PYTHONTRACEMALLOC=5 \
PYTHONPATH="/Users/EdouardGonnu/asf-wms/.worktrees/codex/django-5-2-upgrade-spike/.spikes/django52-site-packages:/Users/EdouardGonnu/asf-wms/.venv/lib/python3.11/site-packages" \
/Users/EdouardGonnu/asf-wms/.venv/bin/python -Wa manage.py test \
  wms.tests.management.tests_management_makemigrations_check \
  wms.tests.planning.tests_outputs \
  wms.tests.views.tests_views \
  wms.tests.views.tests_views_print_docs \
  wms.tests.views.tests_views_print_labels \
  wms.tests.views.tests_views_planning \
  wms.tests.admin.tests_admin_extra -v 2
```

Result: `Ran 152 tests in 229.133s` -> `OK`

### Django 5.2 full suite on final code

```bash
PYTHONTRACEMALLOC=5 \
PYTHONPATH="/Users/EdouardGonnu/asf-wms/.worktrees/codex/django-5-2-upgrade-spike/.spikes/django52-site-packages:/Users/EdouardGonnu/asf-wms/.venv/lib/python3.11/site-packages" \
/Users/EdouardGonnu/asf-wms/.venv/bin/python -Wa manage.py test
```

Result: `Ran 1916 tests in 1061.427s` -> `OK (skipped=43)`

## Remaining follow-up outside this spike

- Upgrade runtime dependencies in the real project environment, especially `djangorestframework`, to a Django 5.2 compatible version.
- Decide whether the compatibility helper should stay in place during a staged rollout or whether the codebase should be switched fully to `condition=` once Django 4.2 support is dropped.
- If production uses MariaDB, confirm the exact server version before the real framework bump.
