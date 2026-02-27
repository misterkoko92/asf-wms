# Admin Design Usability Polish - Lot 41

## Scope
- Fix visual alignment of the `Couleurs` section header on `Scan > Admin > Design`.
- Improve color controls with larger visual blocks for immediate rendering feedback.
- Clarify typography inputs by splitting heading fonts per level (`H1`, `H2`, `H3`) and keeping one font per field.

## Target files
- `wms/models_domain/integration.py`
- `wms/migrations/0056_wmsruntimesettings_design_font_h1_and_more.py`
- `wms/forms_scan_design.py`
- `wms/views_scan_design.py`
- `wms/context_processors.py`
- `templates/scan/admin_design.html`
- `templates/includes/design_vars_style.html`
- `wms/static/scan/scan.css`
- `wms/static/scan/scan-bootstrap.css`
- `wms/static/wms/admin-bootstrap.css`
- `wms/tests/views/tests_views_scan_admin.py`

## Implementation checklist
- [x] Add runtime typography fields for `H1/H2/H3`.
- [x] Keep backward compatibility by syncing legacy `design_font_heading` with `H2`.
- [x] Replace typography form controls with explicit `H1/H2/H3 + texte` inputs.
- [x] Enforce one font per field in form validation.
- [x] Redesign color inputs into larger preview cards with live hex display.
- [x] Keep global CSS token injection aligned with new heading variables.
- [x] Update tests for new field names and persisted values.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin.ScanAdminViewTests.test_scan_admin_design_renders_design_form wms.tests.views.tests_views_scan_admin.ScanAdminViewTests.test_scan_admin_design_post_updates_runtime_design_values -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_dashboard -v 2`
- [x] `./.venv/bin/python manage.py check`
- [x] `./.venv/bin/python manage.py makemigrations --check --dry-run`
