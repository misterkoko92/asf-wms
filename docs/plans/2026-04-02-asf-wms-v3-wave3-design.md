# ASF WMS V3.3 Domain And Runtime Simplification Design

## Goal

Deliver a structural `V3.3` that simplifies the most expensive shared domains left after `V3.1` and `V3.2`, with a focus on:

- `parties / contacts / portal recipient sync`
- planning and document artifact runtime
- legacy `scan` frontend modularization
- broader quality gates on the new structural boundaries

The target is not a visible product rewrite. The target is a codebase that is materially easier to reason about, test, and operate.

## Context After V3.1 And V3.2

`V3.1` extracted shared application queries and policies.

`V3.2` introduced explicit `events`, `jobs`, `OperationalJobRun`, and a normalized outbox boundary around `IntegrationEvent`.

Those two waves removed a large part of the orchestration debt, but they also made the remaining structural hotspots more obvious:

- the shipment-party graph is still spread across multiple runtime entry points
- portal sync still mixes contact upsert, shipment-party creation, and fallback heuristics in one mutation flow
- planning artifacts still mix workbook rendering, PDF conversion, readiness, and attachment selection
- `scan.js`, `scan.css`, and `scan-bootstrap.css` are still monolithic legacy entry points
- static analysis still covers a narrow, curated slice instead of the main structural hotspots

## Evidence From The Current Code

### 1. Parties And Contacts Remain Over-Coupled

The current runtime splits shipment-party behavior across:

- `wms/portal_recipient_sync.py`
- `wms/shipment_party_setup.py`
- `wms/shipment_party_registry.py`
- `wms/shipment_party_rules.py`
- `wms/admin_contacts_merge_service.py`
- `wms/scan_admin_contacts_cockpit.py`
- `wms/models_domain/shipment_parties.py`
- `wms/models_domain/portal.py`

What the code shows today:

- `portal_recipient_sync.py` orchestrates `Contact`, `ContactAddress`, `ShipmentShipper`, `ShipmentRecipientOrganization`, `ShipmentRecipientContact`, `ShipmentShipperRecipientLink`, and `ShipmentAuthorizedRecipientContact` in one file
- the same file also decides whether a `synced_contact` can be reused for another destination
- `shipment_party_setup.py` still embeds business-default heuristics such as `PRIORITY_SHIPPER_NAME = "Aviation Sans Frontieres"` and fallback contact names
- `shipment_party_registry.py` and `shipment_party_rules.py` duplicate parts of the same “validated + active + destination eligible” logic under different shapes
- `admin_contacts_merge_service.py` re-implements graph-level reconciliation rules for recipient organizations, links, and authorized contacts
- `scan_admin_contacts_cockpit.py` still contains additional graph mutation logic in the admin flow

The result is not only duplication. The harder problem is that the source of truth for shipment-party behavior is still implicit.

### 2. Recipient Organization Scope Is Still Structurally Awkward

`ShipmentRecipientOrganization` currently enforces a unique organization globally:

- `wms/models_domain/shipment_parties.py`

At the same time, the runtime repeatedly reasons in terms of `(organization, destination)`:

- `portal_recipient_sync.py` checks whether a synced organization can be reused for a different destination
- multiple views and tests use `(recipient.synced_contact_id, recipient.destination_id)` as the effective identity
- admin merge logic and portal edit flows already treat destination as part of the real business scope

This means the current schema still forces destination-scoped workarounds in sync logic. That is a structural V3.3 problem, not a local bug.

### 3. Planning And Document Artifacts Still Mix Concerns

The planning artifact chain is split across:

- `wms/planning/exports.py`
- `wms/planning/communication_actions.py`
- `tools/planning_comm_helper/planning_pdf.py`
- `wms/planning/artifact_health.py`
- `wms/print_pack_sync.py`

Today, one feature area still carries too many responsibilities:

- workbook generation
- PDF conversion
- readiness / health persistence
- delivery blocking rules
- attachment selection
- proof / sync behavior

The code works, but it is still harder than it should be to answer simple runtime questions like:

- what artifacts are required for this communication?
- which step failed, generation or readiness?
- what can be replayed safely?
- what is UI-triggered versus job-triggered?

### 4. Legacy Scan Frontend Is Still Monolithic

Current asset sizes:

- `wms/static/scan/scan.js`: `3813` lines
- `wms/static/scan/scan.css`: `1863` lines
- `wms/static/scan/scan-bootstrap.css`: `2051` lines

The coupling is also broader than one surface:

- `templates/scan/base.html` loads `scan.js`
- `scan.css` and `scan-bootstrap.css` are reused by `scan`, `portal`, `planning`, `benevole`, and some print/public pages

So the frontend problem is not “one large file”. The real issue is that shared entrypoints currently blend:

- foundation styles
- auth/public styles
- scan staff cockpit styles
- page-specific staff behaviors

### 5. Type And Contract Safety Are Still Too Narrow

Current type-checking config remains intentionally small:

- `mypy.ini`
- `pyrightconfig.json`

The include lists still focus on document scan, emailing, upload helpers, and a few management commands. They do not yet cover the structural layers created in `V3.1` and `V3.2`, nor the planned `V3.3` boundaries.

## Non-Goals

`V3.3` does not target:

