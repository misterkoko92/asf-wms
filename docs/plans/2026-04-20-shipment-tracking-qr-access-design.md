# Shipment Tracking QR Access Design

**Date:** 2026-04-20

## Goal

Turn the legacy Django shipment tracking QR route `/scan/shipment/track/<tracking_token>/` into an authenticated, role-aware gateway that:

- reuses the existing role identifiers already present in the repository
- blocks every tracking update until the actor is logged in
- supports `Code perdu ?` recovery from `email + escale + role`
- creates `pending` identities when no identifier exists yet while still allowing the scan after a restricted login
- requires an IATA-face carton proof for downstream correspondent / recipient receipt scans

## Context

The current tracking QR route is effectively public. It renders the shipment status plus a direct update form with:

- `Étape`
- `Nom`
- `Structure`
- `Commentaires`

The route currently stores a minimal `ShipmentTrackingEvent` snapshot and does not enforce:

- authentication
- role-specific identifier resolution
- lost-code recovery
- pending identity creation
- proof capture for downstream receipt events

Validated user direction for this ticket:

- use the identifiers already in place; do not invent a new identifier namespace
- there must be no scan without a successful login
- `Code perdu ?` must ask for `email + escale + rôle`
- while the shipment has not reached `OK mise à bord`, the default escale shown in that flow must be `CDG`
- the lost-code email must tell the user the identifier and the assigned role
- if there is no identifier, create an account in `pending` state, but still allow the scan once the user has logged in through a restricted access path
- when the selected role changes, only the fields relevant to that role should remain visible
- for `correspondant` and `destinataire` receipt scans, an IATA-face carton photo is mandatory unless the operator explicitly checks `Je ne peux pas prendre de photos`, in which case the carton number becomes mandatory

## Scope And Boundaries

This design stays on the legacy Django stack only.

In scope:

- `wms/scan_urls.py`
- `wms/views_scan_shipments.py`
- `wms/shipment_tracking_handlers.py`
- `wms/forms.py`
- scan templates / page-local JS for the QR flow
- email templates and access-recovery helpers
- shipment-tracking data model changes
- repo-reference / ops docs that describe this critical route

Out of scope:

- Next / React migration files
- FR / EN translation parity work
- rewriting the existing portal or volunteer authentication systems
- broader refactors of shipment or contact architecture not required for this gateway

## Canonical Identifier Mapping

The QR flow must reuse the identifiers already present in the repository.

Recommended mapping:

- `bénévole` -> `VolunteerProfile.volunteer_id`
- `expéditeur` -> `Contact.asf_id`
- `destinataire` -> `Contact.asf_id`
- `correspondant` -> `Contact.asf_id`

No new `QR-*`, `TRACK-*`, or similar business identifier should be introduced.

## User-Facing Workflow

### 1. QR Entry Gate

Scanning the QR still opens `/scan/shipment/track/<tracking_token>/`.

The page no longer behaves as a direct public mutation surface. Instead it becomes a gateway with two modes:

- `access required` when no compatible authenticated session exists yet
- `tracking update` when the user is authenticated and authorized for the requested role

### 2. Identification Path

The first visible block asks the actor to choose a role:

- `bénévole`
- `expéditeur`
- `destinataire`
- `correspondant`

Then the page renders the role-specific identifier field:

- volunteer id for `bénévole`
- ASF ID for the contact roles

If the identifier resolves successfully and the current session is already compatible with that identity, the page reveals the tracking update form immediately.

If the identifier resolves but no compatible session exists yet, the page redirects the user to the appropriate login flow with a `next` parameter that returns to the same tracking token and role.

### 3. `Code perdu ?`

The lost-code panel remains on the QR entry page.

Required inputs:

- `email`
- `escale`
- `rôle`

Default escale behavior:

- before `OK mise à bord`, prefill `CDG`
- from `OK mise à bord` onward, prefill the shipment destination IATA code when available

The UI response must stay generic regardless of whether the email exists, to avoid account enumeration.

If the repository can resolve a matching identity, the outbound email must include:

