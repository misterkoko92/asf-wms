# P3 Report - Increment 30 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur la microcopy de confirmation:

- supprimer le dernier fragment anglais visible apres creation expedition,
- harmoniser le message de succes avec les libelles metier francises,
- verrouiller la non-regression avec tests navigateur.

## Livrables

## 1) Front Next shipment-create: message de succes francise

Fichier:

- `frontend-next/app/components/scan-shipment-options-live.tsx`

Modification:

- message post-creation:
  - `Expedition creee. Shipment #<id>.` -> `Expedition creee. Expedition #<id>.`

## 2) Couverture navigateur adaptee (TDD)

Fichier:

- `wms/tests/core/tests_ui.py`

Modifications:

- ajout d'assertions dans:
  - `test_next_shipment_create_tracking_close_workflow`
  - `test_next_shipment_create_from_product_line_workflow`
- comportement attendu:
  - presence de `expedition #` dans le texte de page apres creation,
  - absence de `shipment #`.

## Validation executee

- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_tracking_close_workflow wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_from_product_line_workflow -v 2` -> OK
- `make test-next-ui` -> OK (32 tests)
- `.venv/bin/ruff check wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- poursuivre l'alignement micro-libelles/help texts restants sur `shipment-create`,
- consolider la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
