# P3 Report - Increment 11 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur `shipments-tracking`:

- aligner les etats visuels des boutons de cloture avec le legacy,
- distinguer clairement les cas clos / closable / bloque,
- verrouiller la non-regression via test navigateur dedie.

## Livrables

## 1) Etats visuels de cloture alignes sur legacy

Fichiers:

- `frontend-next/app/components/scan-shipment-tracking-live.tsx`
- `frontend-next/app/globals.css`

Changements:

- ajout de variantes visuelles:
  - `btn-success-soft` pour les etats closables et dossiers deja clos,
  - `btn-danger-soft` pour les dossiers non closables,
- application des classes selon l'etat metier de chaque ligne:
  - `shipment.is_closed` -> bouton desactive style succes,
  - `shipment.can_close` -> bouton actif style succes,
  - sinon -> bouton alerte style danger.

## 2) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajout:

- `test_next_shipments_tracking_route_close_buttons_match_state_styles`.

Scenario:

- creer des expeditions de test pour couvrir les 3 etats (closable, bloquee, deja close),
- verifier les classes CSS attendues sur les boutons,
- verifier que le bouton dossier clos est desactive.

## Validation executee

- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipments_tracking_route_close_buttons_match_state_styles` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipments_tracking_route_workflow wms.tests.core.tests_ui.NextUiTests.test_next_shipments_tracking_route_lists_shipments wms.tests.core.tests_ui.NextUiTests.test_next_shipments_tracking_route_close_buttons_match_state_styles` -> OK
- `make test-next-ui` -> OK (19 tests)
- `.venv/bin/ruff check wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- finaliser les derniers ecarts de micro-libelles/structure visuelle sur ecrans prioritaires,
- preparer et executer la recette metier manuelle complete,
- consolider le bilan de fin Sprint B pour passage Sprint C.
