# Planning Impact Map

Use this file when touching any `/planning/` workflow, allocation logic, run generation, exports, publication flow, or planning artifacts.

Read this file for changes involving:

- planning runs
- planning versions
- solve / allocation workflows
- shipment eligibility for planning
- flight load balancing
- publish flows
- communication exports
- workbook exports
- PDF planning artifacts
- attachments / proofs
- planning cockpit UI
- planning filters / views
- planning commands / automation
- planning visibility from shipment readiness states

Planning changes can silently affect real operations, cargo allocation, and communication quality.

---

## Also Read

Depending on the change, also read:

- `03c-impact-shipments.md` — shipment readiness / eligibility
- `03a-impact-scan.md` — operational handoff from warehouse
- `03e-impact-print-documents.md` — exports / PDFs / generated packs
- `03g-impact-shared-ui-api.md` — mirrored payloads / shared UI
- `03h-impact-email-events.md` — publication notifications / async jobs
- `04-shared-contracts.md` — shared lists / filters / UI patterns

If unsure, read more than one file.

---

## Critical Invariants

These rules must remain true unless explicitly redesigned.

### Readiness Integrity

Only eligible shipments should appear in planning.

Non-ready states (such as current `PICKING`) must remain excluded unless business rules explicitly change.

### Allocation Integrity

- no shipment should be allocated twice unintentionally
- weight / volume / capacity constraints must remain coherent
- manual overrides must remain visible

### Version Integrity

- versions must remain distinguishable
- published vs draft states must remain clear
- users must know which version is authoritative

### Artifact Integrity

Exports, PDFs, and generated files must reflect the selected planning version.

### Communication Integrity

Shared planning outputs must not contradict operational reality.

---

## Always Check

### Runtime Sources

- `wms/planning_urls.py`
- `wms/views_planning.py`
- `wms/planning/*`

### Domain Sources

- `wms/models_domain/planning.py`

### Modern Boundaries

- `wms/application/planning/*`
- `wms/artifacts/*`
- `wms/application/planning_artifacts/*`

### Commands / Automation

- planning-related commands under `wms/management/commands/`

### Templates

- `templates/planning/`

### Tests

- `wms/tests/planning/`

---

## Ask Yourself

### Eligibility Questions

- did shipment readiness rules change?
- are non-ready shipments leaking into planning?
- are ready shipments missing unexpectedly?

### Solver / Allocation Questions

- does solve still complete?
- do allocations remain coherent?
- are edge constraints respected?
- did manual adjustments get lost?

### Version Questions

- can users distinguish draft vs published?
- is latest visible version obvious?
- do historical versions remain readable?

### Artifact Questions

- do exports match selected version?
- are attachment names stable?
- do PDFs still render correctly?

### Operational Questions

- will coordinators trust this output?
- does this reduce or increase manual rework?
- can a mistake propagate to real flights?

### UX Questions

- is cockpit navigation still clear?
- do filters survive navigation?
- are priorities obvious?

---

## Precision Checks

### If Editing Eligibility Rules

Also verify:

- `wms/planning/sources.py`
- shipment status logic
- warehouse handoff assumptions
- `03c-impact-shipments.md`

### If Editing Solve / Allocation

Also verify:

- planning run creation
- version generation
- manual override persistence
- edge-case capacity scenarios

### If Editing Publish Flow

Also verify:

- visible published marker
- downstream exports
- notifications if any
- operator understanding of active version

### If Editing Artifacts

Also verify:

- `wms/artifacts/planning.py`
- `wms/artifacts/attachments.py`
- `wms/artifacts/proofs.py`
- generated filenames
- downloadable routes

### If Editing Cockpit UI

Also verify:

- hierarchy remains clear:

`header -> priorities -> section nav -> main planning by flight -> secondary details`

---

## Run First

Choose nearest tests.

### High Value

- `wms/tests/planning/tests_smoke_planning_flow.py`

### Planning Domain

- nearest tests under `wms/tests/planning/`

### If Shipment Eligibility Changed

- shipment flow tests
- E2E workflow tests

### If Artifacts Changed

- print/export tests
- artifact tests

---

## Known Traps

### False Ready Trap

Shipments enter planning before physically ready.

### Invisible Constraint Trap

Solver appears successful but violates real capacity logic.

### Wrong Version Trap

Users act on stale draft instead of published version.

### Export Drift Trap

Workbook/PDF no longer matches displayed planning data.

### Manual Override Trap

Re-run solve silently discards coordinator adjustments.

### Communication Trap

Published outputs sent with outdated assumptions.

---

## Docs To Update

If behavior changed, review:

- `docs/operations.md`
- `docs/release_checklist.md`
- `docs/repo-reference/02-key-flows-and-living-tests.md`
- `docs/repo-reference/04-shared-contracts.md`

---

## Final Rule

If changing planning logic, optimize for operational trust, clarity, and real-world correctness — not algorithm elegance alone.
