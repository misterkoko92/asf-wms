# P3 Report - Increment 2 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur l'ecran prioritaire `/app/scan/stock/`:

- brancher un workflow de filtrage utilisateur (recherche, categorie, entrepot, tri),
- aligner la table "Produits en stock" avec les colonnes metier utiles,
- conserver les mutations stock inline (`MAJ`, `Sortie`) deja actives.

## Livrables

## 1) Filtrage stock et table "Produits en stock" (route Next)

Fichier:

- `frontend-next/app/components/scan-stock-live.tsx`

Ajouts:

- formulaire de filtres avec labels/actions:
  - `Recherche`
  - `Categorie`
  - `Entrepot`
  - `Tri`
  - `Filtrer`
  - `Reinitialiser`
- branchement des filtres sur `GET /api/v1/ui/stock/` via query string (`q`, `category`, `warehouse`, `sort`),
- rechargement de la liste en conservant le filtre actif apres mutation stock,
- table "Produits en stock (N)" avec:
  - `Reference`
  - `Produit`
  - `Categorie`
  - `Stock`
  - `Derniere modification`.

## 2) Couverture navigateur Playwright dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajout:

- `test_next_stock_filters_by_query_workflow`.

Scenario:

- ouvrir `/app/scan/stock/`,
- attendre l'affichage de deux SKU connues,
- saisir une recherche SKU et cliquer `Filtrer`,
- verifier que la ligne attendue reste visible et que l'autre disparait.

## Ajustements de stabilite

- hydratation initiale des filtres stock fiabilisee avec `useRef` (evite un rechargement parasite),
- assertion Playwright de filtre rendue robuste via verification sur SKU (independante des transformations de casse UI).

## Validation executee

- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_stock_filters_by_query_workflow` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_stock_update_and_out_workflow` -> OK
- `make test-next-ui` -> OK (10 tests)
- `.venv/bin/ruff check wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- finir la parite stricte dashboard/stock/shipment-create sur structure visuelle et micro-interactions legacy,
- traiter les routes dediees encore absentes (`shipments-ready`, `shipments-tracking` cible finale, `cartons`),
- preparer puis derouler la recette metier manuelle ecran par ecran.
