# Cartons Ready Preassignment Mismatch Design

**Date:** 2026-04-23

## Goal

Adjust the legacy Django `Vue Colis` screen under `/scan/cartons/` so operators can safely assign prepared cartons in bulk to multiple shipments at the end of the day, even when some cartons were optionally preassigned to a destination earlier in the preparation flow.

## Context

The current recommended warehouse workflow for this use case is:

- prepare cartons in `/scan/pack/` without selecting a shipment
- fill `Destination pre-affectee` only when the destination is already known
- keep cartons unassigned while operators prepare many cartons in sequence
- assign cartons to shipments later from `Vue Colis`

This workflow already fits the real operational need better than assigning cartons one by one from each shipment dossier.

However, the current bulk assignment action on `/scan/cartons/` does not warn the operator when one or more selected cartons were preassigned to destination `Y` and are about to be assigned to a shipment whose destination is `Z`.

The shipment dossier flow already has such a warning when an operator adds a carton from the shipment form. The gap exists specifically on the bulk assignment flow in `Vue Colis`.

Validated user direction for this ticket:

- keep the end-of-day bulk assignment workflow as the main operational path
- do not introduce a hard block for destination mismatch
- add a strong warning before bulk assignment when the target shipment destination conflicts with a carton's preassigned destination
- keep advanced list filters for a later follow-up, not this MVP

## Existing Behavior

### Shipment Dossier Flow

When an operator adds an existing carton from the shipment create/edit form:

- client-side JS detects a destination mismatch
- a confirmation overlay is shown
- server-side validation also enforces confirmation

This behavior already exists and should remain the reference contract for mismatch detection and confirmation semantics.

### `Vue Colis` Bulk Assignment Flow

When an operator selects cartons in `/scan/cartons/` and uses `Affecter a une expedition`:

- the page can already confirm skipped status jumps
- the handler can already assign eligible cartons to an editable shipment
- no destination-mismatch warning is shown
- no explicit server-side confirmation contract exists for destination mismatch on this bulk flow

## Decision

The MVP will extend the existing `Vue Colis` bulk assignment flow instead of introducing a new batching surface.

The operator continues to work from the same screen and toolbar. The only new behavior is a dedicated confirmation popup when one or more selected cartons have a `preassigned_destination` different from the chosen shipment destination.

This keeps the workflow fast for the common case while adding the missing safety rail for the risky case.

## User Workflow

### Normal Case

1. Operator prepares cartons in `/scan/pack/`, usually without shipment reference.
2. Some cartons may have a `Destination pre-affectee`; others may not.
3. At end of day, operator opens `/scan/cartons/`.
4. Operator selects a target shipment in the bulk toolbar.
5. Operator selects cartons and applies bulk assignment.
6. If no selected carton conflicts with the shipment destination, assignment happens immediately.

### Conflict Case

1. Operator selects a target shipment in the bulk toolbar.
2. At least one selected carton is preassigned to another destination.
3. Before submission, the page opens a dedicated mismatch popup.
4. The popup summarizes the target shipment and the conflicting cartons.
5. The operator chooses one of three actions:
   - continue anyway
   - remove conflicting cartons from the selection and continue
   - cancel

## Confirmation Modal Contract

The new modal is specific to destination mismatch on bulk shipment assignment.

Required content:

- target shipment label
- target shipment destination label
- count of conflicting cartons
- short list of conflicting carton codes

Required actions:

- `Continuer quand meme`
- `Retirer les colis en conflit`
- `Annuler`

Behavior:

- `Continuer quand meme` submits the original selection with explicit mismatch confirmation metadata
- `Retirer les colis en conflit` unchecks only the conflicting cartons, keeps the non-conflicting selection, and submits
- `Annuler` closes the modal and performs no mutation

This modal is separate from the existing skip-status confirmation modal. The MVP does not merge the two workflows into one combined decision tree.

## Backend Rules

### Conflict Detection

A selected carton is considered a mismatch only when:

- the action is bulk shipment assignment
- the target shipment has a destination
- the carton has `preassigned_destination_id`
- the carton's preassigned destination differs from the shipment destination

No mismatch exists when:

- the carton has no preassigned destination
- the carton preassignment matches the shipment destination

### Mutation Rules

If mismatch confirmation is absent:

- conflicting cartons must not be assigned
- the handler must redirect back with a warning message

If mismatch confirmation is present:

- conflicting cartons may be assigned to the selected shipment
- their `preassigned_destination` must be cleared as part of the assignment
- final carton status stays `ASSIGNED` as in the current bulk assignment flow

### Audit Semantics

The system should preserve real persisted transitions only.

The MVP does not create synthetic intermediate events. It should rely on:

- the existing shipment assignment mutation
- the persisted final carton status event
- user-visible success/warning messages describing the override outcome

If a dedicated reason code is needed, it should be explicit and limited to this mismatch override path.

## UI Scope

Files in scope:

- `templates/scan/cartons_ready.html`
- `wms/static/scan/modules/cartons-ready.js`
- `wms/carton_handlers.py`
- supporting row payload helpers if needed

The current `Vue Colis` table and bulk toolbar remain the same overall. The MVP only adds:

- data attributes or payload needed to detect destination mismatches client-side
- a new modal shell for mismatch confirmation
- small copy updates for post-action messages when overrides occur

## Non-Goals

Out of scope for this MVP:

- new end-of-day batch-assignment screen
- filters such as `crees aujourd'hui`, `non affectes`, `pre-affectes`, or `disponibles`
- regrouping the list by destination
- automatic shipment creation from the cartons list
- merging the mismatch modal with the skip-status modal
- changing the pack flow itself

Those can be addressed in a later follow-up once the mismatch safeguard is in production.

## Tests

Coverage should prove:

- the cartons list exposes enough metadata to detect destination mismatches client-side
- the new modal shell is rendered on `/scan/cartons/`
- bulk assignment without mismatch behaves as before
- bulk assignment with mismatch is rejected server-side when confirmation is missing
- confirmed mismatch assignment succeeds and clears `preassigned_destination`
- `Retirer les colis en conflit` can be supported by the JS flow without requiring a server-side special case

## Repo-Reference Impact

This change affects a critical scan route under `/scan/cartons/`, but it does not alter the global shipment/carton workflow model.

Before closing implementation work, re-check:

- `docs/repo-reference/03-impact-map.md` section for scan pages
- `docs/repo-reference/04-shared-contracts.md` only if the `Vue Colis` list contract becomes durably broader than this local modal behavior
