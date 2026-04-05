# Recipient Product Preferences Design

**Date:** 2026-04-04

## Goal

Add a destination-scoped recipient preference system that lets associations and scan/admin teams manage product-level acceptance rules, quantity targets, and refusal conflicts, then use those rules to:
- warn during shipment creation when a parcel contains refused products
- keep an audit trail of one-off operational overrides
- surface basic compatibility and demand-coverage guidance for parcel selection

## Working Constraints

- Stay on the legacy Django stack only.
- Translation scope remains paused.
- Next/React migration scope remains paused.
- V1 preferences apply to exact catalog products only.
- V1 keeps human validation in the loop; no silent auto-composition of parcels.
- Portal and scan/admin must edit the same canonical data.

## Problem Summary

The repo already has:
- a portal recipient surface in `wms/views_portal_account.py` and `templates/portal/recipients.html`
- recipient synchronization from `AssociationRecipient` into shipment-party runtime structures through `wms/application/parties/use_cases.py`
- a destination-scoped operational recipient model in `wms/models_domain/shipment_parties.py`
- a shipment-create popup pattern already used for destination preassignment conflicts in `templates/scan/includes/shipment_create_preassignment_overlay.html` and `wms/static/scan/scan.js`

What is missing is a shared business contract for recipient product preferences:
- no canonical place to store product-level demand / allowance / refusal
- no operational audit trail for "continue anyway" decisions
- no recipient-centric cockpit to avoid overloading the current inline portal form
- no basic scoring layer to help choose a more suitable ready parcel

## Decisions Validated

- Both associations and scan/admin can edit canonical recipient preferences.
- Preferences are destination-scoped.
- Product statuses in V1:
  - `requested`
  - `allowed`
  - `refused`
- `unspecified` remains implicit: absence of a stored preference row.
- `requested` and `allowed` carry quantity target + period (`week` or `month`).
- `refused` carries no target quantity.
- Shipment creation/edit must support one-off overrides without changing the canonical preference.
- V1 works on exact products only; category and substitution logic are deferred to V2.
- Recipient list pages should stay light; add an `Ouvrir` action and a dedicated recipient detail page.

## Approaches Considered

### 1. Keep everything inline on the existing portal recipients page

Idea:
- extend the existing list/create/edit page with preference rows and alerts

Pros:
- smallest route change
- no new page model

Cons:
- overloads an already dense form
- weak place for future need coverage and override history
- scan/admin would still need a separate dense editing surface

### 2. Add a dedicated recipient detail cockpit, recommended

Idea:
- keep the current list page as entrypoint
- add `Ouvrir` on each recipient
- move preference-heavy workflows into a recipient detail page available from portal and scan/admin

Pros:
- clearer information hierarchy
- supports V1 without cluttering the list page
- leaves room for coverage metrics, override history, and V2 recommendation logic
- keeps one canonical data model with two entry surfaces

Cons:
- requires new routes and templates
- slightly larger initial implementation footprint

### 3. Build a global preference management screen detached from recipients

Idea:
- create one "manage all preferences" page for all recipients

Pros:
- central oversight for admin

Cons:
- weak contextual link with recipient identity, destination, and shipment workflow
- harder for associations to understand and maintain
- duplicates navigation concerns already solved by a recipient detail page

## Recommended Decision

Take approach 2.

Build a recipient detail cockpit centered on the operational destination-scoped recipient runtime, while keeping the current recipients list as the lightweight entrypoint. Store only explicit preferences (`requested`, `allowed`, `refused`) and treat missing rows as implicit `unspecified`.

## Canonical Data Model

### Canonical anchor

Canonical preferences should attach to `ShipmentRecipientOrganization`, not to `AssociationRecipient` and not directly to `Contact`.

Why:
- shipment-party runtime is already destination-scoped, which matches the business rule
- scan/admin already operates on that layer
- portal recipient sync already resolves into that layer
- this avoids trying to reconcile global organization-level preferences with per-destination operations

### New model: `RecipientProductPreference`

Proposed fields:
- `recipient_organization` -> `ShipmentRecipientOrganization`
- `product` -> `Product`
- `status` -> `requested | allowed | refused`
- `quantity_target` -> positive integer, nullable
- `period_unit` -> `week | month`, nullable
- `notes` -> text, blank
- `source` -> `portal | scan_admin`
- `created_by` -> user nullable
- `updated_by` -> user nullable
- `created_at`
- `updated_at`

