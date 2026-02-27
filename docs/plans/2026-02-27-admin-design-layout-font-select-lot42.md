# Admin Design Layout + Font Select - Lot 42

## Scope
- Align the typography section fields cleanly and remove the helper sentence under the section title.
- Render all color cards on a single horizontal line without overlap.
- Slightly reduce color preview block size to fit the line while keeping visual feedback.
- Replace typography free-text inputs with dropdown lists of available fonts.

## Target files
- `wms/forms_scan_design.py`
- `templates/scan/admin_design.html`
- `wms/tests/views/tests_views_scan_admin.py`

## Implementation checklist
- [x] Convert typography fields (`H1`, `H2`, `H3`, `texte`) to `select` widgets.
- [x] Add a curated list of available font options.
- [x] Preserve compatibility for custom values already stored (append current value when missing from the list).
- [x] Remove the sentence `Une seule police par champ (H1, H2, H3 et texte).`.
- [x] Align typography blocks with consistent spacing.
- [x] Keep color cards on one line with horizontal overflow handling and no overlap.
- [x] Reduce color preview/card footprint for better single-line density.

## Validation checklist
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin.ScanAdminViewTests.test_scan_admin_design_renders_design_form -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin -v 2`
- [x] `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_superuser_admin_pages_use_design_component_classes -v 2`
- [x] `./.venv/bin/python manage.py check`
- [x] `./.venv/bin/python manage.py makemigrations --check --dry-run`
