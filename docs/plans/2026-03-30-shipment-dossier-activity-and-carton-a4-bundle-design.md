# Shipment Dossier Activity And Carton A4 Bundle Design

## Goal

Improve the shipment dossier page so operators can read and act faster, and add a second grouped carton packing-list print mode for A4 label sheets.

## Scope

- Reorder the primary dossier actions in the first block.
- Move the close action to a second row and render it as a secondary action.
- Add a dossier activity line under the creation metadata.
- Make the administrative card labels visually bolder for faster scanning.
- Keep the existing continuous-roll carton bundle.
- Add a second grouped carton packing-list action that prints four fixed-height carton sheets per A4 page for 190 x 61 mm labels.

## Constraints

- Legacy Django only. No Next/React work.
- Translation work remains paused; no FR/EN parity changes outside this scope.
- The existing continuous-roll grouped bundle remains intact.
- The new dossier activity must cover administrative edits, tracking updates, document add/delete, dispute actions, and close actions.

## Approved Approach

### 1. Persisted dossier activity on `Shipment`

Add two fields on `Shipment`:

- `dossier_last_activity_at`
- `dossier_last_activity_label`

These fields provide a reliable source for "Dernière MAJ" even when the modification is a plain administrative edit with no tracking event. The label stays short and human-readable, for example:

- `Dossier modifié`
- `Suivi mis à jour`
- `Document ajouté`
- `Document supprimé`
- `Expédition mise en litige`
- `Litige résolu`
- `Dossier clôturé`

### 2. Centralized helper for activity updates

Use a small helper so each dossier-changing action updates the same contract consistently. This avoids duplicating timestamp/label logic across:

- shipment edit handler
- shipment tracking handler
- shipment document upload/delete handlers
- shipment close action

### 3. Dossier header refresh

Update the shipment dossier header so the first action row becomes:

1. `Voir les colis`
2. `Modifier`
3. `Ouvrir suivi`
4. `Retour aux dossiers`

Render `Clore le dossier` on a second row under `Retour aux dossiers` using the secondary button style.

Move the new activity text below the "Créée le ..." metadata line:

- `Créée le ...`
- `Dernière MAJ : ... · ...`

### 4. Administrative card readability

Keep the current summary layout, but strengthen the visual weight of the field titles in the administrative area so the card remains stable while becoming easier to scan.

### 5. Second grouped carton bundle for A4 sheets

Keep the existing `carton_lists` bundle as the continuous-roll action page.

Add a new shipment bundle dedicated to A4 printing, with:

- one printable HTML surface
- four carton packing lists per A4 page
- fixed slot dimensions matching 190 x 61 mm labels
- a shared packing-list partial reused by both the single-carton page and the new grouped A4 bundle

This keeps the current operational roll workflow unchanged while adding a sheet-friendly alternative.

## Impact Map

Relevant repo-reference propagation points:

- shipment creation/edit/tracking/close cluster in `wms/views_scan_shipments.py`
- print/document/label behavior in `wms/views_print_docs.py`
- shipment dossier helpers in `wms/shipment_view_helpers.py`
- scan templates under `templates/scan/`
- print templates under `templates/print/`
- scan shipment and print-doc tests

## Validation Strategy

- Add/adjust shipment dossier view tests for action order and dossier activity rendering.
- Add/adjust helper tests for grouped print actions.
- Add print-doc view tests for the new grouped A4 carton bundle.
- Run targeted shipment and print-doc test modules.
