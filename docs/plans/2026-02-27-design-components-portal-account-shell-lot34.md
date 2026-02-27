# Design Components - Portal Account/Shell Lot 34

## Scope
- Apply validated `ui-comp-*` classes to portal account page, change-password page and shared portal shell.
- Keep account update, document upload and password-change logic unchanged.

## Target templates/tests
- `templates/portal/account.html`
- `templates/portal/change_password.html`
- `templates/portal/base.html`
- `wms/tests/views/tests_portal_bootstrap_ui.py` (new regression test)

## Implementation checklist
- [x] Add `ui-comp-card` on account and change-password cards.
- [x] Add `ui-comp-title` on section headings.
- [x] Add `ui-comp-form` on account/password/upload forms.
- [x] Add `ui-comp-panel` and `ui-comp-actions` on shared portal header/nav/actions shell.
- [x] Add regression test `test_portal_pages_use_design_component_classes`.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests.test_portal_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal -v 2` (69/69)
- [x] `./.venv/bin/python manage.py check`

## Notes
- This lot finalizes low-risk portal migration to `ui-comp-*` classes.
