# Admin Design Wave 3 - Lot A (Bootstrap) Implementation Notes

## Scope
- Bootstrap-only implementation.
- No Next/React changes.
- Goal: expose more useful design variables, remove Bootstrap inline hardcoded styles on targeted pages, and ensure live variable propagation consistency.

## Delivered
- Added navigation micro-typography and structure variables:
  - `nav_item_border`
  - `nav_item_font_size`
  - `nav_item_font_weight`
  - `nav_item_line_height`
  - `nav_item_letter_spacing`
  - `dropdown_item_font_size`
  - `dropdown_item_font_weight`
  - `dropdown_item_padding_y`
  - `dropdown_item_padding_x`
- Added table readability variables:
  - `table_header_font_size`
  - `table_header_letter_spacing`
  - `table_header_padding_y`
  - `table_header_padding_x`
  - `table_cell_padding_y`
  - `table_cell_padding_x`
- Added button state variables (success/warning/danger hover + active):
  - `color_btn_success_hover_bg`, `color_btn_success_active_bg`
  - `color_btn_warning_hover_bg`, `color_btn_warning_active_bg`
  - `color_btn_danger_hover_bg`, `color_btn_danger_active_bg`

## Bootstrap propagation
- Added CSS variable injection in `templates/includes/design_vars_style.html` for all new tokens.
- Wired all new vars in `wms/static/scan/scan-bootstrap.css`:
  - nav links/dropdown text, border, spacing, paddings
  - table header/cell typography and paddings
  - button hover/active states now token-driven (no hardcoded colors)
- Updated live preview style mapping in `templates/scan/admin_design.html` for nav/table rendering variables.

## Inline style migration (Bootstrap mode)
- `templates/portal/base.html`: legacy inline style block now rendered only when `scan_bootstrap_enabled` is false.
- `templates/portal/order_detail.html`: same condition applied.
- `templates/portal/recipients.html`: same condition applied.
- Added Bootstrap equivalent variable-driven rules in `wms/static/portal/portal-bootstrap.css`.
- `templates/scan/shipments_tracking.html`: replaced inline style attributes on close buttons with semantic classes:
  - `scan-shipment-close-btn is-closed`
  - `scan-shipment-close-btn is-ready`
  - `scan-shipment-close-btn is-blocked`
- Added corresponding class styles in `wms/static/scan/scan-bootstrap.css`.

## Test coverage updates
- Extended admin design payload + assertions with new tokens in:
  - `wms/tests/views/tests_views_scan_admin.py`
- Added Bootstrap-specific checks for removed inline styles in:
  - `wms/tests/views/tests_portal_bootstrap_ui.py`
- Added shipments tracking close-button class regression check in:
  - `wms/tests/views/tests_scan_bootstrap_ui.py`

## Verification commands
- Targeted RED/GREEN:
  - `.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin.ScanAdminViewTests.test_scan_admin_design_post_updates_runtime_design_values wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests.test_portal_pages_use_design_component_classes wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_shipments_tracking_uses_design_classes_for_close_buttons -v 2`
- Broader non-regression:
  - `.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_scan_bootstrap_ui -v 2`

## Result
- Non-regression status: `47/47` tests green on impacted suites.
- Lot A objective achieved for Bootstrap scope.
