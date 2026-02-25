# P2 Report - Increment 7 (2026-02-25)

## Objectif

Continuer Sprint A en etendant le harness navigateur Playwright vers des workflows metier reels sur les ecrans Next deja disponibles.

Scope livre dans cet increment:

- workflow documents expedition (chargement + upload + suppression),
- workflow templates impression (save + reset versionne),
- alignement client API Next avec la protection CSRF Django pour mutations.

## Livrables

## 1) Next UI tests navigateur etendus

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- `test_next_shipment_documents_upload_and_delete_workflow`
- `test_next_templates_save_and_reset_workflow`

Evolutions setup:

- fixture shipment staff pour workflow documents,
- fixture user superuser pour workflow templates,
- injection session + cookie CSRF dans le contexte Playwright.

## 2) Client API Next compatible CSRF pour mutations

Fichier:

- `frontend-next/app/lib/api/client.ts`

Ajouts:

- lecture cookie `csrftoken`,
- envoi header `x-csrftoken` sur `POST/PATCH/DELETE`,
- conservation du comportement `GET` inchangé.

## 3) Build statique Next regenere

Commande:

- `cd frontend-next && npm run build`

But:

- regenere `frontend-next/out` avec le client API corrige pour execution des tests navigateur.

## Validation executee

- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipment_documents_upload_and_delete_workflow wms.tests.core.tests_ui.NextUiTests.test_next_templates_save_and_reset_workflow` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests` -> OK (5 tests)
- `make test-next-ui` -> OK
- `.venv/bin/ruff check wms/tests/core/tests_ui.py` -> OK
- `cd frontend-next && npm run build` -> OK

## Reste a faire pour Sprint A / P2

- couvrir en navigateur les workflows mutations stock (update/out),
- couvrir en navigateur les workflows expedition (create/tracking/close),
- couvrir en navigateur les workflows portal mutations (orders/recipients/account),
- brancher execution reguliere de ces scenarios sur environnement cible.