- the identifier already assigned to that role
- the role label
- the login or set-password path required to come back authenticated
- a return link to the original shipment tracking QR route

The email content is informative, but the scan remains blocked until the user is actually logged in.

### 4. `Pas d'identifiant`

If the actor has no identifier yet, the page exposes a `Créer un compte` branch.

Mandatory fields:

- `rôle`
- `email`
- role-appropriate identity fields
- structure details for the non-volunteer roles

The form only shows the fields relevant to the chosen role.

Recommended role-specific behavior:

- `bénévole`: person fields only
- `expéditeur`: structure identity and address fields
- `destinataire`: structure identity, address, and destination / escale fields
- `correspondant`: structure identity plus the stopover / escale scope

Once submitted:

- the repository creates the role identifier immediately using the existing domain identifier
- the business identity remains `pending`
- the user receives restricted tracking access credentials
- the scan can proceed only after that restricted login succeeds

## Authentication Model

## Existing Sessions

Existing authenticated sessions should continue to work when they already match the requested identity:

- scan staff users
- volunteer users with an active `VolunteerProfile`
- portal users whose active scope matches the requested shipper / recipient identity

These sessions should not be forced through a second login wall.

## Restricted Tracking Access

The repository needs a new, bounded access layer for shipment tracking QR usage.

Recommended new concept:

- `ShipmentTrackingAccessGrant`

Purpose:

- allow authenticated access to the QR tracking route without opening the broader scan, portal, or volunteer surfaces
- cover `correspondant`
- cover newly created `pending` QR identities
- act as a fallback for contact identities that have an ASF ID but no usable portal session

Recommended grant fields:

- `user`
- `role` (`volunteer`, `shipper`, `recipient`, `correspondent`)
- optional `contact`
- optional `volunteer_profile`
- optional `destination`
- `identity_status` (`verified`, `pending`)
- `is_active`
- audit metadata (`created_by`, `created_at`, `reviewed_by`, `reviewed_at`)

The restricted grant is not a replacement for portal or volunteer access. It is a narrow compatibility layer for the QR route only.

## Login Rules

POST updates to the tracking route must fail fast unless one of these is true:

- the user is scan staff
- the user is a volunteer and the selected identifier maps to that volunteer profile
- the user has a matching portal scope for the requested shipper / recipient identity
- the user has an active `ShipmentTrackingAccessGrant` matching the requested role and identity

## Pending Identity Creation

The user explicitly asked for `pending` identities that can still validate a scan after login.

That is not compatible with the current portal / volunteer permission guards by itself, so the design splits:

- business-domain identity status
- QR access status

### Volunteer

Recommended creation behavior:

- create or reuse the `User`
- create a `VolunteerAccountRequest(status=pending)` for ASF review
- create a `VolunteerProfile` immediately so `volunteer_id` is assigned
- keep the volunteer profile blocked from the normal volunteer space until approval
- grant QR-restricted login through `ShipmentTrackingAccessGrant(identity_status=pending, role=volunteer)`

### Shipper / Recipient

Recommended creation behavior:

- create or reuse an organization `Contact` immediately so `asf_id` exists
- keep the contact blocked from normal operational selectors until reviewed
- create a `PublicAccountRequest(status=pending)` so the existing ASF validation flow still receives the request
- create a QR-restricted access grant in `pending` state

### Correspondent

There is no current public account-request type dedicated to correspondents.

Recommended behavior:

- create or reuse the organization `Contact` immediately so `asf_id` exists
- keep that contact outside the regular active runtime selectors until ASF review
- create a `ShipmentTrackingAccessGrant(status=pending, role=correspondent)` scoped to the relevant destination / escale
- notify ASF through the QR-access email path instead of trying to force this role through the portal request types

This keeps the first delivery bounded and avoids inventing a full portal-correspondent product surface inside this ticket.

## Tracking Event Contract

`ShipmentTrackingEvent` remains the canonical event history.

The design does not introduce a second event table for QR scans.

Instead, the existing event model is enriched with a durable actor snapshot and proof fields captured at submission time.

Recommended additions:

