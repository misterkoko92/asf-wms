# V2 Prod Readiness Excel-First Design

## Goal

Close ASF WMS V2 for production by hardening the planning PDF/mail path, operationalizing pilotage refresh, and making release readiness explicit without reopening V3 scope.

## Chosen Approach

Use `Microsoft Excel` as the official planning PDF backend for V2 production.

Why this approach:

- the strict planning output already uses the workbook as the source of truth
- you explicitly rejected LibreOffice because the visual fidelity is not good enough
- a server-only HTML/CSS rewrite would reopen rendering scope and delay V2
- the remaining risk is operational, not architectural, so V2 should harden the Excel path instead of replacing it

## Rejected Alternatives

### 1. LibreOffice-first

Rejected because the resulting PDF layout is not good enough for the planning sheet.

### 2. HTML/CSS PDF rewrite now

Rejected for V2 because it would require a second rendering contract and a full visual requalification.

### 3. Delay production until V3

Rejected because the remaining work can be closed by hardening the current stack instead of redesigning it.

## Scope

In scope:

- make `excel_desktop` the explicit V2 planning PDF backend
- add a runtime readiness check before planning PDF generation and before release
- persist clearer PDF backend failure details in artifact health
- block or mark internal planning mail payloads when no ready PDF exists
- expose runtime readiness in the legacy planning cockpit
- add one command to refresh pilotage snapshots and escalations together
- update release and operations docs for the real V2 production loop

Out of scope:

- replacing Excel with another rendering engine
- HTML/CSS planning rendering
- V3 product features
- background schedulers tied to a specific production platform

## Runtime Design

### 1. Planning PDF backend contract

The planning PDF backend for V2 is:

- backend id: `excel_desktop`
- source artifact: strict `planning_workbook`
- output artifact: `planning_pdf`

The backend selection rule is simple:

- V2 tries Excel only
- if Excel is unavailable, the export is considered not production-ready
- no silent fallback to LibreOffice

### 2. Runtime readiness boundary

Add a small boundary around Excel runtime detection in the helper layer.

It should answer:

- which backend is expected
- whether the current host is ready to generate the PDF
- which stable failure code applies when it is not ready
- a short human-readable detail for operators and release checks

Expected stable readiness codes:

- `ready`
- `platform_unsupported`
- `excel_not_installed`
- `excel_automation_unavailable`

This boundary must be reusable from:

- planning export generation
- management commands
- planning cockpit status
- release checks

### 3. Export path hardening

The strict workbook still generates first.

The PDF step must:

- check runtime readiness before attempting conversion
- record the backend actually used
- record stable failure details in `PlanningCommunicationArtifact.payload`
- keep the workbook artifact even when PDF generation fails
- make the failure explicit in the planning cockpit and pilotage

Expected stable failure payload keys:

- `error_code`
- `runtime_status`
- `runtime_detail`

### 4. Mail and helper safety

Internal planning mail flows should never behave as if the planning PDF were ready when it is not.

For planning families that require the planning PDF:

- prefer the latest ready PDF artifact
- if none exists, expose a blocked payload state
- include a stable `blocking_reason`, for example `planning_pdf_not_ready`

This keeps the helper contract honest and avoids a pseudo-ready send path in production.

### 5. Planning cockpit visibility

The legacy planning export block should expose two kinds of status:

- artifact health: what was last generated
- runtime readiness: whether the current host can generate a PDF now

This is important because an operator may otherwise only see “last PDF failed” without understanding whether the runtime itself is currently viable.

### 6. Pilotage operational loop

V2 production needs a simple and repeatable ops loop.

Add a single command that chains:

- `capture_ops_pilotage_snapshot`
- `evaluate_ops_escalations`

The purpose is not to introduce a scheduler abstraction. It is to give production one stable entry point for cron, launchd, task scheduler, or manual ops replay.

### 7. Release gate expectation

Production readiness for V2 should require:

- planning PDF runtime check passes
- workbook/PDF export path passes on a real planning version
- pilotage refresh command runs cleanly
- cockpit screens expose the expected threshold and export health states

## Surface Impact

Runtime and helper layer:

- `tools/planning_comm_helper/excel_runtime.py`
- `tools/planning_comm_helper/excel_pdf.py`
- `tools/planning_comm_helper/planning_pdf.py`

WMS planning layer:

- `wms/planning/exports.py`
- `wms/planning/artifact_health.py`
- `wms/planning/communication_actions.py`
- `wms/planning/version_dashboard.py`
- `wms/views_planning.py`
- `templates/planning/_version_exports_block.html`

Ops commands:

- `wms/management/commands/check_planning_pdf_runtime.py`
- `wms/management/commands/refresh_ops_pilotage.py`

Docs:

- `docs/operations.md`
- `docs/repo-reference/02-key-flows-and-living-tests.md`
- `docs/repo-reference/04-shared-contracts.md`
- `docs/release_checklist.md`

## Risks

### Excel remains a host dependency

This is acceptable for V2, but it must be made explicit in runtime checks and release docs.

### Mac and Windows behavior differ

The readiness boundary must keep the contract stable even if the detection mechanism differs by platform.

### Helper payload compatibility

Adding `blocked` or `blocking_reason` must not break existing consumers; it should extend the payload rather than reshape it.

## Success Criteria

V2 is considered production-ready when:

- a real planning version can generate `planning_workbook` and `planning_pdf` on the target host
- planning email/helper payloads no longer pretend a PDF exists when it does not
- runtime readiness is visible before operators attempt regeneration
- one command refreshes pilotage snapshots and escalations
- release docs and smoke expectations match the real runtime contract
