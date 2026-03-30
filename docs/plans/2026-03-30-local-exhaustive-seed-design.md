# Local Exhaustive Seed Design

**Date:** 2026-03-30

## Goal

Create a local-only exhaustive dataset that makes the legacy Django application broadly operable for manual testing and targeted end-to-end verification across scan, portal, volunteer, planning, emailing, document scan, billing, admin, and public-order flows.

The seed must:
- stay fictional while using production-like formats and business shapes
- be disposable and safe for local development only
- expose action-ready records, not just historical rows
- reuse the repository's existing recipe/demo seed logic where it is already stable

## Context

The repository already contains several useful but partial data entry points:
- simple JSON fixtures in [`contacts/fixtures/sample_contacts.json`](/Users/EdouardGonnu/asf-wms/contacts/fixtures/sample_contacts.json), [`wms/fixtures/sample_chain.json`](/Users/EdouardGonnu/asf-wms/wms/fixtures/sample_chain.json), and [`wms/fixtures/sample_receipts.json`](/Users/EdouardGonnu/asf-wms/wms/fixtures/sample_receipts.json)
- a coherent planning demo command in [`wms/management/commands/seed_planning_demo_data.py`](/Users/EdouardGonnu/asf-wms/wms/management/commands/seed_planning_demo_data.py)
- a richer operator-oriented planning recipe seed in [`wms/management/commands/seed_planning_recipe_data.py`](/Users/EdouardGonnu/asf-wms/wms/management/commands/seed_planning_recipe_data.py)
- cross-domain UI API workflow tests in [`api/tests/tests_ui_e2e_workflows.py`](/Users/EdouardGonnu/asf-wms/api/tests/tests_ui_e2e_workflows.py)

Those pieces are useful references, but they do not currently create one local dataset that:
- lights up all dashboard cards
- leaves every major business surface with actionable records
- provides realistic user accounts per role
- covers billing, volunteer, portal, queue, and document flows together

## Constraints

### Repository constraints

- stay on the legacy Django stack only
- do not reopen translation scope
- do not depend on GitHub network access
- preserve production-like data contracts and status transitions

### Product constraints

- local database only
- fictional data only
- production-like identifiers, chronology, and document shapes
- deterministic enough for tests and repeated reseeds

### Engineering constraints

- idempotent reseed behavior
- optional clean reset for operational rows
- narrow write scope on each rerun through scenario namespacing
- readable implementation that can evolve with the product

## Approaches Considered

### 1. One large JSON fixture dump

Idea:
- generate one exhaustive `loaddata` artifact covering every model

Pros:
- simple load entry point
- easy to inspect as raw rows

Cons:
- fragile foreign-key maintenance
- poor ergonomics for file fields and generated relations
- hard to keep aligned with evolving business rules
- awkward to namespace and reseed incrementally

### 2. One orchestration command over Python seed builders, recommended

Idea:
- add one local command that resets optional operational rows, then seeds each domain through explicit Python builders

Pros:
- idempotent and namespaced
- easy to express realistic business relations
- easier reuse of existing planning/demo seed logic
- easier test coverage for counts, shapes, and side effects

Cons:
- more upfront implementation structure
- requires careful discipline to avoid one giant unreadable module

### 3. Hybrid: stable fixtures plus Python orchestration

Idea:
- keep stable references in JSON fixtures and use Python only for business flows

Pros:
- some reuse of existing fixture files
- simpler bootstrap for low-level reference rows

Cons:
- split maintenance model
- harder mental model for operators
- still needs Python orchestration for the hardest parts

## Recommended Decision

Take approach 2.

Add a dedicated management command:
- [`wms/management/commands/seed_local_exhaustive_data.py`](/Users/EdouardGonnu/asf-wms/wms/management/commands/seed_local_exhaustive_data.py)

Back it with a testable orchestration module:
- [`wms/local_exhaustive_seed.py`](/Users/EdouardGonnu/asf-wms/wms/local_exhaustive_seed.py)

This keeps the entry point obvious while allowing the business dataset logic to stay isolated from command parsing and console output.

## Command Contract

### Primary command

