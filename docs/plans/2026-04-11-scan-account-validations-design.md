# Scan Account Validations Design

## Goal

Move operational review of public account requests from Django admin to a dedicated `/scan`
surface so scan operators can correct the final business type, complete the required shipment-party
fields, and approve the account in one screen.

## Context

The current request flow already supports:

- public `shipper`, `recipient`, and `user` account requests
- recipient signup with one mandatory `Destination`
- approval-time provisioning of recipient runtime objects and portal grants

The operational gap is not in the data model. It is in the review surface.

Today the normal review path still runs through Django admin:

- `PublicAccountRequestAdmin` can approve requests
- `approve_account_request(...)` enforces `destination` for recipient requests
- the scan contact cockpit already knows how to create or update a `recipient` with:
  - destination
  - allowed shippers
  - legal form
  - beneficiary count

This creates a mismatch for real operator work:

- the request review surface is admin-oriented
- the contact correction surface is scan-oriented
- correcting `shipper` to `recipient` during review can require fields the admin page does not show

## Problem

ASF operators need to handle the following case in one pass:

1. open a pending account request
2. realize the requested type is wrong
3. switch the final type from `shipper` to `recipient`
4. complete the missing recipient data
5. validate the account

The current split between Django admin and `/scan/admin/contacts/` turns this into a multi-surface
workflow with an avoidable failure mode.

## Decision

Create a dedicated scan operator flow as the primary account-review surface:

- list page: `/scan/account-validations/`
- detail page: `/scan/account-validations/<id>/`

The detail page becomes a one-screen operator workflow:

- show the original request
- let the operator choose the final business type
- reveal the required fields for that final type
- approve or reject from the same screen

The design keeps the existing public signup and provisioning rules, but changes the operational
entry point used for review.

## Scope

### In scope

- pending public account request list for scan operators
- account review detail page on `/scan`
- one-screen correction + completion + approval flow
- explicit support for correcting `shipper` -> `recipient`
- reuse of existing shipment-party services for final object creation
- minimal audit trace of requested type vs approved type
- lightweight Django admin fallback

### Out of scope

- reopening the paused Next/React migration
- translation parity work
- full replacement of `/scan/admin/contacts/`
- broad contact-directory permission changes for non-admin operators
- advanced duplicate merge UX beyond a simple "use existing structure" review choice

## Operator Roles And Access

The new review pages are for scan operators, not only superusers.

Recommended permission contract:

- keep `scan_staff_required`
- add a dedicated validator capability:
  - superusers are always allowed
  - staff members in the configured validation group are allowed

The simplest fit is to reuse the existing account-validation group setting already used for
notification routing:

- `ACCOUNT_REQUEST_VALIDATION_GROUP_NAME`
- default `Account_User_Validation`

This keeps the same operator population aligned across:

- notification emails
- review responsibilities
- scan review access

`/scan/admin/contacts/` can remain superuser-only in phase 1.

## UX Target

### List page

The list page shows pending requests with operator-first columns:

- created date
- structure / requester label
- email
- requested type
- destination if present
- document status summary
- completeness status
- action `Traiter`

Useful filters:

- requested type
- destination
- text search
- incomplete documents
- corrected-vs-uncorrected once review metadata exists

### Detail page

The detail page has four blocks.

#### 1. Request received

Readonly summary of the original request:

- requested type
- association name
- email
- phone
- address
- destination selected at signup, if any
- requester notes
- uploaded documents

#### 2. Operator qualification

Editable review controls:

- final business type
- optional "use existing structure" target if the request should attach to an existing contact
- visual warning when final type differs from requested type

If the operator changes the type, the page shows a banner such as:

- `Requested as shipper, reviewed as recipient`

#### 3. Business data

Dynamic form fields based on the final type.

For final `recipient`:

- structure name
- referent first name / last name
- email / phone
- destination
- allowed shippers
- legal form
- beneficiary count
- address fields

For final `shipper`:

- structure name
- referent first name / last name
- email / phone
- optional shipper scope fields already used by runtime setup
- address fields

The page should block approval until the final-type contract is satisfied.

#### 4. Decision

Actions:

- `Valider le compte`
- `Refuser la demande`
- `Annuler`

No draft workflow is required in V1.

## Navigation Direction

Phase 1 should prioritize the operator page, not a large contact-nav rewrite.

Recommended navigation change for the first delivery:

- add `Validations comptes` under the existing scan `Gestion` area

Future-friendly target:

- once more contact surfaces are operator-ready, split them into a dedicated
  `Gestion des contacts` sidebar group

This avoids shipping dead or inaccessible links in the first iteration.

## Data Model Direction

The request record needs to preserve both what was requested and what was finally approved.

Recommended minimal schema change on `PublicAccountRequest`:

