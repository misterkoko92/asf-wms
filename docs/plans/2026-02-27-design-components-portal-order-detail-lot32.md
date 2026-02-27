# Design Components - Portal Order Detail Lot 32

## Scope
- Apply validated `ui-comp-*` classes to portal order detail page.
- Keep document upload flow and status display unchanged.

## Target templates
- `templates/portal/order_detail.html`
- `wms/tests/views/tests_portal_bootstrap_ui.py` (regression assertion)

## Implementation checklist
- [x] Add `ui-comp-card` on detail sections.
- [x] Add `ui-comp-title` on section headings.
- [x] Add `ui-comp-form` on upload form.
- [x] Keep upload field names and POST action unchanged.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests.test_portal_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal -v 2` (69/69)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Additive class migration only.
