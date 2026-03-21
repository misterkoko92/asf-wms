# Admin Contacts CRUD Design

## Goal

Add lightweight admin CRUD workflows directly on the legacy Django `scan/admin/contacts/` page so staff can create, edit, deactivate, and merge destinations and contacts without returning to Django admin, while keeping the canonical `Contact` and `Shipment*` models as the only source of truth.

## Constraints

- stay on the legacy Django stack only
- do not reintroduce any generic `org-roles` layer
- keep `views_scan_admin.py` thin
- avoid a new CRUD monolith by splitting forms, duplicate detection, and workflow services
- prefer soft-deactivation over hard delete for user-driven contact cleanup

## Scope

### New UI sections

Add two new closed-by-default collapse cards before `Recherche et filtres`:

- `Creation de destination`
- `Creation de contact`

Both cards stay on the same page, post back to `scan_admin_contacts`, and reopen automatically after validation errors, duplicate review, or edit mode.

### New contact-directory actions

In `Repertoire des contacts`, add an `Actions` column exposing:

- `Modifier`
- `Desactiver`
- `Fusionner`

The action chooser should render as a light inline control (`Voir les choix`) and reveal the matching action form without leaving the page.

## Canonical Data Model

No new data engine is introduced.

- `contacts.Contact`
- `contacts.ContactAddress`
- `contacts.ContactCapability`
- `wms.Destination`
- `wms.ShipmentShipper`
- `wms.ShipmentRecipientOrganization`
- `wms.ShipmentRecipientContact`
- `wms.ShipmentShipperRecipientLink`
- `wms.ShipmentAuthorizedRecipientContact`

The page only orchestrates writes into those models.

## Requested Behaviors

## Destination Creation

The destination form should capture:

- `Ville*`
- `Code IATA*`
- `Pays*`
- `Correspondant par defaut`
- `Active`

Duplicate detection should run before applying changes.

Strong duplicate signals:

- same `iata_code`
- same normalized `city + country`

Fuzzy suggestion signals:

- normalized city close enough after case, accent, punctuation, and minor spelling tolerance

Resolution options:

- `Remplacer`: keep the existing destination row, overwrite its master fields with form values
- `Fusionner`: keep the existing destination row, only fill empty fields and attach missing relationships
- `Dupliquer`: create a second row only when no hard uniqueness conflict exists

## Contact Creation

The contact form starts with `Type metier*` and reveals dynamic sections by type:

- `Expediteur`
- `Destinataire`
- `Correspondant`
- `Donateur`
- `Transporteur`
- `Benevole`

Shared fields:

- contact nature (`personne` or `structure`) when relevant
- structure identity or person identity
- title, first name, last name
- email, phone, secondary coordinates
- address block
- notes
- active flag

Type-specific behaviors:

- `Expediteur`
  - creates or updates the organization contact
  - creates or updates the default person referent
  - creates or updates `ShipmentShipper`
  - optionally scopes to all destinations or selected destinations

- `Destinataire`
  - creates or updates the destination-side organization
  - creates or updates the referent person
  - creates or updates `ShipmentRecipientOrganization`
  - creates or updates `ShipmentRecipientContact`
  - creates or updates allowed `ShipmentShipperRecipientLink`
  - can set a default authorized referent per link

- `Correspondant`
  - creates or updates the support/correspondent structure and referent
  - binds it to one destination
  - marks the corresponding `ShipmentRecipientOrganization` as active correspondent
  - updates `Destination.correspondent_contact`

- `Donateur`
  - creates or updates a contact
  - creates or updates `ContactCapability(donor)`

- `Transporteur`
  - creates or updates a contact
  - creates or updates `ContactCapability(transporter)`

- `Benevole`
  - requires a person contact
  - creates or updates `ContactCapability(volunteer)`

Duplicate detection should run before applying changes.

Strong duplicate signals:

- exact `asf_id`
- same normalized organization name
- same normalized person identity within the same organization
- matching email or phone

Fuzzy suggestion signals:

- close organization name
- close person name paired with same or similar organization

Resolution options:

