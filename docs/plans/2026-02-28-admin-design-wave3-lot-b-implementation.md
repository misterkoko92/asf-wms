# Admin Design Wave 3 - Lot B (Print Picking) Implementation Notes

## Scope
- Target only print picking documents:
  - `print/picking_list_carton.html`
  - `print/picking_list_kits.html`
- Keep behavior stable while replacing hardcoded visual values with runtime design variables.

## Delivered
- Added print-oriented CSS variables in `print/base_a5.html` with safe defaults.
- Mapped runtime design tokens (`wms_design_tokens`) to print variables when available:
  - Typography (`font_body`, `font_h2`)
  - Text colors (`color_text`, `color_text_soft`)
  - Surface/border (`color_surface`, `color_border`, `card_border_color`)
  - Table styles (`table_header_bg`, `table_header_text`, `table_border_color`, `table_row_alt_bg`)
  - Picking sheet background (`color_surface_alt`)
- Updated picking templates to consume variables instead of hardcoded colors for:
  - Sheet border/background
  - Meta badge border/background/text
  - Table border/header/alternate rows

## Tests (TDD)
- Added runtime-variable assertions in `wms/tests/views/tests_views.py`:
  - `test_scan_carton_picking_applies_runtime_design_variables`
  - `test_scan_prepare_kits_picking_applies_runtime_design_variables`

## Verification commands
- Picking view tests:
  - `.venv/bin/python manage.py test wms.tests.views.tests_views.ScanViewTests.test_scan_prepare_kits_picking_renders_rows wms.tests.views.tests_views.ScanViewTests.test_scan_carton_picking_renders_styled_table wms.tests.views.tests_views.ScanViewTests.test_scan_carton_picking_applies_runtime_design_variables wms.tests.views.tests_views.ScanViewTests.test_scan_prepare_kits_picking_applies_runtime_design_variables -v 2`
- Print docs regressions:
  - `.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs -v 2`

## Result
- Lot B validated on targeted tests and print docs regressions.
