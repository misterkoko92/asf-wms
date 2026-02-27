# Design Components - Portal Auth Pages Lot 35

## Scope
- Apply validated `ui-comp-*` classes to remaining portal auth pages.
- Keep login and set-password flows unchanged.

## Target templates/tests
- `templates/portal/login.html`
- `templates/portal/set_password.html`
- `wms/tests/views/tests_portal_bootstrap_ui.py`

## Implementation checklist
- [x] Add `ui-comp-card` on auth page cards.
- [x] Add `ui-comp-title` on auth page headings.
- [x] Add `ui-comp-form` on login and set-password forms.
- [x] Extend `test_portal_auth_pages_include_bootstrap_assets` with `ui-comp-*` assertions.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests.test_portal_auth_pages_include_bootstrap_assets -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal -v 2` (69/69)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Change is additive classes only; no logic or routing changes.
