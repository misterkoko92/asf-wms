# P3 Report - Increment 25 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur `shipment-create`:

- rapprocher le parcours formulaire du legacy (`scan/shipment_create.html` + `scan.js`),
- retirer les auto-selections implicites des contacts,
- afficher les sections de formulaire de maniere progressive.

## Livrables

## 1) Front Next shipment-create: sections progressives sans auto-selection

Fichier:

- `frontend-next/app/components/scan-shipment-options-live.tsx`

Ajouts:

- suppression des auto-selections implicites sur:
  - destination,
  - expediteur,
  - destinataire,
  - correspondant.
- activation progressive des sections:
  - section expediteur visible apres choix destination,
  - sections destinataire/correspondant visibles apres choix expediteur,
  - zone creation colis/produit visible uniquement quand destinataire + correspondant sont valides.
- maintien des messages d'aide/metier:
  - aide destination,
  - aide expediteur,
  - aide destinataire/correspondant,
  - message d'absence expediteur/destinataire/correspondant.

## 2) Couverture navigateur adaptee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- adaptation de `test_next_shipment_create_replaces_placeholder_actions_with_admin_links`:
  - verification des liens admin contacts apres progression destination -> expediteur.
- renforcement `test_next_shipment_create_shows_empty_shipper_message_and_blocks_submit`:
  - verification message d'absence expediteur,
  - verification sections creation (`Carton ID`, `Product code`) non affichees,
  - verification absence du bouton `Creer expedition` quand prerequis non atteints.

## Validation executee

- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_tracking_close_workflow wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_from_product_line_workflow wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_replaces_placeholder_actions_with_admin_links wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_shows_empty_shipper_message_and_blocks_submit -v 2` -> OK
- `make test-next-ui` -> OK (31 tests)
- `.venv/bin/ruff check wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- finaliser l'alignement micro-libelles/help texts restants de `shipment-create`,
- poursuivre la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
