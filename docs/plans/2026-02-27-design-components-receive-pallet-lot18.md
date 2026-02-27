# Design Components - Receive Pallet Page Lot 18

## Scope
- Apply validated `ui-comp-*` classes to `scan/receive-pallet`.
- Keep listing upload/mapping/review flows unchanged.

## Target templates
- `templates/scan/receive_pallet.html`
- `wms/tests/views/tests_scan_bootstrap_ui.py` (regression assertion)

## Implementation checklist
- [x] Add `ui-comp-card` on receive-pallet cards.
- [x] Add `ui-comp-title` on section headings.
- [x] Add `ui-comp-form` on filters/forms used across create/upload/mapping/review stages.
- [x] Keep all field names and posting actions unchanged.
- [x] Add dedicated regression test for `/scan/receive-pallet/`.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_receive_pallet_page_uses_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2` (22/22)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2` (25/25)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc -v 2` (5/5)
- [x] `./.venv/bin/python manage.py check`

## Notes
- No backend logic changes.
