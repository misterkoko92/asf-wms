# P3 Report - Increment 24 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur `shipment-create`:

- aligner le comportement legacy de progression du formulaire,
- masquer la zone creation colis/produit tant que destination/contacts ne sont pas qualifies,
- garder les workflows creation/tracking/cloture existants intacts.

## Livrables

## 1) Front Next shipment-create: masquage conditionnel de la zone creation

Fichier:

- `frontend-next/app/components/scan-shipment-options-live.tsx`

Ajouts:

- rendu conditionnel des champs:
  - `Carton ID`,
  - `Product code (Creation)`,
  - `Quantite (Creation)`,
  - bouton `Creer expedition`.
- ces elements ne sont affiches que si les prerequis contacts sont resolves:
  - destination,
  - expediteur,
  - destinataire,
  - correspondant.
- en etat incomplet, affichage d'un message de guidage:
  - `Merci de selectionner destination, expediteur, destinataire et correspondant...`.

## 2) Couverture navigateur ajustee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- extension du test `test_next_shipment_create_shows_empty_shipper_message_and_blocks_submit`:
  - scenario destination hors scope expediteur,
  - verification du message d'absence expediteur,
  - verification que la zone creation (`Carton ID`, `Product code`) est masquee,
  - verification de la presence du message de guidage.

## Validation executee

- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_shows_empty_shipper_message_and_blocks_submit -v 2` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_tracking_close_workflow wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_from_product_line_workflow wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_replaces_placeholder_actions_with_admin_links wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_shows_empty_shipper_message_and_blocks_submit -v 2` -> OK
- `make test-next-ui` -> OK (31 tests)
- `.venv/bin/ruff check wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- poursuivre l'alignement micro-libelles/help texts restants sur `shipment-create`,
- consolider la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
