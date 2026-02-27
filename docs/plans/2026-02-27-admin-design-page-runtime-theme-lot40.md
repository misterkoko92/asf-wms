# Admin Design Page - Runtime Theme Controls Lot 40

## Scope
- Add a new `Admin > Design` page in scan, visible only to superusers.
- Allow runtime editing of global visual tokens (colors + typography) directly from the site.
- Apply those tokens across main rendered pages through CSS variables.

## Target files
- `wms/models_domain/integration.py`
- `wms/migrations/0055_wmsruntimesettings_design_fields.py`
- `wms/forms_scan_design.py`
- `wms/views_scan_design.py`
- `wms/context_processors.py`
- `wms/scan_urls.py`
- `wms/views_scan.py`
- `wms/views.py`
- `templates/scan/base.html`
- `templates/scan/admin_design.html`
- `templates/includes/design_vars_style.html`
- `templates/portal/base.html`
- `templates/portal/login.html`
- `templates/portal/set_password.html`
- `templates/home.html`
- `templates/password_help.html`
- `templates/app/next_build_missing.html`
- `templates/admin/wms/stockmovement/change_list.html`
- `templates/admin/wms/stockmovement/form.html`
- `templates/admin/wms/shipment/change_form.html`
- `wms/static/scan/scan.css`
- `wms/static/scan/scan-bootstrap.css`
- `wms/static/wms/admin-bootstrap.css`
- `wms/tests/views/tests_views_scan_admin.py`
- `wms/tests/views/tests_views_scan_dashboard.py`
- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/views/tests_views.py`

## Implementation checklist
- [x] Extend `WmsRuntimeSettings` with design fields:
  - fonts: heading/body
  - colors: primary, secondary, background, surface, border, text, text-soft
- [x] Add migration `0055_wmsruntimesettings_design_fields`.
- [x] Create `ScanDesignSettingsForm` with hex color validation.
- [x] Create `scan_admin_design` view (GET/POST, save + reset defaults), superuser-only.
- [x] Create `scan/admin_design.html` with editable controls + preview block.
- [x] Add `scan:scan_admin_design` route and include it in view exports.
- [x] Add `Design` entry in `Scan > Admin` menu (superusers only).
- [x] Inject runtime design tokens in context via `wms_design_tokens`.
- [x] Add shared include `templates/includes/design_vars_style.html` to expose runtime CSS vars.
- [x] Include shared design vars style on scan/portal/base and standalone pages.
- [x] Align CSS foundation variables to consume global design tokens.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_scan_dashboard wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views -v 2` (85/85)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_home wms.tests.views.tests_views_next_frontend -v 2` (23/23)
- [x] `./.venv/bin/python manage.py check`
- [x] `./.venv/bin/python manage.py makemigrations --check --dry-run`

## Notes
- The design editor currently targets global core tokens used by scan/portal/home/admin custom pages.
- Print templates are intentionally out of scope for this lot.
