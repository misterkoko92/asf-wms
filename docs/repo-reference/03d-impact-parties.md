# Parties Impact Map

Use this file when touching any actor / contact / organization / recipient / shipment-party behavior.

Read this file for changes involving:

- contacts
- organizations
- recipients
- shippers
- correspondents
- consignee / destination actors
- shipment-party roles
- portal recipient management
- portal contact sync
- contact merge / deduplication
- permissions linked to parties
- default actor selection in shipment forms
- recipient compliance data
- recipient documents
- party graph rebuild / reconciliation
- actor labels shown in UI or documents

Party logic is highly transversal. Small changes can silently affect many workflows.

---

## Also Read

Depending on the change, also read:

- `03b-impact-portal.md` — portal actor management / external users
- `03c-impact-shipments.md` — shipment forms / actor assignment
- `03e-impact-print-documents.md` — labels / customs / displayed parties
- `03g-impact-shared-ui-api.md` — mirrored APIs / selectors / payloads
- `03h-impact-email-events.md` — notifications using contacts
- `04-shared-contracts.md` — shared selectors / labels / filters

If unsure, read more than one file.

---

## Critical Invariants

These rules must remain true unless explicitly redesigned.

### Scope Integrity

Recipient organizations may require destination-aware scoping.

Use:

`(organization, destination)`

Do not assume global organization-only scope.

### Identity Integrity

- merged contacts must preserve references where required
- linked records must not orphan shipments/orders
- duplicates must not become active conflicting identities

### Authorization Integrity

- default or linked authorizations must remain unique where required
- inactive actors must not gain unintended access

### Sync Integrity

Portal changes and admin/internal changes must not drift into conflicting truths.

### Display Integrity

Printed labels, shipment forms, and UI actor names must reflect canonical data.

---

## Always Check

### Runtime Sources

- `wms/portal_recipient_sync.py`
- `wms/shipment_party_registry.py`
- `wms/shipment_party_setup.py`
- `wms/shipment_party_rules.py`
- `wms/view_permissions.py`

### Modern Boundaries

- `wms/parties/`
- `wms/application/parties/`

### Domain Sources

- `wms/models_domain/portal.py`
- `wms/models_domain/shipment_parties.py`

### Admin / Operational Surfaces

- `wms/views_scan_admin.py`
- `wms/scan_admin_contacts_cockpit.py`
- `wms/admin_contacts_merge_service.py`

### Forms / UI

- `wms/forms_admin_contacts_contact.py`
- `wms/shipment_form_helpers.py`
- shipment create/edit forms using actor selectors
- `wms/views_portal_*` recipient pages
- related templates under `templates/portal/` and `templates/scan/`

---

## Ask Yourself

### Data Integrity Questions

- does merge preserve all needed links?
- does dedup create hidden duplicates elsewhere?
- can inactive contacts still be selected?
- do edits preserve historical references if required?

### Shipment Questions

- will shipment forms now show different shippers or recipients?
- did default actor resolution change?
- do shipment labels still display correct names?

### Portal Questions

- do portal users see the same recipient truth as internal users?
- did portal self-service break sync assumptions?
- are actor permissions still correct?

### Permission Questions

- who gains access because of this change?
- who loses access unexpectedly?
- are validations still enforced?

### UX Questions

- can operators still find the right contact quickly?
- did selector usability regress?
- did duplicate names become confusing?

---

## Precision Checks

### If Editing Contact Merge Logic

Also verify:

- `wms/admin_contacts_merge_service.py`
- related admin tests
- shipment references to merged contacts
- portal linked accounts if applicable

### If Editing Recipient Sync

Also verify:

- `wms/portal_recipient_sync.py`
- portal recipient pages
- shipment create/edit selectors
- downstream labels/documents

### If Editing Party Registry / Rules

Also verify:

- `wms/shipment_party_registry.py`
- `wms/shipment_party_setup.py`
- `wms/shipment_party_rules.py`
- shipment creation forms
- print outputs

### If Editing Canonical Graph / Rebuild

Also verify:

- `wms/parties/rebuild.py`
- `wms/management/commands/rebuild_recipient_party_graph.py`

Run dry-run first when appropriate:

`rebuild_recipient_party_graph --dry-run`

### If Editing Compliance Fields / Documents

Also verify:

- scan contacts surfaces
- recipient validation dossier
- uploaded documents visibility
- permissions around sensitive files

---

## Run First

Choose nearest tests.

### High Value

- `wms/tests/portal/tests_portal_recipient_sync.py`
- `wms/tests/portal/tests_portal_shipment_parties.py`

### Admin / Contacts

- `wms/tests/views/tests_views_scan_admin.py`
- admin contact merge tests

### Cross Flow

- nearest shipment form tests
- nearest portal tests

---

## Known Traps

### Hidden Duplicate Trap

Two contacts look merged but both remain selectable elsewhere.

### Wrong Default Trap

New shipments auto-select wrong shipper/recipient.

### Permission Leak Trap

A user gains access through stale role links.

### Historical Break Trap

Old shipments lose readable actor names or references.

### Portal Drift Trap

Portal recipient data diverges from internal canonical truth.

### Destination Scope Trap

Organization-level lookup used where destination-level lookup is required.

---

## Docs To Update

If behavior changed, review:

- `docs/mvp_spec.md`
- `docs/repo-reference/02-key-flows-and-living-tests.md`
- `docs/repo-reference/04-shared-contracts.md`

---

## Final Rule

If changing parties data, assume shipment behavior is affected until proven otherwise.
