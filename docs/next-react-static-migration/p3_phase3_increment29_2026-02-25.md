# P3 Report - Increment 29 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur la coherence des libelles:

- supprimer les derniers libelles anglais visibles dans le workflow expeditions,
- harmoniser la terminologie utilisateur sur `suivi`,
- verrouiller la non-regression par tests navigateur.

## Livrables

## 1) Front Next: libelles francises sur create/tracking

Fichiers:

- `frontend-next/app/components/scan-shipment-options-live.tsx`
- `frontend-next/app/components/scan-shipment-tracking-live.tsx`

Modifications:

- tracking/cloture:
  - `Expedition (Tracking)` -> `Expedition (Suivi)`
  - `Statut tracking` -> `Statut suivi`
  - `Envoyer tracking` -> `Envoyer suivi`
  - message d'erreur `... (Tracking) invalide.` -> `... (Suivi) invalide.`
- creation colis:
  - `Product code (Creation)` -> `Code produit (Creation)`
- `aria-label` alignes sur les nouveaux libelles pour garder des selecteurs exacts stables.

## 2) Couverture navigateur adaptee

Fichier:

- `wms/tests/core/tests_ui.py`

Modifications:

- mise a jour des interactions Playwright vers les nouveaux labels/boutons sur:
  - `test_next_shipment_create_tracking_close_workflow`
  - `test_next_shipment_create_from_product_line_workflow`
  - `test_next_shipments_tracking_route_workflow`
- renforcement de `test_next_shipment_create_selects_use_business_labels_without_id_prefix`:
  - verification d'absence de `product code (creation)` et `statut tracking`.

## Validation executee

- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_tracking_close_workflow wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_from_product_line_workflow wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_selects_use_business_labels_without_id_prefix wms.tests.core.tests_ui.NextUiTests.test_next_shipments_tracking_route_workflow -v 2` -> OK
- `make test-next-ui` -> OK (32 tests)
- `.venv/bin/ruff check wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- poursuivre l'alignement micro-libelles/help texts restants sur `shipment-create`,
- consolider la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
