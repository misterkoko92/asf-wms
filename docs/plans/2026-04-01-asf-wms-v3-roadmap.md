# ASF WMS V3 Roadmap

## Scope

This roadmap complements the global V3 design.

It now keeps:

- a completed detailed implementation plan for `V3.1`
- a detailed implementation plan for `V3.2`
- a detailed design and implementation plan for `V3.3`

That balance remains intentional. `V3.2` is now specific enough to execute because `V3.1` is complete. `V3.3` is now detailed enough to execute because the runtime boundaries introduced by `V3.2` are explicit.

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

Design:

- `docs/plans/2026-04-01-asf-wms-v3-wave2-design.md`

Detailed implementation plan:

- `docs/plans/2026-04-01-asf-wms-v3-wave2-implementation-plan.md`

### V3.3 Domain and Runtime Simplification

Goal:

- simplify cross-surface domain complexity and reduce legacy runtime cost

Detailed design:

- `docs/plans/2026-04-02-asf-wms-v3-wave3-design.md`

Detailed implementation plan:

- `docs/plans/2026-04-02-asf-wms-v3-wave3-implementation-plan.md`

## Detailed Execution Plan: V3.2

The detailed slice sequencing now lives in:

- `docs/plans/2026-04-01-asf-wms-v3-wave2-implementation-plan.md`

The wave is executed in this order:

1. event scaffolding and runtime map
2. explicit event contracts
3. notification handlers
4. projection and sync handlers
5. job layer
6. job-run visibility
7. durable outbox normalization

## Detailed Execution Plan: V3.3

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
2. Execute `V3.2` in full
3. Start `V3.3.1` on the stabilized structural stack
4. Continue with artifacts, frontend modularization, and quality gates

## Decision Rule

If a future structural change can be handled inside `V3.1` through shared queries and policies, do not pull it forward into `V3.2` or `V3.3`.

Use `V3.2` only for orchestration and runtime boundaries.
Use `V3.3` only for domain or legacy simplification that becomes safe after those boundaries exist.
