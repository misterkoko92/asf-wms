# Product Packaging Aliases Follow-Up

## Context

Some medical products have one scannable identifier only on the containing box, while the unit
inside has no individual UDI/barcode. A common example is a box of compresses where the box has the
UDI/SKU, but each individual compress does not.

The current preparateur batch implements scan fallback for barcode, EAN, and GS1/UDI GTIN
extraction against the canonical product identifiers. It intentionally does not add a packaging
alias model, because that requires a catalog data-model change and stock/order quantity semantics.

## Deferred Model

Keep one canonical `Product` for the real stock/order unit.

Add a packaging-alias layer later with:

- canonical product link,
- packaging label, for example `Boite de 50`,
- unit multiplier, for example `50`,
- barcode/EAN/UDI/SKU-like identifiers for that packaging,
- optional default display note for scan operators.

## Scan Behavior

When a scan matches a packaging alias:

- resolve to the canonical product,
- show the matched packaging label and multiplier,
- let the operator confirm or adjust the quantity in canonical units,
- keep stock movement and order-preparation math in canonical units.

Example:

- canonical product: `Compresse sterile unite`
- alias: `Boite de 50 compresses`
- alias UDI: value printed on the box
- scan result: proposes the canonical product with quantity `50`

## Why Deferred

This is larger than the current operational fix because it affects:

- catalog schema and admin/editing UX,
- product import/export,
- product lookup contracts,
- stock movement semantics,
- order preparation and carton packing math,
- test fixtures and existing product data cleanup.

## Reopen Trigger

Reopen when ASF wants box/unit aliases to be managed directly in the product catalog, or when
operators repeatedly need to scan a containing box while preparing canonical unit quantities.
