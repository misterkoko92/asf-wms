# P3 Report - Increment 4 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) en couvrant l'ecran prioritaire `shipments-ready`:

- ouvrir une route Next dediee `/app/scan/shipments-ready/`,
- exposer les donnees expeditions cote API UI,
- valider le rendu navigateur avec references expeditions visibles.

## Livrables

## 1) Endpoint UI dedie "vue expeditions"

Fichiers:

- `api/v1/ui_views.py`
- `api/v1/urls.py`
- `api/tests/tests_ui_endpoints.py`

Ajouts:

- nouvel endpoint `GET /api/v1/ui/shipments/ready/`,
- payload livre:
  - meta (`total_shipments`, `stale_draft_count`, `stale_draft_days`),
  - liste expeditions (reference, nb colis, parties, dates, statut),
  - URLs action/document (suivi, edition, bon expedition, labels, etc.),
- test endpoint dedie + extension matrice role API.

## 2) Route Next dediee `/app/scan/shipments-ready/`

Fichiers:

- `frontend-next/app/scan/shipments-ready/page.tsx`
- `frontend-next/app/components/scan-shipments-ready-live.tsx`
- `frontend-next/app/lib/api/ui.ts`
- `frontend-next/app/lib/api/types.ts`

Ajouts:

- page Next dediee "Vue expeditions",
- table live avec colonnes principales legacy:
  - N° expedition
  - Nb colis
  - Destination (IATA)
  - Expediteur
  - Destinataire
  - Date creation / mise a dispo
  - Statut
  - Documents
  - Actions,
- branchement API vers `/api/v1/ui/shipments/ready/`.

## 3) Navigation et bascule legacy

Fichiers:

- `frontend-next/app/components/app-shell.tsx`
- `frontend-next/app/components/mode-switch.tsx`

Ajouts:

- entree scan `Vue expeditions`,
- mapping `ModeSwitch` vers `/scan/shipments-ready/` en legacy.

## 4) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajout:

- `test_next_shipments_ready_route_lists_shipments`.

Scenario:

- ouvrir `/app/scan/shipments-ready/`,
- verifier qu'une reference expedition existante est visible.

## Validation executee

- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipments_ready_route_lists_shipments` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipments_tracking_route_workflow` -> OK
- `make test-next-ui` -> OK (12 tests)
- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_shipments_ready_returns_rows` -> OK
- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_scan_role_matrix_allows_staff_roles_and_blocks_non_staff` -> OK

## Reste Sprint B (Phase 3)

- harmoniser parite visuelle stricte dashboard/stock/shipment-create/shipments-ready,
- couvrir les ecrans restants prioritaires (`cartons` encore TODO),
- preparer la recette metier manuelle complete.
