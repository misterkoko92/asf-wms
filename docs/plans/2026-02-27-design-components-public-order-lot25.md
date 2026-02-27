# Design Components - Public Order Page Lot 25

## Scope
- Apply validated `ui-comp-*` classes to `scan/public_order`.
- Keep public order form behavior and client-side estimation logic unchanged.

## Target templates
- `templates/scan/public_order.html`
- `wms/tests/views/tests_scan_bootstrap_ui.py` (regression assertion)

## Implementation checklist
- [x] Add `ui-comp-card` on public-order cards.
- [x] Add `ui-comp-title` on section headings.
- [x] Add `ui-comp-form` on the main order form.
- [x] Add `ui-comp-actions` on top action row.
- [x] Keep all IDs and JS hooks unchanged.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_remaining_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_public_order wms.tests.views.tests_views_public_account wms.tests.views.tests_views_scan_misc -v 2` (49/49)
- [x] `./.venv/bin/python manage.py check`

## Notes
- No server-side logic changes.
