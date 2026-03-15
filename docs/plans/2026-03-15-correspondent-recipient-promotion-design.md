# Correspondent Recipient Promotion Design

**Date:** 2026-03-15

**Goal:** Ensure every contact tagged `Correspondant` is also usable as a `Destinataire`, both for the current database and for all future creations, without degrading existing legacy or org-role behavior.

## Scope

- Stay on the legacy Django stack only.
- Automate promotion from `Correspondant` to `Destinataire`.
- Cover existing contacts and future tag additions.
- Preserve current selector behavior for correspondents and recipients.
- Keep the modern org-role layer coherent with the legacy contact/tag layer.

## Non-Goals

- Do not touch paused Next/React files.
- Do not remove `Destinataire` automatically when `Correspondant` is removed later.
- Do not delete or rewrite existing destination, binding, or notification data beyond what is needed to make correspondents recipient-ready.
- Do not create one synthetic organization per isolated person correspondent.

## Problem

The current model treats `Correspondant` and `Destinataire` as separate tags and partially separate behaviors:

- recipient selectors and bindings expect a recipient-ready structure
- correspondents can be a person or an organization
- people without an organization are not structurally eligible in recipient selectors

That creates a gap: a correspondent may be selected as a correspondent but still not be operationally usable as a recipient.

## Approaches Considered

### 1. Tag-only promotion

- Add `Destinataire` automatically whenever a contact receives `Correspondant`.
- Rejected because it does not make person correspondents without an organization truly usable in the recipient flows.

### 2. Additive safe promotion

- Add `Destinataire`.
- For organizations and people with an organization, create the modern recipient role on the existing organization.
- Leave people without an organization for manual review.
- Rejected because it still leaves a recurring manual cleanup path in normal operations.

### 3. Full promotion with shared support organization

- Add `Destinataire`.
- Resolve a recipient organization for every correspondent.
- If a person has no organization, attach them to a shared technical organization `ASF - CORRESPONDANT`.
- Ensure the modern recipient role exists on the resolved organization and let the existing default-shipper machinery do the rest.
- Approved because it closes the operational gap without multiplying synthetic organizations.

## Approved Rules

- Every contact tagged `Correspondant` must also have the tag `Destinataire`.
- The rule is one-way:
  - `Correspondant` implies `Destinataire`
  - `Destinataire` does not imply `Correspondant`
- If the correspondent is an `ORGANIZATION`, that organization becomes the recipient structure.
- If the correspondent is a `PERSON` with an organization, that organization becomes the recipient structure.
- If the correspondent is a `PERSON` without an organization, the person is attached to the singleton support organization `ASF - CORRESPONDANT`.
- The contact itself remains selectable; the support organization only provides the structural recipient backing.

## Runtime Design

### Trigger point

Use the existing `Contact.tags` `m2m_changed` hook in [`contacts/models.py`](/Users/EdouardGonnu/asf-wms/.worktrees/correspondent-recipient-promotion/contacts/models.py), not a form-only hook.

Why:

- it covers admin changes, imports, rebuild flows, and future automated writes
- it keeps the behavior centralized
- it avoids duplicating promotion logic in several entry points

### Promotion service

Add a dedicated idempotent service, likely under `contacts/`, responsible for:

1. detecting whether the contact currently matches the `Correspondant` tag aliases
2. ensuring the `Destinataire` tag exists and is attached
3. resolving the backing recipient organization
4. creating or reactivating `OrganizationRoleAssignment(role=RECIPIENT)` for that organization
5. returning without side effects when the state is already correct

This service must be re-entrant because adding `Destinataire` from inside the tag signal will retrigger the same signal flow.

### Organization resolution

- `ORGANIZATION` contact: use the contact itself
- `PERSON` with `organization`: use that organization
- `PERSON` without `organization`:
  - find or create `ASF - CORRESPONDANT`
  - attach the person to that organization
  - mark the support organization so later runs can identify it as technical support data

The support organization is shared, not per-person.

### Modern role synchronization

The promotion service creates or reactivates the `RECIPIENT` role assignment on the resolved organization.

It does not manually recreate all default-shipper bindings. Instead it relies on the existing post-save signal on `OrganizationRoleAssignment` in [`wms/signals.py`](/Users/EdouardGonnu/asf-wms/.worktrees/correspondent-recipient-promotion/wms/signals.py) so the current ASF default-shipper behavior stays the single source of truth.

## Backfill Design

Add a dedicated management command to process existing correspondents in `--dry-run` and `--apply` modes.

Behavior:

- iterate over all contacts matching `Correspondant`
- run the same promotion service used by runtime automation
- report:
  - correspondents scanned
  - recipient tags added
  - support organizations created or reused
  - people attached to `ASF - CORRESPONDANT`
  - recipient roles created or reactivated

The backfill is additive only. It does not remove tags, roles, or bindings.

## Safety Rules

- Removing `Correspondant` later does not automatically remove `Destinataire`.
- Removing `Correspondant` later does not automatically remove created recipient roles or bindings.
- The support organization `ASF - CORRESPONDANT` is a technical helper, not a business contact to be manually duplicated.
- The person remains the visible usable contact where selectors support person contacts linked to an organization.

## Testing Strategy

Cover the feature with targeted tests instead of a full E2E suite:

- unit tests for the promotion service
- signal-level tests for tag-driven automation
- person-without-organization tests for support-organization reuse
- recipient-surface tests proving the promoted correspondent is eligible in existing recipient flows
- non-regression tests proving removal of `Correspondant` does not undo promoted state

Relevant existing suites:

- [`wms/tests/core/tests_contact_filters.py`](/Users/EdouardGonnu/asf-wms/.worktrees/correspondent-recipient-promotion/wms/tests/core/tests_contact_filters.py)
- [`wms/tests/shipment/tests_shipment_party_rules.py`](/Users/EdouardGonnu/asf-wms/.worktrees/correspondent-recipient-promotion/wms/tests/shipment/tests_shipment_party_rules.py)
- [`wms/tests/portal/tests_default_shipper_bindings.py`](/Users/EdouardGonnu/asf-wms/.worktrees/correspondent-recipient-promotion/wms/tests/portal/tests_default_shipper_bindings.py)

## Acceptance Criteria

- Tagging a contact as `Correspondant` automatically ensures `Destinataire`.
- A correspondent organization becomes recipient-ready immediately.
- A person correspondent with an organization makes that organization recipient-ready.
- A person correspondent without an organization is attached to `ASF - CORRESPONDANT`, and that support organization becomes recipient-ready.
- Repeating the operation does not create duplicates.
- Existing default-shipper recipient bindings continue to be created by the current role-assignment signals.
- Removing `Correspondant` later does not automatically remove `Destinataire` or the created recipient role state.
