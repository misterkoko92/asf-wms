# Print Packs Refactor Design (Excel Templates + Graph PDF)

## Context
Le flux d'impression actuel ne convient plus. Les flux utilisateur restent pertinents, mais la génération documentaire doit être refondue.

Décisions validées:
- Génération manuelle via les boutons existants.
- Source de vérité des données: WMS (Excel = template de rendu).
- Mapping champ WMS -> cellule Excel en base (modifiable en admin).
- Rendu PDF strictement identique aux templates Excel.
- Moteur PDF V1: Microsoft Graph (Excel Online -> PDF), sans fallback LibreOffice en V1.
- Archivage OneDrive: local temporaire puis synchro asynchrone OneDrive (job dédié).
- Pas d'envoi mail automatique en V1.

## Scope V1
- Pack A: `picking`.
- Pack B: `liste de colisage (globale + par carton) + attestation donation`.
- Pack C: `bon d'expédition + etiquette contact`.
- Pack D: `etiquette destination`.
- Support des formats `A5` prioritaire, `A4` fallback pour B/C.

## Non-Goals V1
- Envoi email automatique.
- Fallback de conversion PDF (LibreOffice).
- Refonte UX/IA des écrans; on garde les routes/boutons existants.

## Architecture Cible
1. `PrintPackEngine` orchestre la génération par pack.
2. `TemplateResolver` charge les templates XLSX actifs par document et variant.
3. `CellMapper` applique le mapping DB sur les cellules cibles.
4. `GraphPdfConverter` convertit XLSX en PDF via Graph.
5. `PdfAssembler` fusionne les PDF dans l'ordre du pack.
6. `ArtifactStore` sauvegarde localement les sorties.
7. `OneDriveSyncWorker` synchronise ensuite vers OneDrive (retry exponentiel).

La compatibilité UI repose sur la conservation des points d'entrée existants (scan/admin/API). Seule l'implémentation interne des routes change.

## Modèle De Données Proposé

### `PrintPack`
- `code` (`A`, `B`, `C`, `D`)
- `name`
- `active`
- `default_page_format` (`A5`, `A4`)
- `fallback_page_format` (optionnel)
- `description`

### `PrintPackDocument`
- `pack` (FK `PrintPack`)
- `doc_type` (ex: `shipment_note`, `packing_list_shipment`, `packing_list_carton`, `donation_certificate`, `contact_label`, `destination_label`, `picking`)
- `variant` (ex: `shipment`, `per_carton`, `single_carton`, `all_labels`, `single_label`)
- `sequence`
- `xlsx_template_file`
- `enabled`

### `PrintCellMapping`
- `pack_document` (FK `PrintPackDocument`)
- `worksheet_name`
- `cell_ref` (ex: `D5`)
- `source_key` (ex: `shipment.recipient.full_name`)
- `transform` (optionnel: `date_fr`, `upper`, etc.)
- `required` (bool)

### `GeneratedPrintArtifact`
- `shipment` (nullable selon contexte)
- `carton` (nullable selon contexte)
- `pack_code`
- `status` (`generated`, `sync_pending`, `synced`, `sync_failed`, `failed`)
- `pdf_file`
- `checksum`
- `created_by`
- `created_at`
- `onedrive_path`
- `sync_attempts`
- `last_sync_error`

### `GeneratedPrintArtifactItem` (optionnel mais recommandé)
- `artifact` (FK)
- `doc_type`
- `variant`
- `sequence`
- `source_xlsx_file`
- `generated_pdf_file`

## Mapping Des Boutons Existants Vers La Nouvelle Logique

Objectif: **zéro changement de navigation utilisateur**. Les mêmes boutons/routes déclenchent le nouveau moteur.

### Scan Django templates

| Ecran | Bouton | Route actuelle | Mapping moteur V1 |
| --- | --- | --- | --- |
| `templates/scan/shipment_create.html` | Bon d'expédition | `scan:scan_shipment_document(shipment_note)` | Génère **Pack C** (bon + etiquette contact), retourne PDF fusionné |
| `templates/scan/shipment_create.html` | Liste colisage (lot) | `scan:scan_shipment_document(packing_list_shipment)` | Génère **Pack B** (liste globale + listes carton + attestation donation) |
| `templates/scan/shipment_create.html` | Attestation donation | `scan:scan_shipment_document(donation_certificate)` | Génère **Pack B** (même sortie que bouton liste colisage) |
| `templates/scan/shipment_create.html` | Etiquettes colis | `scan:scan_shipment_labels` | Génère **Pack D** (etiquettes destination) |
| `templates/scan/shipment_create.html` | Liste colisage par carton (par code) | `scan:scan_shipment_carton_document` | Variante `B/per_carton_single` (PDF carton ciblé) |
| `templates/scan/shipment_create.html` | Etiquette par carton | `scan:scan_shipment_label` | Variante `D/single_label` |
| `templates/scan/cartons_ready.html` | Imprimer / télécharger | `scan:scan_shipment_carton_document` ou `scan:scan_carton_document` | Si carton lié shipment: `B/per_carton_single`; sinon mode standalone legacy |
| `templates/scan/cartons_ready.html` | Picking | `scan:scan_carton_picking` | Génère **Pack A** |
| `templates/scan/pack.html` | Imprimer / télécharger | `carton.packing_list_url` | Même mapping que cartons_ready |
| `templates/scan/pack.html` | Picking | `carton.picking_url` | Génère **Pack A** |
| `templates/scan/shipments_ready.html` | Bon d'expédition | `scan_shipment_document(shipment_note)` | **Pack C** |
| `templates/scan/shipments_ready.html` | Liste colisage (lot) | `scan_shipment_document(packing_list_shipment)` | **Pack B** |
| `templates/scan/shipments_ready.html` | Attestation donation | `scan_shipment_document(donation_certificate)` | **Pack B** |
| `templates/scan/shipments_ready.html` | Etiquettes colis | `scan_shipment_labels` | **Pack D** |
| `templates/scan/shipment_tracking.html` | Documents liés | `build_shipment_document_links` -> routes scan | Même mapping ci-dessus pour doc types A/B/C/D |

