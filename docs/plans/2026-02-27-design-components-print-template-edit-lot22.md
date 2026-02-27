# Design Components - Print Template Edit Lot 22

## Scope
- Apply validated `ui-comp-*` classes to template editor page.
- Keep template edition, restore and preview workflows unchanged.

## Target templates
- `templates/scan/print_template_edit.html`
- `wms/tests/views/tests_scan_bootstrap_ui.py` (regression assertion)

## Implementation checklist
- [x] Add `ui-comp-card` on the editor intro card.
- [x] Add `ui-comp-title` on main headings.
- [x] Add `ui-comp-panel` on side panel sections.
- [x] Add `ui-comp-form` on version and toolbar forms.
- [x] Add `ui-comp-note` on editor helper text.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_misc_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_imports wms.tests.views.tests_views_print_templates wms.tests.views.tests_views_scan_misc wms.tests.views.tests_views_scan_shipments -v 2` (82/82)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Existing IDs/data attributes used by JS editor are untouched.
