# P3 Report - Increment 26 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur `shipment-create`:

- retirer les libelles techniques `id -` dans les listes de selection,
- conserver uniquement des libelles metier lisibles (destination/contact/carton),
- verrouiller ce comportement via test navigateur.

## Livrables

## 1) Front Next shipment-create: options select en libelles metier

Fichier:

- `frontend-next/app/components/scan-shipment-options-live.tsx`

Ajouts:

- suppression du prefixe technique `${id} -` dans les options:
  - destination,
  - expediteur,
  - destinataire,
  - correspondant,
  - carton.
- conservation des valeurs techniques (`value`) pour les POST API; seul le texte affiche evolue.

## 2) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- test `test_next_shipment_create_selects_use_business_labels_without_id_prefix`:
  - verifie que l'option destination affiche `str(destination)` sans prefixe id,
  - verifie que les options contacts affichent `name` sans prefixe id,
  - verifie que l'option carton affiche le `code` sans prefixe id.

## Validation executee

- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_selects_use_business_labels_without_id_prefix -v 2` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_tracking_close_workflow wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_from_product_line_workflow wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_replaces_placeholder_actions_with_admin_links wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_shows_empty_shipper_message_and_blocks_submit wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_selects_use_business_labels_without_id_prefix -v 2` -> OK
- `make test-next-ui` -> OK (32 tests)
- `.venv/bin/ruff check wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- poursuivre l'alignement micro-libelles/help texts restants sur `shipment-create`,
- consolider la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
