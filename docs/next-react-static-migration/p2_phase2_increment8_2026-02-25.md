# P2 Report - Increment 8 (2026-02-25)

## Objectif

Poursuivre Sprint A en couvrant en navigateur le workflow stock mutation (`update` puis `out`) sur l'ecran Next `/app/scan/stock/`.

## Livrables

## 1) Ecran stock Next connecte aux mutations API

Fichier:

- `frontend-next/app/components/scan-stock-live.tsx`

Ajouts:

- formulaire mutation `stock/update` (product code, quantite, date expiration, lot),
- formulaire mutation `stock/out` (product code, quantite, raison, notes),
- feedback inline succes/erreur,
- rechargement automatique de la table stock apres mutation.

Endpoints utilises:

- `POST /api/v1/ui/stock/update/`
- `POST /api/v1/ui/stock/out/`

## 2) Test navigateur workflow stock complet

Fichier:

- `wms/tests/core/tests_ui.py`

Ajout:

- `test_next_stock_update_and_out_workflow`

Scenario:

- ouvrir `/app/scan/stock/` en session staff,
- executer une MAJ stock valide,
- executer une sortie stock valide,
- verifier en base le resultat quantitatif attendu.

## Validation executee

- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_stock_update_and_out_workflow` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests` -> OK (6 tests)
- `make test-next-ui` -> OK
- `.venv/bin/ruff check wms/tests/core/tests_ui.py` -> OK
- `cd frontend-next && npm run build` -> OK

## Reste a faire pour Sprint A / P2

- workflow navigateur expedition mutations (`create/tracking/close`),
- workflow navigateur portal mutations (`orders/recipients/account`),
- execution reguliere des E2E navigateur sur environnement cible.
