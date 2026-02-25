# P3 Report - Increment 17 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur le dashboard scan:

- rapprocher le bloc `Receptions / Commandes` du template legacy,
- exposer les cartes metier flow en API dashboard,
- verifier le rendu navigateur des cartes flow sur la route Next.

## Livrables

## 1) API dashboard: cartes flow receptions/commandes

Fichiers:

- `api/v1/ui_views.py`
- `api/tests/tests_ui_endpoints.py`

Ajouts:

- `GET /api/v1/ui/dashboard/` enrichi avec `flow_cards`:
  - `Receptions en attente`,
  - `Cmd en attente de validation`,
  - `Cmd a modifier`,
  - `Cmd validees sans expedition`.
- logique alignee legacy:
  - comptage global (non filtre destination),
  - tons `warn` sur receptions en attente et commandes a modifier.
- test API dedie `test_ui_dashboard_exposes_flow_cards`.

## 2) Front Next dashboard: panneau receptions/commandes

Fichiers:

- `frontend-next/app/components/scan-dashboard-live.tsx`
- `frontend-next/app/lib/api/types.ts`

Ajouts:

- nouveau panneau `Receptions / Commandes` dans le dashboard Next:
  - rendu des 4 cartes flow,
  - application des tons visuels (`warn`).

## 3) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- test `test_next_scan_dashboard_displays_flow_cards`.

Scenario:

- ouvrir `/app/scan/dashboard/`,
- verifier la presence du panneau `Receptions / Commandes`,
- verifier les labels et valeurs des cartes flow creees dans le setup test.

## Validation executee

- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_exposes_flow_cards api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_exposes_carton_cards` -> OK
- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_flow_cards wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_carton_cards wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_shipment_cards` -> OK
- `make test-next-ui` -> OK (25 tests)
- `.venv/bin/ruff check api/v1/ui_views.py api/tests/tests_ui_endpoints.py wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- finaliser les ecarts visuels/libelles residuels sur ecrans prioritaires (dashboard/stock/shipment-create),
- consolider la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
