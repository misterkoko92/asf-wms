# Design Foundations - Lot 8

## Scope
- Start the design phase without touching business logic.
- Define reusable visual foundations for the Bootstrap rollout (`Sauge douce`, `Manrope + Source Sans 3`, density standard).
- Add a safe sandbox page to iterate quickly on UI style.

## Deliverables
- New staff-only sandbox page:
  - `wms/scan_urls.py` (`scan_ui_lab` route)
  - `wms/views_scan_misc.py` + exports (`wms/views_scan.py`, `wms/views.py`)
  - `templates/scan/ui_lab.html`
  - `wms/static/scan/ui-lab.css`
- Navigation link in scan settings menu:
  - `templates/scan/base.html`
- Foundation tokens and Bootstrap bridge refresh:
  - `wms/static/scan/scan-bootstrap.css`
- Palette alignment updates for existing bridge files:
  - `wms/static/portal/portal-bootstrap.css`
  - `wms/static/wms/admin-bootstrap.css`

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc -v 2` (5/5)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2` (13/13)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_public_order -v 2` (15/15)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2` (25/25)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Sandbox page is intentionally non-functional and safe for visual experimentation only.
- Rollback remains immediate with `SCAN_BOOTSTRAP_ENABLED=false`.
