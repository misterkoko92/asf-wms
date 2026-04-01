# ASF WMS V3 Roadmap

## Scope

This roadmap complements the global V3 design.

It keeps:

- a detailed implementation plan only for `V3.1`
- lighter execution guidance for `V3.2` and `V3.3`

That balance is intentional. The later waves depend on structural choices made in `V3.1`, so they should not be overspecified too early.

## Wave Summary

### V3.1 Application and Policies

Goal:

- remove duplicated business composition across HTML and UI API
- centralize operational rules into explicit policy modules

Detailed implementation plan:

- `docs/plans/2026-04-01-asf-wms-v3-wave1-implementation-plan.md`

### V3.2 Events and Jobs

Goal:

- replace implicit orchestration with explicit event and job boundaries

### V3.3 Domain and Runtime Simplification

Goal:

- simplify cross-surface domain complexity and reduce legacy runtime cost

## Lightweight Execution Plan: V3.2

### V3.2.1 Event Catalog

Deliverables:

- a catalog of domain events emitted by shipment, order, portal recipient, planning artifact, and pilotage flows
- a first event taxonomy doc and runtime map

Prerequisites:

- `V3.1` query and policy extraction must already clarify where decisions happen

Exit criteria:

- event producers and consumers are identified
- `wms/signals.py` responsibilities are grouped by concern

### V3.2.2 Signal Bridge

Deliverables:

- Django signals reduced to bridging logic
- side-effect code moved into event handlers

Prerequisites:

- `V3.2.1`

Exit criteria:

- signal modules no longer contain heavy branching and orchestration logic

### V3.2.3 Job Layer

Deliverables:

- `wms/jobs/` modules for queue processors, projections, snapshots, escalations, and artifact checks
- management commands wrapped around job modules

Prerequisites:

- `V3.1` application extraction for the most critical reads

Exit criteria:

- job execution can be tested without shelling through management commands

### V3.2.4 Outbox and Run Visibility

Deliverables:

- durable outbox or equivalent local dispatch boundary
- job run and result visibility for retries, failures, and timeouts

Prerequisites:

- `V3.2.2` and `V3.2.3`

Exit criteria:

- notification and projection side effects are traceable and replayable

## Lightweight Execution Plan: V3.3

### V3.3.1 Parties and Contacts Simplification

Deliverables:

- clearer orchestration between portal recipients, shipment recipients, shipment shippers, and authorized contacts
- fewer implicit sync paths

Prerequisites:

- `V3.1` application layer around portal and scan forms
- `V3.2` event boundaries for sync side effects

Exit criteria:

- shipment-party behavior is easier to explain through one runtime map

### V3.3.2 Document and Export Runtime

Deliverables:

- cleaner separation between workbook generation, PDF readiness, proof of diffusion, and email attachment selection

Prerequisites:

- `V3.2` job layer

Exit criteria:

- artifact handling is observable, replayable, and less tightly coupled to UI actions

### V3.3.3 Legacy Frontend Modularization

Deliverables:

- `scan.js` and large CSS split by surface or concern
- less shared accidental coupling across scan pages

Prerequisites:

- stable application/query contracts so UI changes do not need to reshape business logic

Exit criteria:

- page-level UI changes no longer require touching one monolithic JS or CSS file

### V3.3.4 Quality Gate Expansion

Deliverables:

- broader static-check coverage
- stronger contract tests for application, policy, and event boundaries

Prerequisites:

- `V3.1` and early `V3.2` modules in place

Exit criteria:

- the highest-risk modules are inside the type and contract safety perimeter

## Recommended Order

1. Deliver `V3.1`
2. Start `V3.2.1`, `V3.2.2`, and `V3.2.3`
3. Only then detail the exact implementation plan for `V3.2.4`
4. Open `V3.3.1` once `V3.2` clarifies orchestration ownership
5. Finish with `V3.3.2`, `V3.3.3`, and `V3.3.4`

## Decision Rule

If a future structural change can be handled inside `V3.1` through shared queries and policies, do not pull it forward into `V3.2` or `V3.3`.

Use `V3.2` only for orchestration/runtime boundaries.
Use `V3.3` only for domain or legacy simplification that becomes safe after those boundaries exist.
