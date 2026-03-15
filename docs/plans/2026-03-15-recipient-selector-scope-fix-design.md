# Recipient Selector Scope Fix Design

**Date:** 2026-03-15

**Goal:** Make the shipment `Destinataire` selector strict for `destination + shipper`, while ensuring promoted correspondents inherit a real destination scope instead of behaving like global recipients.

## Scope

- Stay on the legacy Django stack only.
- Fix the data model behavior that makes promoted correspondents appear as global recipients.
- Hide non-authorized recipients completely in the shipment create/edit UI when the org-role engine is enabled.
- Keep existing server-side validation as the final gate.
- Provide a safe additive backfill path for existing correspondents.

## Non-Goals

- Do not touch paused Next/React files.
- Do not redesign the `Correspondant` selector itself.
- Do not invent destination scope for contacts that have no reliable destination source.
- Do not change the org-role authorization model or binding semantics.
- Do not broaden the support organization `ASF - CORRESPONDANT` beyond its existing technical role.

## Problem

The current `Correspondant => Destinataire` promotion is structurally incomplete for selector behavior:

- promoted correspondents gain the `Destinataire` tag and recipient role
- but they do not inherit destination scope from the destinations where they are used as `correspondent_contact`
- the shipment recipient payload therefore treats them as global recipients
- the shipment UI also keeps rendering non-matching recipients as visible-but-disabled when the org-role engine is enabled

In practice this produces a noisy and misleading recipient selector. For a chosen pair like `ANTANANARIVO + AVIATION SANS FRONTIERES`, users can see recipients from unrelated countries and correspondents from unrelated destinations.

## Approaches Considered

### 1. UI-only masking

- Remove disabled recipient options from the shipment selector.
- Rejected because promoted correspondents would still be incorrectly global in the data model.

### 2. Data-only backfill

- Synchronize destination scope for correspondents but keep current selector rendering.
- Rejected because the UI would still show non-authorized recipients as disabled clutter.

### 3. Data correction plus strict selector rendering

- Make promoted correspondents inherit destination scope from the destinations referencing them.
- Reuse the same logic in the additive backfill command.
- Render only authorized recipients in the shipment selector when org roles are enabled.
- Approved because it fixes both the underlying data and the user-facing behavior.

## Approved Rules

- A promoted correspondent must inherit the destination scope of every active `Destination` that references that contact as `correspondent_contact`.
- If that set contains exactly one destination, the legacy `destination` field must also be synchronized to that single value.
- If that set contains multiple destinations, the M2M scope is authoritative and the legacy single `destination` field becomes empty.
- If a promoted correspondent is not referenced by any destination, no scope is invented automatically.
- In the shipment recipient selector, when org roles are enabled, only recipients with an active `RecipientBinding` for the selected `shipper + destination` are visible.
- Non-authorized recipients are not shown at all; they are no longer rendered as disabled options.
- The destination correspondent may appear in the recipient selector only if it is truly authorized for that pair.

## Runtime Design

### Correspondent scope resolution

Add a small helper in the correspondent promotion service to compute destination IDs from:

- `Destination.objects.filter(correspondent_contact=contact, is_active=True)`

That helper is used only as a source of truth for promoted correspondent scope. It does not alter unrelated contacts.

### Promotion service behavior

Extend the promotion flow in [`contacts/correspondent_recipient_promotion.py`](/Users/EdouardGonnu/asf-wms/.worktrees/recipient-selector-scope-fix/contacts/correspondent_recipient_promotion.py):

1. verify the contact currently matches `Correspondant`
2. ensure `Destinataire` tag exists and is attached
3. resolve the structural recipient organization as today
4. compute destination IDs from linked destinations where the contact is the actual destination correspondent
5. if destination IDs exist, call `set_contact_destination_scope(contact=contact, destination_ids=...)`
6. ensure or reactivate `OrganizationRoleAssignment(role=RECIPIENT)`

Important detail:

