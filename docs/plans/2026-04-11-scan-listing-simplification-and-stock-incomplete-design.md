# Scan Listing Simplification And Stock Incomplete Cockpit Design

## Goal

Simplify `/scan/receive-listing/` so it behaves like a strict receipt-linked import flow, and move the global incomplete-product cockpit to `/scan/stock-update/` where operators already manage stock corrections.

## Context

The current listing redesign solved the PDF analysis problem and introduced receipt linkage, but it still leaves too much responsibility on `/scan/receive-listing/`:

- import setup
- optional receipt creation draft
- import execution
- global incomplete-product cleanup

This mixes two operator jobs:

1. importing lines into an already known receipt
2. maintaining an incomplete product catalog backlog

The second job belongs in stock maintenance, not in listing import.

## Decision

### Listing

`/scan/receive-listing/` becomes a strict import surface.

At page load it shows only one card:

- `Préparer l'import`

This card contains:

- required file-type select
- required pallet-receipt select
- warning copy explaining that the import must be linked to an already created receipt
- shortcut button to `/scan/receive-pallet/`
- `Valider`

Only after a valid `Valider` submit do we show the card for the selected file type.

The inline `Réception à créer` draft block is removed entirely.

PDF keeps its strengthened flow:

- upload
- analysis
- mapping
- review
- confirm

Excel and CSV keep their existing mapping and review behavior.

The incomplete-product block no longer appears during listing setup or review. It appears only after final import confirmation, and only for incomplete products linked to that import.

### Stock Update

`/scan/stock-update/` becomes the global operator cockpit for incomplete products.

The current `MAJ Stock` card stays on the page but moves into a collapse section, closed by default.

A new collapse section `Produits incomplets` appears below it, open by default. It contains:

- the existing incomplete-product table
- batch update controls
- individual `Ouvrir` actions
- a receipt filter select using the same pallet-receipt label format as listing

The default receipt filter is `Toutes les réceptions`.

Filtering rule:

- show incomplete products that are linked to the selected receipt through stock received from that receipt
- in practice, this means filtering incomplete products through their `ProductLot.source_receipt`

This is the most stable and auditable definition because it ties the product backlog to a real stock intake event instead of transient session state.

## Data Flow

### Listing import

1. Operator opens `/scan/receive-listing/`
2. Operator selects:
   - file type
   - existing pallet receipt
3. `Valider` stores:
   - selected file type
   - selected receipt id
4. Operator uploads file
5. Import progresses through analysis/mapping/review
6. At `listing_confirm`, the import reuses the selected receipt
7. Any products created as incomplete are captured
8. After redirect, the page shows only the incomplete products linked to that confirmed import

### Stock update incomplete cockpit

1. Operator opens `/scan/stock-update/`
2. `MAJ Stock` card is collapsed by default
3. `Produits incomplets` card is open by default
4. Operator may filter the backlog by linked receipt or see all incomplete products
5. Operator uses:
   - batch actions
   - individual edit

## Extraction Strategy

To keep future maintenance simpler, incomplete-product logic should move out of `views_scan_receipts.py` into a shared helper module. That shared layer should own:

- the base incomplete-products queryset
- optional filtering by linked receipt
- batch-update application
- shared context payload for templates
- receipt selector queryset/labels reused by listing and stock update

This avoids duplicating receipt-label logic and avoids keeping catalog-maintenance logic tied to the listing view.

## Validation Rules

- listing file type is required
- listing receipt is required
- listing import cannot proceed without a linked receipt
- listing quantities remain additive stock receipts, never overwrite behavior
- stock-update incomplete filter is optional
- `Toutes les réceptions` remains the default option

## Testing Impact

The design changes the contracts for:

- `wms/tests/receipt/tests_receipt_listing.py`
- `wms/tests/pallet/tests_pallet_listing_handlers.py`
- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/views/tests_views_scan_receipts.py`
- `wms/tests/views/tests_views_scan_stock.py`

We also need dedicated tests for:

- filtering incomplete products by receipt on stock update
- showing incomplete products linked to the last confirmed listing import only after confirm
- not showing any incomplete-product cockpit on initial listing load

## Risks

- If we keep the current edit route name (`scan_receive_listing_product_edit`), stock update can still reuse it short term, but the route naming becomes misleading.
- If we rename the edit route now, propagation cost increases.

Recommendation:

- keep the route temporarily for this batch
- add optional `next` support so stock update can return there cleanly
- extract the shared incomplete-product logic first
- rename route later only if the user wants the cleanup
