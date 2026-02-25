# P3 Report - Increment 12 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur le dashboard scan:

- rapprocher la section Stock du template legacy,
- exposer les donnees `stock sous seuil` en API dashboard,
- valider le rendu navigateur du tableau low stock.

## Livrables

## 1) API dashboard enrichie `stock sous seuil`

Fichiers:

- `api/v1/ui_views.py`
- `api/tests/tests_ui_endpoints.py`

Ajouts:

- `GET /api/v1/ui/dashboard/` enrichi avec:
  - `low_stock_threshold`,
  - `low_stock_rows` (top low stock),
- reutilisation de `low_stock_rows` pour les pending actions stock,
- test API dedie `test_ui_dashboard_exposes_low_stock_rows`.

## 2) Front Next dashboard: panneau low stock

Fichiers:

- `frontend-next/app/components/scan-dashboard-live.tsx`
- `frontend-next/app/lib/api/types.ts`

Ajouts:

- nouveau panneau `Stock sous seuil`:
  - table `Produit / Ref / Disponible` si lignes presentes,
  - message explicite si aucune ligne,
  - rappel du seuil global.

## 3) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- fixture produit low stock dashboard,
- test `test_next_scan_dashboard_displays_low_stock_table`.

Scenario:

- ouvrir `/app/scan/dashboard/`,
- verifier la presence du panneau `stock sous seuil`,
- verifier la presence du SKU low stock dans ce panneau.

## Validation executee

- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_exposes_low_stock_rows api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_destination_filter_and_options` -> OK
- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_low_stock_table wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_filters_by_destination` -> OK
- `make test-next-ui` -> OK (20 tests)
- `.venv/bin/ruff check api/v1/ui_views.py api/tests/tests_ui_endpoints.py wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- finaliser les ecarts visuels/libelles residuels sur ecrans prioritaires,
- consolider la checklist de recette metier manuelle complete,
- preparer la cloture Sprint B et cadrage Sprint C.
