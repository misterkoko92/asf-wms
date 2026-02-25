# P3 Report - Increment 13 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur le dashboard scan:

- rapprocher le filtre `Periode KPI` du comportement legacy,
- exposer les donnees de periode (`period`, `period_choices`, `period_label`) en API dashboard,
- afficher un bloc `KPI periode` en Next avec les cartes d activite.

## Livrables

## 1) API dashboard: filtre periode + cartes activite

Fichiers:

- `api/v1/ui_views.py`
- `api/tests/tests_ui_endpoints.py`

Ajouts:

- `GET /api/v1/ui/dashboard/` enrichi avec:
  - `filters.period`,
  - `filters.period_choices`,
  - `period_label`,
  - `activity_cards`.
- prise en charge de `?period=today|7d|30d|week` avec normalisation et borne temporelle.
- test API dedie `test_ui_dashboard_period_filter_and_activity_cards`.

## 2) Front Next dashboard: filtre Periode KPI + bloc KPI periode

Fichiers:

- `frontend-next/app/components/scan-dashboard-live.tsx`
- `frontend-next/app/lib/api/types.ts`

Ajouts:

- formulaire filtres dashboard etendu:
  - select `Periode KPI`,
  - conservation du filtre destination existant,
  - reset revenant a l etat par defaut API.
- nouveau panneau `KPI periode (<label>)`:
  - cartes `Expeditions creees`, `Colis crees`, `Receptions creees`, `Commandes creees`.

## 3) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- test `test_next_scan_dashboard_filters_by_period`.

Scenario:

- ouvrir `/app/scan/dashboard/`,
- verifier la carte `Expeditions creees` par defaut,
- selectionner `30d`,
- re-filtrer et verifier la mise a jour de la valeur.

## Validation executee

- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_period_filter_and_activity_cards api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_destination_filter_and_options` -> OK
- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_filters_by_period wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_filters_by_destination wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_low_stock_table` -> OK
- `make test-next-ui` -> OK (21 tests)
- `.venv/bin/ruff check api/v1/ui_views.py api/tests/tests_ui_endpoints.py wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- finaliser les ecarts visuels/libelles residuels sur ecrans prioritaires (dashboard/stock/shipment-create),
- consolider la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
