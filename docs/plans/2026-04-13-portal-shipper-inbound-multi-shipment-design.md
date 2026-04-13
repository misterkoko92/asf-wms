# Portal Shipper Inbound Multi-Shipment Design

## Goal

Support two new shipper workflows in the legacy Django portal and scan surfaces:

- a shipper can declare cartons prepared outside ASF, upload the compliance documents later, and
  either drop the cartons at the warehouse or request home-to-warehouse pickup
- the same order can mix shipper-prepared cartons and ASF-prepared cartons from ASF stock, then be
  split into multiple shipments with explicit carton-by-carton allocation

## Context

The current implementation already supports:

- portal order creation for unit-stock lines
- selection of ready internal cartons and ready internal kits
- automatic creation of one shipment per order through `create_portal_order(...)`
- staff-side `Réception association` with conformity, carrier, pickup cost, and receipt-to-shipment
  allocations

The main gaps are structural:

- `Order.shipment` is a `OneToOneField`, so the business model still assumes one shipment per order
- shipper-prepared cartons do not exist as first-class objects before shipment assignment
- portal order documents can only be uploaded after order approval
- the shipment-ready gate only knows about shipment-local state, not order-level shipper documents
  or inbound receipt traceability

## Problem

ASF needs a single business dossier per order that can cover:

1. cartons prepared by the shipper outside ASF
2. optional complementary cartons prepared by ASF from stock
3. either direct drop-off or ASF-organized pickup
4. one-time order-level attestations
5. manual distribution of the available cartons across multiple shipments

The current model can represent the ASF-prepared side, but not the external inbound side or the
multi-shipment split.

## Decision

Add an explicit inbound-delivery aggregate to the order, a reusable pickup-address book for the
shipper, a many-link relation from orders to shipments, and first-class cartons created at receipt
time for shipper-delivered goods.

The authoritative rules become:

- one `Order` can have zero or one shipper inbound delivery
- one `Order` can have zero, one, or many linked shipments
- documents are stored once at order level
- order submission is never blocked by missing documents
- shipment readiness is blocked only when the specific shipment actually depends on the missing
  inbound requirements

## Scope

### In scope

- portal order declaration for shipper-prepared cartons
- pickup vs warehouse drop-off declaration
- reusable pickup-address book for shipper organizations
- order-level packing-list and attestation documents
- receipt traceability for direct drop-off and pickup
- creation of physical WMS cartons from shipper receipts
- manual carton selection into one or many shipments
- shipment-ready gate before planning
- pickup-cost billing propagation

### Out of scope

- Next/React migration work
- translation parity work
- automated carton-to-shipment assignment
- partial override workflow for non-conform receipts in V1
- multiple inbound deliveries per order

## Target Workflow

### 1. Portal order submission

The shipper can submit an order with:

- only ASF-stock lines
- only shipper-prepared cartons
- or both

No document is required to submit the order.

If the order includes shipper-prepared cartons, the portal stores a single `OrderInboundDelivery`
record with:

- declared carton and out-of-format counts
- arrival mode: `dropoff_warehouse` or `pickup_requested`
- pickup snapshot data when pickup is requested

### 2. Pickup data capture

When `pickup_requested` is selected, the portal requires a full pickup snapshot. The shipper can
choose a saved pickup address or enter a new one, but the order always stores its own frozen
snapshot so later edits on the address book do not rewrite history.

Required pickup rules:

- `pickup_company_name` is optional
- at least one phone number is required across `pickup_contact_phone` / `pickup_contact_phone_2`
- `pickup_requested_for_date` is optional
- access constraints are mandatory as a block:
  - either `pickup_has_no_access_constraints = True`
  - or `pickup_access_constraints_details` must be filled
- `tail_lift_required` defaults to `True`
- `pallet_truck_required` defaults to `True`
- `pickup_information_confirmed` is mandatory

Opening hours use one mandatory slot and one optional second slot behind an explicit midday-break
flag so the common `09:00-12:00 / 13:00-17:00` case stays structured.

