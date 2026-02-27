# Design Components - Order Page Lot 15

## Scope
- Apply validated `ui-comp-*` classes to `scan/order`.
- Keep command creation/selection/reservation workflows unchanged.

## Target templates
- `templates/scan/order.html`
- `wms/tests/views/tests_scan_bootstrap_ui.py` (regression assertion)

## Implementation checklist
- [x] Add `ui-comp-card` on all order cards.
- [x] Add `ui-comp-title` on key headings.
- [x] Add `ui-comp-form` on selection/creation/line forms.
- [x] Keep all form ids/names and datalist hooks unchanged.
- [x] Add dedicated regression test for `/scan/order/`.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_order_page_uses_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2` (19/19)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2` (25/25)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc -v 2` (5/5)
- [x] `./.venv/bin/python manage.py check`

## Notes
- No backend logic changes.
