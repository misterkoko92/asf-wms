# P3 Report - Increment 5 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur l'ecran prioritaire `cartons`:

- ajouter une route Next dediee `/app/scan/cartons/`,
- exposer la vue colis en API UI,
- valider le rendu navigateur avec des colis reels.

## Livrables

## 1) Endpoint UI dedie "vue colis"

Fichiers:

- `api/v1/ui_views.py`
- `api/v1/urls.py`
- `api/tests/tests_ui_endpoints.py`

Ajouts:

- nouvel endpoint `GET /api/v1/ui/cartons/`,
- payload livre:
  - meta (`total_cartons`, `carton_capacity_cm3`),
  - liste colis (code, dates, statut, expedition, emplacement, remplissage, liste de colisage, URLs impression/picking),
- test endpoint dedie + extension de la matrice role API.

## 2) Route Next dediee `/app/scan/cartons/`

Fichiers:

- `frontend-next/app/scan/cartons/page.tsx`
- `frontend-next/app/components/scan-cartons-live.tsx`
- `frontend-next/app/lib/api/ui.ts`
- `frontend-next/app/lib/api/types.ts`

Ajouts:

- page Next "Vue colis",
- table live branchee sur `/api/v1/ui/cartons/`,
- affichage des lignes colisage + boutons impression/picking.

## 3) Navigation et bascule legacy

Fichiers:

- `frontend-next/app/components/app-shell.tsx`
- `frontend-next/app/components/mode-switch.tsx`

Ajouts:

- entree scan `Vue colis`,
- mapping `ModeSwitch` vers legacy `/scan/cartons/`.

## 4) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- fixture colis avec contenu (`NEXT-UI-CARTON-READY`) en setup,
- test `test_next_cartons_route_lists_cartons`.

Scenario:

- ouvrir `/app/scan/cartons/`,
- verifier que le code colis de reference est visible.

## Validation executee

- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_cartons_route_lists_cartons` -> OK
- `make test-next-ui` -> OK (13 tests)
- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_cartons_returns_rows` -> OK
- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_scan_role_matrix_allows_staff_roles_and_blocks_non_staff` -> OK
- `.venv/bin/ruff check api/v1/ui_views.py api/v1/urls.py api/tests/tests_ui_endpoints.py wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- renforcer la parite visuelle stricte des ecrans prioritaires deja routes,
- traiter les ecarts de libelles/etat restants vs templates legacy,
- lancer la recette metier manuelle complete.
