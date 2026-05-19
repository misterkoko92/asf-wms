# Order Multi-Shipment Preparation Design

**Goal:** Make scan order preparation reliable when orders need one or several shipment dossiers, while preserving document-first workflows.

**Classification:** A. ASF operational need + B. reusable capability.

## Design

Scan order actions must be idempotent by default. If a command already has linked shipments, the quick "create shipment" action opens or completes the existing dossier instead of silently creating another shipment.

The operator can still explicitly create several shipments for a command. When the estimated carton count is above 10, the UI should ask how many shipments to create, defaulting to `ceil(carton_count / 10)`. Ten cartons per shipment is guidance only; operators may choose another count.

Preparation applies fallback weight and volume values for packing calculation when product measurements are missing, and shows warnings for affected products. These fallback values are not written back to product records.

Automatic multi-shipment preparation creates the requested shipment dossiers and distributes generated cartons by batches of 10 by default. Empty shipment dossiers are allowed when explicitly requested, because they support document-first preparation. Empty dossiers must stay non-ready and must remain excluded from planning readiness until real cartons are attached and readiness is explicitly confirmed.

Manual correction remains available through existing shipment dossier editing and the carton view bulk assignment workflow. The scan UI should provide direct links to the relevant filtered carton view from the order or shipment dossier.

## Safety Checks

- Do not mark empty or picking shipments as ready.
- Do not create duplicate shipments from repeated quick scan actions.
- Keep order-to-shipment compatibility through `OrderShipmentLink` and `order.shipment`.
- Keep document print actions truthful to the selected shipment and attached cartons.
- Keep manual carton reassignment guarded by existing shipment lock and destination preassignment checks.
