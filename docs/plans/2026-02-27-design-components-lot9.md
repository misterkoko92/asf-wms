# Design Components - UI Lab Lot 9

## Scope
- Keep this lot fully safe and non-functional (sandbox only).
- Add live controls to test design combinations instantly in `UI Lab`.
- Keep business pages unchanged while validating palette, typography, and density options.

## Deliverables
- UI Lab controls:
  - Palette selector (`Sauge douce`, `Bleu brume`, `Thé vert sable`)
  - Typography selector (`Manrope + Source Sans 3`, `DM Sans + Nunito Sans`, `Aptos-like`)
  - Density selector (`compact`, `standard`, `aéré`)
- Preview container with runtime data attributes:
  - `data-ui-lab-palette`
  - `data-ui-lab-typography`
  - `data-ui-lab-density`
- New JS behavior (`wms/static/scan/ui-lab.js`):
  - Applies selector values to preview
  - Persists settings in `localStorage`
- Extended UI test assertions for controls and preview markers.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc -v 2` (5/5)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2` (13/13)
- [x] `./.venv/bin/python manage.py check`

## Notes
- This lot intentionally does not modify workflow/business templates.
- Changes are isolated to `UI Lab` for fast visual iteration with zero production risk.
