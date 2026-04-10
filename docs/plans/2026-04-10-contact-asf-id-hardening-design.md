# Contact ASF ID Hardening Design

## Goal

Make `Contact.asf_id` the canonical business identifier for people and organizations, then
prefer that identifier over name-based resolution on the critical binding and sync paths.

## Current State

The repository already has the right field:

- `contacts.models.Contact.asf_id` exists, is unique, and is exposed in admin and exports.

The repository does not yet treat it as the primary runtime identifier:

- imports still resolve contacts by name first in `wms/import_services_contacts.py`
- default ASF shipper resolution still anchors on organization name in `wms/default_shipper_bindings.py`
- recipient sync and projection reuse still contain exact-name lookups in
  `wms/application/parties/use_cases.py` and `wms/parties/sync.py`
- duplicate detection already prefers exact `asf_id`, but that preference is not yet generalized
  across the critical runtime paths

The result is a mixed contract: `asf_id` exists, but important flows still depend on mutable text.

## Problem

Name-based matching is fragile for structures and contacts:

- names can change
- spelling and case can drift
- duplicates are possible
- the same organization may be reused across multiple flows with slightly different wording
- default ASF bindings should not depend on a hard-coded display name

Without a canonical identifier strategy, bindings and sync behavior remain less predictable than
they need to be.

## Constraints

- stay on the legacy Django stack only
- keep `Destination.iata_code` as the canonical destination identifier
- do not introduce role-specific business identifiers such as `EXP-*` or `DEST-*`
- preserve manually assigned `asf_id` values
- support all existing contacts, including inactive and legacy rows
- keep a temporary explicit fallback by name while the repository transitions

## Scope

This ticket covers the intermediate hardening slice:

- generate an `asf_id` automatically for every new `Contact`
- backfill missing `asf_id` values for all existing contacts
- prefer `asf_id` on the critical `Contact` / `Structure` resolution paths
- keep bounded, explicit nominal fallback where the repo still depends on legacy data

This ticket does not cover:

- a full purge of every nominal lookup in the repository
- a broad rebuild/refactor of all legacy sync and reporting flows
- destination identifier changes
- role-specific business reference formats

## Options Considered

### Option 1: Minimal hardening

Only update the default ASF shipper binding and contact import.

Pros:

- smallest delivery
- low implementation risk

Cons:

- leaves multiple critical bindings on name-based resolution
- does not establish a consistent repository rule for `asf_id`

### Option 2: Intermediate hardening

Generate and backfill `asf_id`, then make it the preferred key on critical runtime resolution
paths while keeping a temporary nominal fallback.

Pros:

- best robustness-to-scope ratio
- removes the main fragile bindings without turning the ticket into a repo-wide cleanup
- creates a clear canonical contract for later work

Cons:

- touches several modules across imports, bindings, and portal sync
- needs careful regression coverage

### Option 3: Full hardening

Replace nearly all nominal contact/organization lookups in one pass, including rebuild and
historical legacy paths.

Pros:

- strongest long-term consistency

Cons:

- too wide for a first identifier ticket
- higher regression risk
- harder to verify in one delivery

## Recommendation

Choose Option 2.

This ticket should establish the canonical identifier contract and apply it to the runtime paths
that matter most:

- new `Contact` creation
- backfill for existing contacts
- default ASF shipper resolution
- contact import reuse
- recipient shared-profile reuse and sync
- admin duplicate and CRUD-adjacent flows already close to the same contract

## Proposed Design

### 1. Canonical identifier policy

`Contact.asf_id` becomes the canonical business identifier for both:

- organization contacts
- person contacts

The identifier is per entity, not per role. A structure keeps the same `asf_id` whether it acts
as shipper, recipient, correspondent, donor, or partner.

### 2. Generated ID format

Automatically generated identifiers use a reserved, neutral namespace:

- format: `ASF-C-<pk-zero-padded>`
- example: `ASF-C-00000042`

Why this format:

- stable and deterministic from the persisted row
- neutral across organization/person and across runtime roles
- easy to backfill idempotently
- unlikely to collide with existing manually curated values such as `ASF-1`, `ASF-100`, or custom
  prefixes

Existing manual `asf_id` values remain untouched.

### 3. New-contact generation

Whenever a new `Contact` is created without an `asf_id`, the runtime assigns one automatically
after the row has a primary key.

Rules:

- never overwrite an existing `asf_id`
- generation must be deterministic for the same row
- generation must not require callers to remember a separate helper

