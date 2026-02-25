# P3 Report - Increment 18 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur le dashboard scan:

- rapprocher le bloc `Suivi / Alertes` du template legacy,
- exposer les cartes metier tracking en API dashboard,
- verifier le rendu navigateur des cartes suivi/alertes sur la route Next.

## Livrables

## 1) API dashboard: cartes suivi/alertes

Fichiers:

- `api/v1/ui_views.py`
- `api/tests/tests_ui_endpoints.py`

Ajouts:

- `GET /api/v1/ui/dashboard/` enrichi avec:
  - `tracking_alert_hours`,
  - `tracking_cards`.
- logique alignee legacy:
  - `Planifiees sans mise a bord >Nh`,
  - `Expediees sans recu escale >Nh`,
  - `Recu escale sans livraison >Nh`,
  - `Dossiers cloturables`.
- annotation tracking enrichie (`planned`, `boarding_ok`, `received_correspondent`, `received_recipient`) pour calculer alertes et cloturables.
- test API dedie `test_ui_dashboard_exposes_tracking_cards`.

## 2) Front Next dashboard: panneau suivi/alertes

Fichiers:

- `frontend-next/app/components/scan-dashboard-live.tsx`
- `frontend-next/app/lib/api/types.ts`

Ajouts:

- nouveau panneau `Suivi / Alertes (>Nh)` dans le dashboard Next:
  - rendu des 4 cartes tracking,
  - application des tons (`danger`, `success`, `neutral`).

## 3) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- test `test_next_scan_dashboard_displays_tracking_cards`.

Scenario:

- ouvrir `/app/scan/dashboard/`,
- verifier la presence du panneau `Suivi / Alertes`,
- verifier la presence des 4 cartes tracking et du compteur `Dossiers cloturables`.

## Validation executee

- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_exposes_tracking_cards api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_dashboard_exposes_flow_cards` -> OK
- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_tracking_cards wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_flow_cards wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_displays_carton_cards` -> OK
- `make test-next-ui` -> OK (26 tests)
- `.venv/bin/ruff check api/v1/ui_views.py api/tests/tests_ui_endpoints.py wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- finaliser les ecarts visuels/libelles residuels sur ecrans prioritaires (dashboard/stock/shipment-create),
- consolider la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