### 3. Order review and shipment creation

ASF can approve the order even if documents are still missing.

After approval, staff can create one or many shipments from the same order. Shipment creation is no
longer a one-shot terminal action. Each shipment is linked back to the order through a dedicated
link model.

### 4. Receipt at warehouse

If the order contains shipper-prepared cartons, ASF must create a `Réception association` linked to
the inbound delivery when the cartons physically reach the warehouse.

This rule applies for:

- direct drop-off by the shipper
- ASF-organized pickup after transport arrives at the warehouse

The receipt is the physical trace that moves cartons from “announced” to “received”.

### 5. Carton materialization

At receipt time, the system creates one WMS `Carton` row per received shipper carton. These cartons:

- have no shipment yet
- carry explicit provenance showing they came from the linked receipt
- are selectable later in scan shipment edit

This is what enables manual carton-by-carton split across multiple shipments.

### 6. Shipment composition

In `scan/shipment/<id>/edit/`, staff can mix:

- cartons received from the shipper
- cartons prepared by ASF from stock

No carton is auto-assigned. A carton can only belong to one shipment at a time.

### 7. Shipment-ready gate

The blocking gate remains the explicit transition to `Prêt`, implemented through
`confirm_shipment_ready(...)` before planning.

Blocking rules:

- for every shipment linked to the order:
  - `donation_attestation` must exist and be scan-clean
  - `humanitarian_attestation` must exist and be scan-clean unless the shipper is exempt
- for shipments that contain at least one shipper-received carton:
  - the order inbound delivery must have a linked receipt
  - the receipt must be conform in V1
  - `packing_list_global` must exist and be scan-clean
  - `packing_list_by_carton` must exist and be scan-clean

Shipments that only contain ASF-prepared cartons are not blocked by the absence of shipper-carton
receipt or packing lists.

## Data Model Direction

### `Order`

`Order` remains the commercial and portal dossier.

Short-term compatibility rule:

- `Order.shipment` stays in place as a temporary legacy pointer
- new business logic must read `OrderShipmentLink` as the source of truth
- compatibility code may keep `Order.shipment` pointing to the first linked shipment while legacy
  callers are migrated to aggregated helpers

This avoids a flag-day rewrite while still allowing the model to move to multi-shipment behavior.

### `OrderInboundDelivery`

New `OneToOne` child of `Order`.

Recommended fields:

- `order`
- `arrival_mode`
- `declared_carton_count`
- `declared_out_of_format_count`
- `notes`
- `receipt`
- `pickup_address_book_entry` optional FK for provenance only
- pickup snapshot fields copied into the order:
  - `pickup_company_name`
  - `pickup_contact_name`
  - `pickup_contact_phone`
  - `pickup_contact_phone_2`
  - `pickup_address_line1`
  - `pickup_address_line2`
  - `pickup_postal_code`
  - `pickup_city`
  - `pickup_country`
  - `pickup_available_from_date`
  - `pickup_requested_for_date`
  - `pickup_opening_slot_1_start`
  - `pickup_opening_slot_1_end`
  - `pickup_has_midday_break`
  - `pickup_opening_slot_2_start`
  - `pickup_opening_slot_2_end`
  - `pickup_has_no_access_constraints`
  - `pickup_access_constraints_details`
  - `tail_lift_required`
  - `pallet_truck_required`
  - `pickup_information_confirmed`

No extra status field is required in V1. The UI can derive state from:

- presence or absence of `receipt`
- `receipt.conformity_status`

### `AssociationPickupAddress`

New reusable address-book model keyed by the shipper organization, not the user.

Recommended fields:

- `association_contact`
- `label`
- the same pickup snapshot fields as above, except order-specific dates
- `is_default`
- `times_used`
- `last_used_at`

The portal should surface the two most recent or most-used entries first, without enforcing a hard
limit in the database.

### `OrderShipmentLink`

New explicit many-link relation from orders to shipments.

Recommended fields:

- `order`
- `shipment`
- `created_at`
- `created_by`

One order can therefore generate multiple shipment dossiers while keeping a shared commercial
origin.

### `OrderDocumentType`

Extend the existing order document enum with:

- `packing_list_global`
- `packing_list_by_carton`

The existing types remain:

- `donation_attestation`
- `humanitarian_attestation`
- `invoice`
- `other`

With only one inbound delivery per order, keeping the documents on `OrderDocument` is simpler than
introducing a second document table.

### Shipper compliance flag

Store the humanitarian-attestation exemption on the shipper organization, not on the portal user.

Recommended minimal shape:

- add `is_humanitarian_attestation_exempt` on `contacts.Contact`

This keeps the flag manageable from the same operational contact surfaces that already own shipper
metadata.

### Carton provenance

Shipper-received cartons need explicit provenance so scan shipment edit can show their origin.

Recommended additions on `Carton`:

- `source_kind` with at least:
  - `warehouse_prepared`
  - `shipper_received`
- `source_receipt` nullable FK to `Receipt`

This keeps the selection logic simple:

- all cartons still use the same `Carton.shipment` assignment field
- provenance is used only for filtering, display, and readiness checks

## Portal UX Direction

### Order create

Add a dedicated block such as `Colis préparés par votre structure` to the existing
`templates/portal/order_create.html` workflow. The order-create page should allow:

- ASF stock only
- shipper cartons only
- mixed orders

Suggested new includes:

- `templates/portal/includes/order_create_shipper_inbound_card.html`
- `templates/portal/includes/order_create_pickup_card.html`
- `templates/portal/includes/order_create_pickup_saved_addresses_card.html`

### Order detail

The order detail page should expose:

- inbound-delivery declaration summary
- pickup vs drop-off summary
- receipt linked or missing
- documents present / missing / quarantined / blocked
- linked shipments list, not only one shipment status

Document upload must be unlocked as soon as the order exists, not only after approval.

## Scan UX Direction

### Orders view

`scan/orders_view` must stop treating shipment creation as a one-time action. The page should show:

- linked shipment count
- inbound-delivery presence
- receipt state
- order-level compliance document state
- create-another-shipment action when approval is complete

### Order detail

`scan/order` should show:

- inbound delivery summary
- linked shipments
- unassigned shipper-received cartons
- quick link to `Réception association`

### Receipt association

`scan/receive_association` should allow explicit linkage to the order inbound delivery and should
pre-fill the source organization where possible. Saving the receipt must materialize the shipper
cartons.

### Shipment dossier

`scan/shipment/<id>/edit/` should gain:

- origin-aware carton selection
- a panel summarizing the parent order
- order-level documents shown directly on the dossier
- receipt summary when shipper cartons are included

## Document Propagation

Order documents remain the source of truth.

Operationally:

- shipment readiness checks read order documents directly
- the existing `attach_order_documents_to_shipment(...)` helper may remain for the two attestation
  files if shipment-local document exports still depend on them
- packing lists do not need to be duplicated to every shipment document table in V1

## Billing Direction

Pickup billing remains captured on `Receipt`.

For invoicing:

- drop-off orders generate no pickup transport line
- pickup orders reuse the actual pickup charge recorded on the linked receipt
- the billing draft builder should inject that charge automatically instead of relying on manual
  re-entry

Because receipts already link to shipments through `ReceiptShipmentAllocation`, the transport line
can stay traceable to both the physical receipt and the shipment billed.

## Compatibility And Rollout Notes

- keep the legacy Django stack only
- migrate read paths from `Order.shipment` to `OrderShipmentLink` before removing the one-to-one
  assumption
- update portal dashboard helpers to aggregate linked shipments instead of reading the compatibility
  pointer
- keep the receipt-to-shipment allocation mechanism; do not invent a parallel billing linkage
- update repo-reference docs alongside implementation because this work changes portal order flow,
  receipt semantics, shipment dossier composition, and shared operational contracts
