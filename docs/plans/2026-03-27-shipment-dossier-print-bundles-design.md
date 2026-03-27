# Shipment Dossier Print Bundles Design

**Date:** 2026-03-27

## Goal

Define how shipment document printing should be organized inside `Expéditions > Dossiers`, with clear internal print actions, grouped print bundles by physical support, and explicit PDF exports for external sharing.

## Context

The shipment area now has a validated navigation structure:
- `Préparation > Préparation expédition`
- `Expéditions > Dossiers`
- `Expéditions > Suivi des expéditions`

That structure changes the printing center of gravity:
- shipment creation remains a preparation flow
- existing-shipment document work should be centered in `Dossiers`
- tracking stays a separate operational surface, not the main print cockpit

At the moment, the dossier page in `templates/scan/shipment_dossier.html` still reuses the creation-era generated-documents panel:
- `templates/scan/includes/shipment_create_generated_documents_panel.html`

That panel reflects legacy route structure rather than the validated shipment-dossier workflow.

## Scope

### In Scope

- dossier-level printing UX for shipment logistics documents
- grouped print actions by support
- per-carton reprint actions
- internal print behavior for desktop and mobile
- explicit PDF export positioning for external use

### Out of Scope

- Next/React work
- translation work
- Brother SDK integration
- silent printer control
- redesign of the underlying print rendering engine

## Validated Business Inventory

The dossier must cover these operational shipment documents:
- shipment note
- customs document
- carton packing list
- shipment packing list
- shipment label
- contact label
- donation certificate

Validated usage summary:
- shipment note: plain paper
- customs document: plain paper
- carton packing list: custom-sized label, one per carton
- shipment packing list: plain paper by default, adhesive variant optional later
- shipment label: adhesive label, one per carton
- contact label: adhesive label, one per carton
- donation certificate: adhesive label, one per carton

The previous `contact sheet` concept is replaced by a `contact label`.

## Core Decision

Do not merge document content in V1.

Instead:
- keep each document as its own business artifact
- add grouped actions that orchestrate multiple print lots
- split those lots by physical support

This preserves clarity and reduces migration risk:
- the shipment note, customs document, and shipment packing list stay paper-first
- the carton packing list stays continuous-roll-first
- shipment label, contact label, and donation certificate stay standard-label-first

## Printing Model

### Principle

`Imprimer tous les documents d'expédition` must not pretend to be one physical print job.

It should behave as an orchestrator for multiple lots, because the dossier mixes different supports:
- A4 paper
- continuous roll
- standard adhesive labels

That is the only model that remains credible on both desktop and mobile browser printing.

### Supported Internal Behaviors

For internal use:
- desktop printing is browser-first
- mobile printing is browser/system-print-first
- helper-assisted desktop flows may exist later as an optimization

The current local helper is still positioned as an Excel/PDF helper and can already chain PDF bundle jobs, but that is not the right UX contract for the V1 dossier flow.

## Bundle Structure

### Global Bundle

`Imprimer tous les documents d'expédition` should execute three successive lots:

1. `Lot papier A4`
   - shipment note
   - customs document
   - shipment packing list
2. `Lot rouleau continu`
   - carton packing list
   - one document per carton, in shipment carton order
3. `Lot étiquettes standard`
   - for each carton, in shipment carton order:
   - shipment label
   - contact label
   - donation certificate

### Why This Order

- paper documents are usually prepared first as the shipment folder
- carton-content lists come next because they depend on carton sequence and variable height
- standard labels should be grouped by carton rather than by document type to reduce handling errors during application

If donation certificates later require a different physical format, the standard-label lot can split into sub-lots without changing the overall dossier model.

## Dossier Panel Contract

The current dossier `Documents` section should evolve into a dossier-specific panel with four blocks.

### 1. Grouped Printing

- `Imprimer tous les documents d'expédition`
- `Imprimer dossier papier`
- `Imprimer toutes les listes colisage carton`
- `Imprimer toutes les étiquettes standard`

### 2. Paper Documents

- `Imprimer bon d'expédition`
- `Imprimer document douane`
- `Imprimer liste générale`

### 3. Per-Carton Actions

One row per carton with:
- `Liste colisage`
- `Étiquette colis`
- `Étiquette contact`
- `Attestation donation`

These actions exist for controlled reprints and carton-level troubleshooting.

### 4. PDF Exports

- `Télécharger dossier papier (PDF)`
- `Télécharger bon d'expédition (PDF)`
- `Télécharger document douane (PDF)`
- `Télécharger liste générale (PDF)`
- `Télécharger attestation donation (PDF)` when an individual external artifact is needed

## Labeling Rules

The panel should follow one strict rule:

- `Imprimer ...` means internal print surface
- `Télécharger ... (PDF)` means explicit external/export artifact

This avoids ambiguity between operational printing and partner-facing distribution.

## Relation To Existing Code

The design should reuse the new shipment-dossier positioning already in place:
- `templates/scan/shipment_dossier.html`
- `templates/scan/includes/scan_sidebar_navigation.html`
- `wms/views_scan_shipments.py`

It should stop using the current creation-oriented grouping as the final dossier UX:
- `templates/scan/includes/shipment_create_generated_documents_panel.html`

The existing legacy print routes remain important as compatibility and migration paths:
- `wms/views_print_docs.py`
- `wms/views_print_labels.py`
- `wms/shipment_view_helpers.py`

Existing bundle behavior in `wms/views_print_docs.py` and helper chaining in `wms/static/wms/local_document_helper.js` are useful implementation constraints, but they should not dictate the final dossier information architecture.

## Recommended Near-Term Direction

1. Create a dossier-specific document panel partial instead of reusing the creation panel.
2. Reorganize dossier actions by workflow and support, not by legacy endpoint family.
3. Keep legacy direct PDF routes for compatibility.
4. Introduce explicit grouped print surfaces for:
   - paper bundle
   - carton packing-list bundle
   - standard-label bundle
5. Keep PDF exports explicit and secondary in the dossier UI.

## Acceptance Criteria

This design is satisfied when:
- `Dossiers` is the main place where users print shipment documents
- grouped print buttons exist by physical support
- the global print button orchestrates multiple lots instead of hiding support differences
- per-carton reprints remain available
- PDF exports stay clearly separated from internal print actions
- the dossier UI no longer reflects the old creation-era document grouping
