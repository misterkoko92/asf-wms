# Recipient Portal Profile Editing Design

## Goal

Allow a recipient-scoped portal user to edit their shared recipient profile directly from the recipient portal, including main contact details and structure documents, instead of being limited to a read-only summary.

## Current State

- Recipient-scoped users land on `/portal/`, rendered by `portal_dashboard` in `wms/views_portal_orders.py`.
- That surface uses `build_recipient_scope_home_payload` in `wms/application/portal/dashboard_queries.py` and `templates/portal/recipient_scope_home.html`.
- The current recipient scope home is a read-only summary for identity, contacts, documents, and product preferences.
- Shipper-scoped users already have a full recipient maintenance form in `wms/views_portal_account.py` and `templates/portal/recipients.html`.
- The existing shipper recipient form already covers shared structure fields, a single main contact, delivery flags, and structure document upload on creation.

## Problem

Recipient-scoped users can review their structure information but cannot maintain it directly. This blocks a legitimate self-service workflow for recipient organizations and creates an asymmetry between the shipper portal and the recipient portal, even though both surfaces ultimately depend on the same shared recipient runtime data.

## Decision

Keep the recipient home page as a dashboard and add a dedicated recipient-scoped profile-editing page linked from that dashboard.

## Why This Approach

### Recommended approach: dedicated recipient-scoped edit page

- Keeps the recipient home readable and focused on summary information.
- Reuses the same field contract already proven on the shipper recipient form.
- Lets the recipient portal become an operational maintenance surface without mixing edit state into the dashboard route.
- Avoids coupling recipient-scope permissions to shipper-only `AssociationRecipient` list semantics.

### Rejected approach: inline editing on the recipient home

- Turns the dashboard into a large multi-section form.
- Makes success and error handling heavier on the active-scope landing page.
- Increases template complexity on the main portal entrypoint.

### Rejected approach: full CRUD for all recipient referents in this ticket

- The current shipper portal form already models a single main contact rather than full referent management.
- A full contact-graph editor would widen the ticket substantially and create more sync edge cases.
- The approved scope is to reuse the existing “main contact” model first.

## Target UX

### Recipient home page

- Keep the existing summary sections.
- Add a CTA near the identity card header: `Modifier mes informations`.
- Keep the product preference CTA on the preferences card.

### Recipient profile editing page

- New recipient-scoped page under the portal scope.
- Display a form close to the shipper recipient form, but bound to the active recipient organization.
- Allow editing:
  - structure name
  - legal form
  - beneficiary count
  - main contact title, first name, last name, phones, emails
  - address
  - notes
  - notification and delivery-contact flags
  - structure documents
- Keep destination visible but read-only.
- Show current structure documents with upload controls that replace the document of the same type.

## Runtime Design

### Routing

- Add a new recipient-scoped route in `wms/portal_urls.py`.
- Protect it with `portal_scope_required`.
- Restrict access to active `recipient_admin` scope with a bound `ShipmentRecipientOrganization`.

### View

- Add a new recipient-scoped view in `wms/views_portal_account.py`.
- Reuse the existing recipient form extraction and validation helpers where possible.
- Build form defaults from the active `ShipmentRecipientOrganization` and its main active `ShipmentRecipientContact`.
- On POST:
  - validate the form
  - persist shared structure and main contact updates onto the active runtime recipient organization
  - upsert uploaded structure documents through the shared use-case helper
  - redirect back to the same page with a success message

### Persistence

- Keep the recipient scope bound to the existing `ShipmentRecipientOrganization`.
- Do not allow destination reassignment from the recipient portal.
- Update the shared organization contact and one main recipient referent.
- Refresh legacy projections after save so shipper-facing compatibility surfaces remain aligned.
- Reuse `upsert_recipient_structure_documents` for document replacement and scan queueing.

## Data And Rule Constraints

- Destination is read-only because the grant is scoped to one `(organization, destination)` recipient runtime row.
- This ticket edits one main contact, not the full list of recipient referents.
- Shared structure fields and documents must still propagate to shipper and scan/admin surfaces that read the same runtime/canonical data.
- No change to translation or Next/React paused scope.

## Tests

Add or update tests for:

- recipient home CTA presence
- recipient-scoped profile edit page GET
- permission guard for shipper scope
- POST update for structure fields, contact fields, address, and notes
- document upload/replacement on the active recipient organization
- payload propagation back to the recipient home summary
- Bootstrap/UI contract for the new page

## Docs Impact

If the recipient portal becomes an official maintenance surface for recipient shared profile data, update the relevant `docs/repo-reference/` sections covering portal recipient scope behavior and portal/shipment-party shared contracts.
