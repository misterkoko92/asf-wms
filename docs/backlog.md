# Backlog

This backlog is aligned with the current application state (updated February 19, 2026).

## Delivered baseline (kept for tracking)

- Product catalog CRUD, category tree, tags, dimensions, and QR generation.
- Product imports (CSV/XLS/XLSX) with update flows.
- Warehouse/location management and stock movement audit trail.
- Carton lifecycle with explicit labeling and shipment linkage.
- Shipment lifecycle with status sync from cartons and tracking events.
- Public QR/token shipment tracking page.
- "Suivi des expeditions" board with filters, milestone dates, and case closure.
- Contact scoping for shipment creation:
  - destinations for shippers/correspondents
  - linked shippers for recipients
  - default recipient shipper enforcement.

## Short-term priorities

- Strengthen role separation for tracking updates (public actors vs internal staff actions).
- Add functional dashboards for bottlenecks (shipments blocked, disputed, delayed).
- Add explicit audit views for dispute history and resolution reasons.
- Expand regression tests around high-volume contact filtering and shipment form sequencing.

## Mid-term priorities

- Integration with scheduling/planning tools (flight planning synchronization).
- Better operational analytics (lead time by step, closure SLA, dispute aging).
- Multi-language and localization improvements for scan UI messages.
- Offline scan improvements beyond current service-worker cache scope.

## Strategic options

- Study a dedicated contacts application/service shared across missions (WMS, marketing, other operations).
- Define data ownership, synchronization contracts, and migration path before extraction.
