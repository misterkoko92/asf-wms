# P2 Report - Increment 9 (2026-02-25)

## Objectif

Poursuivre Sprint A en couvrant en navigateur le workflow expedition complet (`create` -> `tracking` -> `close`) sur l'ecran Next `/app/scan/shipment-create/`.

## Livrables

## 1) Ecran expedition Next branche aux mutations API

Fichier:

- `frontend-next/app/components/scan-shipment-options-live.tsx`

Ajouts:

- formulaire creation expedition (destination, expediteur, destinataire, correspondant, carton),
- formulaire tracking expedition (shipment id, statut, actor),
- formulaire cloture expedition,
- feedback inline succes/erreur sur les 3 mutations.

Endpoints utilises:

- `POST /api/v1/ui/shipments/`
- `POST /api/v1/ui/shipments/<id>/tracking-events/`
- `POST /api/v1/ui/shipments/<id>/close/`

## 2) Test navigateur workflow expedition complet

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- fixture contacts tags metier (`expediteur`, `destinataire`, `correspondant`) pour alimenter `form-options`,
- test `test_next_shipment_create_tracking_close_workflow`.

Scenario:

- ouvrir `/app/scan/shipment-create/` en session staff,
- creer une expedition depuis un carton disponible,
- pousser deux evenements tracking (`received_correspondent`, `received_recipient`),
- cloturer l'expedition,
- verifier en base l'affectation carton + `closed_at`.

## Validation executee

- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_tracking_close_workflow` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests` -> OK (7 tests)
- `make test-next-ui` -> OK
- `.venv/bin/ruff check wms/tests/core/tests_ui.py` -> OK
- `cd frontend-next && npm run build` -> OK

## Reste a faire pour Sprint A / P2

- couvrir en navigateur les workflows portal mutations (`orders/recipients/account`),
- brancher execution reguliere des scenarios Playwright sur environnement cible.
