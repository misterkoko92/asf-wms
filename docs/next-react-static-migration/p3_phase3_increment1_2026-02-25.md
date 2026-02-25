# P3 Report - Increment 1 (2026-02-25)

## Objectif

Demarrer Sprint B (Phase 3 parite stricte) avec un premier lot sur l'ecran prioritaire `/app/scan/shipment-create/`:

- couvrir la creation expedition depuis un produit + quantite (creation colis inline),
- conserver la voie existante par selection de carton,
- ajouter la couverture navigateur correspondante.

## Livrables

## 1) Workflow creation colis inline sur shipment-create

Fichier:

- `frontend-next/app/components/scan-shipment-options-live.tsx`

Ajouts:

- mode creation expedition "carton **ou** produit+quantite",
- option vide sur `Carton ID` pour activer le mode produit,
- champs `Product code (Creation)` et `Quantite (Creation)`,
- validation front explicite sur les combinaisons invalides.

## 2) Test navigateur dedie (Playwright)

Fichier:

- `wms/tests/core/tests_ui.py`

Ajout:

- `test_next_shipment_create_from_product_line_workflow`.

Scenario:

- ouvrir `/app/scan/shipment-create/`,
- creation expedition sans carton pre-existant (produit + quantite),
- verifier en base:
  - creation d'un nouveau carton,
  - statut `ASSIGNED`,
  - affectation shipment,
  - decrement stock lot.

## Validation executee

- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_from_product_line_workflow` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_tracking_close_workflow` -> OK
- `make test-next-ui` -> OK (9 tests)
- `.venv/bin/ruff check wms/tests/core/tests_ui.py` -> OK
- `cd frontend-next && npm run build` -> OK

## Reste Sprint B (Phase 3)

- finaliser parite stricte UI/UX/dashboard/stock/shipment-create,
- finir les actions 1 clic restantes (notamment vues dediees `shipments-ready`, `tracking`),
- preparer recette metier manuelle ecran par ecran.
