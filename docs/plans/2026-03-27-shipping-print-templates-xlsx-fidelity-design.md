# Shipping Print Templates XLSX Fidelity Design

## Context

The current HTML/CSS print templates for shipment logistics documents are not faithful reproductions of the legacy `.xlsx` templates used by operations. The user wants:

- V1: HTML/CSS templates that closely match the existing `.xlsx` visual structure.
- V2: room to modernize later without redoing data mapping.
- `etiquette colis` to remain unchanged because it still needs the QR code flow.
- the `Documents` panel inside `Expéditions > Dossiers` to use the same horizontal action-row layout for `Impression groupée`, `Documents papier`, and `Exports PDF` as the existing `Par colis` section.

## Recommendation

Use a shared print-form styling layer plus document-specific HTML templates.

- V1 templates should reproduce the `.xlsx` hierarchy, labels, tables, and signature zones as faithfully as practical in HTML/CSS.
- V2 can later modernize the presentation while keeping the same data contexts and routing.
- Do not attempt an automatic Excel-to-HTML conversion. The templates should be manually authored, using the `.xlsx` files as the visual source of truth.

## Scope

Templates to realign from `.xlsx`:

- `bon d’expédition`
- `document douane`
- `liste générale`
- `liste colisage par carton`
- `attestation donation`
- `étiquette contact`

Out of scope for this pass:

- `étiquette colis` with QR code

## Design

### Shared print primitives

Add or reuse a small set of print-oriented primitives to support V1 fidelity and V2 evolution:

- sheet header with ASF heading and reference lines
- summary form grid for labels and values
- compact table styles for packing lists
- contact form blocks with label/value rows
- signature and stamp areas
- compact label-form layout for contact labels

These primitives should support faithful rendering without coupling templates to spreadsheet cell geometry.

### Document rules

`bon d’expédition`
- Rebuild as a form-style document based on `C__shipment_note__shipment.xlsx`.
- Restore origin/destination/IATA/flight/weight/parcel structure.
- Keep shipper/recipient/correspondent sections as printed forms, not modern cards.
- Keep donation certificate separate.

`document douane`
- Rebuild from `C__customs_note__shipment.xlsx`.
- Follow the same high-level frame as the shipment note where the source matches.
- Preserve customs-specific labels and structure.

`liste générale`
- Rebuild from `B__packing_list_shipment__shipment.xlsx`.
- Restore humanitarian subtitle and shipment summary lines.
- Keep the source column order and title block.

`liste colisage par carton`
- Rebuild from `B__packing_list_carton__per_carton_single.xlsx`.
- Use the compact single-carton form with carton reference line and 3-column table.

`attestation donation`
- Keep content strictly identical.
- Realign visual layout to `B__donation_certificate__shipment.xlsx`.
- Preserve stamp/signoff structure.

`étiquette contact`
- Rebuild from `C__contact_label__shipment.xlsx`.
- Use a simple printed label structure with repeated contact fields, closer to the source form than the current card layout.

### Dossier documents panel

The `Documents` panel should keep the same logical grouping already introduced in `Expéditions > Dossiers`, but the action layout should be visually consistent:

- `Impression groupée`
- `Documents papier`
- `Exports PDF`
- `Par colis`

Each group should present its actions as a labeled row followed by one horizontal `ui-comp-actions` line that wraps cleanly when needed. `Par colis` remains the reference behavior.

## Validation

Success for this pass means:

- dossier panel groups use the same action-row layout pattern
- HTML print outputs are visibly based on the legacy `.xlsx` templates
- `etiquette colis` remains unchanged
- routing and internal-vs-PDF delivery behavior stay intact
- the existing test and coverage gates remain green
