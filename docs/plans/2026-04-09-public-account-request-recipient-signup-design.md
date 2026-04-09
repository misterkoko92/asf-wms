# Public Account Request Recipient Signup Design

## Goal

Allow public account requests to explicitly choose `Expediteur` or `Destinataire`, require one delivery stop for recipient requests, and provision recipient-only portal access automatically after ASF approval.

## Current State

Today the public account request flow only supports:

- `association` requests, which are approved as legacy shipper-facing portal accounts
- `user` requests, which are approved as WMS backoffice users

Recipient portal access already exists, but it is only provisioned when an admin manually creates a `PortalAccessGrant` pointing to an existing `ShipmentRecipientOrganization`. The public signup flow cannot currently create that runtime because it does not collect a destination and does not create recipient-side shipment-party data at approval time.

## Problem

ASF wants a real public signup path for recipients:

- the requester must explicitly choose `Expediteur` or `Destinataire`
- recipient requests must select exactly one delivery stop during signup
- once ASF approves a recipient request, the account must open only the recipient portal
- the validated recipient must automatically be linked to the default ASF shipper

Without a destination collected up front, ASF approval cannot create the recipient runtime scope required by the portal.

## Constraints

- Stay on the legacy Django stack only.
- Keep legacy `association` requests working as shipper requests.
- Do not introduce the broader transverse identifier strategy in this ticket. `asf_id` hardening stays for a separate follow-up.
- Recipient portal access must remain recipient-only for this flow: no automatic shipper scope.
- Automatic ASF linking must use existing default-shipper binding logic rather than introducing a second binding path.

## Options Considered

### Option 1: Keep destination selection for ASF admin only

The public form would add `Destinataire` but no destination field. ASF would choose the destination at approval time.

Pros:

- smallest public form change

Cons:

- approval stays partially manual
- ASF cannot approve directly from the request without extra data entry
- higher risk of incomplete provisioning or inconsistent approval behavior

### Option 2: Collect destination in the public form for recipient requests

The public form shows a mandatory destination selector when `Destinataire` is selected. Approval creates the recipient runtime, recipient-only grant, and ASF binding immediately.

Pros:

- approval is deterministic and complete
- the portal scope can be created from the request alone
- aligns with the data model, where recipient access is scoped to one `ShipmentRecipientOrganization`

Cons:

- requires a schema change and UI validation

### Option 3: Create a temporary recipient account without a recipient runtime

Approval would create a user first, then wait for ASF to attach the recipient runtime later.

Pros:

- avoids collecting destination up front

Cons:

- produces an incomplete portal account
- conflicts with the current access model, which expects a concrete recipient scope
- creates more admin follow-up and more edge cases

## Recommendation

Choose Option 2.

Recipient signup must collect the destination because the portal access model is runtime-scoped to one recipient organization and one destination. This keeps the approval step idempotent and avoids creating half-configured accounts.

## Proposed Design

### 1. Public request types

Extend `PublicAccountRequestType` so the public form can distinguish:

- `shipper`
- `recipient`
- `user`

Legacy `association` requests remain supported as an alias of the shipper flow during approval and access-line rendering so older rows do not break.

### 2. Public form behavior

The public account request form will expose:

- `Expediteur`
- `Destinataire`
- `Utilisateur WMS` where already supported by the current route

When `Destinataire` is selected:

- the structure/address/documents block remains visible
- a required `Escale de livraison` select appears
- only one destination can be chosen

When `Expediteur` is selected:

- the current structure/address/documents flow remains
- no destination is required

When `Utilisateur WMS` is selected:

- the current username/password block remains

### 3. Stored request data

`PublicAccountRequest` gains a nullable `destination` foreign key. It is required by validation for recipient requests and ignored for shipper/user requests.

This makes the approval flow deterministic and avoids stuffing destination information into free text or notes.

### 4. Recipient approval flow

When ASF approves a recipient request:

- create or reuse the organization contact for the recipient structure
- create or update its address
- create or reuse the Django user by email
- do not create an `AssociationProfile`
- create or reuse the `ShipmentRecipientOrganization` for `(organization, destination)`
- mark it validated and active
- create or update one minimal default recipient person contact attached to the organization
- create or reactivate a `PortalAccessGrant` with role `recipient_admin`
- trigger the existing default ASF shipper binding logic so the recipient is linked to ASF automatically

If the default ASF shipper cannot be resolved, approval must fail explicitly rather than silently validating an unusable recipient account.

### 5. Recipient contact bootstrap

Approval will bootstrap one minimal recipient contact so the ASF binding has an authorized contact to point to immediately.

Seed values:

- email from the request email
- phone from the request phone
- name derived from the structure name if no person name is available

This is intentionally minimal. The recipient can refine the contact details later in the recipient portal profile screen.

### 6. Access contract after approval

Approved recipient requests receive:

- one active `PortalAccessGrant(recipient_admin)`
- no legacy `AssociationProfile`
- no shipper scope

Portal login behavior then remains unchanged:

- one scope opens directly
- multiple scopes go to scope selection

### 7. Automatic ASF link

The default ASF binding must reuse the existing `default_shipper_bindings` helpers rather than duplicating shipper lookup or authorization logic inside account approval.

This preserves one business rule for "ASF can send to validated recipients by default".

### 8. Deferred identifier work

The broader question of stable business identifiers stays out of scope for this ticket.

For now:

- destinations continue to rely on `iata_code`
- contacts/structures may continue to use names or existing `asf_id`

A separate ticket can generalize `asf_id` usage and progressively remove name-based resolution where it still exists.

## Affected Areas

- public account request model, handler, template, and tests
- approval flow and tests
- portal access grant provisioning for recipients
- default ASF shipper binding path
- admin access-line display for approved requests
- repo-reference docs for account requests and portal access contracts

## Test Strategy

- form renders `Expediteur` and `Destinataire`
- recipient requests require one destination
- shipper requests still work
- legacy `association` requests still approve as shipper accounts
- recipient approval creates recipient runtime + recipient-only grant
- recipient approval auto-links the validated recipient to ASF
- approved recipient user logs into the recipient portal directly when no other scope exists

## Risks

- destination is now part of public request data, so form validation and approval code must stay aligned
- reusing existing organizations could accidentally attach to the wrong contact if matching stays too permissive
- ASF default-shipper lookup still depends on the existing canonical shipper policy until the future identifier ticket hardens it

## Mitigations

- make destination mandatory for recipient requests
- keep reuse rules conservative
- fail approval explicitly when the default ASF shipper cannot be resolved
- cover legacy `association` behavior with regression tests
