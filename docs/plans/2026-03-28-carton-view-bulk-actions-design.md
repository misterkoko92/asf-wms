# Carton View And Bulk Actions Design

**Date:** 2026-03-28

## Goal

Reorganize the legacy Django carton UI so `Vue Colis` becomes a lighter consultation surface, carton-level operations move to a dedicated `Fiche colis`, and repetitive carton actions are handled through a small set of safe bulk actions.

## Context

The current carton UI in `templates/scan/cartons_ready.html` mixes multiple intents in the same table:
- consultation of prepared cartons
- inline status changes
- carton mutation actions
- document launchers
- full packing-list detail

That makes the page harder to scan and recreates the same ambiguity that recently existed on the shipment side before the `Dossiers` / `Dossier expédition` split.

The current legacy codebase already provides most of the building blocks needed for a cleaner model:
- `scan_cartons_ready` is the list entry point
- `scan_carton_edit` already opens a dedicated page for one carton
- carton documents and carton picking already exist as standalone routes
- the codebase already uses checkbox-based batch selection patterns on other legacy pages

Validated product direction from discussion:
- simplify `Vue Colis`
- do not create a heavy `Dossier colis`
- keep a dedicated carton detail page
- add group actions on `Vue Colis` because opening each carton one by one would be too heavy for operational use
- include `Picking` and `Liste de colisage` in V1 bulk actions

## Scope

### In Scope

- legacy Django carton list under `/scan/cartons/`
- carton detail page presentation and naming
- batch selection UX on `Vue Colis`
- grouped carton actions for:
  - `Marquer étiqueté`
  - `Retirer étiquette`
  - `Picking`
  - `Liste de colisage`
- copy/help updates related to the new carton UI roles

### Out of Scope

- Next/React surfaces
- translation work
- changes to carton business status semantics
- shipment dossier behavior except linked navigation from carton pages
- destructive bulk actions such as batch deletion

## Approaches Considered

### 1. Keep `Vue Colis` as the main cockpit

Idea:
- keep inline actions on each row
- optionally add checkboxes and a generic bulk-action selector

Pros:
- low UI change
- familiar to existing operators

Cons:
- keeps the current visibility / action overload
- adds batch operations on top of an already crowded table
- weakens the list-vs-detail mental model

### 2. Split list and carton detail, recommended

Idea:
- turn `Vue Colis` into a consultation-first list
- move carton-specific operations to a dedicated `Fiche colis`
- add a compact bulk-action bar for repetitive actions that are genuinely faster in list context

Pros:
- clearest mental model
- preserves list readability
- reduces repeated navigation cost for frequent operational actions
- reuses the current carton edit page and current print routes

Cons:
- requires template restructuring
- requires clear action-eligibility rules for mixed selections

### 3. Create a full `Dossier colis`

Idea:
- mirror the shipment pattern literally with a `Dossier colis`

Pros:
- conceptual symmetry with shipments

Cons:
- too heavy for a simpler operational object
- adds unnecessary ceremony
- product language feels inflated for carton-level work

## Recommended Decision

Take approach 2.

Target information architecture:
- `Vue Colis`: find, scan, filter, select, and open cartons
- `Fiche colis`: inspect one carton and perform carton-level operations

Target interaction model:
- row-level default action: `Ouvrir`
- repetitive operational actions handled through a contextual bulk-action bar
- no return to a table full of permanent inline action controls

## `Vue Colis`

### Role

`Vue Colis` becomes a consultation and triage surface:
- find cartons quickly
- understand current carton state
- select one or many cartons for repeated operations
- open a carton for detailed work

It is not a full per-row cockpit anymore.

### Table Content

Recommended columns:
- selection
- code colis
- statut
- expédition liée or destination pré-affectée
- emplacement
- date de création
- résumé contenu
- documents
- action

Recommended content rules:
- `résumé contenu` should stay compact, for example number of lines and total units
- `documents` should indicate availability, not embed the full current document action cluster in each row
- `action` should be `Ouvrir`

### Removed From The Row

- inline status select
- inline `Marquer étiqueté`
- inline `Retirer étiquette`
- inline `Modifier`
- inline `Supprimer`
- full packing-list content
- inline `Imprimer / télécharger`
- inline `Picking`

## `Fiche colis`

### Role

`Fiche colis` becomes the canonical carton-level surface:
- inspect carton state
- inspect carton content
- open carton documents
- perform carton-specific operations
- navigate to the linked shipment dossier when relevant

The page should feel consultation-first, with edit controls clearly grouped instead of dominating the screen.

### Page Structure

Top to bottom:
- header
- synthesis block
- contents block
- documents block
- operations block
- edit panel

### Header

The header should show:
- carton code
- carton status
- linked shipment reference when present
- current location
- creation date
- state warning when mutation is blocked

### Synthesis

The synthesis block should summarize:
- carton format
- estimated weight
- fill percentage / volume
- preassigned destination
- linked shipment
- location

### Contents

This block should list:
- product
- lot
- quantity

### Documents

This block should centralize:
- `Liste de colisage`
- `Picking`

### Operations

Primary carton actions should be explicit and grouped:
- `Modifier`
- `Marquer étiqueté`
- `Retirer étiquette`
- `Supprimer` when allowed
- `Ouvrir expédition` when linked