- for `PERSON` contacts attached to `ASF - CORRESPONDANT`, the scope is applied to the person contact, not to the support organization
- this keeps the visible selectable contact scoped correctly without turning the support organization into a synthetic global recipient

### Shipment selector rendering

Update the recipient rendering logic in [`wms/static/scan/scan.js`](/Users/EdouardGonnu/asf-wms/.worktrees/recipient-selector-scope-fix/wms/static/scan/scan.js):

- keep the current destination filter
- keep the pair check based on `binding_pairs`
- keep the destination correspondent recipient as a priority bucket when it matches
- remove the `otherRecipientOptions` bucket entirely when org roles are enabled
- render only:
  - destination correspondent recipient if authorized
  - recipients matching `shipper + destination`

This makes the selector visually strict and removes disabled noise.

### Server-side validation

No new validation layer is needed. Existing server checks in:

- [`wms/forms.py`](/Users/EdouardGonnu/asf-wms/.worktrees/recipient-selector-scope-fix/wms/forms.py)
- [`wms/organization_role_resolvers.py`](/Users/EdouardGonnu/asf-wms/.worktrees/recipient-selector-scope-fix/wms/organization_role_resolvers.py)

already enforce the final constraints on submit.

## Backfill Design

Reuse the existing additive command:

- [`wms/management/commands/backfill_correspondent_recipients.py`](/Users/EdouardGonnu/asf-wms/.worktrees/recipient-selector-scope-fix/wms/management/commands/backfill_correspondent_recipients.py)

The command keeps the same interface:

- `--dry-run`
- `--apply`

But its internal promotion service now also synchronizes destination scope for correspondents linked to destinations.

Expected deployment sequence after merge:

1. `git pull`
2. `python manage.py backfill_correspondent_recipients --apply`
3. reload the PythonAnywhere web app

No schema migration is required.

## Safety Rules

- Scope is derived only from actual destination correspondent assignments.
- Contacts with no reliable destination reference remain unchanged instead of receiving guessed scope.
- Existing recipient role assignments are preserved and only created/reactivated when needed.
- Existing form validation remains authoritative even if a stale client tries to submit an out-of-scope recipient.
- The fix stays additive and idempotent.

## Testing Strategy

Add or extend targeted tests in the existing suites:

- [`wms/tests/core/tests_correspondent_recipient_promotion.py`](/Users/EdouardGonnu/asf-wms/.worktrees/recipient-selector-scope-fix/wms/tests/core/tests_correspondent_recipient_promotion.py)
  - promoted correspondent with one destination gets that scope
  - promoted correspondent with multiple destinations gets all scopes
  - promoted correspondent with no linked destination keeps existing behavior

- [`wms/tests/management/tests_management_backfill_correspondent_recipients.py`](/Users/EdouardGonnu/asf-wms/.worktrees/recipient-selector-scope-fix/wms/tests/management/tests_management_backfill_correspondent_recipients.py)
  - backfill applies scope synchronization
  - rerun is idempotent

- [`wms/tests/shipment/tests_shipment_helpers.py`](/Users/EdouardGonnu/asf-wms/.worktrees/recipient-selector-scope-fix/wms/tests/shipment/tests_shipment_helpers.py)
  - payload reflects scoped promoted correspondents instead of empty global scope

- [`wms/tests/forms/tests_forms_org_roles_gate.py`](/Users/EdouardGonnu/asf-wms/.worktrees/recipient-selector-scope-fix/wms/tests/forms/tests_forms_org_roles_gate.py)
  - strict recipient queryset for `destination + shipper`
  - unrelated recipients are absent, not merely invalid later

## Acceptance Criteria

- With org roles enabled, the shipment `Destinataire` selector shows only recipients truly authorized for the selected `destination + shipper`.
- Non-authorized recipients no longer appear as disabled options.
- A destination correspondent promoted to recipient appears only on the destination(s) where it is actually referenced.
- Promoted correspondents from other destinations no longer appear for unrelated destinations.
- Existing correspondents can be resynchronized with `backfill_correspondent_recipients --apply`.
- Re-running the backfill after synchronization produces no further changes.
