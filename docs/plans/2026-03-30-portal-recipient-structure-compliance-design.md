# Portal Recipient Structure Compliance Design

**Date:** 2026-03-30

## Goal

Extend the legacy Django portal recipient flow so each newly created recipient structure captures the compliance data now required by operations:
- mandatory `Preuve d'enregistrement`
- mandatory `Statut`
- mandatory `Forme juridique`
- mandatory `Nombre de beneficiaires`
- controlled `Pays` selection from a world-country list

The same data must then be visible from `scan/contacts` without creating a second source of truth.

## Context

The current portal recipient page at `/portal/recipients/` is a manually managed form in `wms/views_portal_account.py`. It stores recipient data on `AssociationRecipient`, then synchronizes the operational structure and contact records through `wms/portal_recipient_sync.py`.

That sync already creates the operational recipient structure used by shipment-party logic and by `scan/admin/contacts`. The impact map confirms this is not a presentation-only change:
- portal recipient edits propagate into shipment eligibility
- operational admins inspect and validate the resulting structure in `scan/contacts`
- reusing an existing recipient structure must not create conflicting copies of the same structure metadata

The design therefore has to preserve one canonical structure record once the recipient is synchronized.

## Constraints

### Product constraints

- the two uploads are mandatory only when creating a recipient
- editing an existing recipient must not force re-upload
- if the portal reuses an existing recipient structure, the existing structure metadata and documents should remain the source of truth
- `scan/contacts` must expose the same structure information to operators

### Repository constraints

- legacy Django only
- no translation work
- no Next/React changes
- keep upload validation and antivirus queue behavior aligned with the existing document flows

### Engineering constraints

- avoid duplicating canonical structure data across multiple portal recipient rows
- keep country selection shared between portal and scan forms
- preserve current shipment-party validation workflow

## Approaches Considered

### 1. Store everything only on `AssociationRecipient`

Idea:
- add legal form, beneficiary count, and both uploaded files directly on portal recipients
- let `scan/contacts` read those values indirectly through the synced portal recipient

Pros:
- smallest schema change
- lowest short-term implementation cost

Cons:
- duplicates canonical structure data when multiple shippers reference the same structure
- documents become attached to a portal row instead of the operational structure
- `scan/contacts` would depend on a portal-specific record rather than the structure it actually manages

### 2. Store canonical structure metadata on the synchronized organization, recommended

Idea:
- keep portal recipient inputs on create/update
- synchronize legal form and beneficiary count onto the canonical organization contact
- attach recipient-structure documents to that canonical organization contact through a dedicated recipient-structure document model

Pros:
- one operational source of truth for both portal and scan
- structure reuse remains coherent
- admin validation in `scan/contacts` sees the same canonical data

Cons:
- requires sync, CRUD, and merge updates
- slightly wider schema change than option 1

### 3. Introduce a dedicated one-to-one recipient structure profile

Idea:
- create a new profile model linked one-to-one with the synchronized organization
- store legal form, beneficiary count, and documents there

Pros:
- clean separation from generic contact data
- flexible if many future compliance fields are expected

Cons:
- more plumbing for this ticket
- more indirection in scan/admin rendering and merge logic

## Recommended Decision

Take approach 2.

Canonical structure metadata should live on the synchronized organization contact, while recipient-structure documents should be stored in a dedicated model linked to that organization contact.

This keeps:
- one canonical operational structure
- one canonical set of compliance documents
- one display path for `scan/contacts`

without making `AssociationRecipient` the long-term owner of structure compliance state.

## Target Design

## 1. Portal form layout and interaction

In `templates/portal/recipients.html`:
- keep the recipient form on the legacy template
- reshape the top structure row into three fields on the same line:
  - `Nom de la structure`
  - `Forme juridique`
  - `Nombre de beneficiaires`
- make `Forme juridique` a required select with:
  - `Association`
  - `Secteur prive`
  - `Publique`
  - `Autre`
- make `Nombre de beneficiaires` a required numeric input

The two portal switch groups must render with the control at the start of the line and the text on the right:
- `Reutiliser une structure existante`
- switches in the `Options` block

This orientation change should be implemented as a portal-scoped switch layout variant so other scan/admin switches do not regress.

## 2. Country selection

Replace the free-text `Pays` input with a shared select populated from a repository-local world-country list.

Recommendation:
- add one shared module that exposes country choices in French-friendly display order
- use that same choice source in both portal recipients and `ContactCrudForm`
- keep `France` as the default selected value where the form currently defaults to France

Using a repository-local list is preferred over adding a new dependency for this ticket because:
- the repository currently has no country-choice package in use
- the behavior only needs stable select options, not locale-aware country services

## 3. Canonical data ownership

### Organization contact

