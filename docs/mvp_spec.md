# ASF WMS Functional Spec (Current)

This document reflects the implemented product behavior as of **February 19, 2026**.

## Scope

- Product catalog with categories, tags, dimensions, weights, and QR codes.
- Lot-level stock with FEFO consumption, quarantine states, and movement traceability.
- Structured storage (`Warehouse` + `Location`).
- Carton preparation and assignment to shipments.
- Shipment creation with destination-driven contact filtering and draft support.
- Public shipment tracking page (token URL) with step-based updates.
- Shipment tracking board for planned+ shipments, with case closure workflow.
- Printable shipment documents and labels.
- CSV/XLS/XLSX imports for key entities.

## Roles

- `admin`: full settings and admin workflows.
- `staff` (scan users): day-to-day WMS operations.
- public tracking actor: can update shipment tracking through QR/token link (no login), with actor identity fields.

## Core domain objects

### Product / ProductLot

- Product identity and physical attributes.
- Lots store quantities, expiry, location, and status (`quarantined`, `available`, `hold`, `expired`).
- FEFO is applied when consuming stock.

### Carton

- `code` (unique), dimensions, location, optional shipment link.
- Status lifecycle:
  - `draft` (Cree)
  - `picking` (En preparation)
  - `packed` (Pret)
  - `assigned` (Affecte)
  - `labeled` (Étiquette)
  - `shipped` (Expedie)
- Status events are persisted (`CartonStatusEvent`).

### Shipment

- Core fields: `reference`, `tracking_token`, destination, shipper/recipient/correspondent refs.
- Overlay flags/metadata: `is_disputed`, `disputed_at`, `ready_at`, `archived_at`, `closed_at`, `closed_by`.
- Shipment status lifecycle:
  - `draft` (Creation)
  - `picking` (En cours)
  - `packed` (Pret)
  - `planned` (Planifie)
  - `shipped` (Expedie)
  - `received_correspondent` (Recu escale)
  - `delivered` (Livre)

### ShipmentTrackingEvent

- Step-level event log with actor name/structure/comments.
- Steps:
  - `planning_ok`
  - `planned`
  - `moved_export`
  - `boarding_ok`
  - `received_correspondent`
  - `received_recipient`

### Contacts

- Tags drive role usage in shipment forms (`Expéditeur`, `Destinataire`, `Correspondant`, etc.).
- `destinations` (M2M): destination scoping for shippers/correspondents.
- `linked_shippers` (M2M): shipper scoping for recipients.
- Recipient governance:
  - linked shippers required when creating a recipient contact.
  - default shipper `AVIATION SANS FRONTIERES` auto-added when available.

## Shipment workflow (implemented)

1. In `Créer une expédition`, destination is selected first.
2. Shipper list is filtered by destination (explicit match + global contacts).
3. Recipient list is filtered by selected shipper (explicit linked shippers + global recipients).
4. Correspondent list is destination-scoped and forced to the destination configured correspondent; if destination has no configured correspondent, the list is empty.
5. Details section appears only after destination + shipper + recipient + correspondent are selected.
6. User can:
   - create final shipment immediately
   - save draft (`EXP-TEMP-XX`)
   - save draft and jump to multi-product packing.

Draft behavior:

- Draft reference format: `EXP-TEMP-XX`.
- When shipment leaves `draft`, temporary reference is automatically promoted to a final reference.

## Status and lock rules

- Shipment readiness (`draft`/`picking`/`packed`) is synchronized from carton states.
- Labeling is explicit (button action), not automatic.
- Removing an assigned/labeled carton from shipment returns carton to `packed`.
- `planned` and later shipment statuses lock carton modifications.
- Dispute (`is_disputed=true`) blocks tracking progression and carton updates.
- Resolving dispute resets shipment to `packed`; shipped cartons are reset to `labeled` when needed.

## Tracking board and closure

- `scan/shipments-tracking/` lists shipments with status in:
  - `planned`, `shipped`, `received_correspondent`, `delivered`
- Table includes milestone timestamp columns (planned, boarding OK, shipped, received escale, delivered).
- Filters:
  - planned week (`planned_week`)
  - closed case filter (`exclude`/`all`)
- Case closure writes `closed_at`/`closed_by` when all required milestones are complete and shipment is not disputed.

## Observability (phase 3)

- `scan/dashboard/` provides operational cards for:
  - email queue health (`pending`, `processing`, `failed`, stale processing timeout),
  - workflow blockages (>72h),
  - SLA breach ratios per tracking segment.
- Workflow transitions are logged as structured JSON on logger `wms.workflow`.

## Non-goals (current perimeter)

- Full TMS planning automation.
- Marketing CRM workflows.
- External cross-application master contact service (still a roadmap topic).

## Data and audit

- Shipment/carton transitions are traceable by status events and tracking events.
- Minimal personal data is stored for operational contacts.
