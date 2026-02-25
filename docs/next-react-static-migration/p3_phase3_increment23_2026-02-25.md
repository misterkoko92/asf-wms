# P3 Report - Increment 23 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur `shipment-create`:

- aligner le filtrage des contacts sur la logique legacy (destination -> expediteur -> destinataire/correspondant),
- afficher un message explicite quand aucun expediteur n'est disponible,
- bloquer la creation d'expedition tant que les selections requises ne sont pas completes,
- exposer un libelle destination explicite cote API UI.

## Livrables

## 1) Front Next shipment-create: filtrage en cascade + guardrail de submit

Fichier:

- `frontend-next/app/components/scan-shipment-options-live.tsx`

Ajouts:

- adaptation de la logique legacy de filtrage des options contacts:
  - expediteurs filtres par destination,
  - destinataires filtres par destination + expediteur lie,
  - correspondants filtres par destination + correspondant impose par destination.
- ajout de messages d'absence de donnees:
  - `Aucun expediteur trouve dans la base...`,
  - `Aucun destinataire trouve dans la base...`,
  - `Aucun correspondant trouve dans la base...`.
- desactivation du bouton `Creer expedition` quand les selections minimales ne sont pas valides.
- conservation des workflows mutation existants (create/tracking/close) et des liens admin.

## 2) API UI shipment form-options: libelle destination

Fichier:

- `wms/shipment_helpers.py`

Ajouts:

- enrichissement `destinations_json` avec:
  - `label` (valeur `str(destination)`),
  - `city`,
  - `iata_code`.

## 3) Couverture tests

Fichiers:

- `wms/tests/core/tests_ui.py`
- `api/tests/tests_ui_endpoints.py`

Ajouts:

- test navigateur `test_next_shipment_create_shows_empty_shipper_message_and_blocks_submit`:
  - cree une destination hors scope des expediteurs,
  - verifie le message legacy d'absence expediteur,
  - verifie le bouton `Creer expedition` desactive.
- extension test API `test_ui_shipment_form_options_returns_collections`:
  - verifie la presence et la valeur du `label` destination.

## Validation executee

- `cd frontend-next && npm run build` -> OK
- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiApiEndpointsTests.test_ui_shipment_form_options_returns_collections -v 2` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_tracking_close_workflow wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_from_product_line_workflow wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_replaces_placeholder_actions_with_admin_links wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_shows_empty_shipper_message_and_blocks_submit -v 2` -> OK
- `make test-next-ui` -> OK (31 tests)
- `.venv/bin/ruff check api/tests/tests_ui_endpoints.py wms/shipment_helpers.py wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- poursuivre l'alignement micro-libelles/help texts de `shipment-create` avec le template legacy,
- finaliser la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
