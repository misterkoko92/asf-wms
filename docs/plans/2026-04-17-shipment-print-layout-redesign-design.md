# Shipment Print Layout Redesign Design

**Date:** 2026-04-17

## Goal

Adjust the legacy Django shipment print flow under `/scan/shipment/<id>/edit/` so operators can:

- print a reordered `dossier papier` bundle containing `Bon d'expédition`, `Document douane`,
  then `Liste colisage générale` twice
- print the general packing list in `A4 portrait`, full page, with normal margins
- print one `A4 portrait` page per carton for carton-label paperwork, with four `A6` blocks laid
  out in this order:
  - top left: `Attestation donation`
  - top right: `Étiquette colis`
  - bottom left: `Contact`
  - bottom right: `Liste colisage par colis`
- keep landscape backups for the shipment note and customs note in case the portrait layout proves
  too tight during operator validation

## Context

The current shipment print actions split the workflow across:

- an `Imprimer dossier papier` HTML bundle that currently renders three full-page sections in
  sequence
- a separate `Imprimer toutes les listes par carton` action that currently renders carton packing
  lists four-up on `A4`
- a `Imprimer toutes les étiquettes standard` action that renders contact labels, shipment labels,
  and donation certificates as two-up `A5` content

That no longer matches the operator workflow. The paper bundle must now be reordered and duplicated
for the shipment packing list, while carton paperwork must be emitted as one `A4` portrait page
per carton with a fixed `2 x 2` arrangement of four compact documents.

Validated user direction for this ticket:

- `Imprimer dossier papier` must print, in order:
  1. `Bon d’expédition`
  2. `Document douane`
  3. `Liste colisage générale` copy 1
  4. `Liste colisage générale` copy 2
- the `Bon d’expédition` and `Document douane` should move to `A4 portrait`
- keep a landscape backup for those two documents in code so the old orientation can be restored if
  needed
- the grouped carton-label bundle must produce one `A4` page per carton; for a shipment with five
  cartons, it must print five `A4` pages

## Workflow Surface

The legacy Django print surface remains the source of truth:

- grouped bundle routing in `wms/views_print_docs.py`
- shipment dossier action labels in `wms/shipment_view_helpers.py`
- HTML templates under `templates/print/`
- regression coverage in `wms/tests/views/tests_views_print_docs.py` and
  `wms/tests/shipment/tests_shipment_view_helpers.py`

No Next/React scope is involved.

## Design

### 1. `Imprimer dossier papier`

The grouped `paper` bundle keeps the same route family, but its HTML output changes to a four-page
portrait sequence:

1. shipment note (`Bon d'expédition`)
2. customs document (`Document douane`)
3. shipment packing list (`Liste colisage générale`) copy 1
4. shipment packing list (`Liste colisage générale`) copy 2

The bundle should remain direct-print HTML so operators still get a browser print preview from the
shipment dossier. Since all four sections will now share `A4 portrait`, the bundle no longer needs
mixed-orientation handling.

### 2. `Bon d’expédition` / `Document douane`

The shipment note and customs note templates currently use `A4 landscape`. They should move to
`A4 portrait` and tighten typography/spacing enough to fit on one portrait sheet without changing
the business fields shown.

Landscape backup rule:

- keep the existing layout characteristics recoverable in code
- the simplest acceptable backup is to factor the page-size-sensitive styling behind template
  classes or dedicated backup templates/partials so future rollback is localized
- no user-facing alternate action is required in this ticket

### 3. `Liste colisage générale`

The shipment packing list currently uses `A5 landscape`. It should move to `A4 portrait` with:

- normal print margins
- full-page use of the portrait sheet
- unchanged business data and totals
- stable row order and labels

The same portrait template is reused both for the standalone `Imprimer liste générale` action and
for the two duplicated pages inside the paper bundle.

### 4. `Imprimer étiquettes cartons`

The grouped action currently labeled `Imprimer toutes les étiquettes standard` should be repurposed
to a carton-paperwork bundle labeled `Imprimer étiquettes cartons`.

Output contract:

- one `A4 portrait` page per carton
- each page contains exactly four `A6` quadrants in a `2 x 2` grid
- each quadrant contains one compact document body
- quadrant order is fixed and must not depend on carton ordering

Per-carton page composition:

- top left: donation certificate body
- top right: shipment label body (`Étiquette colis`)
- bottom left: contact sheet body
- bottom right: carton packing list body

The existing per-carton individual actions (`Étiquette colis`, `Étiquette contact`,
`Attestation donation`, `Liste colisage`) remain available and unchanged.

### 5. Compact A6 Variants

The four-up `A4` carton pages should not scale down whole existing pages blindly. Instead, the
existing partials should be reused inside a purpose-built `A6` composition template with targeted
compact CSS overrides.

Expected adaptation strategy:

- reuse existing HTML partials where possible:
  - `print/partials/donation_certificate_body.html`
  - `print/partials/shipment_label_body.html`
  - `print/partials/contact_label_body.html`
  - `print/partials/packing_list_carton_body.html`
- scope compact rules under the carton-page wrapper so standalone prints do not change
- reduce fonts, paddings, logo sizes, and row heights enough for `A6`
- preserve the critical human-readable identifiers:
  - shipment reference
  - carton code / position
  - destination / IATA
  - contact coordinates
  - carton item rows

### 6. Existing Bundle Preservation

The current `carton_lists_a4` bundle should remain available as the four-up carton packing-list
bundle. It serves a different workflow from the new four-block carton paperwork bundle.

The only grouped-action rename in this ticket is:

- `Imprimer toutes les étiquettes standard` -> `Imprimer étiquettes cartons`

Its destination route can stay `standard_labels` if that is simpler for compatibility, but the
behavior behind the route must switch to the new one-page-per-carton bundle.

## Testing

Coverage should prove:

- the grouped shipment `paper` bundle renders sections in the new order
- the grouped shipment `paper` bundle contains the general packing list twice
- the grouped carton-label bundle renders one page per carton instead of grouped document runs
- each carton page contains the four expected block types in the expected order
- helper action labels reflect the renamed grouped action
- the direct `Liste colisage générale` route still resolves to the shipment packing-list template
- the paper bundle and carton bundle still render direct-print HTML without intermediate chooser UI

Where practical, template tests should assert stable DOM ids or `data-*` markers for the four
block types rather than relying only on free text.

## Repo-Reference Impact

This changes a critical shipment print/document flow under `/scan/`, so the print/document section
of `docs/repo-reference/03-impact-map.md` and the scan workflow reference in
`docs/repo-reference/02-key-flows-and-living-tests.md` must be re-checked before closing.