Constraints:
- unique on `(recipient_organization, product)`
- `quantity_target` and `period_unit` required for `requested` and `allowed`
- `quantity_target` and `period_unit` forbidden for `refused`

### Implicit status: `unspecified`

`unspecified` is not stored as a row.

Rules:
- if no preference row exists for `(recipient_organization, product)`, the effective status is `unspecified`
- `unspecified` is treated operationally like `allowed` in V1 for blocking behavior
- `unspecified` remains semantically distinct so future scoring and reporting can tell "explicitly allowed" from "not stated"

### New model: `ShipmentPreferenceOverride`

Purpose:
- journal one-off decisions such as "continue despite refused product"

Proposed fields:
- `shipment` -> `Shipment`
- `carton` -> `Carton`, nullable when the conflict comes from a newly created mono-product parcel line
- `recipient_organization` -> `ShipmentRecipientOrganization`
- `product` -> `Product`
- `preference_status_snapshot` -> `requested | allowed | refused | unspecified`
- `action` -> `override_refusal`
- `reason` -> text, blank
- `created_by` -> user nullable
- `created_at`

This model is append-only and should not mutate canonical preferences.

## UI Surface Design

### Portal entry surface

Keep `templates/portal/recipients.html` as the entry list.

Changes:
- add an `Ouvrir` action next to or instead of the current edit-first flow
- keep the list lightweight
- add a compact summary column or badge cluster:
  - number of requested products
  - number of allowed products
  - number of refused products

### Portal recipient detail page

Add a dedicated portal recipient detail cockpit with sections:
- identity and destination
- contact and structure data
- product preferences
- needs and coverage

V1 detail-page behavior:
- product search from the catalog
- add/edit/remove explicit preference rows
- fields per row:
  - product
  - status
  - quantity target when status is `requested` or `allowed`
  - period unit when status is `requested` or `allowed`
  - notes
- no override history exposed to associations in V1

### Scan/admin recipient detail surface

Expose the same canonical preference editor from the scan/admin recipient runtime side.

Recommended shape:
- add an `Ouvrir` action from the destination-scoped recipient admin/cockpit area
- point to a scan/admin recipient detail page mirroring the same sections:
  - runtime recipient identity
  - preferences
  - needs and coverage
  - override history

Admin-specific additions:
- visibility into one-off overrides
- ability to edit canonical notes/source

### Recipient detail page instead of a detached global preference page

Do not create a generic "preferences management" page detached from a specific recipient.

Reason:
- preference meaning depends on destination and recipient context
- future coverage and suggestions are recipient-specific
- it keeps both portal and scan/admin mental models aligned

## Shipment Workflow Behavior

### Conflict detection

During shipment create/edit, when a recipient is selected and a ready parcel is assigned:
- inspect parcel contents
- resolve the operational recipient organization for the selected recipient/destination
- compute effective preferences for each product in the parcel

If one or more products are `refused`:
- show a blocking confirmation popup
- list only conflicting products, not the entire parcel contents
- offer:
  - continue
  - choose another parcel

If the user continues:
- assign the parcel
- write one `ShipmentPreferenceOverride` row per refused product conflict

If the user rejects:
- keep the parcel unassigned
- no override row is written

### Mono-product shipment lines

Apply the same rule when the shipment form creates a parcel directly from a product line:
- if the chosen product is `refused` for the recipient, show the same conflict popup before final submission
- if accepted, create the parcel and log the override

### Non-blocking guidance

For statuses other than `refused`, V1 stays non-blocking.

Suggested UI hints:
- `requested`: positive/high-priority badge
- `allowed`: neutral badge
- `unspecified`: neutral but visually distinct from `allowed`
- `refused`: danger badge / conflict marker

## Needs And Coverage Logic

### Period semantics

Use local calendar periods:
- `week` = Monday to Sunday in the app timezone
- `month` = calendar month in the app timezone

### Coverage metrics per recipient/product

For each explicit preference with quantity target:
- `target_quantity`
- `delivered_quantity_in_period`
- `pipeline_quantity_in_period`
- `remaining_need = max(target_quantity - delivered_quantity_in_period - pipeline_quantity_in_period, 0)`

Suggested semantics:
- `delivered_quantity_in_period`: units whose shipment reached a delivered milestone during the current period
- `pipeline_quantity_in_period`: units already committed to in-flight shipments for the same recipient/product but not yet delivered

