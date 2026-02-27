# Design Components - State Pages Lot 12

## Scope
- Apply validated `ui-comp-*` classes to scan state pages:
  - `Vue Colis`
  - `Vue Exp&eacute;ditions`
  - `Vue r&eacute;ception`
- Keep table tools, forms, and status actions unchanged.

## Target templates
- `templates/scan/cartons_ready.html`
- `templates/scan/shipments_ready.html`
- `templates/scan/receipts_view.html`
- `wms/tests/views/tests_scan_bootstrap_ui.py` (regression assertions)

## Implementation checklist
- [x] Add component classes on cards and titles (`ui-comp-card`, `ui-comp-title`).
- [x] Add count badges (`ui-comp-count-badge`) on page headers.
- [x] Keep `data-table-tools="1"` and existing forms/actions.
- [x] Add dedicated regression test on the three pages.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_state_tables_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2` (16/16)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2` (25/25)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc -v 2` (5/5)
- [x] `./.venv/bin/python manage.py check`

## Notes
- No backend logic changes.
- Rollback remains immediate through `SCAN_BOOTSTRAP_ENABLED=false`.
