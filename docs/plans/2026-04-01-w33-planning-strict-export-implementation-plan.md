# W3.3 Planning Strict Export Implementation Plan

## Goal

Implement a strict planning export bundle in `asf-wms` legacy planning:

- strict `planning_workbook`
- server-side `planning_pdf`
- PDF-first planning communication attachments

## Task 1: Lock the strict export contract in tests first

Files:

- modify `wms/tests/planning/tests_outputs.py`
- modify `wms/tests/planning/tests_communication_actions.py`
- modify `wms/tests/views/tests_views_planning.py`

Add failing coverage for:

- strict workbook export uses the template shape instead of the old flat sheet
- workbook export creates or updates a `planning_workbook` artifact
- PDF export creates or updates a `planning_pdf` artifact when the converter succeeds
- internal communication payloads now use `planning_pdf`
- planning communication PDF endpoint downloads the artifact
- version detail POST export reports the combined export path

## Task 2: Vendor the planning template and implement the strict workbook service

Files:

- create `data/planning_templates/Planning-maquette.xlsx`
- modify `wms/planning/exports.py`

Implementation:

- add template resolution in repo data
- add strict row mapping from assignments and snapshots
- port the day-block, grid reset, row hide, and layout rules needed from `asf_scheduler`
- keep workbook artifact storage compatible with existing `PlanningArtifact`

## Task 3: Add PDF artifact generation on top of the workbook

Files:

- modify `wms/planning/exports.py`

Implementation:

- add an export function that regenerates workbook then PDF
- call the existing planning PDF converter boundary
- store/update `planning_pdf` artifact
- raise a specific export exception for UI and endpoint handling

## Task 4: Expose workbook/PDF downloads in planning views and templates

Files:

- modify `wms/views_planning.py`
- modify `wms/planning_urls.py`
- modify `templates/planning/_version_exports_block.html`
- modify `wms/planning/version_dashboard.py`

Implementation:

- keep workbook download endpoint
- add PDF download endpoint
- enrich export block with regenerate action and per-artifact download links
- keep the cockpit ordering intact

## Task 5: Switch internal planning attachments to PDF-first

Files:

- modify `wms/planning/communication_actions.py`
- modify `wms/views_planning.py`
- optionally modify helper-side attachment tests only if needed

Implementation:

- add `planning_pdf` attachment type
- map internal planning email families to PDF attachments
- add download URL resolution for the PDF route
- keep packing-list attachments unchanged

## Task 6: Update docs and verify end to end

Files:

- modify `docs/repo-reference/02-key-flows-and-living-tests.md`
- modify `docs/repo-reference/04-shared-contracts.md`
- modify `docs/operations.md`

Run:

```bash
./.venv/bin/python manage.py test wms.tests.planning.tests_outputs wms.tests.planning.tests_communication_actions wms.tests.views.tests_views_planning -v 2
uv run ruff check wms/planning/exports.py wms/planning/communication_actions.py wms/views_planning.py wms/planning/version_dashboard.py wms/planning_urls.py
```

Optional smoke after implementation:

- export from `/planning/versions/<id>/`
- download workbook and PDF
- open internal communication helper payload and verify `planning_pdf`
