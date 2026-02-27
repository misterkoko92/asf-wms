# Design Components - Kits Pages Lot 11

## Scope
- Apply validated design component classes to the two kits production pages:
  - `Vue Kits`
  - `Pr&eacute;parer des kits`
- Keep workflows, form ids and client-side behavior unchanged.

## Target templates
- `templates/scan/kits_view.html`
- `templates/scan/prepare_kits.html`
- `wms/tests/views/tests_scan_bootstrap_ui.py` (regression assertions)

## Implementation checklist
- [x] Add `ui-comp-*` classes to `Vue Kits` card, title and counter badge.
- [x] Add `ui-comp-*` classes to `Pr&eacute;parer des kits` form panels and actions area.
- [x] Keep JS-sensitive markers unchanged (`id_kit_id`, `prepare-kits-components`, `prepare-kits-theoretical`, `prepare-kits-max`).
- [x] Add a dedicated bootstrap UI regression test for kits pages.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_kits_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2` (15/15)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2` (25/25)
- [x] `./.venv/bin/python manage.py check`

## Notes
- No backend logic changes.
- Styles remain feature-flag safe through the existing `scan-bootstrap-enabled` scope.
