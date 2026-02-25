# P3 Report - Increment 28 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur les blocs `tracking/cloture`:

- retirer les libelles techniques restants `Shipment ID (...)`,
- harmoniser les libelles metier sur `shipment-create` et `shipments-tracking`,
- verrouiller la non-regression via tests navigateur.

## Livrables

## 1) Front Next: labels tracking/cloture harmonises

Fichiers:

- `frontend-next/app/components/scan-shipment-options-live.tsx`
- `frontend-next/app/components/scan-shipment-tracking-live.tsx`

Modifications:

- labels/erreurs de validation:
  - `Shipment ID (Tracking)` -> `Expedition (Tracking)`
  - `Shipment ID (Cloture)` -> `Expedition (Cloture)`
  - `Status tracking` -> `Statut tracking`
  - `Actor name` -> `Nom acteur`
  - `Actor structure` -> `Structure acteur`
- ajout de `aria-label` explicites sur les champs tracking/cloture pour fiabiliser les selecteurs Playwright exacts.

## 2) Couverture navigateur adaptee

Fichier:

- `wms/tests/core/tests_ui.py`

Modifications:

- mise a jour des interactions Playwright vers les nouveaux labels metier sur:
  - `test_next_shipment_create_tracking_close_workflow`
  - `test_next_shipments_tracking_route_workflow`
- renforcement du test `test_next_shipment_create_selects_use_business_labels_without_id_prefix`:
  - verification d'absence des textes `shipment id (tracking)` et `shipment id (cloture)` dans la page.

## Validation executee

- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_tracking_close_workflow wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_selects_use_business_labels_without_id_prefix wms.tests.core.tests_ui.NextUiTests.test_next_shipments_tracking_route_workflow -v 2` -> OK
- `make test-next-ui` -> OK (32 tests)
- `.venv/bin/ruff check wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- poursuivre l'alignement micro-libelles/help texts restants sur `shipment-create`,
- consolider la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
