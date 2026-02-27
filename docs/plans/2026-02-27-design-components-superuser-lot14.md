# Design Components - Superuser Pages Lot 14

## Scope
- Apply validated `ui-comp-*` classes to superuser pages:
  - `Paramètres`
  - `Admin - Contacts`
  - `Admin - Produit`
- Keep all admin links and management workflows unchanged.

## Target templates
- `templates/scan/settings.html`
- `templates/scan/admin_contacts.html`
- `templates/scan/admin_products.html`
- `wms/tests/views/tests_scan_bootstrap_ui.py` (regression assertions)

## Implementation checklist
- [x] Add `ui-comp-card` on page cards.
- [x] Add `ui-comp-title` on main titles.
- [x] Add `ui-comp-form` on main filter/settings forms.
- [x] Keep admin links, actions and table content unchanged.
- [x] Add dedicated superuser regression test for component markers.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_superuser_admin_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2` (18/18)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2` (25/25)
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc -v 2` (5/5)
- [x] `./.venv/bin/python manage.py check`

## Notes
- No backend logic changes.
- Visual migration remains reversible through `SCAN_BOOTSTRAP_ENABLED`.