`python manage.py seed_local_exhaustive_data`

### Expected options

- `--scenario=local-exhaustive`
- `--fresh`
- `--with-planning-solve`
- `--with-demo-documents`
- `--with-queue-backlog`
- `--with-e2e-baseline`

### Behavioral rules

- default mode is idempotent reseed for the selected namespace
- `--fresh` runs the operational reset before reseeding
- command output prints a compact local operator guide:
  - users and passwords
  - key URLs
  - named records to use for each business flow
  - summary counts by domain

## Namespace Strategy

Every seeded row that can safely be namespaced should carry one shared scenario prefix, for example:
- `LOCAL-EXHAUSTIVE`
- `local-exhaustive@example.test`
- `[LOCAL local-exhaustive]`

This allows:
- coexistence with other local data
- deterministic lookups during reseed
- easy cleanup and inspection

Where the business contract already has a canonical format, the namespace should be embedded without breaking the format, for example:
- shipment references
- draft shipment `EXP-TEMP-XX`
- invoice and quote numbers
- integration payload labels
- planning dataset names

## Dataset Architecture

The seed should be built as scenario groups rather than as one flat list of rows.

### `core-reference`

Covers stable shared references:
- warehouses and locations
- product categories and products
- unit equivalence rules
- communication templates
- notification groups and runtime-friendly defaults

### `ops-happy-path`

Covers a nominal operational chain:
- stock available in several lots
- cartons across active preparation states
- one shipment that can be tracked through the full chain
- ready labels and attached documents
- one closable delivered case

### `ops-alerts-and-blockers`

Covers dashboard alertability:
- stale planned shipment
- stale shipped shipment
- stale received-correspondent shipment
- delivered but not closed case
- open dispute
- low-stock products
- validated order without downstream shipment
- pending, processing, failed, and stale queue rows

### `portal-association-a`

Covers the complete association case:
- portal user and profile
- admin, shipping, and billing portal contacts
- active recipients synchronized into shipment-party records
- portal orders in different statuses
- account and order documents with scan statuses
- billing profile with usable history

### `portal-association-b`

Covers controlled business variation:
- recipients partially inactive
- pending billing change request
- document under review
- secondary order and contact permutations for filters and dashboards

### `volunteer-planning`

Covers volunteer and planning flows:
- multiple volunteer accounts
- varied availability and constraint patterns
- planning run ready and solved
- communication drafts and templates for email and WhatsApp
- artifacts visible from the planning cockpit

### `billing-periods`

Covers invoice and quote workflows:
- per-shipment and grouped billing profiles
- quote draft, issued invoice, partially paid invoice, and correction chain
- multiple periods and currencies
- price overrides and computation profile defaults

### `public-intake`

Covers public-order and document-intake paths:
- public account request
- public order
- document upload rows with clean, pending, and review-needed states
- queue rows ready for processor commands

## Domain Coverage Matrix

### Dashboard

The seed must light up all dashboard card families in [`wms/views_scan_dashboard.py`](/Users/EdouardGonnu/asf-wms/wms/views_scan_dashboard.py):
- stock cards
- shipment cards
- tracking cards
- workflow blockage cards
- technical queue cards
- SLA and destination steering blocks

### Stock and catalog

Required shapes:
- active and archived products
- multi-level categories
- lots in `available`, `hold`, `quarantined`, and `expired`
- low stock and healthy stock examples
- realistic locations across at least two warehouses

### Cartons and kits

Required shapes:
- cartons in `draft`, `picking`, `packed`, `assigned`, `labeled`, `shipped`
- carton items across several product families
- at least one kit product path
- enough seeded rows to exercise list, detail, and shipment assignment flows

### Shipments and tracking

Required shapes:
- one `EXP-TEMP-XX` draft
- final shipments in each core status
- one disputed shipment
- one closable delivered shipment
- one already closed shipment
- realistic tracking events with staggered timestamps

### Portal and shipment-party graph

Required shapes:
- two association portal accounts with different business profiles
- organization and person contacts
- shipper, recipient, and correspondent relationships
- active and inactive authorization edges
- synchronized recipients that appear in shipment create filters

