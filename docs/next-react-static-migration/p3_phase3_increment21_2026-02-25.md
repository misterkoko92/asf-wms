# P3 Report - Increment 21 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur la route stock `/app/scan/stock/`:

- rapprocher le rendu table des details produit legacy (barcode + marque),
- gerer explicitement l etat vide apres filtrage,
- remettre les liens d administration `categorie` / `entrepot` presents en legacy.

## Livrables

## 1) API stock: champ barcode expose

Fichiers:

- `api/v1/ui_views.py`
- `api/tests/tests_ui_endpoints.py`

Ajouts:

- `GET /api/v1/ui/stock/` expose desormais `barcode` pour chaque ligne produit.
- test API dedie `test_ui_stock_exposes_brand_and_barcode_fields`.

## 2) Front Next stock: parite micro-UX

Fichiers:

- `frontend-next/app/lib/api/types.ts`
- `frontend-next/app/components/scan-stock-live.tsx`

Ajouts:

- extension `ScanStockDto.products[]` avec `barcode`.
- table stock enrichie:
  - reference + barcode (si present),
  - produit + marque (si presente),
  - etat vide explicite: `Aucun produit en stock pour ces filtres.`.
- filtres categorie/entrepot enrichis avec liens admin:
  - `/admin/wms/productcategory/add/`,
  - `/admin/wms/warehouse/add/`.

## 3) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- test `test_next_stock_displays_product_metadata_and_empty_state`.

Scenario:

- ouvrir `/app/scan/stock/`,
- verifier affichage barcode + marque sur une ligne produit,
- verifier presence des liens `Ajouter categorie` / `Ajouter entrepot`,
- appliquer un filtre sans resultat et verifier le message d etat vide.

## Validation executee

- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_stock_exposes_brand_and_barcode_fields` -> OK
- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_stock_displays_product_metadata_and_empty_state wms.tests.core.tests_ui.NextUiTests.test_next_stock_filters_by_query_workflow wms.tests.core.tests_ui.NextUiTests.test_next_stock_update_and_out_workflow` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests -v 2` -> OK (29 tests)
- `.venv/bin/ruff check api/v1/ui_views.py api/tests/tests_ui_endpoints.py wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- finaliser les ecarts visuels/libelles residuels sur `shipment-create` (encore le plus hybride),
- consolider la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
