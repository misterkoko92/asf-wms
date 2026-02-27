# Design Components - Tabler Lite Sandbox Lot 37

## Scope
- Add a low-risk Tabler exploration layer in UI sandbox only.
- Keep production business pages unchanged.

## Target files
- `templates/scan/ui_lab.html`
- `wms/static/scan/ui-lab.css`
- `wms/tests/views/tests_scan_bootstrap_ui.py`

## Implementation checklist
- [x] Add Tabler Icons webfont include in UI Lab head.
- [x] Add two demo component groups in sandbox:
  - `ui-lab-stat-card` (KPI cards with icons)
  - `ui-lab-activity-item` (activity rows with icons)
- [x] Add dedicated CSS styles scoped to UI Lab only.
- [x] Extend regression assertions for UI Lab markers in scan bootstrap tests.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_remaining_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_misc -v 2` (30/30)
- [x] `./.venv/bin/python manage.py check`

## Notes
- This lot is sandbox-only and intended to evaluate Tabler-style components before broader rollout.
