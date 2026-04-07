# Scan Receipts And Pack Adjustments Design

## Goal

Apply four operator-facing scan adjustments on the legacy Django stack:

- capture persisted receipt conformity data for `receive-pallet` and `receive-association`
- require an observation when a receipt is marked non-conform
- keep the `prepare-kits` top panel full-width
- turn `scan/pack` shipment reference into a descending select and default the missing-dimensions switch to enabled

## Scope

In scope:

- `templates/scan/receive_pallet.html` and `templates/scan/includes/receive_pallet_create_card.html`
- `templates/scan/receive_association.html` and `templates/scan/includes/receive_association_create_card.html`
- `templates/scan/prepare_kits.html`
- `templates/scan/pack.html` and `templates/scan/includes/pack_shipping_section.html`
- `wms/forms.py`
- `wms/receipt_pallet_handlers.py`
- `wms/receipt_handlers.py`
- `wms/views_scan_shipments.py`
- `wms/pack_handlers.py`
- `wms/models_domain/inventory.py`
- migration + focused tests

Out of scope:

- translation work
- Next/React migration
- new reporting screens for receipt conformity statistics

## Current State

`Receipt` already stores free-text notes and association pickup-comment fields, but it does not persist a receipt-level conformity state.

`receive-pallet` creates `Receipt` rows through `ScanReceiptPalletForm` and `handle_pallet_create_post`.

`receive-association` creates `Receipt` rows through `ScanReceiptAssociationForm` and `handle_receipt_association_post`.

`prepare-kits` already has a dedicated top panel class, but desktop bootstrap CSS still caps its width with `max-width: min(100%, 62rem)`.

`scan/pack` currently uses a free-text `shipment_reference` field and defaults `confirm_defaults` to unchecked on GET.

## Decisions

### 1. Persist conformity on `Receipt`

Add a new `ReceiptConformityStatus` choice field on `Receipt` with:

- `unknown` for historical rows
- `conform`
- `non_conform`

Reasoning:

- better than a nullable boolean for future filters and statistics
- explicit backfill/default semantics
- low migration cost

### 2. Map UI to persisted conformity cleanly

For both receipt forms:

- expose a boolean UI control labeled around non-conformity
- map unchecked to `ReceiptConformityStatus.CONFORM`
- map checked to `ReceiptConformityStatus.NON_CONFORM`

Server-side validation remains authoritative:

- if non-conform is checked, observation is required

UI-side validation should mirror it with native `required` toggling for faster operator feedback.

### 3. Reuse existing text storage where it already exists

For `receive-pallet`:

- add a new `observation` form field
- persist it into `Receipt.notes`

For `receive-association`:

- keep using `pickup_charge_comment`
- rename the visible label/block to `Observation`
- require it when non-conform is checked

This keeps the code change minimal while satisfying the request.

### 4. Keep `scan/pack` handler compatibility

The handler already resolves a shipment from a reference string.

Instead of changing the POST contract to submit shipment IDs:

- keep the form field named `shipment_reference`
- change it to a `ModelChoiceField` that renders as a native `<select>`
- set `to_field_name="reference"` so the submitted value remains the shipment reference
- format labels as `REFERENCE - IATA`
- sort queryset by `-reference`

This delivers the new operator UX with minimal downstream change.

### 5. Keep `prepare-kits` width fix local

Remove the desktop width cap from the existing `scan-prepare-kits-top-panel-full` bootstrap rule so the panel spans the available page width. No template restructuring is needed.

## Data Flow

### Receive pallet

1. Operator fills receipt metadata, observation, and conformity switch.
2. Form validates:
   - base receipt fields
   - observation required when non-conform is checked
3. Handler creates `Receipt` with:
   - `receipt_type=PALLET`
   - `notes=observation`
   - `conformity_status`

### Receive association

1. Operator fills association receipt metadata, pickup billing fields, observation, and conformity switch.
2. Form validates:
   - existing receipt fields
   - observation required when non-conform is checked
3. Handler creates `Receipt` with:
   - `receipt_type=ASSOCIATION`
   - `pickup_charge_comment`
   - `conformity_status`

### Pack

1. GET builds `ScanPackForm`.
2. Shipment field renders as descending select of active shipments.
3. `confirm_defaults` is initialized `True` on GET.
4. POST keeps sending the shipment reference string; `handle_pack_post` continues to resolve from that reference.

## Testing Strategy

Add or update focused tests for:

- form validation for pallet/association non-conform observation requirement
- `ScanPackForm` shipment queryset ordering and label format
- `scan_receive_pallet` and `scan_receive_association` persistence of conformity + observation
- bootstrap/template assertions for new switches/fields
- `scan_pack` GET defaulting `confirm_defaults` to true
- `prepare-kits` CSS full-width contract

## Risks

- existing code may assume `Receipt.notes` is unused on pallet receipts
- the association observation rename must not break receipt billing tests
- changing `shipment_reference` to a select must preserve current GET prefill and invalid-reference handling

## Mitigations

- keep field names and handler inputs compatible wherever possible
- keep association persistence on the same model field
- add regression tests around GET prefill, queryset order, labels, and validation

## Docs Impact

If implementation lands as designed, update repo-reference docs for:

- receipt conformity capture on scan reception flow
- explicit descending shipment select exception on `scan/pack`
