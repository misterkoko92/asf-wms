# V3.3 Artifacts Runtime Map

## Goal

Freeze the current planning/document artifact lifecycle before moving orchestration into `wms/artifacts/`.

The target boundary for `V3.3` is:

- `wms/artifacts/planning.py`
- `wms/artifacts/attachments.py`
- `wms/artifacts/proofs.py`
- `wms/application/planning_artifacts/use_cases.py`

## Current Runtime Entry Points

### Planning workbook and PDF generation

Current entrypoints:

- `wms/planning/exports.py`
- `tools/planning_comm_helper/planning_pdf.py`
- `tools/planning_comm_helper/excel_pdf.py`
- `tools/planning_comm_helper/excel_runtime.py`

Current responsibilities mixed in `wms/planning/exports.py`:

- template resolution
- workbook row rendering and layout hiding
- file naming and output directory resolution
- PDF conversion delegation
- artifact status/error recording

### Readiness and health visibility

Current entrypoints:

- `wms/planning/artifact_health.py`
- `wms/jobs/runtime_checks.py`
- `wms/management/commands/check_planning_pdf_runtime.py`
- `wms/management/commands/check_document_scan_runtime.py`

Current responsibilities:

- readiness status persistence for workbook/PDF artifacts
- backend/runtime availability checks
- operator-facing health messages

### Communication attachment selection and proofs

Current entrypoints:

- `wms/planning/communication_actions.py`
- `wms/planning/communications.py`
- `wms/planning/communication_plan.py`
- `wms/print_pack_sync.py`

Current responsibilities:

- choosing which planning artifacts may be attached
- preferring PDF-first communication payloads
- surfacing missing artifacts as blocking runtime state
- syncing generated print artifacts and proof-like metadata

## Current Structural Invariants

The runtime currently assumes:

- planning workbook generation remains the source of truth for strict layout output
- PDF availability is tracked as a readiness artifact, not only as a transient file
- communication flows should prefer `planning_pdf` when available
- runtime checks, not UI views, are the source of truth for artifact health state

## Target V3.3 Boundary

`wms/artifacts/` will become the orchestration boundary for:

- workbook generation
- PDF conversion
- readiness/result persistence
- attachment resolution for communications
- proof and downstream sync behavior

Legacy planning modules will stay in place temporarily as adapters:

- `wms/planning/exports.py`
- `wms/planning/communication_actions.py`
- `wms/planning/communications.py`

## First Migration Slice

The first executable `V3.3` slice should:

1. isolate planning artifact orchestration behind `wms/artifacts/planning.py`
2. separate attachment resolution from export rendering
3. keep existing commands and views stable while the new boundary becomes the only place that decides artifact readiness and communication eligibility
