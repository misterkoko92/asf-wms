# Bootstrap Migration - Portal Lot 2

## Scope
- Keep production-safe rollout with `SCAN_BOOTSTRAP_ENABLED`.
- Migrate portal UI shell and key pages to Bootstrap-compatible markup.
- Preserve existing backend logic and JS hooks.

## Target pages
- `templates/portal/base.html`
- `templates/portal/dashboard.html`
- `templates/portal/order_create.html`
- `templates/portal/login.html`
- `templates/portal/set_password.html`
- `templates/portal/change_password.html`

## Implementation checklist
- [x] Add conditional Bootstrap CDN assets and bridge styles in portal base/login/set-password templates.
- [x] Add portal-specific bootstrap bridge stylesheet: `wms/static/portal/portal-bootstrap.css`.
- [x] Migrate dashboard table shell/actions to Bootstrap table/button classes.
- [x] Migrate order-create form/table controls to Bootstrap classes while keeping `data-table-tools` and current names/ids.
- [x] Add dedicated regression tests for portal bootstrap rendering behind feature flag.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui -v 2` (4/4)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal -v 2` (59/59)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Bootstrap assets remain CDN-based (jsDelivr) and only load when `SCAN_BOOTSTRAP_ENABLED=true`.
- Rollback remains immediate by setting `SCAN_BOOTSTRAP_ENABLED=false`.
