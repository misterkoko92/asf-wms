# Design Components - UI Lab Page Lot 27

## Scope
- Apply validated `ui-comp-*` classes to `scan/ui_lab` sandbox page.
- Keep live controls and preview JS behavior unchanged.

## Target templates
- `templates/scan/ui_lab.html`
- `wms/tests/views/tests_scan_bootstrap_ui.py` (regression assertion)

## Implementation checklist
- [x] Add `ui-comp-card` on all sandbox demo cards.
- [x] Add `ui-comp-title` on section headings.
- [x] Add `ui-comp-form` on demo form block.
- [x] Keep control IDs (`ui-lab-palette`, `ui-lab-typography`, `ui-lab-density`) unchanged.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_remaining_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_public_order wms.tests.views.tests_views_public_account wms.tests.views.tests_views_scan_misc -v 2` (49/49)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Sandbox behavior unchanged.
