# Design Components - Imports Page Lot 20

## Scope
- Apply validated `ui-comp-*` classes to `scan/import` page.
- Keep all import actions, hidden fields, and export/download links unchanged.

## Target templates
- `templates/scan/imports.html`
- `wms/tests/views/tests_scan_bootstrap_ui.py` (regression assertion)

## Implementation checklist
- [x] Add `ui-comp-card` on all import cards.
- [x] Add `ui-comp-title` on section headings.
- [x] Add `ui-comp-form` on all import forms.
- [x] Add `ui-comp-actions` on form action rows.
- [x] Keep current form names, IDs and POST actions unchanged.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_misc_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_imports wms.tests.views.tests_views_print_templates wms.tests.views.tests_views_scan_misc wms.tests.views.tests_views_scan_shipments -v 2` (82/82)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Change is additive classes only.
