# P3 Report - Increment 14 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur le dashboard scan:

- rapprocher la section `Graphique expeditions` du template legacy,
- exposer les donnees de repartition statuts en API dashboard,
- verifier le rendu navigateur du graphique sur la route Next.

## Livrables

## 1) API dashboard: repartition statuts expedition

Fichiers:

- `api/v1/ui_views.py`
- `api/tests/tests_ui_endpoints.py`

Ajouts:

- `GET /api/v1/ui/dashboard/` enrichi avec:
  - `shipments_total`,
  - `shipment_chart_rows` (`status`, `label`, `count`, `percent`).
- ordre de statuts aligne sur legacy (`draft` -> `delivered`) et calcul des pourcentages.
- test API dedie `test_ui_dashboard_exposes_shipment_chart_rows`.

## 2) Front Next dashboard: panneau graphique expeditions

Fichiers:

- `frontend-next/app/components/scan-dashboard-live.tsx`
- `frontend-next/app/lib/api/types.ts`
- `frontend-next/app/globals.css`

Ajouts:

- nouveau panneau `Graphique expeditions (N)`:
  - lignes par statut,
  - barre de progression (%),
  - valeur `count / percent`.
- styles dedies `chart-*` pour une lecture compacte desktop/mobile.

## 3) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- test `test_next_scan_dashboard_displays_shipment_chart`.

Scenario:

- ouvrir `/app/scan/dashboard/`,
- verifier la presence du panneau `graphique expeditions`,
- verifier la presence du total et des lignes du graphique.

## Validation executee

- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_exposes_shipment_chart_rows api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_period_filter_and_activity_cards` -> OK
- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_shipment_chart wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_filters_by_period wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_low_stock_table` -> OK
- `make test-next-ui` -> OK (22 tests)
- `.venv/bin/ruff check api/v1/ui_views.py api/tests/tests_ui_endpoints.py wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- finaliser les ecarts visuels/libelles residuels sur ecrans prioritaires (dashboard/stock/shipment-create),
- consolider la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
