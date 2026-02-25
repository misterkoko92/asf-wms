# P3 Report - Increment 27 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur `shipment-create`:

- supprimer le suffixe technique `ID` dans les libelles de champs select,
- garder des libelles metier simples et coherents avec les options deja nettoyees,
- stabiliser les selecteurs Playwright pour eviter les collisions de labels.

## Livrables

## 1) Front Next shipment-create: labels de champs sans suffixe `ID`

Fichier:

- `frontend-next/app/components/scan-shipment-options-live.tsx`

Modifications:

- renommage des labels:
  - `Destination ID` -> `Destination`
  - `Expediteur ID` -> `Expediteur`
  - `Destinataire ID` -> `Destinataire`
  - `Correspondant ID` -> `Correspondant`
  - `Carton ID` -> `Carton`
- mise a jour du message d'erreur mutation:
  - `Carton ID ou produit+quantite requis.` -> `Carton ou produit+quantite requis.`
- ajout de `aria-label` explicites sur les `select` concerns pour fiabiliser les interactions test navigateur.

## 2) Adaptation couverture navigateur shipment-create

Fichier:

- `wms/tests/core/tests_ui.py`

Modifications:

- migration des interactions Playwright vers les nouveaux labels (`Destination`, `Expediteur`, `Destinataire`, `Correspondant`, `Carton`) avec `exact=True`,
- renforcement du test `test_next_shipment_create_selects_use_business_labels_without_id_prefix`:
  - verification de l'absence des textes `destination id`, `expediteur id`, `destinataire id`, `correspondant id`, `carton id` dans la page,
  - maintien de la verification des options metier (destination/contact/carton) sans prefixe technique.

## Validation executee

- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_tracking_close_workflow wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_from_product_line_workflow wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_replaces_placeholder_actions_with_admin_links wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_shows_empty_shipper_message_and_blocks_submit wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_selects_use_business_labels_without_id_prefix -v 2` -> OK
- `make test-next-ui` -> OK (32 tests)
- `.venv/bin/ruff check wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- poursuivre l'alignement micro-libelles/help texts restants sur `shipment-create`,
- consolider la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
