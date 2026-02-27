# Design Components - Portal Order Create Lot 31

## Scope
- Apply validated `ui-comp-*` classes to portal order creation page.
- Keep recipient filtering and carton estimation JS behavior unchanged.

## Target templates
- `templates/portal/order_create.html`
- `wms/tests/views/tests_portal_bootstrap_ui.py` (regression assertion)

## Implementation checklist
- [x] Add `ui-comp-card` on top-level cards.
- [x] Add `ui-comp-title` on primary heading.
- [x] Add `ui-comp-form` on main order form.
- [x] Add `ui-comp-actions` on category/product actions rows.
- [x] Keep form names/ids and JS hooks unchanged.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests.test_portal_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal -v 2` (69/69)
- [x] `./.venv/bin/python manage.py check`

## Notes
- No backend changes.
