# Shipments, Tracking, Disputes, And Workflow Projection Contracts

Read this file when touching shipment readiness, QR tracking, disputes, workflow projections, shipment timing, or tracking access.

---

## Shipment Ready Confirmation Contract

### Primary runtime sources

- `wms/shipment_status.py`
- `wms/views_scan_shipments.py`
- `wms/views_scan_shipments_support.py`
- `templates/scan/includes/shipment_dossier_header.html`
- `wms/planning/sources.py`

### Current contract

- Helper pair: `shipment_can_be_confirmed_ready(shipment)` and `confirm_shipment_ready(shipment, user)`.
- Confirmation is explicit dossier-level action after physical preparation.
- Valid only while shipment editable and every carton is `ASSIGNED` or `LABELED`.
- Linked orders require clean order-level attestations.
- Shipper-received cartons require conform inbound association receipt and clean packing lists.
- Order linkage resolves through `OrderShipmentLink`; `order.shipment` is compatibility only.
- Confirmation relabels remaining `ASSIGNED` cartons to `LABELED`, sets shipment to `PACKED`, and stamps `ready_at`.
- Planning eligibility remains restricted to `PACKED` and `PLANNED`; `PICKING` stays excluded.
- Prepared shipments without cartons may carry `planned_carton_count`, but readiness still depends only on real attached cartons. A planned count alone must not satisfy ready confirmation.

### Maintenance rule

- If readiness semantics change, update helper, dossier view, header actions, planning source filter, and tests.
- Keep this shipment-level and operator-triggered.

---

## Shipment QR Tracking Access Contract

### Primary runtime sources

- `wms/models_domain/shipment.py`
- `wms/shipment_tracking_access.py`
- `wms/shipment_tracking_handlers.py`
- `wms/views_scan_shipments.py`
- `wms/views_shipment_tracking_access.py`
- `templates/scan/shipment_tracking.html`
- tracking email templates
- `wms/static/scan/modules/shipment-tracking.js`

### Current contract

- `/scan/shipment/track/<tracking_token>/` is public to open but authenticated to mutate.
- Anonymous QR scan can view gateway, documents, and history, but cannot create `ShipmentTrackingEvent`.
- Contact roles use `Contact.asf_id`; volunteers use `VolunteerProfile.volunteer_id`.
- Users authenticate through QR tracking login before continuing.
- Restricted grants require active and non-expired status.
- Login and lost-code recovery are throttled.
- Unknown emails remain indistinguishable in recovery.
- No-identifier flow creates restricted pending identity and pending review object.
- Before `BOARDING_OK`, escale defaults to `CDG`; after boarding, destination IATA.
- Correspondent/recipient receipt scans require photo proof or manual fallback.
- Role-to-status authorization is server-side.

### Maintenance rule

- If identity, recovery, throttling, grants, pending creation, proof, or authorization changes, update tests and contract together.
- Keep this on legacy Django scan stack while Next/React migration remains paused.

---

## Local Shipment Dispute Center Contract

### Primary runtime sources

- `wms/models_domain/shipment.py`
- `wms/shipment_tracking_handlers.py`
- `wms/views_scan_shipments.py`
- `wms/views_scan_shipments_support.py`
- `wms/shipment_view_helpers.py`
- dispute templates

### Current contract

- `Shipment` keeps structured dispute fields.
- `Shipment.is_disputed` remains active lock signal.
- Opening a dispute requires valid reason and stores owner/status/due date.
- Resolving requires `dispute_resolution_notes`.
- `scan/shipment_tracking` is edit surface.
- `scan/shipments_tracking` is prioritization surface.
- Filters `dispute=open|overdue|unassigned` stay aligned with row metadata.

### Maintenance rule

- If dispute vocabulary or fields change, update validation, templates, list filters, and tests.

---

## Shipment Workflow Projection Contract

### Primary runtime sources

- `wms/models_domain/integration.py`
- `wms/workflow_projection.py`
- `wms/signals.py`
- `wms/management/commands/rebuild_workflow_projections.py`
- `api/v1/views.py`

### Current contract

- `ShipmentWorkflowProjection` is derived read model with one row per shipment dossier.
- Recomputed from shipment, tracking events, disputes, and closure.
- Stable segments include creation, planned-to-boarding, boarding-to-correspondent, correspondent-to-delivery, delivery-to-close, closed.
- Delay states: `on_time`, `new`, `persistent`, `critical`.
- Local refresh happens on shipment save and tracking-event creation.
- Full rebuild command: `python manage.py rebuild_workflow_projections`.

### Maintenance rule

- If timing, segment vocabulary, dispute projection, or delay classification changes, update helper, API endpoint, rebuild command, tests, and repo-reference.

---

## Destination Aggregates Contract

### Primary runtime sources

- `wms/workflow_projection.py`
- `wms/scan_dashboard_destination_risk.py`
- `wms/views_scan_dashboard.py`
- `api/v1/ui_views.py`
- `api/v1/views.py`

### Current contract

- Destination aggregate groups `ShipmentWorkflowProjection` rows.
- Filters apply before grouping.
- Default ordering is operational: critical, disputes, oldest open segment, destination label.
- Dashboard consumes top 5 and links to `scan/shipments_tracking?destination=<id>`.
- Destination-week aggregate uses `(destination, ISO week)` anchored on `planned_at`.

### Maintenance rule

- If aggregate fields, ranking, period anchor, or formatting changes, update helpers, dashboard/API adapters, tests, and repo-reference.
