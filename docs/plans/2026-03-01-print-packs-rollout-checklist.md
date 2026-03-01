# Print Packs Rollout Checklist

## Prerequisites
- [ ] Variables Graph configurées: `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`, `GRAPH_DRIVE_ID`, `GRAPH_WORK_DIR`.
- [ ] Templates Excel chargés pour les packs `A`, `B`, `C`, `D`.
- [ ] Mappings cellules (`PrintCellMapping`) validés sur chaque document/variant.

## Mapping Buttons (Bootstrap)
- [ ] `scan_shipment_document(shipment_note)` -> Pack `C` (`shipment`).
- [ ] `scan_shipment_document(packing_list_shipment)` -> Pack `B` (`shipment`).
- [ ] `scan_shipment_document(donation_certificate)` -> Pack `B` (`shipment`).
- [ ] `scan_shipment_labels` -> Pack `D` (`all_labels`).
- [ ] `scan_shipment_label` -> Pack `D` (`single_label`).
- [ ] `scan_shipment_carton_document` -> Pack `B` (`per_carton_single`).
- [ ] `scan_carton_picking` -> Pack `A` (`single_carton`).
- [ ] Admin `wms_shipment_print_doc` (shipment_note/packing_list/donation) -> packs `C/B/B`.
- [ ] Admin `wms_shipment_print_carton` -> Pack `B` (`per_carton_single`).

## Functional Validation
- [ ] Pack A: génération PDF valide depuis bouton picking.
- [ ] Pack B: PDF fusionné avec ordre `liste globale -> listes carton -> attestation`.
- [ ] Pack C: PDF fusionné `bon expédition + etiquette contact`.
- [ ] Pack D: génération labels en mode all labels et single label.
- [ ] Doc types hors pack V1 (`humanitarian_certificate`, `customs`) restent en fallback legacy.

## Storage & Sync
- [ ] `GeneratedPrintArtifact` créé avec statut `sync_pending` après génération.
- [ ] `GeneratedPrintArtifactItem` créé pour chaque document source.
- [ ] Commande queue OK: `manage.py process_print_artifact_queue --limit 20`.
- [ ] Passage de statut vérifié: `sync_pending -> synced` (succès) et retry/`sync_failed` (erreur).
- [ ] `onedrive_path` rempli pour les artefacts synchronisés.

## Validation Commands
- [ ] `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.print -v 2`
- [ ] `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs wms.tests.views.tests_views_print_labels wms.tests.admin.tests_admin_extra api.tests.tests_ui_endpoints -v 2`
- [ ] `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py check`
- [ ] `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py makemigrations --check`
- [ ] `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py migrate --plan`
