# Design Components - Foundations UI Lab Lot 38

## Scope
- Finalize a reusable "component foundation" set for Bootstrap migration.
- Keep business behavior unchanged and deliver visual validation in UI Lab sandbox first.

## Target files
- `templates/scan/ui_lab.html`
- `wms/static/scan/scan-bootstrap.css`
- `wms/static/scan/ui-lab.css`
- `wms/tests/views/tests_scan_bootstrap_ui.py`

## Implementation checklist
- [x] Add sandbox examples for foundation components:
  - filters + sorting toolbar
  - active filter chips
  - table sortable headers + unified status pills
  - KPI cards tagged with reusable `ui-comp-*` classes
- [x] Add reusable foundation CSS classes in `scan-bootstrap.css`:
  - `ui-comp-toolbar`, `ui-comp-filter`, `ui-comp-filter-actions`, `ui-comp-sort-btn`
  - `ui-comp-chip-list`, `ui-comp-chip`
  - `ui-comp-data-table`
  - `ui-comp-status-pill` (+ `is-ready`, `is-progress`, `is-info`)
  - `ui-comp-kpi-grid`, `ui-comp-kpi-card`
- [x] Add UI Lab preview skin rules in `ui-lab.css` so palette/typography/density controls still apply.
- [x] Extend regression assertions for new foundation markers rendered in UI Lab.

## Validation checklist
- [x] RED check: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_remaining_pages_use_design_component_classes -v 2` (fails before implementation)
- [x] GREEN check: same test passes after implementation
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_misc -v 2` (30/30)
- [x] `./.venv/bin/python manage.py check`

## Notes
- This lot is intentionally low-risk: no functional workflow change, only visual/component foundation work and regression coverage updates.
- These `ui-comp-*` classes are now ready for propagation to business pages in next lots.
