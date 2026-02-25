# P3 Report - Increment 20 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur le dashboard scan:

- combler les blocs dashboard encore absents cote API/Next (`Stock`, `Blocages workflow`, `Suivi SLA`),
- aligner les metriques avec la logique legacy existante,
- valider le rendu navigateur de ces blocs sur la route Next.

## Livrables

## 1) API dashboard: stock/workflow/SLA

Fichiers:

- `api/v1/ui_views.py`
- `api/tests/tests_ui_endpoints.py`

Ajouts:

- nouveaux helpers dashboard:
  - `_dashboard_stock_snapshot(...)`,
  - `_dashboard_workflow_blockage_snapshot(...)`,
  - `_build_dashboard_sla_rows(...)`.
- payload `GET /api/v1/ui/dashboard/` enrichi avec:
  - `stock_cards`,
  - `workflow_blockage_hours`,
  - `workflow_blockage_cards`,
  - `sla_cards`.
- conservation des `low_stock_rows` via snapshot stock unifie.
- tests API dedies:
  - `test_ui_dashboard_exposes_stock_cards`,
  - `test_ui_dashboard_exposes_workflow_blockage_and_sla_cards`.

## 2) Front Next dashboard: 3 panneaux manquants

Fichiers:

- `frontend-next/app/lib/api/types.ts`
- `frontend-next/app/components/scan-dashboard-live.tsx`

Ajouts:

- extension du contrat `ScanDashboardDto` pour les nouveaux champs dashboard.
- rendu live des panneaux:
  - `Stock`,
  - `Blocages workflow (>Nh)`,
  - `Suivi SLA`.

## 3) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- test `test_next_scan_dashboard_displays_workflow_and_sla_cards`.

Scenario:

- ouvrir `/app/scan/dashboard/`,
- verifier la presence du panneau `Blocages workflow` et de ses cartes metier,
- verifier la presence du panneau `Suivi SLA` et de ses libelles de segments.

## Validation executee

- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_exposes_tracking_cards api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_exposes_technical_cards api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_exposes_stock_cards api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_exposes_workflow_blockage_and_sla_cards` -> OK
- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_workflow_and_sla_cards wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_technical_cards wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_tracking_cards` -> OK
- `make test-next-ui` -> OK (28 tests)
- `.venv/bin/ruff check api/v1/ui_views.py api/tests/tests_ui_endpoints.py wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- finaliser les ecarts visuels/libelles residuels sur ecrans prioritaires (dashboard/stock/shipment-create),
- consolider la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
