# Bootstrap Migration - Admin Lot 4

## Scope
- Keep rollout reversible with `SCAN_BOOTSTRAP_ENABLED`.
- Modernize custom Django admin templates used by stock movements and shipment print actions.
- Preserve admin business flows and URL handlers.

## Target pages
- `templates/admin/wms/stockmovement/change_list.html`
- `templates/admin/wms/stockmovement/form.html`
- `templates/admin/wms/shipment/change_form.html`

## Implementation checklist
- [x] Add conditional Bootstrap CDN assets in custom admin templates.
- [x] Add admin bridge stylesheet: `wms/static/wms/admin-bootstrap.css`.
- [x] Upgrade action links/buttons to Bootstrap button classes.
- [x] Keep existing admin routes and actions unchanged.
- [x] Add UI regression tests behind feature flag.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.admin.tests_admin_bootstrap_ui -v 2` (4/4)
- [x] `./.venv/bin/python manage.py test wms.tests.admin.tests_admin_extra -v 2` (17/17)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Bootstrap CSS is loaded only when `SCAN_BOOTSTRAP_ENABLED=true`.
- Rollback path remains `SCAN_BOOTSTRAP_ENABLED=false`.
- Safety fix included: `ShipmentAdmin.readonly_fields` now includes `created_at` to avoid admin form `FieldError` on shipment change page.