Design rule:
- operations belong in one clear action area
- the page should not scatter mutation controls inside data blocks

## Bulk Actions On `Vue Colis`

### Principle

Bulk actions are recommended in V1 because list-only consultation would make high-volume carton operations too slow, and opening each carton one by one is not acceptable for common status/document workflows.

The bulk-action bar should be contextual:
- hidden when nothing is selected
- visible as soon as one or more cartons are selected

### Recommended V1 Layout

The contextual bar should contain:
- selected count
- direct button `Liste de colisage`
- direct button `Picking`
- select `Changer le statut`
- button `Appliquer`

Status select options:
- `Marquer étiqueté`
- `Retirer étiquette`

This yields a hybrid model:
- documents are direct buttons because they are frequent output actions
- status changes stay in a guarded select because they change business state

### Why Not A Generic Action Menu

Do not create a large catch-all menu with every current row action.

Reasons:
- it would recreate the old cockpit behavior in another place
- some actions are too risky or too complex for V1
- the bulk bar should remain learnable and operationally safe

### V1 Bulk Actions Included

- `Liste de colisage`
- `Picking`
- `Marquer étiqueté`
- `Retirer étiquette`

### V1 Bulk Actions Excluded

- `Supprimer`
- `Modifier`
- free-form manual status changes
- carton content changes

## Action Eligibility Rules

### Per-Carton Rules

Recommended rules for the future carton UI:

- non-assigned carton in `Créé`, `En préparation`, `Prêt`
  - can open detail
  - can mutate content
  - can use carton document / carton picking
  - can be deleted
  - cannot use shipment-linked status toggles

- assigned carton in editable shipment
  - can open detail
  - can mutate content
  - can use carton document / carton picking
  - can mark labeled from `Affecté` or `Prêt`
  - can remove label from `Étiqueté`

- carton linked to planned, disputed, shipped, received-correspondent, or delivered shipment
  - remains readable
  - documents remain accessible
  - business mutation actions are blocked

- shipped carton
  - read only
  - documents remain accessible

### Mixed Selection Rules

Bulk actions should not require a perfectly homogeneous selection.

Recommended behavior:
- an action is available when at least one selected carton is eligible
- ineligible cartons are skipped
- the result message must always report processed vs ignored counts

Examples:
- `12 colis passés en Étiqueté, 3 ignorés car expédition planifiée`
- `8 pickings générés, 2 ignorés car colis vide`

### Locking Rule Recommendation

The product rule should be clarified so that cartons linked to a `Planifiée` shipment are fully mutation-blocked in the carton UI.

This is consistent with the current FAQ wording that says `Planifié` locks carton modification for the shipment.

## Bulk Documents

### Picking

V1 should support grouped picking output from `Vue Colis`.

Implementation direction:
- when one carton is selected, reuse the existing single-carton route
- when multiple cartons are selected, use a grouped picking output based on the existing multi-carton pattern already used for prepared kits

### Liste de Colisage

V1 should support grouped packing-list output from `Vue Colis`.

Implementation direction:
- when one carton is selected, reuse the existing single-carton route
- when multiple cartons are selected, generate a grouped packing-list output instead of opening multiple tabs

The expected UX is one grouped output, not one browser tab per carton.

## UX Rules

### Selection

- each row has a checkbox
- the header can expose `Tout sélectionner` for the current filtered table
- the bulk bar should display the number of selected cartons

### Feedback

After each bulk operation, the user should receive one compact message summarizing:
- how many cartons were processed
- how many were ignored
- why ignored cartons were skipped when relevant

### Return Cost

The carton list should preserve operator momentum:
- bulk operations happen without forcing navigation away from the table
- opening a carton detail should provide a clear return path to `Vue Colis`

## Implementation Shape

Recommended legacy implementation path:

1. reshape `templates/scan/cartons_ready.html` into a consultation-first list with selection
2. enrich `build_cartons_ready_rows` with the compact metadata needed by the lighter table
3. add a contextual bulk-action form and handler branch on `scan_cartons_ready`
4. reuse existing single-carton document routes for one-carton selections
5. add grouped routes/helpers for carton picking and carton packing-list outputs for multi-carton selections
6. refactor `scan_carton_edit` presentation into a consultation-first `Fiche colis`
7. update FAQ and copy to reflect the new carton information architecture

## Risks

- if bulk actions are too permissive, the list becomes a cockpit again
- mixed selections can become confusing unless ignored-carton messaging is explicit
- grouped document generation must avoid opening many tabs or many helper jobs
- current business rules around planned shipment locking are not fully uniform across carton actions and should be normalized during implementation

## Testing

Add or update legacy Django tests for:
- `Vue Colis` lighter table structure and row action reduction
- checkbox selection and bulk-action bar visibility
- bulk `Marquer étiqueté`
- bulk `Retirer étiquette`
- mixed-selection processed / ignored feedback
- grouped picking for one carton and multiple cartons
- grouped packing-list output for one carton and multiple cartons
- `Fiche colis` structure and blocked-state messaging
- linked navigation from carton detail to shipment dossier
- FAQ and copy updates
