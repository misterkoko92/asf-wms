# Repository Reference

This directory is the canonical maintenance entry point for the repo.

Use it to re-enter the codebase quickly before a change, and again before closing the work to check propagation, shared contracts, and docs drift.

## Read This At The Start Of A Ticket

1. `docs/repo-reference/01-architecture-and-entrypoints.md`
2. `docs/repo-reference/02-key-flows-and-living-tests.md`
3. `docs/repo-reference/03-impact-map.md`
4. `docs/repo-reference/04-shared-contracts.md`

If the change is very local, read `01` then jump directly to the relevant sections in `02` and `03`.

## What This Reference Covers

- global repository entry points
- runtime architecture and file clusters
- critical end-to-end and partial flows
- cross-cutting impact propagation
- shared contracts reused across multiple screens or surfaces
- the reference tests and docs that should move with the code

## What This Reference Is Not

This is a synthesis layer.

It does not replace:

- runtime code
- living tests
- operational runbooks
- functional specs
- historical implementation plans

When this reference and runtime code disagree, runtime code wins. Then update this reference.

## Source Hierarchy

Read sources in this order:

1. runtime entry points: `asf_wms/urls.py`, `wms/scan_urls.py`, `wms/portal_urls.py`, `wms/volunteer_urls.py`, `wms/planning_urls.py`, `api/v1/urls.py`
2. runtime orchestration: `wms/views.py`, `wms/views_*`, `*_handlers.py`, `wms/services.py`, `wms/signals.py`
3. data and contracts: `wms/models.py`, `wms/models_domain/*`, shared template tags, templates, static assets
4. living tests: `api/tests/`, `wms/tests/`, `contacts/tests/`
5. docs: `docs/mvp_spec.md`, `docs/audit_2026-02-19.md`, `docs/operations.md`, `docs/release_checklist.md`, targeted matrices

## Current Working Constraints

- Legacy Django is the active delivery surface.
- Next/React migration files remain paused by default and are intentionally out of this reference unless a ticket explicitly re-opens them.
- Translation parity work is also paused by default and is not part of the routine maintenance flow covered here.

## Fast Maintenance Loop

At the start of a change:

1. identify the main surface: `scan`, `portal`, `benevole`, `planning`, `api`, `admin`, `print`, `emailing`
2. open the URL module and the matching view/handler cluster
3. check `03-impact-map.md` for propagation candidates
4. check `04-shared-contracts.md` if the change touches cross-screen behavior
5. run or inspect the closest living reference tests from `02-key-flows-and-living-tests.md`

Before closing the change:

1. re-read the relevant impact-map section
2. update docs if a rule, route, contract, or smoke changed
3. verify that the reference tests still describe the real contract
4. if an important follow-up was explicitly deferred, record it in `docs/deferred-follow-ups.md`

## Update This Reference When

- a route, endpoint, or entry point changes
- a business workflow order changes
- a shared UI primitive or contract changes
- a portal/contact synchronization rule changes
- a release smoke or operations rule changes
- a referenced test file is renamed, split, or removed

## Files In This Directory

- `01-architecture-and-entrypoints.md`: where the app starts and how the layers fit together
- `02-key-flows-and-living-tests.md`: the critical business flows and the tests that currently embody them
- `03-impact-map.md`: change propagation checklist for recurring maintenance work
- `04-shared-contracts.md`: shared UI and cross-surface contracts that are easy to forget
