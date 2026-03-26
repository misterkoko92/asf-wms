# Shipping Logistics Print Template Strategy Design

**Date:** 2026-03-26

## Goal

Define the long-term source template strategy for the shipment logistics documents so they stay easy to redesign in code, print cleanly from desktop and mobile for internal use, and still produce standard PDFs for external sharing.

## Context

The current shipment-document stack is split across two different rendering models:
- legacy Django HTML templates in `templates/print/`
- the newer print-pack pipeline that treats Excel workbooks as source templates and converts them to PDF

For the validated shipment-document scope, Excel is no longer the right source format.

Validated constraints:
- V1 templates can be maintained in code.
- Internal use does not require PDF by default.
- Internal use is primarily about reliable printing from desktop and mobile.
- External use requires PDF output.
- Document fidelity is not the same for every document:
  - shipment label: keep the same visual language, but size may be reduced
  - donation certificate: content must stay identical and visual should stay almost identical
  - all other documents may be redesigned as long as they carry the same information

## Scope

### In Scope

- carton packing list
- shipment packing list
- shipment note
- customs document
- shipment label
- donation certificate
- contact sheet

### Out of Scope

- billing documents
- product labels
- planning PDFs
- Brother SDK work
- Next/React work
- translation work

## Current State In Code

Relevant legacy HTML templates already exist:
- `templates/print/bon_expedition.html`
- `templates/print/liste_colisage_lot.html`
- `templates/print/liste_colisage_carton.html`
- `templates/print/attestation_douane.html`
- `templates/print/attestation_donation.html`
- `templates/print/etiquette_expedition.html`

Relevant legacy routing and context paths already exist:
- `wms/shipment_view_helpers.py`
- `wms/views_print_docs.py`
- `wms/print_context.py`

The repository also contains a block-layout override system in `wms/print_layouts.py` and `wms/print_renderer.py`, plus the Excel print-pack pipeline in `wms/print_pack_engine.py`.

That mixed state is useful as a migration bridge, but it should not remain the architecture target for the shipment logistics documents.

## Approaches Considered

### 1. Keep Excel as a primary source format

Idea:
- continue using `.xlsx` as the master template for some or all shipment documents

Pros:
- reuses the current print-pack investment
- familiar when the current visual reference is already an Excel file

Cons:
- weak fit for mobile-first internal printing
- poor fit for future design evolution in code
- difficult to test semantically
- makes the HTML / mobile print story secondary

### 2. Move everything to a single HTML/CSS source layer, recommended

Idea:
- use code-managed HTML/CSS templates as the only source format for shipment logistics documents
- generate different delivery formats from the same source templates

Pros:
- easiest long-term evolution path
- best fit for browser-based desktop and mobile printing
- clear separation between source templates and delivery formats
- strong testability

Cons:
- some strict-fidelity documents need more careful implementation discipline
- requires an explicit PDF export layer for external sharing

### 3. Hybrid source formats by document type

Idea:
- use HTML/CSS for flexible documents
- use SVG or fixed overlays for strict visual documents

Pros:
- strongest control for labels
- can preserve visual fidelity where needed

Cons:
- more moving parts than necessary if overused
- can become fragmented if every document gets its own rendering technology

## Recommended Decision

Take approach 2 with one narrow exception:
- HTML/CSS becomes the master source format for all shipment logistics documents
- the shipment label may use an SVG-backed implementation if that proves simpler for preserving the current visual identity

This keeps the architecture simple:
- one primary source technology
- one print-first internal delivery story
- one standard PDF external delivery story

## Canonical Model

### Source Format

For this document family, the source of truth should live in code:
- Django HTML templates for documents
- shared CSS primitives for print
- optional SVG only for the shipment label if needed for strict visual fidelity

Excel should not remain a source format for these documents once migrated.

### Internal Delivery

Internal usage should optimize for direct printing:
- desktop browser print
- mobile browser print
- no mandatory PDF generation

PDF may still exist for convenience, but it is not the primary internal target.

### External Delivery

External usage requires PDF:
- email attachments
- partner sharing
- consistent printable exchange format

So PDF remains required, but as a delivery artifact generated from the code-managed source templates, not as the master template format.

## Document Matrix