- keep `account_type` as the final operative type used by approval and access emails
- add `requested_account_type` to preserve the original requested value when the operator corrects
  the type
- add `review_snapshot` as a `JSONField(default=dict, blank=True)` to store the operator-reviewed
  payload used for approval

Why this shape:

- existing approval and notification code already branches on `account_type`
- preserving the original type in a second field avoids a broad "resolved type" rewrite
- `review_snapshot` gives a durable audit trail for:
  - corrected type
  - selected destination
  - allowed shippers
  - referent data used at approval time

If the operator does not change the type:

- `requested_account_type` may stay blank
- `account_type` keeps its current meaning

If the operator does change the type:

- write the original value into `requested_account_type`
- replace `account_type` with the final approved type before provisioning

## Service Architecture

Do not duplicate the runtime provisioning logic inside the new scan view.

Recommended architecture:

1. Extract a shared account-review approval service from `approve_account_request(...)`
2. Let both surfaces call the same provisioning path:
   - Django admin fallback
   - scan account validation page
3. Pass an explicit resolved review payload into that shared service

The shared service should own:

- user creation / reactivation
- recipient or shipper runtime provisioning
- destination validation
- default ASF shipper binding for recipients
- portal grant creation
- account-request status / reviewer updates
- review snapshot persistence

The scan page should own only:

- list/query/filter composition
- review-form validation
- operator UX

## Reuse Of Existing Domain Logic

The new scan page should reuse the existing recipient runtime helpers instead of rebuilding them:

- `update_runtime_recipient_shared_profile(...)`
- default shipper binding helpers
- contact CRUD patterns already used by scan admin

That keeps the contracts aligned across:

- portal signup approval
- scan contact maintenance
- recipient shipment-party runtime

## Django Admin Fallback

Django admin remains a fallback, not the primary operator flow.

Minimal fallback changes are still recommended:

- expose `destination` on `PublicAccountRequestAdmin`
- show a readonly link to the scan review page when the request is still pending

This ensures a superuser can still unblock a case without turning Django admin into the official
review UX again.

## Notification And Banner Direction

The scan shell already exposes a pending-account banner for superusers.

Phase 1 should evolve that into an operator-facing signal:

- expose pending account validation count for authorized validators, not only superusers
- point the banner toward `/scan/account-validations/` instead of Django admin

This aligns the alert with the new operator workflow.

## Approval Outcomes

### Recipient approval

If the final type is `recipient`, approval must still guarantee:

- destination-scoped `ShipmentRecipientOrganization`
- one active `ShipmentRecipientContact`
- one active `PortalAccessGrant(recipient_admin)`
- default ASF shipper binding

### Shipper approval

If the final type is `shipper`, approval must keep the current shipper-facing behavior:

- organization contact
- legacy `AssociationProfile` path where still required
- shipper runtime provisioning

## Testing Impact

This design changes or adds contracts in the following areas:

- account-request approval service tests
- scan operator view tests for list/detail/review actions
- permission tests for validator-group access
- scan sidebar / banner bootstrap tests
- admin fallback tests

Likely test files:

- `wms/tests/admin/tests_account_request_handlers.py`
- `wms/tests/portal/tests_portal_role_review_gate.py`
- `wms/tests/views/tests_scan_bootstrap_ui.py`
- new `wms/tests/views/tests_views_scan_account_validations.py`

## Repo Reference Impact

When implemented, the following repo-reference docs must move in the same work:

- `docs/repo-reference/02-key-flows-and-living-tests.md`
- `docs/repo-reference/04-shared-contracts.md`

Relevant sections:

- public account request portal contract
- scan sidebar navigation contract
- scan/admin contact propagation notes where operator review now starts on a dedicated scan page

## Risks

### Risk 1 - type correction drifts away from approval logic

If the scan page reimplements approval instead of reusing the shared service, `shipper` and
`recipient` provisioning rules will diverge.

Mitigation:

- extract a shared approval service first

### Risk 2 - operator page depends on superuser-only follow-up surfaces

If the new flow still needs `/scan/admin/contacts/` to finish normal cases, the feature does not
really solve the operator problem.

Mitigation:

- ensure the review page contains every field required for nominal approval

### Risk 3 - original request intent is lost after correction

If the final type overwrites the request with no audit trail, operators lose context.

Mitigation:

- persist `requested_account_type` and `review_snapshot`

## Recommendation

Ship this in a bounded first slice:

1. new `/scan/account-validations/` list + detail pages
2. shared approval service with review overrides
3. minimal request audit fields
4. operator banner + sidebar entry
5. Django admin fallback link and destination field

Do not start with a full contact-management refactor. The account-validation surface is the
highest-value operational gap and should be the first delivery.
