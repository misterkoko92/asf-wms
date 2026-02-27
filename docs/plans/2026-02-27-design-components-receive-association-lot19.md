# Design Components - Receive Association Page Lot 19

## Scope
- Apply validated `ui-comp-*` classes to `scan/receive-association`.
- Keep association-receipt and hors-format capture behavior unchanged.

## Target templates
- `templates/scan/receive_association.html`
- `wms/tests/views/tests_scan_bootstrap_ui.py` (regression assertion)

## Implementation checklist
- [x] Add `ui-comp-card` on the page card.
- [x] Add `ui-comp-title` on primary headings.
- [x] Add `ui-comp-form` on the main form.
- [x] Keep existing field names and dynamic JS behavior unchanged.
- [x] Add dedicated regression test for `/scan/receive-association/`.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_receive_association_page_uses_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2` (23/23)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2` (25/25)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc -v 2` (5/5)
- [x] `./.venv/bin/python manage.py check`

## Notes
- No backend logic changes.
