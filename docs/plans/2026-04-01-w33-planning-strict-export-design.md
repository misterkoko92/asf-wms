# W3.3 Planning Strict Export Design

## Goal

Deliver a strict planning export for legacy Django planning versions in `asf-wms`, with:

- workbook rendering aligned with the existing `asf_scheduler` final output rules
- PDF generation derived from the rendered workbook
- operator-facing download actions in the planning cockpit
- planning email attachments switched to PDF-first delivery

This lot stays local-first and is optimized for calibration, visual verification, and future mail diffusion of the PDF.

## Chosen Approach

Use an Excel-first export pipeline and derive the PDF from the generated workbook.

Why this approach:

- the strict layout rules already exist in `asf_scheduler`
- the reference output is workbook-driven, not HTML-driven
- PDF fidelity is more likely if the workbook remains the rendering source of truth
- the PDF backend can be isolated so a later HTML/CSS print renderer can replace it without changing the planning UI or attachment contracts

## Scope

In scope:

- strict planning workbook generation for a `PlanningVersion`
- PDF artifact generation from that workbook
- version cockpit export actions and artifact download links
- internal planning communication attachments changed to planning PDF
- reference tests, repo-reference docs, and operations notes

Out of scope:

- HTML/CSS print rendering
- remote mail sending automation
- multi-artifact merge workflows
- forcing strict visual parity for historical diff colors beyond what the current WMS version model can express safely

## Runtime Shape

### 1. Strict workbook service

Add a workbook service in the planning export layer that:

- resolves a vendored `Planning-maquette.xlsx` template from the repo
- maps `PlanningAssignment` + snapshots into export rows compatible with the strict grid
- resets the template grid before writing
- fills the planning sheet using day blocks and row hiding rules adapted from `asf_scheduler`
- updates workbook metadata cells needed by the template, especially week anchor and version number
- stores the result as a `PlanningArtifact` of type `planning_workbook`

### 2. PDF generation service

Add a PDF generation step that:

- takes the generated workbook artifact as input
- uses the existing local Excel automation wrapper in `tools/planning_comm_helper/planning_pdf.py`
- stores the generated PDF as a `PlanningArtifact` of type `planning_pdf`

Behavior:

- the main export action should try to regenerate both workbook and PDF
- if workbook generation succeeds but PDF generation fails, keep the workbook artifact and surface a clear operator error
- communication download endpoints for PDF may regenerate on demand if the artifact is missing

### 3. Planning cockpit integration

Update the legacy planning exports block so operators can:

- regenerate the strict export bundle
- download the workbook
- download the PDF
- see which artifact types are available for the version

The PDF is the primary operator output. The workbook remains available for inspection and calibration.

### 4. Communication attachment contract

Internal planning drafts should attach the planning PDF instead of the workbook.

Rationale:

- the ultimate target is PDF diffusion by mail
- the helper already knows how to attach arbitrary files once downloaded
- sending the server-generated PDF avoids duplicate workbook-to-PDF conversion in the helper

Partner email flows stay unchanged and continue to use packing list PDFs.

## Data Mapping

The strict workbook rows will be derived from current version assignments only.

Planned row mapping:

- volunteer display: `volunteer_snapshot.volunteer_label`
- destination city: `shipment_snapshot.payload.destination_city`
- destination IATA: `shipment_snapshot.destination_iata`
- routing: `flight_snapshot.payload.routing`
- flight display: `format_vol_display(flight_snapshot.flight_number)`
- departure time display: `flight_snapshot.payload.departure_time`
- BE number: derived from `shipment_snapshot.shipment_reference` with `format_be_number(...)`
- carton count: `assigned_carton_count`
- shipment type: `shipment_snapshot.payload.legacy_type`
- shipper: `shipment_snapshot.shipper_name`
- recipient: `shipment_snapshot.payload.legacy_destinataire`
- departure warehouse date: optional `shipment_snapshot.payload.legacy_date_depart_mag`

The first version will not try to recreate historical removed rows from `based_on` into the strict export. If a later lot needs visual old/new diff styling in the workbook, that should be added as a dedicated follow-up.

## Template Ownership

The strict workbook template must be vendored into `asf-wms`, not resolved from `asf_scheduler` at runtime.

Recommended location:

- `data/planning_templates/Planning-maquette.xlsx`

Why:

- avoids a hidden cross-repo runtime dependency
- makes the export portable inside the WMS worktree
- keeps local calibration reproducible

## Routes And Actions

### Existing action to evolve

- `POST /planning/versions/<id>/` with `artifact_action=export`

New behavior:

- regenerate strict workbook
- attempt PDF generation
- report success or partial failure through Django messages

### Download endpoints

Keep workbook download:

- `planning:version_communication_workbook`

Add planning PDF download:

- `planning:version_communication_pdf`

The exports block may also deep-link to these routes for direct download.

## Tests

Primary tests to update or add:

- `wms/tests/planning/tests_outputs.py`
- `wms/tests/planning/tests_communication_actions.py`
- `wms/tests/views/tests_views_planning.py`
- helper-side PDF tests only if the Django layer changes the existing helper contract

Key assertions:

- strict template workbook is created with the expected sheet and populated cells
- unused rows are hidden
- PDF artifact is created through the converter boundary
- planning communication payloads expose `planning_pdf`
- planning communication PDF download endpoint responds correctly
- planning version detail shows the new export controls and artifact labels

## Risks

### Excel automation availability

PDF generation depends on local Excel automation. In local mode this is acceptable, but the UI must surface clear failure when Excel is unavailable.

### Template drift

Vendoring the template means future changes in `asf_scheduler` will not automatically propagate. This is intentional for stability, but should be documented.

### Incomplete legacy data

Some legacy fields such as shipment type or departure warehouse date may be absent in WMS snapshots. The export must degrade to blank values, not fail.

## Follow-ups

- HTML/CSS print renderer if PDF mail diffusion later needs a server-only backend
- richer workbook diff styling for superseded vs current assignments
- optional BI/export API for planning artifacts metadata
