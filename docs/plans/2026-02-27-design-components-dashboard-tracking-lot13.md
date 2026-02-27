# Design Components - Dashboard & Tracking Lot 13

## Scope
- Apply validated `ui-comp-*` classes to:
  - `Tableau de bord`
  - `Vue Commande`
  - `Suivi des exp&eacute;ditions`
- Keep filters, table behavior and workflow actions unchanged.

## Target templates
- `templates/scan/dashboard.html`
- `templates/scan/orders_view.html`
- `templates/scan/shipments_tracking.html`
- `wms/tests/views/tests_scan_bootstrap_ui.py` (regression assertions)

## Implementation checklist
- [x] Add `ui-comp-card` on main cards.
- [x] Add `ui-comp-title` on primary headings.
- [x] Add `ui-comp-form` on tracking filter form.
- [x] Keep `data-table-tools="1"` and action forms unchanged.
- [x] Add dedicated regression test on the three routes.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_dashboard_and_tracking_views_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2` (17/17)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2` (25/25)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc -v 2` (5/5)
- [x] `./.venv/bin/python manage.py check`

## Notes
- No backend logic changes.
- Rollout stays controlled by `SCAN_BOOTSTRAP_ENABLED`.