| Document | Existing Code Reference | Recommended Source Format | Fidelity Level | Internal Delivery | External Delivery |
| --- | --- | --- | --- | --- | --- |
| Packing list carton | `packing_list_carton` / `templates/print/liste_colisage_carton.html` | HTML/CSS | Flexible redesign | Browser print first | PDF required |
| Packing list shipment | `packing_list_shipment` / `templates/print/liste_colisage_lot.html` | HTML/CSS | Flexible redesign | Browser print first | PDF required |
| Shipment note | `shipment_note` / `templates/print/bon_expedition.html` | HTML/CSS | Flexible redesign | Browser print first | PDF required |
| Customs document | `customs` / `templates/print/attestation_douane.html` | HTML/CSS | Flexible redesign with same information | Browser print first | PDF required |
| Donation certificate | `donation_certificate` / `templates/print/attestation_donation.html` | HTML/CSS, strict locked template | Near-identical visual, identical content | Browser print or PDF | PDF required |
| Contact sheet | current `contact_label` route, new dedicated template expected | HTML/CSS | Flexible redesign | Browser print first | PDF required |
| Shipment label | current `shipment_label` flow / `templates/print/etiquette_expedition.html` | HTML/CSS or SVG-backed HTML | Same visual language preserved | Browser print first | PDF optional, only if needed |

## Fidelity Tiers

### Tier 1: Flexible Redesign

Documents:
- packing list carton
- packing list shipment
- shipment note
- customs document
- contact sheet

Rules:
- preserve business information
- improve layout freely
- optimize readability and maintenance

### Tier 2: Locked Content, Near-Identical Visual

Document:
- donation certificate

Rules:
- wording stays identical
- field semantics stay identical
- only minimal visual cleanup is allowed

### Tier 3: Preserved Visual Identity

Document:
- shipment label

Rules:
- keep the same visual language
- allow controlled resizing
- avoid structural redesign that changes how operators recognize the label

## Architecture

### Rendering Layers

The target stack should separate four concerns:

1. Document context
- business data prepared in `wms/print_context.py`

2. Source template
- HTML/CSS template file in `templates/print/`
- optional SVG-backed implementation for the shipment label

3. Internal print surface
- browser-rendered print page for desktop and mobile

4. External delivery adapter
- PDF export from the same source template

This separation is the key to future design evolution without multiplying template technologies.

### Template Strategy

Recommended direction:
- use concrete Django templates as the primary source, not spreadsheet templates
- keep `wms/print_layouts.py` as a compatibility bridge only where still needed
- do not expand the block-layout JSON system as the main future authoring model for these shipment documents

Why:
- rich layout evolution is easier in full HTML/CSS templates than in spreadsheet cell maps
- long-form documents and tables stay easier to reason about
- strict documents can still be locked down with tests and explicit templates

### Shared Print Primitives

The codebase should provide a small reusable print foundation:
- one generic print base template for document pages
- one label-oriented base for narrow or constrained print surfaces
- shared partials for:
  - contacts
  - signatures
  - item tables
  - shipment summaries

Reuse should stay pragmatic. Do not force every document into the same abstraction if readability suffers.

## Migration Strategy

### Phase 1: Codify the policy

- introduce a document strategy registry in code
- mark each shipment document with:
  - source format
  - fidelity tier
  - internal delivery mode
  - external PDF requirement

### Phase 2: Move flexible documents fully to HTML/CSS source templates

- packing list carton
- packing list shipment
- shipment note
- customs document
- contact sheet

### Phase 3: Lock strict documents with stronger regression checks

- donation certificate
- shipment label

### Phase 4: Make PDF an adapter, not a source

- internal routes stay print-first
- external routes or flags produce PDFs from the same templates

## Why This Supports Future Design Changes

This strategy keeps redesign cost low because:
- data preparation stays separate from presentation
- each document can evolve independently
- the same source template can support multiple delivery outputs
- strict documents are isolated instead of forcing all documents into strict fidelity
- Excel conversion logic no longer constrains document design decisions

If future business users provide Excel files as references, they can still be used as visual inputs for migration, but the maintained result should be HTML/CSS in the repository.

## Risks And Mitigations

### Risk: internal print output and external PDF diverge

Mitigation:
- make HTML/CSS the only source
- generate PDF from the same source templates

### Risk: the shipment label becomes hard to preserve visually in plain HTML

Mitigation:
- allow an SVG-backed implementation for that document only

### Risk: strict-fidelity documents drift over time

Mitigation:
- add stronger regression coverage
- keep locked wording and layout tests for the donation certificate

### Risk: migration gets blocked by the current Excel pack routing

Mitigation:
- migrate shipment documents document-by-document
- keep the old Excel pipeline only as a temporary fallback, not as the target architecture

## Verification Strategy

### Automated

- document-policy tests
- context-builder tests
- view tests for internal print routes
- output tests for PDF-required external flows
- strict regression checks for donation certificate and shipment label

### Manual

- desktop browser print for all seven documents
- mobile browser print for the internally printed documents
- email or download validation of external PDFs
- visual comparison against current operational references for:
  - donation certificate
  - shipment label
