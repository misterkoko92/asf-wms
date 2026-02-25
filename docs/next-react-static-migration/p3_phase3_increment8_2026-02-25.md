# P3 Report - Increment 8 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur l'ecran prioritaire `shipments-ready`:

- couvrir l'action legacy "Archiver brouillons anciens",
- exposer une mutation UI dediee cote API,
- valider le workflow navigateur de bout en bout.

## Livrables

## 1) Endpoint UI dedie "archivage brouillons stale"

Fichiers:

- `api/v1/ui_views.py`
- `api/v1/urls.py`
- `api/tests/tests_ui_endpoints.py`

Ajouts:

- nouvel endpoint `POST /api/v1/ui/shipments/ready/archive-stale-drafts/`,
- logique metier:
  - archive uniquement les brouillons temporaires stale,
  - retourne `archived_count`, `stale_draft_count`, `message`, `ok`,
- extension tests API:
  - test d'archivage stale draft,
  - extension matrice role API sur ce nouveau endpoint.

## 2) Route Next `/app/scan/shipments-ready/` - action archive branchee

Fichiers:

- `frontend-next/app/components/scan-shipments-ready-live.tsx`
- `frontend-next/app/lib/api/ui.ts`
- `frontend-next/app/lib/api/types.ts`

Ajouts:

- bouton `Archiver brouillons anciens` lorsque des brouillons stale sont detectes,
- mutation API branchee vers `/api/v1/ui/shipments/ready/archive-stale-drafts/`,
- message de retour mutation + refresh live de la table expeditions apres archivage.

## 3) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajout:

- `test_next_shipments_ready_route_archives_stale_drafts`.

Scenario:

- creer un brouillon temporaire stale,
- ouvrir `/app/scan/shipments-ready/`,
- cliquer `Archiver brouillons anciens`,
- verifier le message de confirmation et l'archivage effectif en base.

## Validation executee

- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_shipments_ready_archive_stale_drafts_archives_only_stale_temp_drafts api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_scan_role_matrix_allows_staff_roles_and_blocks_non_staff` -> OK
- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipments_ready_route_archives_stale_drafts wms.tests.core.tests_ui.NextUiTests.test_next_shipments_ready_route_lists_shipments` -> OK
- `make test-next-ui` -> OK (16 tests)
- `.venv/bin/ruff check api/v1/ui_views.py api/v1/urls.py api/tests/tests_ui_endpoints.py wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- completer les ecarts visuels/textes restants vs templates legacy sur les ecrans prioritaires,
- finaliser la parite stricte avant recette metier manuelle complete,
- consolider la checklist Sprint B -> Sprint C.
