# Django Admin Recipient Canonical Models Design

## Goal

Expose the canonical recipient and portal access runtime in Django admin without reopening unsafe legacy mutations.

## Scope

- register canonical models that now matter for recipient portal and contact operations:
  - `PortalAccessGrant`
  - `ShipmentRecipientOrganization`
  - `RecipientProductPreference`
  - `RecipientStructureDocument`
- keep `AssociationRecipient` available for inspection, but make it read-only in admin

## Design

- `AssociationRecipient` stays a compatibility projection. Django admin must not be a write path for it anymore.
- canonical models get focused `ModelAdmin` classes with:
  - searchable list views
  - useful filters
  - `autocomplete_fields` on heavy foreign keys
  - read-only metadata timestamps
- editing is intentionally limited on existing canonical rows:
  - portal grants: review and activation state stay editable, scope identity locks after creation
  - recipient organizations: status flags stay editable, `(organization, destination)` locks after creation
  - recipient product preferences: target identity locks after creation, operational preference fields stay editable

## Expected Outcome

- Django admin reflects the current canonical recipient/portal model, not only the legacy projection
- admins can inspect and triage the right objects
- accidental drift through legacy `AssociationRecipient` edits is reduced
