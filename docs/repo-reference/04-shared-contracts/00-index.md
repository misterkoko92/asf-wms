# 04 Shared Contracts — Index

Purpose:

This directory contains the modular reference for repository-wide shared contracts.
These files describe cross-surface behaviors, invariants, compatibility facades, and maintenance rules that affect multiple domains.

Use this directory when a change may impact more than one area of ASF-WMS.

---

## Reading Order

Start here depending on the task:

| If the task touches… | Read |
|---|---|
| imports, facades, structural boundaries | `01-core-facades.md` |
| UI primitives, shells, shared assets, frontend security | `02-ui-shell-contracts.md` |
| scan operations, lists, preparateur flows, receipts, pack flows | `03-scan-operations.md` |
| portal users, recipients, shipment-party graph, preferences | `04-portal-parties.md` |
| shipment lifecycle, QR tracking, disputes, projections | `05-shipments-tracking.md` |
| planning, preparation runs, exports, warehouse logic | `06-planning-preparation.md` |
| policies, events, jobs, pilotage, ops checks | `07-runtime-events-jobs-ops.md` |

---

## File Rules

- Keep files scoped by domain family.
- Prefer adding to an existing family before creating a new file.
- If a new top-level family is required, create `08-*.md`, `09-*.md`, etc.
- Keep filenames stable once referenced by prompts or automation.

---

## Section Format

Use this structure for each contract:

    ## Contract Name

    Primary runtime sources:

    - path/a.py
    - path/b.html

    Current contract:

    - invariant
    - behavior
    - allowed vocabulary

    Maintenance rule:

    - what must be updated together

    Reference tests:

    - tests/example.py

---

## Writing Rules

- Describe real enforced behavior, not aspirations.
- Keep wording operational and precise.
- Prefer bullets over prose.
- Keep historical context only when it prevents regressions.
- When behavior changes, update this reference in the same PR.

---

## Scope Boundary

These files are cross-domain contracts.

Do not move page-local implementation details here unless they affect multiple surfaces or multiple teams.

Examples that belong here:

- shared permission rules
- shared model semantics
- portal ↔ scan coupling
- shared UI primitives
- runtime event contracts
- ops smoke procedures

Examples that do not belong here:

- one template spacing fix
- one isolated queryset refactor
- one local label rename

---

## Maintenance Trigger

Update this directory when a change affects:

- multiple apps or surfaces
- user journeys crossing boundaries
- shared selectors or permissions
- queues, jobs, events, notifications
- deployment or smoke checks
- structural import boundaries

---

## Relationship With Other Docs

- `03-impact-map.md` = where changes propagate
- `04-shared-contracts/*` = what must stay true
- `docs/agent/playbooks.md` = how to choose task-specific verification
- `docs/release_checklist.md` and `docs/operations.md` = how to ship safely
- `docs/security-dependencies.md` = dependency security release policy

---

## Agent Rule

If uncertain whether a change is local or shared:

Assume shared until proven local.
