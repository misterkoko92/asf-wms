# ASF WMS V3 Roadmap

## Scope

This roadmap complements the global V3 design.

It now keeps:

- a completed detailed implementation plan for `V3.1`
- a detailed implementation plan for `V3.2`
- a readiness plan, not yet a full implementation plan, for `V3.3`

That balance remains intentional. `V3.2` is now specific enough to execute because `V3.1` is complete. `V3.3` still depends on structural decisions that V3.2 must lock first.

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

Readiness plan:

- `docs/plans/2026-04-01-asf-wms-v3-wave3-readiness-plan.md`

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

## Readiness Plan: V3.3

The current V3.3 guidance lives in:

- `docs/plans/2026-04-01-asf-wms-v3-wave3-readiness-plan.md`

This is intentionally not a full implementation plan yet.

## Recommended Order

1. Deliver `V3.1`
2. Execute `V3.2` in full
3. Re-check the runtime map after `V3.2` job and outbox stabilization
4. Only then freeze the detailed implementation plan for `V3.3.1`
5. Finish the rest of `V3.3`

## Decision Rule

If a future structural change can be handled inside `V3.1` through shared queries and policies, do not pull it forward into `V3.2` or `V3.3`.

Use `V3.2` only for orchestration and runtime boundaries.
Use `V3.3` only for domain or legacy simplification that becomes safe after those boundaries exist.
