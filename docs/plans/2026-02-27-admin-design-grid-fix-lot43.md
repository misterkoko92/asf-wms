# Admin Design Grid Fix - Lot 43

## Scope
- Fix broken layout on `Scan > Admin > Design` where section titles and color blocks were mispositioned.
- Ensure the `Couleurs` title is aligned correctly in its section.
- Ensure all color cards render completely (no truncation after the first two cards).

## Root cause
- The form uses shared class `scan-filters`, which becomes a 4-column CSS grid on desktop (`@media min-width:640px`).
- This caused the design editor sections to be placed in grid cells instead of full-width rows.
- Combined with `overflow: hidden` on `.ui-comp-card`, the color row appeared clipped/incomplete.

## Target files
- `templates/scan/admin_design.html`
- `wms/tests/views/tests_views_scan_admin.py`

## Implementation checklist
- [x] Add a dedicated class `scan-design-form` to force full-width row layout.
- [x] Make all direct children of the design form span full width (`grid-column: 1 / -1`).
- [x] Override card overflow for this editor (`scan-design-editor-card`) to prevent clipping.
- [x] Keep color cards on a single horizontal line with consistent width and no overlap.
- [x] Add regression marker assertion in admin design view test.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_superuser_admin_pages_use_design_component_classes -v 2`