- `Remplacer`: keep the existing contact row, overwrite the master fields, then attach or update missing shipment/capability records
- `Fusionner`: keep the existing contact row, fill only missing fields, then attach missing shipment/capability records
- `Dupliquer`: force a fresh contact only when no unique-constraint conflict blocks it

## Contact Directory Actions

### Edit

`Modifier` reuses the same `Creation de contact` card in edit mode.

- the card opens automatically
- current values are prefilled
- the save button changes label to indicate update mode
- duplicate warnings exclude the record currently being edited

### Deactivate

`Supprimer` should be implemented as `Desactiver`, not hard delete.

Rationale:

- shipment relations use `PROTECT` and should not be broken by UI cleanup
- soft deactivation is reversible and safer
- existing data can remain linked historically

Expected effect:

- set `is_active=False` on the selected contact
- optionally deactivate directly dependent shipment-party rows when that is the canonical meaning of the action
- never cascade a hard delete from the UI

### Merge

`Fusionner` keeps one target record and retires one source record.

Allowed only when source and target are compatible:

- same contact kind (`organization` or `person`)
- same destination scope when merging destination-specific shipment recipient structures
- no irreconcilable unique constraint conflict

Merge flow:

- move or deduplicate addresses
- merge capabilities
- reassign shipment-party relations
- preserve existing target data unless explicit replacement mode is chosen
- deactivate the source contact after successful reassignment

## Anti-Monolith Implementation Shape

Do not concentrate all behavior in `views_scan_admin.py` or one giant helper.

Recommended split:

- `wms/forms_admin_contacts_destination.py`
  - destination create/edit/duplicate-review forms
- `wms/forms_admin_contacts_contact.py`
  - contact create/edit/duplicate-review forms
- `wms/admin_contacts_duplicate_detection.py`
  - normalization helpers
  - fuzzy matching
  - duplicate suggestion builders
- `wms/admin_contacts_destination_service.py`
  - create/edit/replace/fuse destination workflows
- `wms/admin_contacts_contact_service.py`
  - create/edit/deactivate contact workflows
  - contact type specific orchestration
- `wms/admin_contacts_merge_service.py`
  - contact merge logic and relation reassignment
- `wms/views_scan_admin.py`
  - parse POST action
  - delegate to services
  - manage success/error messages
  - prepare template context only

The existing `wms/scan_admin_contacts_cockpit.py` should remain focused on the shipment cockpit, not absorb generic CRUD concerns.

## Duplicate Review UX

The page should use a two-step confirmation pattern:

1. user submits the form normally
2. server detects probable duplicates and re-renders the same card opened
3. the card shows:
   - matching candidates
   - why each candidate matched
   - a required resolution selector
4. user confirms `Remplacer`, `Fusionner`, or `Dupliquer`
5. server applies the chosen workflow transactionally

This keeps duplicate resolution authoritative on the server and avoids hiding business rules in JavaScript.

## Error Handling

- validation errors stay attached to the open card
- duplicate resolution choices are required before applying a destructive or merging workflow
- hard uniqueness conflicts still fail explicitly, even after a user selects `Dupliquer`
- merge operations run in transactions
- partial updates are not allowed for shipment-party rewiring

## Risks

- contact merge semantics can silently damage shipment-party wiring if reassignment is incomplete
- destination replacement can accidentally mutate a live stopover if duplicate review is too permissive
- a single overstuffed form partial would become a maintenance hotspot, so the template should be composed from smaller includes where useful
- edit and create modes must share code without becoming branch-heavy and unreadable

## Testing

- form tests for required fields per contact type
- duplicate-detection tests for exact and fuzzy matching
- service tests for `replace`, `merge`, and `duplicate`
- merge tests for shipment-party reassignment
- view tests for card rendering, collapse defaults, edit mode, duplicate-review flow, and action selectors
- JS tests or DOM assertions for dynamic field visibility and inline action reveal

## Recommendation

Implement this as a thin-page orchestrator with dedicated services per concern. The only shared logic should be duplicate normalization/matching; destination workflows, contact workflows, and merge workflows should stay separate to prevent a new admin-contacts monolith.
