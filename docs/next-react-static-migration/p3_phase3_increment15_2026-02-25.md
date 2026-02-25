# P3 Report - Increment 15 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur le dashboard scan:

- rapprocher le bloc `Expeditions` du template legacy,
- exposer les cartes metier expeditions en API dashboard,
- verifier le rendu navigateur des cartes expeditions sur la route Next.

## Livrables

## 1) API dashboard: cartes expeditions

Fichiers:

- `api/v1/ui_views.py`
- `api/tests/tests_ui_endpoints.py`

Ajouts:

- `GET /api/v1/ui/dashboard/` enrichi avec `shipment_cards`:
  - `Brouillons`,
  - `En cours`,
  - `Pretes`,
  - `Planifiees (semaine)`,
  - `En transit`,
  - `Litiges ouverts`.
- calcul aligne sur la logique legacy:
  - brouillons temporaires `EXP-TEMP-*`,
  - en transit (planifie + expedie + recu escale),
  - planifiees semaine via tracking event `planned`.
- test API dedie `test_ui_dashboard_exposes_shipment_cards`.

## 2) Front Next dashboard: panneau expeditions

Fichiers:

- `frontend-next/app/components/scan-dashboard-live.tsx`
- `frontend-next/app/lib/api/types.ts`
- `frontend-next/app/globals.css`

Ajouts:

- nouveau panneau `Expeditions` dans le dashboard Next:
  - rendu des 6 cartes metier expeditions,
  - lien par carte vers la route legacy cible,
  - application visuelle des tons (`warn`, `success`, `danger`).

## 3) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- test `test_next_scan_dashboard_displays_shipment_cards`.

Scenario:

- ouvrir `/app/scan/dashboard/`,
- verifier la presence du panneau `Expeditions`,
- verifier les cartes `Brouillons` et `En transit`,
- verifier la valeur `En transit` attendue.

## Validation executee

- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_exposes_shipment_cards api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_exposes_shipment_chart_rows api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_period_filter_and_activity_cards` -> OK
- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_shipment_cards wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_shipment_chart wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_filters_by_destination` -> OK
- `make test-next-ui` -> OK (23 tests)
- `.venv/bin/ruff check api/v1/ui_views.py api/tests/tests_ui_endpoints.py wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- finaliser les ecarts visuels/libelles residuels sur ecrans prioritaires (dashboard/stock/shipment-create),
- consolider la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
