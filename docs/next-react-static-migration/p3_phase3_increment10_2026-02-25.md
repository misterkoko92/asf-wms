# P3 Report - Increment 10 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur le dashboard scan:

- couvrir le filtre destination present en legacy,
- exposer les options de destination depuis l'API UI,
- valider le workflow navigateur de filtrage KPI.

## Livrables

## 1) API dashboard: filtre destination complet

Fichiers:

- `api/v1/ui_views.py`
- `api/tests/tests_ui_endpoints.py`

Ajouts:

- enrichissement de `GET /api/v1/ui/dashboard/`:
  - `filters.destination` conserve,
  - nouveau `filters.destinations` (liste `{id,label}` active),
- test API dedie:
  - verification de la presence des options destination,
  - verification de l'effet du filtre `?destination=<id>` sur `kpis.open_shipments`.

## 2) Front Next dashboard: UI filtre destination

Fichiers:

- `frontend-next/app/components/scan-dashboard-live.tsx`
- `frontend-next/app/lib/api/ui.ts`
- `frontend-next/app/lib/api/types.ts`

Ajouts:

- formulaire filtre dashboard:
  - select `Destination`,
  - bouton `Filtrer`,
  - bouton `Reinitialiser`,
- chargement API avec query string destination,
- hydratation/rechargement live des KPI apres application du filtre.

## 3) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- fixture destination secondaire + expedition associee,
- test `test_next_scan_dashboard_filters_by_destination`:
  - verifier KPI `Expeditions ouvertes` avant filtre,
  - appliquer destination secondaire,
  - verifier KPI filtre.

## Validation executee

- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_destination_filter_and_options api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_requires_staff` -> OK
- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_filters_by_destination wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_live_timeline_and_actions` -> OK
- `make test-next-ui` -> OK (18 tests)
- `.venv/bin/ruff check api/v1/ui_views.py api/tests/tests_ui_endpoints.py wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- aligner les derniers ecarts de parite visuelle/micro-libelles sur ecrans prioritaires,
- finaliser la checklist recette metier manuelle ecran par ecran,
- preparer la cloture Sprint B puis transition Sprint C.
