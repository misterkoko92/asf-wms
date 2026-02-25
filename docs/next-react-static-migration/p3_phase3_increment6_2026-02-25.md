# P3 Report - Increment 6 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur le dashboard scan:

- supprimer le contenu maquette statique restant,
- afficher KPI/timeline/actions depuis l'API UI,
- valider le rendu navigateur sur donnees reelles.

## Livrables

## 1) Dashboard Next branche 100% API

Fichiers:

- `frontend-next/app/components/scan-dashboard-live.tsx`
- `frontend-next/app/scan/dashboard/page.tsx`

Changements:

- retrait des jeux de donnees hardcodes (timeline/pending actions/KPI),
- rendu live des KPI API:
  - expeditions ouvertes
  - alertes stock
  - litiges actifs
  - commandes en attente
  - expeditions en retard,
- rendu live timeline (`reference` + `status` + timestamp formatte),
- rendu live table des actions en attente (`label`, `reference`, `owner`, `priority`),
- liens d'action rapides vers routes Next (`cartons`, `shipment-create`, `stock`).

## 2) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajout:

- `test_next_scan_dashboard_displays_live_timeline_and_actions`.

Scenario:

- ouvrir `/app/scan/dashboard/`,
- verifier la presence d'une reference expedition de test issue de la timeline API,
- verifier la presence d'une reference action stock issue de `pending_actions`.

## Validation executee

- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_live_timeline_and_actions` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_loads_for_staff` -> OK
- `make test-next-ui` -> OK (14 tests)
- `.venv/bin/ruff check wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- finaliser l'alignement visuel strict avec les templates legacy sur les ecrans prioritaires deja routes,
- consolider les micro-comportements (libelles, etats, messages) encore divergents,
- preparer la recette metier manuelle complete avant passage Sprint B -> Sprint C.
