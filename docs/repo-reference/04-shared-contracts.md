# Shared Contracts

This file is the entry point for shared contracts reused across multiple ASF-WMS surfaces.

Use it when a change may affect:

- shared imports or facades
- shared UI primitives, shells, CSS, JS, or service worker behavior
- scan navigation, lists, receipts, pack, or preparateur flows
- portal access, recipient sync, shipment-party graph, or portal orders
- shipment readiness, QR tracking, disputes, or workflow projections
- planning exports, artifacts, or warehouse preparation
- events, outbox, jobs, pilotage, operations, release smoke, or security policies

Detailed contracts live under:

`docs/repo-reference/04-shared-contracts/`

---

## How To Use This File

Before changing a shared behavior:

1. Identify the primary contract family below.
2. Open the matching detailed contract file.
3. Check runtime sources.
4. Preserve the current contract unless the task explicitly changes it.
5. Run or inspect reference tests.
6. Update the contract file if the shared behavior changed.

Runtime code and passing tests remain the source of truth.

---

## Contract Index

| Contract family | Read |
|---|---|
| View/model facades and structural package facades | `04-shared-contracts/01-core-facades.md` |
| Shared UI, shells, inputs, assets, frontend security | `04-shared-contracts/02-ui-shell-contracts.md` |
| Scan lists, sidebar, preparateur, receipts, pack, deletion | `04-shared-contracts/03-scan-operations.md` |
| Portal access, shipment-party graph, recipients, preferences, portal orders | `04-shared-contracts/04-portal-parties.md` |
| Shipment readiness, QR tracking, disputes, workflow projections | `04-shared-contracts/05-shipments-tracking.md` |
| Planning cockpit, artifacts, warehouse preparation | `04-shared-contracts/06-planning-preparation.md` |
| Policies, events, outbox, jobs, pilotage, operations, smoke | `04-shared-contracts/07-runtime-events-jobs-ops.md` |
| Directory index and conventions | `04-shared-contracts/00-index.md` |

---

## Cross-Contract Reads

| If touching... | Also read |
|---|---|
| Shared scan assets | `02-ui-shell-contracts.md` + `03-scan-operations.md` |
| Portal recipients or access grants | `04-portal-parties.md` + `05-shipments-tracking.md` if shipment selectors change |
| Shipment status or readiness | `05-shipments-tracking.md` + `06-planning-preparation.md` + `07-runtime-events-jobs-ops.md` |
| Planning exports or PDFs | `06-planning-preparation.md` + `07-runtime-events-jobs-ops.md` |
| Notification or queue behavior | `07-runtime-events-jobs-ops.md` + impacted business contract |
| UI API mirror of an HTML cockpit | `02-ui-shell-contracts.md` + impacted surface contract |

---

## Maintenance Rule

When a shared contract changes:

- update the detailed contract file
- update `02-key-flows-and-living-tests.md` if the workflow changed
- update relevant `03x-impact-*.md` file if propagation changed
- update reference tests or smoke docs when applicable

---

## Final Rule

A shared contract is not local.

If you change it in one place, verify every surface that depends on it.
