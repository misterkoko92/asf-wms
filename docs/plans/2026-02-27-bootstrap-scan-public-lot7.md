# Bootstrap Migration - Scan Public Finalization Lot 7

## Scope
- Keep rollout reversible with `SCAN_BOOTSTRAP_ENABLED`.
- Finalize Bootstrap wiring on remaining standalone scan public pages.
- Preserve existing form logic and tracking workflow behavior.

## Target pages
- `templates/scan/public_order.html`
- `templates/scan/shipment_tracking.html`

## Implementation checklist
- [x] Add conditional Bootstrap CDN CSS includes behind `SCAN_BOOTSTRAP_ENABLED`.
- [x] Add conditional `scan/scan-bootstrap.css` include for both pages.
- [x] Add `scan-bootstrap-enabled` body class when feature flag is enabled.
- [x] Add conditional Bootstrap JS bundle include.
- [x] Add regression test covering both public pages.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views.ScanViewTests.test_scan_public_pages_include_bootstrap_assets_when_enabled -v 2` (1/1)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_public_order -v 2` (15/15)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2` (25/25)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Rollback remains immediate with `SCAN_BOOTSTRAP_ENABLED=false`.
- Remaining non-bootstrap templates are print/document templates intentionally excluded from screen UI migration to avoid print-layout regressions.
