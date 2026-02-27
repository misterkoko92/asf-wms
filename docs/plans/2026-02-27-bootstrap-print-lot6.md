# Bootstrap Migration - Print Preview Lot 6

## Scope
- Keep rollout reversible with `SCAN_BOOTSTRAP_ENABLED`.
- Modernize the public order summary page rendered from `print/` templates.
- Preserve print/PDF output behavior while improving screen preview consistency.

## Target page
- `templates/print/order_summary.html`

## Implementation checklist
- [x] Add conditional Bootstrap CDN CSS include behind `SCAN_BOOTSTRAP_ENABLED`.
- [x] Add conditional scan bridge CSS include (`scan/scan-bootstrap.css`) for visual consistency.
- [x] Upgrade card/table/button markup to Bootstrap-compatible classes while preserving legacy classes.
- [x] Keep print safeguards (`no-print`, no shadow in print media).
- [x] Add UI regression test for bootstrap assets in public order summary.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_public_order -v 2` (15/15)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs -v 2` (11/11)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Rollback remains immediate with `SCAN_BOOTSTRAP_ENABLED=false`.
- This lot is intentionally limited to the summary page; document/label print templates remain unchanged to avoid print-layout regressions.
