# Brother Carton Content Label Design

**Date:** 2026-03-26

## Goal

Add a mobile-friendly carton content label that staff can open from the legacy Django UI and print directly from an iPhone or Android phone to a Brother QL-1110NWB on the same Wi-Fi network, without a custom mobile app.

## Context

The existing carton document flow is split between:
- legacy HTML print templates such as `packing_list_carton`
- and the newer print-pack pipeline based on `.xlsx` templates converted to PDF

That stack is not a good fit for the validated mobile use case:
- the operator does not need a full packing list document
- the target printer is a thermal label printer
- the desired interaction is browser -> native print dialog on phone
- and the label content is intentionally small:
  - carton code
  - one row per product
  - product name
  - quantity
  - expiration date

The Brother QL-1110NWB supports Wi-Fi printing from Apple devices through AirPrint and from Android through the platform print flow plus Brother's print service support. That makes a custom app unnecessary for V1, but it also means the output should be a browser-friendly print surface rather than an Excel workbook.

## Scope

### In Scope

- a new legacy Django print surface dedicated to carton content labels
- one label per carton
- a compact printable layout for a wide continuous Brother QL roll
- variable label height so all products fit on one label
- product names allowed to wrap to two lines
- browser-native mobile printing from iOS and Android
- staff-facing links from the legacy Django UI

### Out of Scope

- Brother SDK integration
- custom iOS or Android app work
- direct silent printing without the native print dialog
- reuse of Excel templates for this label
- Next/React work
- translation scope
- QR code or barcode on the label
- replacing the existing `packing_list_carton` document

## Approaches Considered

### 1. Keep Excel as the template source

Idea:
- keep generating carton content from `.xlsx` and convert as needed for print

Pros:
- reuses the current print-pack infrastructure
- familiar for existing print-pack template maintenance

Cons:
- Excel is the wrong primitive for a narrow thermal label
- no direct value for mobile browser printing
- adds conversion steps for a layout that is mostly a simple table
- makes variable-height labels harder than necessary

### 2. Build a custom mobile app with the Brother SDK

Idea:
- create a dedicated app or hybrid shell and print through the Brother SDK

Pros:
- strongest control over printer settings
- best path for future one-tap printing

Cons:
- unnecessary for the validated V1 workflow
- adds mobile distribution, maintenance, and platform overhead
- requires App Store / Play Store decisions too early

### 3. Add a dedicated printable HTML label, recommended

Idea:
- build a new legacy Django route that renders a print-specific label page for a single carton
- let the phone use the native print dialog over Wi-Fi

Pros:
- no app required
- simplest path to production
- easy to test in Django
- natural fit for variable-height continuous labels
- avoids Excel entirely

Cons:
- relies on native print dialogs rather than silent printing
- requires manual device validation on iOS and Android
- printer paper selection still depends on the mobile print flow

## Recommended Decision

Take approach 3.

V1 should introduce a new document type, distinct from `packing_list_carton`, whose only job is thermal label printing from the browser.

Key decisions:
- Add a dedicated `carton_content_label` render path instead of overloading `packing_list_carton`.
- Use legacy Django templates, not Excel.
- Target wide continuous Brother media, not die-cut labels.
- Let the label height expand to fit all rows on one printed label.
- Use the phone's native print dialog:
  - iOS: AirPrint
  - Android: system print flow with Brother-compatible print services

## Label Contract

### Content

Each label shows:
- one header line: `Colis: <carton_code>`
- one table with three columns:
  - `Produit`
  - `Qté`
  - `Péremption`

Each product row shows:
- product name
- quantity
- expiration date

### Layout Rules

- Product name is the widest column.
- Product name should fit within two lines in the common case.
- If a product name still needs more space, the row may grow vertically rather than truncating the text.
- Quantity stays on one line and is centered or right-aligned.
- Expiration date stays on one line in `dd/mm/YYYY` format when available.
- If the carton has more rows, the label grows vertically rather than splitting across two labels.

### Visual Rules

- The carton code must be visible but not oversized.
- The label should stay monochrome-friendly for thermal output.
- Borders and row separators should be simple and dark enough for 300 dpi thermal print.
- The layout should reserve safe horizontal margins because Brother documents warn that full-width output can be cut off if the roll is not fed perfectly straight.

## Architecture

### Data Flow

1. The operator opens a carton content label URL from the legacy Django UI.
2. Django loads the carton and its items.
3. Django builds a small context payload dedicated to the label:
   - `carton_code`
   - `item_rows[] = {product_name, quantity, expires_on}`
4. Django renders a print-only HTML page.
5. The operator uses the phone's native print action to send the page to the Brother printer over Wi-Fi.

### Server Responsibilities

- own the label layout
- own the row formatting rules
- render a stable print surface
- keep printer-specific assumptions small and explicit

### Mobile Responsibilities

- open the label page
- choose the printer
- confirm the print job in the native dialog

The mobile browser does not:
- compute layout
- render Excel
- call a Brother SDK
- manage custom printer protocols

## Legacy Django Integration

The new label should remain on the legacy stack.

Recommended additions:
- a dedicated context builder in `wms/print_context.py`
- a dedicated template such as `templates/print/carton_content_label.html`
- dedicated routes in `wms/scan_urls.py`
- dedicated views in `wms/views_print_docs.py`
- legacy Django re-exports in `wms/views_print.py` and `wms/views.py`

Initial staff UI exposure should stay narrow and explicit:
- add one carton-level action from the shipment/carton legacy screens

The existing `packing_list_carton` route should remain unchanged.

## Media And Printer Assumptions

- Printer: Brother QL-1110NWB
- Network: phone and printer on the same Wi-Fi network
- Media: wide continuous roll
- Preferred width target: near the printer's 4-inch capability, while preserving visible side margins

This design intentionally avoids die-cut media because the validated requirement is a single expanding label rather than multiple fixed-height labels.

## Risks And Mitigations

### Risk: mobile print behavior differs between iOS and Android

Mitigation:
- keep the rendered output simple
- validate on one real iPhone and one real Android device
- document the supported print path in operator guidance

### Risk: browser printing adds unexpected margins or page chrome

Mitigation:
- use a print-only template
- keep the page visually minimal
- test directly on the target printer and media

### Risk: the user selects die-cut paper instead of continuous media

Mitigation:
- document continuous media as a requirement for this feature
- keep the UI wording explicit: this is a roll label, not a standard document page

## Verification Strategy

### Automated

- context-builder tests for carton label rows and expiry fallback
- view tests for both shipment-linked and standalone carton routes
- URL and response tests for staff access

### Manual

- iPhone Safari -> Print -> AirPrint -> Brother QL-1110NWB
- Android Chrome -> Print -> Brother-compatible print service -> Brother QL-1110NWB
- real continuous-roll print with:
  - 1 product row
  - 6 product rows
  - more than 6 rows
  - long product names wrapping to two lines
  - missing expiry dates

## Rollout

1. Implement the new label route without removing existing carton documents.
2. Expose one explicit UI action to operators.
3. Validate on real iOS and Android devices with the target Brother printer.
4. Only after field validation, decide whether a PDF fallback is still needed.
