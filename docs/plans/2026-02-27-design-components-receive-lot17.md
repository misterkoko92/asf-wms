# Design Components - Receive Main Page Lot 17

## Scope
- Apply validated `ui-comp-*` classes to `scan/receive`.
- Keep receipt selection, creation and line-entry workflows unchanged.

## Target templates
- `templates/scan/receive.html`
- `wms/tests/views/tests_scan_bootstrap_ui.py` (regression assertion)

## Implementation checklist
- [x] Add `ui-comp-card` on the receive page cards.
- [x] Add `ui-comp-title` on primary section headings.
- [x] Add `ui-comp-form` on selection/creation/add-line forms.
- [x] Keep existing field names and JS blocks unchanged.
- [x] Add dedicated regression test for `/scan/receive/`.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_receive_page_uses_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2` (21/21)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2` (25/25)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc -v 2` (5/5)
- [x] `./.venv/bin/python manage.py check`

## Notes
- No backend logic changes.
