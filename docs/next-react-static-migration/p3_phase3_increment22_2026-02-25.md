# P3 Report - Increment 22 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur `shipment-create`:

- retirer les blocs/actions placeholders non relies,
- renforcer le formulaire live avec les liens admin legacy (destination/contacts),
- garder les workflows creation/tracking/cloture inchanges et verifies.

## Livrables

## 1) Front Next shipment-create: suppression du shell hybride

Fichier:

- `frontend-next/app/scan/shipment-create/page.tsx`

Ajouts:

- suppression des panneaux statiques non branches:
  - `Formulaire expedition` (mock),
  - `Etat documents` (mock),
  - actions `Save draft`, `Publish warning`, `Set ready to ship` (placeholders).
- conservation du flux live `ScanShipmentOptionsLive` + checklist.

## 2) Formulaire live: liens admin alignes legacy

Fichier:

- `frontend-next/app/components/scan-shipment-options-live.tsx`

Ajouts:

- liens directs depuis les selects:
  - `Ajouter destination` -> `/admin/wms/destination/add/`,
  - `Ajouter expediteur` -> `/admin/contacts/contact/add/`,
  - `Ajouter destinataire` -> `/admin/contacts/contact/add/`,
  - `Ajouter correspondant` -> `/admin/contacts/contact/add/`.

## 3) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- test `test_next_shipment_create_replaces_placeholder_actions_with_admin_links`.

Scenario:

- ouvrir `/app/scan/shipment-create/`,
- verifier la presence des liens admin de creation destination/contacts,
- verifier l absence des anciens placeholders (`Save draft`, `Publish warning`, `Set ready to ship`, `Formulaire expedition`, `Etat documents`).

## Validation executee

- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_replaces_placeholder_actions_with_admin_links` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_tracking_close_workflow wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_from_product_line_workflow wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_replaces_placeholder_actions_with_admin_links` -> OK
- `make test-next-ui` -> OK (30 tests)
- `.venv/bin/ruff check wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- finaliser les derniers ecarts visuels/libelles residuels sur l ecran `shipment-create`,
- consolider la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
