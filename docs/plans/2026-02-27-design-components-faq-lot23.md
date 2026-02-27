# Design Components - FAQ Page Lot 23

## Scope
- Apply validated `ui-comp-*` classes to `scan/faq` informational page.
- Keep all content and access control unchanged.

## Target templates
- `templates/scan/faq.html`
- `wms/tests/views/tests_scan_bootstrap_ui.py` (regression assertion)

## Implementation checklist
- [x] Add `ui-comp-card` on all FAQ content blocks.
- [x] Add `ui-comp-title` on all section titles and sub-titles.
- [x] Keep textual content and structure unchanged.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_misc_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_imports wms.tests.views.tests_views_print_templates wms.tests.views.tests_views_scan_misc wms.tests.views.tests_views_scan_shipments -v 2` (82/82)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Visual-only class additions.