Add canonical structure fields on `contacts.Contact` for organization contacts:
- `legal_form`
- `beneficiary_count`

These values should be populated during portal recipient sync and edited from `scan/contacts`.

`AssociationRecipient` remains the portal-side input record and synchronization trigger, not the canonical owner of those two fields.

### Recipient structure documents

Add a new document model for recipient-structure compliance documents, linked to the canonical organization contact.

Recommended shape:
- foreign key to `contacts.Contact`
- document type limited to:
  - `registration_proof`
  - `statutes`
- file
- scan status/message/timestamp
- review status
- uploaded by / uploaded at

This model should reuse the same upload validation and antivirus queue conventions already used by account and order documents.

## 4. Creation-time document rule

The portal creation flow must require both files:
- `Preuve d'enregistrement`
- `Statut`

This requirement applies only to recipient creation.

Editing an existing recipient:
- does not require re-upload
- may allow replacing documents later as a follow-up enhancement, but replacement is not required for this ticket

When `reuse_existing_structure` results in an actual reuse of the canonical structure:
- keep the existing structure documents
- do not require the user to upload the two files again

This avoids duplicate document sets for the same operational structure.

## 5. Portal create/update flow

In `wms/views_portal_account.py`:
- extend default/extracted/bound form data with:
  - `legal_form`
  - `beneficiary_count`
- validate both fields on create and update
- validate both uploaded files on create only, unless the request resolves to an already reused canonical structure
- keep email and notification rules unchanged

In `AssociationRecipient`, keep enough portal-side fields to round-trip the create/edit form cleanly. The portal row may mirror the legal-form and beneficiary-count values for edit convenience, but the canonical operational value remains the synchronized organization contact.

## 6. Sync behavior

In `wms/portal_recipient_sync.py`:
- when a structure is created or reused, push `legal_form` and `beneficiary_count` onto the canonical organization contact
- preserve the current destination and shipper-link logic
- if a canonical structure is reused, keep its documents attached to that structure instead of copying them onto a new row

The sync must remain safe for repeated updates:
- later portal edits update the canonical organization values
- they do not create duplicate document rows for the same document type unless replacement is explicitly implemented

## 7. `scan/contacts` visibility

In `templates/scan/includes/admin_contacts_contact_form.html` and `ContactCrudForm`:
- display and edit `Forme juridique`
- display and edit `Nombre de beneficiaires`
- replace the free-text `Pays` input with the same shared country select

Also add a read-only structure-document panel for recipient organizations:
- show the two document types when present
- show scan status and scan message if relevant
- provide an operator-visible link to the uploaded file

This keeps the operational validation screen aligned with the new portal requirements.

## 8. Contact merge behavior

Because the canonical fields now live on the organization contact, contact merges must preserve them.

Update merge rules so that:
- `legal_form` and `beneficiary_count` survive merges
- recipient-structure documents are reassigned or merged onto the surviving contact
- duplicate document rows for the same contact and type are handled deterministically

The existing merge constraint that recipient structures must remain on the same destination still applies.

## 9. Error handling and operator feedback

Portal validation errors should be explicit:
- missing legal form
- missing beneficiary count
- missing registration proof on create
- missing statutes on create
- invalid country selection

Upload failures should reuse the repository's existing validation style:
- unsupported file type
- file too large
- antivirus quarantine status once queued

`scan/contacts` should not block editing for missing documents in this ticket. It only needs to expose the current state clearly.

## 10. Testing strategy

### Portal tests

Add or extend tests to cover:
- create fails without legal form
- create fails without beneficiary count
- create fails without one or both required documents
- edit succeeds without re-upload
- country select renders instead of free text
- switch layout contract remains stable on the portal page

### Sync tests

Add or extend tests to cover:
- legal form and beneficiary count copied onto the canonical organization contact
- reused structure keeps canonical document ownership
- new structure gets the required two document rows on successful create

### Scan tests

Add or extend tests to cover:
- `scan/contacts` renders legal form and beneficiary count
- `scan/contacts` uses the shared country select
- recipient-structure documents appear in the admin contact form when present

### Regression focus

Keep existing shipment-party and recipient-validation tests green to confirm:
- destination sync still works
- allowed shipper links still work
- pending validation workflow is unchanged except for the richer visible data

## Migration impact

Expected schema changes:
- add contact fields for `legal_form` and `beneficiary_count`
- add a new recipient-structure document model
- possibly add portal-side mirror fields on `AssociationRecipient` if needed for edit round-tripping

No route changes are required.

## Non-Goals

- reopening translation work
- changing the recipient validation workflow itself
- replacing the legacy portal form with Django forms
- adding a generic document manager to all contact types
- introducing a new external dependency only to source country choices
