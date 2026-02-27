# Design Components - Public Account Request Page Lot 26

## Scope
- Apply validated `ui-comp-*` classes to `scan/public_account_request`.
- Keep delegated handler flow and form submission unchanged.

## Target templates
- `templates/scan/public_account_request.html`
- `wms/tests/views/tests_scan_bootstrap_ui.py` (regression assertion)

## Implementation checklist
- [x] Add `ui-comp-card` on page cards.
- [x] Add `ui-comp-title` on section heading.
- [x] Add `ui-comp-form` on the main request form.
- [x] Keep account-type toggle sections and address autocomplete hooks unchanged.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_remaining_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_public_order wms.tests.views.tests_views_public_account wms.tests.views.tests_views_scan_misc -v 2` (49/49)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Visual-only class additions.
