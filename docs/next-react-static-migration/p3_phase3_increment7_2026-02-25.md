# P3 Report - Increment 7 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur l'ecran prioritaire `shipments-tracking`:

- brancher la liste expedition live (plus uniquement les mutations),
- exposer un endpoint UI dedie avec filtres legacy,
- valider le rendu navigateur sur donnees reelles.

## Livrables

## 1) Endpoint UI dedie "suivi expeditions"

Fichiers:

- `api/v1/ui_views.py`
- `api/v1/urls.py`
- `api/tests/tests_ui_endpoints.py`

Ajouts:

- nouvel endpoint `GET /api/v1/ui/shipments/tracking/`,
- filtres supportes:
  - `planned_week` (format `YYYY-Www` ou `YYYY-ww`),
  - `closed` (`exclude` par defaut, `all` en option),
- payload livre:
  - meta (`total_shipments`),
  - filtres normalises,
  - warning explicite si semaine invalide,
  - lignes suivi (references, dates etapes, etat cloture/litige, action `tracking_url`),
- extension des tests API:
  - contrat endpoint tracking,
  - warning filtre semaine invalide,
  - matrice role API (`staff roles` autorises, `basic/portal` interdits).

## 2) Route Next `/app/scan/shipments-tracking/` branchee en live

Fichiers:

- `frontend-next/app/components/scan-shipment-tracking-live.tsx`
- `frontend-next/app/lib/api/ui.ts`
- `frontend-next/app/lib/api/types.ts`

Ajouts:

- chargement live des expeditions depuis `/api/v1/ui/shipments/tracking/`,
- formulaire filtres (semaine planifiee, dossiers clos) + reset,
- table de suivi complete (reference, nb colis, etapes, actions),
- cloture possible directement depuis une ligne si eligibilite metier,
- refresh automatique de la liste apres mutation tracking/cloture.

## 3) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajout:

- test `test_next_shipments_tracking_route_lists_shipments`.

Scenario:

- ouvrir `/app/scan/shipments-tracking/`,
- verifier qu'une reference expedition de test apparait dans la table live.

## Validation executee

- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_shipments_tracking_returns_rows_and_filters api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_shipments_tracking_invalid_week_returns_warning api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_scan_role_matrix_allows_staff_roles_and_blocks_non_staff` -> OK
- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipments_tracking_route_lists_shipments wms.tests.core.tests_ui.NextUiTests.test_next_shipments_tracking_route_workflow` -> OK
- `make test-next-ui` -> OK (15 tests)
- `.venv/bin/ruff check api/v1/ui_views.py api/v1/urls.py api/tests/tests_ui_endpoints.py wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- aligner plus finement les micro-details visuels/textes de `shipments-tracking` vs template legacy,
- terminer la parite stricte des ecrans prioritaires avec validation metier manuelle,
- preparer la transition Sprint B -> Sprint C avec checklist recette complete.
