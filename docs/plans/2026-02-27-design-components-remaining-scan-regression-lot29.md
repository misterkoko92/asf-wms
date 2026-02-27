# Design Components - Remaining Scan Regression Lot 29

## Scope
- Add targeted regression coverage for the last migrated scan templates.
- Verify that base shell, UI Lab and public pages expose `ui-comp-*` markers.

## Target tests
- `wms/tests/views/tests_scan_bootstrap_ui.py`

## Implementation checklist
- [x] Add `test_scan_remaining_pages_use_design_component_classes`.
- [x] Cover base shell markers rendered from `scan_stock`.
- [x] Cover `scan_ui_lab` markers.
- [x] Cover `scan_public_order` and `scan_public_account_request` markers.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_remaining_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_public_order wms.tests.views.tests_views_public_account wms.tests.views.tests_views_scan_misc -v 2` (49/49)
- [x] `./.venv/bin/python manage.py check`

## Notes
- This closes the remaining `templates/scan/*.html` migration coverage for `ui-comp-*` classes.
