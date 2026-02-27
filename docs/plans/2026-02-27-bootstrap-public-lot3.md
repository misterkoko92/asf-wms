# Bootstrap Migration - Public Pages Lot 3

## Scope
- Keep reversible rollout through `SCAN_BOOTSTRAP_ENABLED`.
- Modernize remaining public legacy pages outside authenticated scan/portal flows.
- Preserve existing routes, forms, and handlers.

## Target pages
- `templates/home.html`
- `templates/password_help.html`
- `templates/scan/public_account_request.html`

## Implementation checklist
- [x] Add conditional Bootstrap CDN assets on `home` and `password_help`.
- [x] Align `home` form controls and CTA button with Bootstrap classes.
- [x] Add conditional Bootstrap + scan bridge CSS on public account request page.
- [x] Align public account request form fields (`select`, `input`, `textarea`, file inputs) with Bootstrap classes.
- [x] Extend UI tests for public pages under feature flag.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_home -v 2` (4/4)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_public_account -v 2` (4/4)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui -v 2` (9/9)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal -v 2` (59/59)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Assets remain CDN-based and only load when `SCAN_BOOTSTRAP_ENABLED=true`.
- Rollback remains immediate by setting `SCAN_BOOTSTRAP_ENABLED=false`.