- `actor_role`
- `actor_identifier`
- `actor_email`
- `actor_identity_status`
- `auth_source` (`staff`, `portal`, `volunteer`, `qr_restricted`)
- `escale_code`
- `actor_snapshot` as a compact JSON payload for display / audit
- `proof_mode` (`photo`, `manual`)
- `proof_file`
- `proof_carton_reference`

The existing `actor_name`, `actor_structure`, and `created_by` fields should stay in place.

Rationale:

- the history stays human-readable
- later approval changes do not rewrite past scans
- the UI can still render meaningful rows without chasing live identity objects

## Role-To-Step Authorization

Recommended authorization matrix:

- `staff`: all steps
- `bénévole`: upstream logistics steps through `OK mise à bord`
- `expéditeur`: upstream logistics steps through `OK mise à bord`
- `correspondant`: `Reçu correspondant`
- `destinataire`: `Reçu destinataire`

This matrix keeps downstream receipt confirmation tied to the correct business actor instead of allowing any authenticated identity to validate the final legs.

## Escale Defaults

The `escale` field is used by:

- `Code perdu ?`
- pending account creation
- the stored scan snapshot

Recommended defaulting rules:

1. if the shipment has not reached `ShipmentTrackingStatus.BOARDING_OK`, default to `CDG`
2. otherwise default to the shipment destination IATA code when available
3. if neither value is available, keep `CDG` as the final fallback

The field must stay overridable where the user is explicitly asked to confirm or recover access using an escale.

## Proof Capture Rules

The user requirement targets the downstream receipt scans performed by correspondents and recipients.

Recommended rule:

- when the chosen event is `Reçu correspondant` or `Reçu destinataire`, proof is mandatory

Default proof mode:

- `photo`

Required UI copy:

- checkbox label: `Je ne peux pas prendre de photos`
- helper text for the manual fallback: `Le numéro du colis se trouve sur la liste de colisage collée sur un côté du colis`

Behavior:

- if the checkbox is not selected, an IATA-face carton photo is required
- if the checkbox is selected, photo upload becomes optional and the carton number becomes required

This proof must be validated server-side. Client-side JS is only a convenience layer.

## Emailing

Recommended new outbound templates:

- `shipment_tracking_access_recovery`
- `shipment_tracking_pending_created`

Recovery email content must include:

- shipment reference
- role
- identifier
- escale when relevant
- login / set-password path
- return link to the QR route

Pending-creation email content must include:

- role
- newly assigned identifier
- explicit `pending` status wording
- the restricted login path
- the return link to the QR route

The UI must keep a generic success message for recovery submissions regardless of whether an email was actually matched.

## UI Shape

The existing `templates/scan/shipment_tracking.html` should remain the main surface, but it needs two sections:

- gateway / access resolution
- tracking form

Recommended page-local JS responsibilities:

- show only the field groups relevant to the selected role
- toggle the proof block between photo mode and manual carton number mode
- preserve the current unsaved-change overlay for the authenticated update form

## Testing

Minimum proof coverage should include:

- unauthenticated QR GET renders the gateway instead of the direct update form
- POST update is rejected without a valid session
- matching staff / volunteer / portal / QR-restricted sessions are accepted
- role-to-step authorization is enforced
- `Code perdu ?` keeps a generic UI response and sends the correct email payload
- pending creation issues the expected identifier and QR-restricted access
- `CDG` defaults before boarding
- destination IATA defaults after boarding
- proof photo is required for `Reçu correspondant` / `Reçu destinataire`
- checking `Je ne peux pas prendre de photos` requires the carton number instead
- history rows keep the actor snapshot even if the live account changes later

## Repo-Reference Impact

This work changes a critical route and a named flow under the repo reference.

Before closing the implementation, re-check and update as needed:

- `docs/repo-reference/02-key-flows-and-living-tests.md`
- `docs/repo-reference/03-impact-map.md`
- `docs/repo-reference/04-shared-contracts.md`
- `docs/operations.md`
- `docs/release_checklist.md`

The critical contract change is that shipment tracking QR becomes an authenticated gateway with restricted QR access support, pending identity creation, and proof requirements for downstream receipt scans.