Implementation preference:

- keep the generation logic in one dedicated helper module under `contacts/`
- call that helper from `Contact.save()` after the initial insert when `asf_id` is missing
- avoid duplicating generation logic in forms, services, or commands

### 4. Existing-contact backfill

Add an idempotent management command that assigns generated `asf_id` values to every existing
contact missing one.

Rules:

- cover all contacts, including inactive and legacy rows
- preserve all existing `asf_id` values
- support `--dry-run` and `--apply`
- report how many rows would change or did change

This command is the explicit rollout tool for production and staging.

### 5. Resolution precedence

Critical flows move to this lookup order:

1. exact `asf_id` when available
2. bounded legacy nominal fallback when `asf_id` is absent or the caller has only legacy text

This is intentionally transitional. The repository still accepts legacy rows and inputs, but the
runtime contract becomes clear: `asf_id` is preferred whenever present.

### 6. Default ASF shipper hardening

`wms/default_shipper_bindings.py` currently resolves the ASF shipper by organization name.

Change the contract so the helper can prefer a canonical ASF `asf_id` first, with the existing
name-based fallback kept temporarily for legacy compatibility.

The design should centralize the canonical ASF identifier in settings or in one small policy/helper
module, instead of scattering a hard-coded name anchor across the repo.

### 7. Contact import hardening

`wms/import_services_contacts.py` should resolve an existing contact by exact `asf_id` before
falling back to name + contact type matching.

Import behavior after the change:

- if the row provides `asf_id`, it is the primary reuse key
- if the row does not provide `asf_id`, legacy nominal reuse still works
- if an existing contact already has an `asf_id`, an import row must not replace it silently
- new contacts created without an input `asf_id` still receive a generated one via the common
  model-level generation path

### 8. Shared-profile and sync hardening

The recipient shared-profile and sync adapters currently reuse structures and people via exact-name
matches in several places.

For this ticket:

- extend the relevant use cases and sync helpers so they can prefer exact `asf_id` when that
  identifier is available on the source/projection/runtime object
- keep nominal fallback where the upstream source still only carries names

This does not require a complete rewrite of all legacy projection models. It does require the
critical reuse points to stop ignoring `asf_id` when it is present.

### 9. Admin contract

Admin duplicate detection already prefers exact `asf_id`. The broader admin contract should stay
aligned with the new canonical rule:

- create/edit flows must preserve manually entered `asf_id`
- duplicate review should continue to surface exact `asf_id` matches first
- generated `asf_id` values must appear consistently in admin search/export flows

### 10. Rollout strategy

Rollout order:

1. add generation helper and automated generation for new contacts
2. add backfill command for existing contacts
3. harden the critical runtime resolution paths
4. run backfill in dry-run, then apply
5. keep bounded nominal fallback temporarily
6. remove more nominal fallbacks in later tickets once the repo has stabilized on `asf_id`

## Affected Areas

- `contacts/models.py`
- new helper under `contacts/`
- new management command under `contacts/management/commands/`
- `wms/default_shipper_bindings.py`
- `wms/admin_account_request_approval.py`
- `wms/import_services_contacts.py`
- `wms/application/parties/use_cases.py`
- `wms/parties/sync.py`
- nearby tests in `contacts/tests/`, `wms/tests/imports/`, `wms/tests/portal/`,
  `wms/tests/core/`, and `wms/tests/views/`

## Test Strategy

Minimum proof for this ticket:

- new contacts auto-generate an `asf_id`
- manually defined `asf_id` values stay unchanged
- backfill command reports and applies only missing IDs
- default ASF shipper resolution prefers canonical `asf_id`
- contact import reuses by exact `asf_id` before name
- recipient shared-profile/sync critical paths still work with both canonical and legacy inputs
- legacy nominal fallback remains functional where no `asf_id` is available

## Risks

- generated IDs could conflict with a future format if the namespace is not frozen now
- a partial rollout could create two lookup rules if runtime paths are updated unevenly
- sync paths that only know names today may require careful fallback handling to avoid false
  negatives

## Mitigations

- reserve one generated namespace now: `ASF-C-*`
- keep generation/backfill logic in one helper
- keep nominal fallback explicit and local during transition
- cover each hardened resolution path with regression tests before removing any fallback

## Follow-Up After This Ticket

- progressively remove additional nominal lookups once backfill is complete in the target
  environments
- decide whether projections and import/export templates should carry `asf_id` more broadly
- update repo-reference docs once the runtime contract has actually changed in implementation
