# Design Components - Preparation Pages Lot 16

## Scope
- Apply validated `ui-comp-*` classes to preparation pages:
  - `Pr&eacute;paration cartons`
  - `Supprimer produit`
  - `MAJ stock`
- Keep JS hooks and form behavior unchanged.

## Target templates
- `templates/scan/pack.html`
- `templates/scan/out.html`
- `templates/scan/stock_update.html`
- `wms/tests/views/tests_scan_bootstrap_ui.py` (regression assertion)

## Implementation checklist
- [x] Add `ui-comp-card` on page cards.
- [x] Add `ui-comp-title` on main titles.
- [x] Add `ui-comp-form` on primary forms.
- [x] Add `ui-comp-note` on helper notes where relevant.
- [x] Add dedicated regression test on preparation routes.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_preparation_forms_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2` (20/20)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2` (25/25)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc -v 2` (5/5)
- [x] `./.venv/bin/python manage.py check`

## Notes
- No backend logic changes.