### Volunteer and planning

Required shapes:
- volunteer login-ready accounts
- one first-login or password-reset case
- availabilities, unavailabilities, constraints
- one run ready for validation review
- one run solved with assignments and communication drafts

### Billing

Required shapes:
- `AssociationBillingProfile`
- `AssociationBillingChangeRequest`
- `BillingDocument` rows covering quote and invoice workflows
- `BillingDocumentShipment`, `BillingDocumentReceipt`, `BillingDocumentLine`
- payment and correction history that is visible from both scan and portal

### Queue and document scan

Required shapes:
- `IntegrationEvent` email rows in `pending`, `processing`, `processed`, and `failed`
- document scan rows that let operators exercise both queue processors and dashboard health
- uploaded files attached to shipment, portal-account, and order document models

## Production-Like Format Rules

The dataset should look operationally believable without using real data:
- realistic email addresses under `.test` or `.example.com`
- E.164-like phone numbers
- shipment references and invoice numbers that follow current app conventions
- timestamps spread across several days and weeks to trigger boards and dashboard alerts
- PDFs or text files with valid filenames and content types for upload flows

## Reuse Strategy

Reuse existing builders where they already encode business rules:
- planning seed logic from [`wms/planning/recipe_dataset.py`](/Users/EdouardGonnu/asf-wms/wms/planning/recipe_dataset.py) or [`wms/management/commands/seed_planning_recipe_data.py`](/Users/EdouardGonnu/asf-wms/wms/management/commands/seed_planning_recipe_data.py)
- reset logic from [`wms/reset_operational_data.py`](/Users/EdouardGonnu/asf-wms/wms/reset_operational_data.py)

Do not reuse the old JSON fixtures as the runtime substrate for the new seed. They remain references and optional local examples, not the new canonical recipe.

## Validation Strategy

### Management-command coverage

Add a dedicated test module:
- [`wms/tests/management/tests_management_seed_local_exhaustive_data.py`](/Users/EdouardGonnu/asf-wms/wms/tests/management/tests_management_seed_local_exhaustive_data.py)

It should verify:
- command creates the minimum expected rows per domain
- command is idempotent for a given namespace
- `--fresh` works with the operational reset
- solved planning mode produces a solved run when requested
- queue and document states are present when the relevant flags are enabled

### Integration and E2E alignment

The seed should support, not replace, the existing cross-domain smoke references:
- [`api/tests/tests_ui_e2e_workflows.py`](/Users/EdouardGonnu/asf-wms/api/tests/tests_ui_e2e_workflows.py)
- [`wms/tests/emailing/tests_notifications_queue.py`](/Users/EdouardGonnu/asf-wms/wms/tests/emailing/tests_notifications_queue.py)
- [`wms/tests/emailing/tests_order_status_notifications.py`](/Users/EdouardGonnu/asf-wms/wms/tests/emailing/tests_order_status_notifications.py)
- [`wms/tests/planning/tests_smoke_planning_flow.py`](/Users/EdouardGonnu/asf-wms/wms/tests/planning/tests_smoke_planning_flow.py)

If new end-to-end coverage is added, keep it targeted:
- dashboard with all cards visible
- portal account and recipient/order/document path
- volunteer login and availability path
- nominal billing editor flow on seeded data

## Documentation Impact

No repository-reference update is required by default because the change introduces a new local seed workflow rather than altering a critical runtime route or contract.

The user-facing docs that should be updated in the same work are:
- [`README.md`](/Users/EdouardGonnu/asf-wms/README.md)

If the final command becomes part of standard local QA loops, then [`docs/operations.md`](/Users/EdouardGonnu/asf-wms/docs/operations.md) may also need a short local-only note.

## Final Recommendation

Implement one namespaced, idempotent, local-only orchestration command that seeds:
- realistic users
- operational graph data
- action-ready shipments and orders
- queue and document backlog samples
- billing lifecycle samples
- solved planning samples

Treat the dataset as the local recipe substrate for manual testing and selective E2E, not as a fixture dump and not as a replacement for domain-specific tests.
