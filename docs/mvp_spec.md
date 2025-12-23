# ASF WMS MVP Spec

## Scope
- Product catalog with categories, tags, dimensions, weight, volume
- Lot-level stock with FEFO picking and quarantine status
- Two warehouses with structured locations (zone/aisle/shelf)
- Stock movements: in, out, transfer, adjust, precondition
- Cartons with QR codes, carton composition, and shipment lots
- A5 printable documents (PDF via browser print)
- CSV/Excel import for initial product catalog

## Roles
- admin: manage critical settings, quarantine release, user management
- magazinier: day to day operations (stock moves, picking, packing)

## Domain objects
### ProductCategory
- Hierarchical tree (parent/child)
- One path per product (category_l1..category_l4)

### Product
- sku (internal, unique)
- name, category (deepest node)
- brand
- tags (multi)
- barcode (optional external code)
- default_location (optional)
- length_cm, width_cm, height_cm, weight_g, volume_cm3
- storage_conditions, perishable, quarantine_default

### ProductLot
- product, lot_code
- expires_on, received_on
- status: quarantined, available, hold, expired
- quantity_on_hand
- location

### Warehouse / Location
- warehouse: name
- location: warehouse + zone + aisle + shelf

### StockMovement
- type: IN, OUT, TRANSFER, ADJUST, PRECONDITION, UNPACK
- product, product_lot
- qty, from_location, to_location
- reason_code, reason_notes
- created_by, created_at

### Carton
- code (QR)
- status: draft, ready, assigned, shipped
- current_location
- shipment (nullable)

### CartonItem
- carton, product_lot, qty

### Shipment (Lot d'expedition)
- reference
- shipper_name, shipper_contact
- recipient_name, recipient_contact
- destination_address (full)
- requested_delivery_date
- status: draft, picking, packed, shipped, delivered

### Document
- shipment
- type: donation_certificate, humanitarian_certificate, customs, shipment_note,
  packing_list_carton, packing_list_shipment
- file_path or generated_on_demand

## Key flows
- Product import (CSV/Excel)
- Receiving: create product lot, assign location, status quarantined or available
- Quarantine release (admin only)
- Stock move: in/out/transfer/adjust with audit trail
- Precondition: build cartons from product lots, reduce product lot qty
- Picking: FEFO by default, carton fill, shipment assemble
- Print docs: A5 templates for shipment and compliance

## Rules
- FEFO enforced when selecting lots
- Quarantine lots cannot be picked or packed
- Cartons can be mixed, but prefer mono-product
- Preconditioned cartons are available for shipment

## Non-goals (MVP)
- External customer portal
- Automated analytics dashboard
- Full TMS features

## Data and privacy
- Minimal personal data
- Basic audit trail for stock moves and shipment changes
