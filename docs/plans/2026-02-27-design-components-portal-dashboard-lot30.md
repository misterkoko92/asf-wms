# Design Components - Portal Dashboard Lot 30

## Scope
- Apply validated `ui-comp-*` classes to portal dashboard page.
- Keep order listing behavior, table tools, and links unchanged.

## Target templates
- `templates/portal/dashboard.html`
- `wms/tests/views/tests_portal_bootstrap_ui.py` (regression assertion)

## Implementation checklist
- [x] Add `ui-comp-card` on dashboard cards.
- [x] Add `ui-comp-title` on page heading.
- [x] Keep existing table hooks (`data-table-tools`) unchanged.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests.test_portal_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal -v 2` (69/69)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Visual-only class additions.
