# Design Components - Print Template List Lot 21

## Scope
- Apply validated `ui-comp-*` classes to template list page.
- Preserve superuser-only behavior and existing links.

## Target templates
- `templates/scan/print_template_list.html`
- `wms/tests/views/tests_scan_bootstrap_ui.py` (regression assertion)

## Implementation checklist
- [x] Add `ui-comp-card` on the main page card.
- [x] Add `ui-comp-title` on the page heading.
- [x] Keep table markup and edit links unchanged.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_misc_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_imports wms.tests.views.tests_views_print_templates wms.tests.views.tests_views_scan_misc wms.tests.views.tests_views_scan_shipments -v 2` (82/82)
- [x] `./.venv/bin/python manage.py check`

## Notes
- No backend or permission changes.
