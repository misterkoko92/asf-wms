# Cartons Ready Status Skip Confirmation Design

**Date:** 2026-04-16

## Goal

Adjust the legacy Django `Vue Colis` screen under `/scan/cartons/` so operators can:

- confirm any status jump that skips one or more intermediate carton workflow steps
- require shipment assignment when jumping directly to `Étiqueté`
- select all visible cartons quickly
- read the actual product contents of each carton directly from the list

## Context

The existing `/scan/cartons/` page exposes bulk status actions but applies them directly. That is too permissive for operators when a requested target status silently skips workflow steps.

The current table also spends three columns on warehouse metadata (`Emplacement`, `Remplissage`, `Contenu`) while hiding the concrete carton contents behind an aggregate summary.

Validated user direction for this ticket:

- confirmation must appear for any skipped status transition, not only for `Étiqueté`
- when the target is `Étiqueté` and the jump skips at least one step, the confirmation must include an expédition selector and that selector is mandatory
- the shipment selector must be sorted by shipment reference descending and display labels such as `260012 - NKC - Expéditeur`
- the list must add a `Tout sélectionner` control
- `Emplacement`, `Remplissage`, and `Contenu` must be replaced by a single `Produits` column that shows one line per product in the format `Nom x quantité`, without truncation

## Workflow Model

Canonical visible carton preparation flow on this screen:

1. `Créé`
2. `En préparation`
3. `Disponible`
4. `Affecté`
5. `Étiqueté`

`Expédié` remains out of scope for the bulk toolbar on this page.

## Status Jump Confirmation

### General Rule

When a requested target status is later in the workflow than the current visible status and at least one intermediate step would be skipped, the UI must block immediate submission and show a confirmation pop-up.

The pop-up text must state which intermediate steps will be considered complete, then state the final target status.

Example patterns:

- `Créé -> Disponible`: skipped steps are `En préparation`
- `Créé -> Affecté`: skipped steps are `En préparation`, `Disponible`
- `En préparation -> Étiqueté`: skipped steps are `Disponible`, `Affecté`

If no step is skipped, the page keeps the current direct-submit behavior.

### `Étiqueté` Special Case

If the target is `Étiqueté` and the jump skips at least one step:

- the confirmation pop-up must render a shipment selector
- selecting a shipment is mandatory before validation
- submission must assign the selected cartons to that shipment as part of the same action
- server-side handling must still validate that the selected shipment is editable

Rationale:

- operators cannot physically label a carton that is not already assigned
- when jumping to `Étiqueté`, the system must not silently end in an impossible intermediate state

## UI Changes On `Vue Colis`

### Bulk Toolbar

Keep the existing bulk toolbar but support the confirmation overlay in front of the final form submit.

For the `Étiqueté` confirmation case:

- the modal uses the same editable shipment dataset as the toolbar
- labels are shown as `REFERENCE - IATA - SHIPPER`
- sort order stays descending on shipment reference

### Selection Column

Add a `Tout sélectionner` button in the checkbox-column header.

Behavior:

- first click selects all currently rendered carton checkboxes
- second click clears them all
- label can remain `Tout sélectionner`; toggled button state can be conveyed through pressed styling rather than label mutation

### Products Column

Replace these columns:

- `Emplacement`
- `Remplissage`
- `Contenu`

with:

- `Produits`

Rendering contract:

- one line per distinct product row already aggregated in the carton payload
- each line uses `Nom x quantité`
- no truncation
- wrapping allowed
- cell content left-aligned and vertically centered
- the new column takes the horizontal space previously used by the three removed columns

## Backend Contract

### Shipment Options

The shipment-option builder used by `/scan/cartons/` must expose labels suitable for both the toolbar and the confirmation modal:

- `reference`
- destination IATA code when available, else current destination fallback wording
- shipper display name

### Bulk Status Mutation

The POST handler must accept explicit target-status submissions coming from the confirmation modal.

Expected server behavior:

- mutate each eligible carton directly to the requested final status
- when the target is `Étiqueté` and a shipment was provided, assign that shipment before final status mutation
- keep existing editable/locked shipment protections
- continue to journal only real persisted transitions through `set_carton_status(...)`

The server should not fabricate intermediate `CartonStatusEvent` rows for the skipped steps. The user-facing confirmation is sufficient for intent acknowledgement, while the persisted history remains a single actual state transition.

## Tests

Coverage should prove:

- skipped transitions are detected correctly
- direct transitions do not request confirmation
- jumping to `Étiqueté` without a shipment is rejected server-side
- jumping to `Étiqueté` with a valid editable shipment assigns the carton and marks it labeled
- the cartons-ready table renders `Tout sélectionner`
- the table renders the `Produits` column and no longer renders the removed columns
- shipment option labels are sorted descending and formatted as `REFERENCE - IATA - SHIPPER`

## Repo-Reference Impact

This change updates a critical scan route under `/scan/cartons/`, so the matching repo-reference flow and shared-contract notes should be re-checked before closing. The workflow semantics themselves do not change globally, but the list-screen contract and confirmation behavior do.
