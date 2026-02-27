# Bootstrap Migration - App Fallback Lot 5

## Scope
- Keep reversible rollout with `SCAN_BOOTSTRAP_ENABLED`.
- Modernize the Next fallback page displayed when static export is missing.
- Preserve current behavior and HTTP status (`503`) for operational troubleshooting.

## Target page
- `templates/app/next_build_missing.html`

## Implementation checklist
- [x] Add conditional Bootstrap CDN CSS include behind `SCAN_BOOTSTRAP_ENABLED`.
- [x] Add dedicated bridge stylesheet: `wms/static/app/next-bootstrap.css`.
- [x] Keep standalone fallback styles when feature flag is disabled.
- [x] Add UI regression assertion for Bootstrap assets in Next fallback test suite.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_next_frontend -v 2` (9/9)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Rollback remains immediate with `SCAN_BOOTSTRAP_ENABLED=false`.
- This lot intentionally excludes `templates/print/*` to avoid print layout regressions.