### Next UI (React)

| Ecran Next | Source des liens | Mapping |
| --- | --- | --- |
| `frontend-next/app/components/scan-shipments-ready-live.tsx` | URLs livrées par `UiShipmentsReadyView` | Identique aux routes scan, donc mapping A/B/C/D inchangé |
| `frontend-next/app/components/scan-cartons-live.tsx` | `packing_list_url`, `picking_url` via API | Identique au mapping carton ci-dessus |
| `frontend-next/app/components/scan-shipment-documents-live.tsx` | `UiShipmentDocumentsView` (`documents`, `labels`) | Identique aux routes scan existantes |

### Admin Django

| Ecran | Bouton | Route actuelle | Mapping moteur V1 |
| --- | --- | --- | --- |
| `templates/admin/wms/shipment/change_form.html` | Bon d'expédition | `admin:wms_shipment_print_doc(shipment_note)` | **Pack C** |
| idem | Attestation donation | `admin:wms_shipment_print_doc(donation_certificate)` | **Pack B** |
| idem | Liste colisage lot | `admin:wms_shipment_print_doc(packing_list_shipment)` | **Pack B** |
| idem | Liste colisage par carton | `admin:wms_shipment_print_carton` | Variante `B/per_carton_single` |

### Docs hors packs V1
- `humanitarian_certificate`
- `customs`

Ces doc types restent sur le moteur actuel V1 (pas de regroupement imposé).

## Orchestration Par Pack

### Pack A (`picking`)
- Entrée: carton (`scan_carton_picking`).
- Étapes: resolve template -> map cellules -> Graph PDF -> store + sync.
- Sortie: 1 PDF.

### Pack B (`packing list + attestation`)
- Entrée: shipment (ou carton variant).
- Étapes shipment:
  1. Générer liste globale expédition.
  2. Générer liste par carton (tous cartons triés code).
  3. Générer attestation donation.
  4. Convertir chaque XLSX via Graph.
  5. Fusion ordre: globale -> cartons -> attestation.
- Sortie: 1 PDF.

### Pack C (`bon expédition + etiquette contact`)
- Entrée: shipment.
- Étapes: bon -> etiquette contact -> conversion Graph -> fusion.
- Sortie: 1 PDF.

### Pack D (`etiquette destination`)
- Entrée: shipment (all labels) ou carton (single label).
- Étapes: template(s) destination -> conversion Graph.
- Sortie: PDF unique (multi-pages possible).

## Formats A5/A4
- Le format cible est défini par le template XLSX (mise en page Excel).
- `PrintPack.default_page_format` indique l'attendu (`A5`).
- Si template A5 indisponible/invalide, fallback contrôlé vers template A4 configuré (B/C).
- Chaque fallback est journalisé dans l'artefact.

## Archivage OneDrive (Option 3)
1. Génération locale OK -> statut `sync_pending`.
2. Worker async pousse vers OneDrive par dossier cible.
3. Retry exponentiel: `1m`, `5m`, `15m`, `1h`, `6h`.
4. Statut final `synced` ou `sync_failed`.

Convention de chemin OneDrive proposée:
- `/WMS/Prints/{pack_code}/{YYYY}/{shipment_ref}/...`

## Fiabilité Et Erreurs
- Erreur mapping cellule requise: arrêt du pack avec erreur explicite (cellule/source_key).
- Erreur Graph conversion: pack `failed`, détail par doc_type.
- Pas de transaction DB longue autour d'appels externes.
- Logs corrélés: `artifact_id`, `pack_code`, `shipment_id`, `carton_id`, `doc_type`.

## Sécurité
- Identifiants Graph en variables d'environnement.
- Permissions Graph minimales.
- Pas de token persistant en base.
- Traçabilité des accès/documents générés.

## Tests

### Unit
- Résolution du mapping (`source_key`, transforms, required).
- Sélection des templates (A5/A4 fallback).
- Composition et ordre des documents par pack.

### Integration
- Mock Graph: succès/erreurs/timeouts.
- Génération complète de A/B/C/D.
- Workflow `sync_pending -> synced/sync_failed`.

### UI/E2E
- Boutons existants (scan + next + admin) déclenchent le bon pack.
- Vérification que les routes historiques restent valides.
- Vérification présence artefact local et statut sync.

## Rollout
1. Feature flag `PRINT_PACK_ENGINE_V1` (off par défaut).
2. Charger templates Excel réels pack par pack.
3. UAT visuelle PDF (comparaison avec modèles métiers).
4. Activation progressive prod.

## Hypothèses Explicites
- Le clic sur `shipment_note` déclenche désormais Pack C complet (bon + etiquette contact).
- Le clic sur `packing_list_shipment` et `donation_certificate` retourne la même sortie Pack B.
- Les routes carton gardent un mode `single carton` pour ne pas casser les usages terrain.
