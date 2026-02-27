# Design Components - Shipment Tracking Page Lot 24

## Scope
- Apply validated `ui-comp-*` classes to public/staff shipment tracking page.
- Keep dispute, tracking update and navigation logic unchanged.

## Target templates
- `templates/scan/shipment_tracking.html`
- `wms/tests/views/tests_scan_bootstrap_ui.py` (regression assertion)

## Implementation checklist
- [x] Add `ui-comp-card` on main tracking card.
- [x] Add `ui-comp-title` on page/section headings.
- [x] Add `ui-comp-form` on tracking action forms.
- [x] Keep all hidden inputs and IDs used by JS unchanged.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_misc_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_imports wms.tests.views.tests_views_print_templates wms.tests.views.tests_views_scan_misc wms.tests.views.tests_views_scan_shipments -v 2` (82/82)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Additive class updates only, no flow changes.