`requested` and `allowed` both compute remaining need, but `requested` receives higher ranking weight in suggestions.

`unspecified`:
- no target quantity
- no remaining-need calculation

`refused`:
- no target quantity
- no remaining-need calculation

### Delivery evidence source

Use shipment workflow projection / milestone timestamps already available in the repo as the authoritative delivery timing source for V1 period computations, instead of inventing a new delivery ledger.

## V1 Recommendation Layer

Do not build a global stock optimizer in V1.

Instead, add a lightweight scoring layer for ready parcels:
- `tres adaptes`
- `compatibles`
- `a eviter`
- `incompatibles`

Suggested scoring priorities:
1. zero refused products
2. parcels containing `requested` products with remaining need
3. parcels containing `allowed` products with remaining need
4. parcels containing only `unspecified` products
5. parcels mixing useful products with refused products should remain `incompatibles`

Expected V1 use cases:
- sort ready parcels for a recipient by compatibility
- highlight parcels that cover an active explicit need
- guide staff toward a better choice before they commit a shipment

### Auto-creation boundary in V1

Allowed in V1:
- generate proposal lists
- optionally suggest mono-product preparation candidates from stock with human validation

Not in V1:
- silent auto-creation
- multi-product parcel composition engine
- global optimization across all recipients

## Runtime Areas Expected To Change

### Models / migrations

- `wms/models_domain/shipment_parties.py` or a nearby domain module for new preference models
- `wms/models.py` facade export updates
- new migration(s)

### Shared business services

- new preference-resolution service module under `wms/` or `wms/application/parties/`
- possible helper for period coverage computation
- shipment conflict evaluation helper used by scan shipment handlers

### Portal

- `wms/views_portal_account.py`
- `templates/portal/recipients.html`
- new recipient detail template(s)
- nearest portal tests in `wms/tests/views/tests_views_portal.py`
- bootstrap contract tests in `wms/tests/views/tests_portal_bootstrap_ui.py`
- recipient sync tests in `wms/tests/portal/tests_portal_recipient_sync.py`

### Scan/admin

- scan/admin recipient cockpit route/view/template cluster
- `templates/scan/includes/admin_contacts_contact_form.html` only if the entrypoint needs a new `Ouvrir` action or summary
- nearest scan/admin recipient tests

### Scan shipment flow

- `wms/views_scan_shipments.py`
- `wms/scan_shipment_handlers.py`
- `wms/scan_carton_helpers.py`
- `wms/shipment_form_helpers.py`
- `wms/static/scan/scan.js`
- `templates/scan/shipment_create.html`
- `templates/scan/includes/shipment_create_preassignment_overlay.html`
- shipment UI tests and handler tests

## Test Strategy

### Model and service tests

- preference row validation by status
- implicit `unspecified` resolution when no row exists
- override rows never mutate canonical preference
- coverage calculations for week and month periods
- parcel compatibility scoring

### Portal tests

- recipient list shows `Ouvrir`
- recipient detail page loads for owned recipient only
- associations can create/update/delete explicit preference rows
- portal edits still preserve recipient sync contracts

### Scan/admin tests

- admin can edit canonical preferences on the operational recipient detail page
- override history is visible on scan/admin detail pages
- permissions stay aligned with existing admin/staff rules

### Shipment flow tests

- assigning a ready parcel with refused product triggers conflict
- confirming the conflict writes override rows and proceeds
- rejecting the conflict prevents assignment
- mono-product shipment creation applies the same refusal rule
- parcels with requested or allowed products remain non-blocking

## Documentation Propagation Planned During Implementation

Implementation should review and update as needed:
- `docs/repo-reference/02-key-flows-and-living-tests.md`
- `docs/repo-reference/03-impact-map.md`
- `docs/repo-reference/04-shared-contracts.md`

Reason:
- this changes portal recipient behavior
- this adds a shared shipment-party business contract
- this affects scan shipment workflow guidance and blocking behavior

## Non-Goals

- no category-based preferences in V1
- no substitution/equivalence engine in V1
- no Next/React work
- no translation-scope work
- no detached global preference management page
- no automatic multi-product parcel optimizer in V1

## V2 Trace To Keep

Explicit future evolution to retain:
- category-level preferences
- product substitutions and equivalences
- richer recommendation weights using dormant stock and expiry pressure
- automatic multi-product parcel composition
- global optimization across recipients to maximize stock usage and need fit
