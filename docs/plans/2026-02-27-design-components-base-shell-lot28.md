# Design Components - Base Shell Lot 28

## Scope
- Apply validated `ui-comp-*` classes to shared `scan/base.html` shell.
- Keep navigation, account menu, theme/ui toggle and scan overlay behavior unchanged.

## Target templates
- `templates/scan/base.html`
- `wms/tests/views/tests_scan_bootstrap_ui.py` (regression assertion)

## Implementation checklist
- [x] Add `ui-comp-panel` on header and navigation shells.
- [x] Add `ui-comp-title` on global app title.
- [x] Add `ui-comp-actions` on header action cluster.
- [x] Keep existing ids/classes used by `scan.js` unchanged.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_remaining_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_public_order wms.tests.views.tests_views_public_account wms.tests.views.tests_views_scan_misc -v 2` (49/49)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Additive classes only.
