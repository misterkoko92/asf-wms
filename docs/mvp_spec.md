# ASF WMS Functional Spec (Current)

This document reflects the implemented product behavior as of **February 19, 2026**.

## Scope

- Product catalog with categories, tags, dimensions, weights, and QR codes.
- Lot-level stock with FEFO consumption, quarantine states, and movement traceability.
- Structured storage (`Warehouse` + `Location`).
- Carton preparation and assignment to shipments.
- Shipment creation with destination-driven contact filtering and document-first support.
- Public shipment tracking page (token URL) with step-based updates.
- Shipment tracking board for planned+ shipments, with case closure workflow.
- Printable shipment documents and labels.
- CSV/XLS/XLSX imports for key entities.

## Roles

- `admin`: full settings and admin workflows.
- `staff` (scan users): day-to-day WMS operations.
- `portal shipper admin`: authenticated portal scope for orders, account maintenance, and shipper-owned recipient relation management.
- `portal recipient admin`: authenticated portal scope for recipient shared data maintenance on the existing `/portal/` shell.
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

- `contacts.Contact` is the unique backbone for organizations and people.
- Shipment forms use the dedicated shipment-party registry:
  - `ShipmentShipper`
  - `ShipmentRecipientOrganization`
  - `ShipmentRecipientContact`
  - `ShipmentShipperRecipientLink`
  - `ShipmentAuthorizedRecipientContact`
- Recipient governance:
  - recipient availability requires an active shipment-party authorization chain.
  - default shipper automation is handled through shipment-party services.
  - recipient shared data is canonical on the shipment-party runtime and propagated back to legacy portal compatibility rows only as a projection.

## Portal access model (implemented)

- `/portal/` uses an active scope resolved from explicit `PortalAccessGrant` rows, with a legacy `AssociationProfile` fallback while shipper access remains in transition.
- A single user can own shipper and recipient scopes; when multiple scopes exist, `/portal/scope-select/` binds the active scope in session.
- Shipper scopes keep order and billing flows plus shipper-owned recipient relation management.
- Recipient scopes land on a recipient home for one `ShipmentRecipientOrganization` and can maintain shared structure data, recipient contacts, structure documents, and product preferences.
- Scan/admin, shipper portal, recipient portal, and the mirrored UI API are expected to converge on the same shipment-party write path.

## Shipment workflow (implemented)

1. In `Créer une expédition`, destination is selected first.
2. Shipper list is filtered by validated shipment-party eligibility on the selected destination.
3. Recipient list is filtered by active shipment-party links and authorized recipient contacts for the selected shipper and destination.
4. Correspondent list is destination-scoped and forced to the destination configured correspondent; if destination has no configured correspondent, the list is empty.
5. The minimum required data to create a shipment is destination + shipper + recipient + correspondent.
6. Details section appears after those four fields are selected.
7. User can create a shipment with zero cartons and complete the physical part later.
8. The shipment receives its final reference immediately at creation time, including the document-first flow.
9. User can jump directly to multi-product packing after creation; this still starts from the final shipment reference.

Creation behavior:

- `carton_count` and total weight can stay empty at creation time.
- When no carton is linked yet, shipment status stays `draft` (`Creation`) with a final reference.
- Carton count and total weight are derived from linked cartons once cartons are added.

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
