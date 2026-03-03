# Next/React Migration Pause Policy

## Status

Next/React migration is paused until further notice.

## Goal

Protect delivery velocity on the legacy Django product by preventing accidental work on paused Next migration scope.

## Default execution rule

For any request that does not explicitly ask for Next/React:

- do not modify Next routes, Next mode switching, or Next frontend app;
- do not create migration tasks for Next rollout;
- do not run Next-specific tests or build steps;
- implement requested behavior on legacy Django flow.

## Paused scope list

- `frontend-next/`
- `wms/views_next_frontend.py`
- `wms/ui_mode.py`
- `wms/tests/views/tests_views_next_frontend.py`
- related Next migration execution plans in `docs/plans/` containing `next`

## Allowed by default

- `wms/views_*.py` legacy scan/portal/public handlers
- `templates/scan/*`
- `templates/portal/*`
- `templates/home.html` and Django-side flows
- Django tests outside Next-specific suites

## Override

Next scope can be re-enabled only when the user explicitly asks in the current request (for example: "integrer Next", "modifier frontend-next", "reprendre migration Next").
