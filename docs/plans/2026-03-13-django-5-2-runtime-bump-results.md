# Django 5.2 Runtime Bump Results

Date: 2026-03-13
Branch: `codex/django-5-2-upgrade-spike`
Scope: legacy Django runtime bump only

## Final versions

- `Django==5.2.12`
- `djangorestframework==3.16.1`

Updated files:

- `pyproject.toml`
- `uv.lock`
- `requirements.txt`
- `requirements-dev.txt`

## Kept compatibility code

The branch keeps the compatibility helper introduced during the spike for `CheckConstraint` declarations. This is intentional for rollout safety and avoids mixing the dependency bump with a cleanup to Django-5.2-only APIs.

## Verification

### Version guard

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.management.tests_management_runtime_dependencies -v 2
```

Result: `Ran 4 tests` -> `OK`

### Structural checks

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py check
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py makemigrations --check --dry-run
```

Results:

- `System check identified no issues`
- `No changes detected`

### Targeted legacy regression suite

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

Result: `Ran 292 tests in 172.515s` -> `OK`

### Full suite

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python -Wa manage.py test
```

Result: `Ran 1917 tests in 768.329s` -> `OK (skipped=43)`

## Environment note

`make sync` was not usable in this worktree because `uv` attempted to rebuild `mysqlclient` in a local `.venv` without `pkg-config`. The runtime verification was therefore executed with the established repository virtualenv at `/Users/EdouardGonnu/asf-wms/.venv` after explicitly installing:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/pip install Django==5.2.12 djangorestframework==3.16.1
```

This does not affect repository contents, only the local verification path.

## Remaining follow-up

- Merge the bump PR and let CI confirm the same dependency set in a clean environment.
- Remove the `CheckConstraint` compatibility helper later, in a separate cleanup PR, once Django 4.2 support is fully dropped.
- Confirm the production MariaDB version before deployment if that database family is in use.
