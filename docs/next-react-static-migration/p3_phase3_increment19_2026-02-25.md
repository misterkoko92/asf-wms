# P3 Report - Increment 19 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur le dashboard scan:

- ajouter le bloc `Technique / Queue email` cote API dashboard,
- brancher ce bloc en rendu live sur la route Next,
- couvrir ce lot par tests API + navigateur.

## Livrables

## 1) API dashboard: cartes techniques queue email

Fichiers:

- `api/v1/ui_views.py`
- `api/tests/tests_ui_endpoints.py`

Ajouts:

- nouveau helper `_dashboard_email_queue_snapshot(...)`:
  - scope queue email uniquement (`OUTBOUND`, `source=wms.email`, `event_type=send_email`),
  - comptage `pending`, `processing`, `failed`,
  - comptage des `processing` depassant le timeout runtime.
- payload `GET /api/v1/ui/dashboard/` enrichi avec:
  - `queue_processing_timeout_seconds`,
  - `technical_cards`.
- 4 cartes techniques exposees:
  - `Queue email en attente`,
  - `Queue email en traitement`,
  - `Queue email en echec`,
  - `Queue email bloquee (timeout)`.
- test API dedie `test_ui_dashboard_exposes_technical_cards`.

## 2) Front Next dashboard: panneau technique

Fichiers:

- `frontend-next/app/lib/api/types.ts`
- `frontend-next/app/components/scan-dashboard-live.tsx`

Ajouts:

- extension du contrat `ScanDashboardDto`:
  - `queue_processing_timeout_seconds`,
  - `technical_cards`.
- nouveau panneau dashboard `Technique / Queue email`:
  - rendu live des 4 cartes techniques,
  - gestion des tons (`warn`, `danger`, `success`, `neutral`) selon payload API.

## 3) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- test `test_next_scan_dashboard_displays_technical_cards`.

Scenario:

- ouvrir `/app/scan/dashboard/`,
- verifier la presence du panneau `Technique / Queue email`,
- verifier la presence des 4 cartes techniques et des compteurs attendus.

## Validation executee

- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_exposes_tracking_cards api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_exposes_technical_cards` -> OK
- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_tracking_cards wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_technical_cards` -> OK
- `make test-next-ui` -> OK (27 tests)
- `.venv/bin/ruff check api/v1/ui_views.py api/tests/tests_ui_endpoints.py wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- finaliser les ecarts visuels/libelles residuels sur ecrans prioritaires (dashboard/stock/shipment-create),
- consolider la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
