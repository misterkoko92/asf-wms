# Repository Reference Design

Date: 2026-03-28

## Goal

Create a maintenance-oriented repository reference that can be read at the start and end of routine implementation work to reduce re-scanning, make cross-cutting impacts explicit, and keep the main flows visible.

## Problem

The repository already contains strong documentation, but it is fragmented:

- high-level repo entry points in `README.md` and `docs/README.md`
- business scope in `docs/mvp_spec.md`
- transversal flow and risk analysis in `docs/audit_2026-02-19.md`
- domain-specific matrices such as `docs/email_flows_target_matrix_2026-02-20.md`
- operational smoke and release checks in `docs/operations.md` and `docs/release_checklist.md`
- cross-screen UI governance in `docs/plans/2026-03-22-ui-library-governance-design.md` and `docs/plans/2026-03-25-core-stable-usage-rules.md`
- living end-to-end knowledge embedded in tests

That makes the repo rich, but not easy to re-enter quickly during maintenance.

## Decision

Do not create one monolithic document.

Create one canonical entry point plus a small set of focused reference files:

1. `docs/repo-reference/README.md`
2. `docs/repo-reference/01-architecture-and-entrypoints.md`
3. `docs/repo-reference/02-key-flows-and-living-tests.md`
4. `docs/repo-reference/03-impact-map.md`
5. `docs/repo-reference/04-shared-contracts.md`

## Why This Structure

- The index gives a stable "start here" file.
- Architecture and entry points change less often than impact rules.
- Flows and living tests should stay close to real runtime entry points.
- The impact map is optimized for day-to-day change propagation questions.
- Shared contracts need their own document because they cut across `scan`, `portal`, `admin`, `benevole`, print, and API surfaces.

## Source Hierarchy

The new reference must remain a synthesis, not a replacement for source truth.

Priority order:

1. Runtime code (`urls`, `views`, `handlers`, `services`, `models_domain`, templates, static files)
2. Living tests
3. Operational docs (`docs/operations.md`, `docs/release_checklist.md`)
4. Functional docs and audits (`docs/mvp_spec.md`, `docs/audit_2026-02-19.md`, targeted matrices)
5. Historical plans

## Update Policy

Update the repository reference when one of these changes:

- a critical user flow
- a route or API entry point
- a cross-screen shared UI contract
- a shipment-party / portal-contact synchronization rule
- a release smoke or operational verification rule
- a named reference test that the docs rely on

## Expected Outcome

Future tickets should be able to answer these questions faster:

- where is the real entry point?
- which screens or APIs probably need the same change?
- which docs and smoke checks must move with the code?
- which tests are the fastest proof that the contract still holds?
