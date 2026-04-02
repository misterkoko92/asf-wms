# ASF WMS V3.3 Readiness Plan

## Decision

Do not write a fully detailed implementation plan for V3.3 yet.

At this stage, a readiness plan is the better tool.

## Why A Full V3.3 Plan Is Premature

V3.3 depends on runtime choices that V3.2 has not locked yet:

- which signal responsibilities remain local and which become event-driven
- what the final `wms/jobs/` boundary looks like
- how much of durable dispatch can safely stay on `IntegrationEvent`
- which sync side effects become easier to reason about after V3.2 extraction

A detailed V3.3 task-by-task plan written now would likely age badly and be rewritten after the first half of V3.2.

## What V3.3 Still Needs To Achieve

V3.3 remains the wave that should simplify the most expensive shared domains and legacy runtime costs.

Target areas:

1. parties and contacts simplification
2. document and export runtime cleanup
3. legacy frontend modularization
4. quality gate expansion

## Entry Criteria Before Writing The Detailed V3.3 Implementation Plan

Do not freeze the detailed V3.3 plan until all of the following are true:

- `wms/signals.py` is mostly registration and event bridging
- operational commands delegate to `wms/jobs/` rather than directly to runtime helpers
- job-run visibility exists and is stable enough to expose real runtime ownership
- `IntegrationEvent` outbox helpers are explicit enough to describe the asynchronous boundary in one place
- `docs/repo-reference/01-architecture-and-entrypoints.md` and `04-shared-contracts.md` describe the new V3.2 runtime map accurately

## Candidate Work Packages

### V3.3.1 Parties And Contacts Simplification

Likely scope:

- `wms/models_domain/portal.py`
- `wms/models_domain/shipment_parties.py`
- `wms/portal_recipient_sync.py`
- `wms/default_shipper_bindings.py`
- `contacts/correspondent_recipient_promotion.py`
- the forms and views that currently rely on implicit sync or fallback rules

Questions V3.2 must answer first:

- which syncs stay synchronous
- which syncs should emit follow-up work through handlers or durable dispatch
- what the authoritative runtime map for recipient and shipper side effects becomes

### V3.3.2 Document And Export Runtime

Likely scope:

- `wms/planning/exports.py`
- `wms/print_pack_sync.py`
- planning communication payload selection
- artifact health checks and proof-of-diffusion logic

Questions V3.2 must answer first:

- which export and sync paths become jobs
- how job-run visibility should be reused for artifacts
- whether the durable outbox helper is sufficient for artifact sync semantics

### V3.3.3 Legacy Frontend Modularization

Likely scope:

- `wms/static/scan/scan.js`
- `wms/static/scan/scan.css`
- `wms/static/scan/scan-bootstrap.css`
- the largest scan staff templates

Questions V3.2 must answer first:

- which UI interactions still depend on implicit orchestration side effects
- whether the V3.2 application and event boundaries are stable enough to support smaller surface-specific JS modules

### V3.3.4 Quality Gate Expansion

Likely scope:

- mypy and pyright coverage expansion
- contract tests on events, jobs, and domain sync boundaries
- stronger runtime smoke slices

Questions V3.2 must answer first:

- which event and job APIs become stable public internal contracts
- which hotspots deserve type-check inclusion first

## Prework That Is Safe Before V3.2 Ends

These activities are safe to do during or near the end of V3.2 without freezing a full V3.3 plan:

- keep an inventory of remaining signal responsibilities after each V3.2 slice
- note repeated complexity in parties/contact synchronization while refactoring handlers
- record friction points in `print_pack_sync.py` and planning export runtime while building jobs
- track which legacy frontend pages still rely on monolithic scan JS behavior
- identify which new V3.2 modules deserve to enter the static-check perimeter first

## Recommended Trigger To Detail V3.3

Write the full V3.3 implementation plan when V3.2 has completed at least:

1. signal bridge extraction
2. jobs layer introduction
3. job-run visibility

At that point, the right order and blast radius of V3.3 will be grounded in the actual runtime architecture, not in assumptions.

## Recommended First Detailed V3.3 Slice

When V3.3 becomes ready for detailed planning, start with:

`V3.3.1 Parties And Contacts Simplification`

It is the most structurally expensive shared domain left in the repo, and it will benefit the most from the runtime clarity created by V3.2.
