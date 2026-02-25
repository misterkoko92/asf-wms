# P3 Report - Increment 9 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur l'ecran `shipments-ready`:

- rapprocher la colonne Documents du comportement legacy,
- exposer les liens documentaires complets sur la route Next,
- verrouiller la non-regression via test navigateur dedie.

## Livrables

## 1) Parite Documents renforcee sur `/app/scan/shipments-ready/`

Fichiers:

- `frontend-next/app/components/scan-shipments-ready-live.tsx`
- `frontend-next/app/globals.css`

Changements:

- remplacement des 2 actions courtes (`Bon`, `Labels`) par un menu `Documents`,
- ajout des 4 liens legacy:
  - `Bon d'expedition`,
  - `Liste colisage (lot)`,
  - `Attestation donation`,
  - `Etiquettes colis`,
- ajout de styles dedies (`doc-menu`, `doc-menu-toggle`, `doc-menu-list`) pour un rendu exploitable desktop/mobile.

## 2) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajout:

- `test_next_shipments_ready_route_shows_legacy_document_links`.

Scenario:

- ouvrir `/app/scan/shipments-ready/`,
- verifier la presence du menu `Documents`,
- verifier la presence des liens `packing_list_shipment` et `donation_certificate` dans le DOM.

## Validation executee

- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipments_ready_route_shows_legacy_document_links` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipments_ready_route_lists_shipments wms.tests.core.tests_ui.NextUiTests.test_next_shipments_ready_route_archives_stale_drafts wms.tests.core.tests_ui.NextUiTests.test_next_shipments_ready_route_shows_legacy_document_links` -> OK
- `make test-next-ui` -> OK (17 tests)
- `.venv/bin/ruff check wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- aligner les derniers ecarts de micro-libelles/etat sur les ecrans prioritaires,
- finaliser la revue de parite visuelle stricte avant recette metier manuelle,
- preparer la checklist de sortie Sprint B -> Sprint C.
