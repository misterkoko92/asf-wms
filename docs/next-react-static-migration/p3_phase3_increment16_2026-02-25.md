# P3 Report - Increment 16 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur le dashboard scan:

- rapprocher le bloc `Colis` du template legacy,
- exposer les cartes metier colis en API dashboard,
- verifier le rendu navigateur des cartes colis et leur reaction au filtre destination.

## Livrables

## 1) API dashboard: cartes colis

Fichiers:

- `api/v1/ui_views.py`
- `api/tests/tests_ui_endpoints.py`

Ajouts:

- `GET /api/v1/ui/dashboard/` enrichi avec `carton_cards`:
  - `En preparation`,
  - `Prets non affectes`,
  - `Affectes non etiquetes`,
  - `Etiquetes`,
  - `Colis expedies`.
- logique de filtrage destination alignee legacy:
  - `En preparation` et `Prets non affectes` restent globaux,
  - `Affectes non etiquetes`, `Etiquetes`, `Colis expedies` sont filtres par destination selectionnee.
- test API dedie `test_ui_dashboard_exposes_carton_cards`.

## 2) Front Next dashboard: panneau colis

Fichiers:

- `frontend-next/app/components/scan-dashboard-live.tsx`
- `frontend-next/app/lib/api/types.ts`

Ajouts:

- nouveau panneau `Colis` dans le dashboard Next:
  - rendu des 5 cartes metier colis,
  - application visuelle des tons (`warn`, `success`).

## 3) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- test `test_next_scan_dashboard_displays_carton_cards`.

Scenario:

- ouvrir `/app/scan/dashboard/`,
- verifier la presence du panneau `Colis`,
- verifier la valeur `Affectes non etiquetes` sans filtre,
- appliquer le filtre destination et verifier la mise a jour de la valeur.

## Validation executee

- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_exposes_carton_cards api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_exposes_shipment_cards` -> OK
- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_carton_cards wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_shipment_cards wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_filters_by_destination` -> OK
- `make test-next-ui` -> OK (24 tests)
- `.venv/bin/ruff check api/v1/ui_views.py api/tests/tests_ui_endpoints.py wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- finaliser les ecarts visuels/libelles residuels sur ecrans prioritaires (dashboard/stock/shipment-create),
- consolider la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
