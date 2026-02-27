# Design Components - Print Picking Lot 36

## Scope
- Keep global print migration on hold.
- Apply targeted visual refresh only for picking print templates.
- Do not change other `templates/print/*` documents.

## Target templates/tests
- `templates/print/picking_list_carton.html`
- `templates/print/picking_list_kits.html`
- `wms/tests/views/tests_views.py`

## Implementation checklist
- [x] Add dedicated picking sheet layout (`picking-sheet`) for both templates.
- [x] Add styled picking metadata block (`picking-meta`).
- [x] Add dedicated table class (`picking-table`) with improved print readability.
- [x] Keep headings/columns/data bindings unchanged.
- [x] Add regression assertions on picking table class for carton and kits routes.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views.ScanViewTests.test_scan_prepare_kits_picking_renders_rows wms.tests.views.tests_views.ScanViewTests.test_scan_carton_picking_renders_styled_table -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs wms.tests.views.tests_views.ScanViewTests.test_scan_prepare_kits_picking_renders_rows wms.tests.views.tests_views.ScanViewTests.test_scan_carton_picking_renders_styled_table -v 2` (13/13)
- [x] `./.venv/bin/python manage.py check`

## Notes
- No changes on non-picking print templates.