- a React or Next migration
- translation parity work
- a wholesale redesign of legacy templates
- new product features as the primary driver
- an immediate replacement of Excel-based planning PDF generation

The goal is to simplify and harden the existing architecture, not to restart the product.

## Recommended Strategy

Use a staged structural simplification with one explicit rule:

`move one boundary at a time, keep user-visible behavior stable until the replacement path is fully testable`

That leads to four coordinated workstreams.

## Workstream 1: Parties And Contacts Simplification

### Recommended Direction

Create a dedicated `wms/parties/` boundary below the `V3.1` application layer.

Recommended modules:

- `wms/parties/selectors.py`
- `wms/parties/sync.py`
- `wms/parties/merge.py`
- `wms/parties/invariants.py`

And the application-facing adapters above it:

- `wms/application/parties/queries.py`
- `wms/application/parties/use_cases.py`

### What Moves There

- active / validated / eligible selectors currently duplicated between registry and rules
- portal recipient sync orchestration
- admin merge orchestration for recipient organizations and authorized contacts
- reusable invariant checks for the shipment-party graph

### Schema Direction

Recommended destination for the recipient scope model:

- replace the global uniqueness assumption on `ShipmentRecipientOrganization.organization`
- move toward a scoped uniqueness on `(organization, destination)`

This should be delivered in a compatibility phase:

1. centralize selectors and use cases first
2. add guard tests that describe the intended destination-scoped behavior
3. only then relax the uniqueness constraint and update callers that still assume a single row per organization

### Why This Is The Right Boundary

This keeps:

- view concerns in views
- application orchestration in `wms/application/parties`
- domain graph behavior in `wms/parties`

It also gives `V3.3` one explainable runtime map for:

- portal recipient sync
- shipment-party eligibility
- admin merge and defaulting flows

## Workstream 2: Planning And Document Artifact Runtime

### Recommended Direction

Create an explicit artifact lifecycle boundary, rather than letting `exports.py` remain the central mixed runtime.

Recommended modules:

- `wms/artifacts/planning.py`
- `wms/artifacts/attachments.py`
- `wms/artifacts/proofs.py`
- `wms/application/planning_artifacts/use_cases.py`

`wms/planning/exports.py` should progressively become an adapter around these services.

### Lifecycle To Make Explicit

For planning artifacts, the runtime should separate:

1. workbook generation
2. PDF conversion
3. artifact persistence and readiness recording
4. communication attachment resolution
5. downstream proof / sync behavior

### Scope Decision

`V3.3` should not merge all artifact models into one table immediately.

Instead, the target should be:

- one explicit orchestration boundary
- explicit statuses and readiness rules
- one replayable job entry point per artifact family
- one place that decides whether a communication is blocked by artifact readiness

That gives most of the structural value without opening an unnecessary model rewrite.

## Workstream 3: No-Build Legacy Frontend Modularization

### Recommended Direction

Keep the existing static entrypoint names stable, but thin them down.

Recommended strategy:

- keep `scan.css` and `scan-bootstrap.css` as stable public entrypoints
- split their implementation into imported partials by concern
- keep `scan.js` as a thin bootstrap
- move page or concern-specific behaviors into separate static modules loaded by `scan/base.html`

Recommended concern split:

- foundation / tokens / layout primitives
- auth and public pages
- cockpit and dashboard pages
- shipment and carton pages
- admin contacts and heavy form pages

### Why Not A Build Step

The repo currently operates well on the legacy Django static pipeline. `V3.3` should reduce coupling without adding a frontend build system that would be a separate migration on its own.

## Workstream 4: Quality Gate Expansion

### Recommended Direction

Expand type and contract safety around the exact layers introduced in `V3.1`, `V3.2`, and `V3.3`.

Priority additions:

- `wms/application/*`
- `wms/policies/*`
- `wms/events/*`
- `wms/jobs/*`
- `wms/parties/*`
- `wms/artifacts/*`
- the highest-risk adapters still using those layers

### Contract Tests To Add

- party graph invariants
- portal sync reuse and merge behavior
- destination-scoped recipient organization behavior
- planning artifact lifecycle and blocking rules
- attachment selection parity between UI actions and background jobs

## Recommended Delivery Order

1. `V3.3.1 Parties boundary and invariant tests`
2. `V3.3.2 Portal sync and admin merge extraction`
3. `V3.3.3 Recipient scope schema simplification`
4. `V3.3.4 Artifact lifecycle services`
5. `V3.3.5 Planning attachment and proof orchestration`
6. `V3.3.6 Legacy scan asset modularization`
7. `V3.3.7 Quality gate expansion`

## Risks

- changing recipient scope semantics too early, before selectors and use cases are centralized
- touching planning exports and communication blocking rules in the same step as PDF backend decisions
- splitting legacy assets by file without stabilizing the shared entrypoint contract first
- expanding static analysis too broadly in one shot and turning the wave into a typing-only cleanup

## Success Criteria

`V3.3` is structurally successful when:

- shipment-party behavior can be explained through one runtime map
- portal sync and admin merge no longer each own their own partial graph orchestration
- recipient scope is destination-aware without sync workarounds
- planning artifact lifecycle is explicit and replayable
- `scan.js` and shared scan CSS entrypoints become thin shells rather than monoliths
- type and contract gates cover the new structural layers instead of only a narrow pre-V3 slice
