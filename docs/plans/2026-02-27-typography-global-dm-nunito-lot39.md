# Typography Global - DM Sans + Nunito Sans Lot 39

## Scope
- Apply a unified typography pair across current pages:
  - Headings: DM Sans
  - Body text: Nunito Sans
- Keep typography fully variable-driven for easy future updates.

## Target files
- `wms/static/scan/scan.css`
- `wms/static/scan/scan-bootstrap.css`
- `wms/static/scan/ui-lab.css`
- `wms/static/scan/ui-lab.js`
- `templates/scan/base.html`
- `templates/portal/base.html`
- `templates/portal/login.html`
- `templates/portal/set_password.html`
- `templates/home.html`
- `templates/password_help.html`
- `templates/app/next_build_missing.html`
- `templates/admin/wms/stockmovement/change_list.html`
- `templates/admin/wms/stockmovement/form.html`
- `templates/admin/wms/shipment/change_form.html`
- `wms/static/wms/admin-bootstrap.css`
- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`
- `wms/tests/views/tests_views_home.py`
- `wms/tests/views/tests_views_next_frontend.py`

## Implementation checklist
- [x] Replace base Google Fonts links with `DM Sans` + `Nunito Sans` on scan and portal shells.
- [x] Add same fonts to standalone pages (home, password help, next missing build, portal auth pages).
- [x] Add same fonts to custom admin templates using bootstrap layer.
- [x] Centralize typography via variables in `scan.css`:
  - `--wms-font-heading`
  - `--wms-font-body`
  - `--font-title`, `--font-heading`, `--font-body` mapped to global tokens.
- [x] Ensure all UI modes (`classic`, `nova`, `studio`, `benev`, `timeline`, `spreadsheet`) use those global font variables.
- [x] Update bootstrap design-system typography tokens in `scan-bootstrap.css` to map to global typography variables.
- [x] Align UI Lab defaults to `DM Sans + Nunito Sans` while keeping typography selector configurable.
- [x] Extend tests to assert the new fonts are loaded in key page families.

## Validation checklist
- [x] RED (before implementation):
  - `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_base_includes_bootstrap_assets_when_enabled wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests.test_portal_base_includes_bootstrap_assets_when_enabled wms.tests.views.tests_views_home.HomePageTests.test_home_page_includes_bootstrap_assets_when_enabled wms.tests.views.tests_views_home.HomePageTests.test_password_help_page_includes_bootstrap_assets_when_enabled wms.tests.views.tests_views_next_frontend.NextFrontendViewsTests.test_next_frontend_missing_build_includes_bootstrap_assets_when_enabled -v 2` (fails)
- [x] GREEN (after implementation): same targeted tests pass.
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_home wms.tests.views.tests_views_next_frontend -v 2` (48/48)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Typography is now controlled by variables, so future font changes can be done primarily via the global font tokens.
- Print templates are intentionally not part of this lot.
