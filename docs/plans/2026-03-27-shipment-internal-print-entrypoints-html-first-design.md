# Shipment Internal Print Entrypoints HTML-First Design

## Goal

Make every internal shipment print button in `scan` and `admin` open the validated HTML/CSS print surfaces by default, while preserving explicit PDF exports and legacy/public PDF-first contracts.

## Scope

- Included:
  - `scan` dossier carton and label actions
  - `scan` bundle lot actions
  - legacy generated-doc links still present in the shipment form template
  - `admin` shipment print buttons
- Excluded:
  - `portal`, because no shipment print buttons are exposed there today
  - explicit PDF export buttons
  - public or compatibility endpoints that are intentionally PDF-first

## Decision

Use option 1:

- internal buttons become HTML-first
- legacy/public routes stay PDF-first unless `delivery=html` is requested
- admin handlers adopt the same delivery contract as scan:
  - default internal render = HTML
  - explicit `?delivery=pdf` = PDF/XLSX/helper path

## Design

### Scan dossier

- Keep paper document actions on `scan_shipment_view_document` because that route is already HTML-first.
- Change carton packing list and single shipment label actions to append `?delivery=html`.
- Apply the same URL policy inside grouped bundle pages.

### Scan legacy generated-doc panel

- Replace direct legacy PDF-first links with HTML-first equivalents.
- Remove local-helper markers from these internal buttons.
- Keep the panel as a compatibility surface, but align it with the new internal print UX.

### Admin shipment print buttons

- Keep the existing admin URLs.
- Change admin view handlers so that, for internal requests without explicit `delivery`, they render HTML by default.
- Preserve helper mode, helper-document mode, explicit PDF mode, and XLSX fallback behavior.
- Remove helper-only button markers from the admin template, since these buttons are no longer PDF-first.

## Validation

- Add/update tests for:
  - dossier and bundle URLs using `delivery=html`
  - admin defaulting to HTML
  - admin explicit `delivery=pdf` staying on PDF/XLSX behavior
  - rendered pages no longer marking internal buttons as helper-only PDF actions
