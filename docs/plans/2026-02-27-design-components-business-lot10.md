# Design Components - Business Pages Lot 10

## Scope
- Apply validated design component classes to two production pages:
  - `Vue stock`
  - `Création / modification expédition`
- Keep all workflows and JS hooks unchanged.

## Target templates
- `templates/scan/stock.html`
- `templates/scan/shipment_create.html`
- `wms/static/scan/scan-bootstrap.css` (component classes)

## Implementation checklist
- [x] Add reusable component classes (`ui-comp-*`) to both target templates.
- [x] Keep existing ids/data attributes (`shipment-form`, `shipment-lines`, etc.).
- [x] Add component bridge styles in `scan-bootstrap.css` (card header strip, title, panel, actions, note, count badge).
- [x] Add regression assertions in `wms/tests/views/tests_scan_bootstrap_ui.py`.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2` (14/14)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc -v 2` (5/5)
- [x] `./.venv/bin/python manage.py check`

## Notes
- No backend logic changed.
- Component classes are additive and scoped under `scan-bootstrap-enabled` for safe rollback.
