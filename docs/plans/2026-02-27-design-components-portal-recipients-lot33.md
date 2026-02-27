# Design Components - Portal Recipients Lot 33

## Scope
- Apply validated `ui-comp-*` classes to portal recipients page.
- Keep create/edit recipient workflows and validation unchanged.

## Target templates
- `templates/portal/recipients.html`
- `wms/tests/views/tests_portal_bootstrap_ui.py` (regression assertion)

## Implementation checklist
- [x] Add `ui-comp-card` on list/form cards.
- [x] Add `ui-comp-title` on section headings.
- [x] Add `ui-comp-form` on recipient form.
- [x] Add `ui-comp-panel` on option flags panel.
- [x] Add `ui-comp-actions` on table action cell.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests.test_portal_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal -v 2` (69/69)
- [x] `./.venv/bin/python manage.py check`

## Notes
- Behavior preserved.
