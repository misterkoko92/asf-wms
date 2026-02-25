# P3 Report - Increment 31 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) sur les statuts de suivi:

- supprimer les libelles anglais restants dans les listes de statuts tracking,
- aligner les labels Next sur la terminologie metier du modele Django,
- verrouiller la non-regression sur les ecrans `shipment-create` et `shipments-tracking`.

## Livrables

## 1) Front Next: labels de statuts suivi aligns metier

Fichiers:

- `frontend-next/app/components/scan-shipment-options-live.tsx`
- `frontend-next/app/components/scan-shipment-tracking-live.tsx`

Modifications:

- `planning_ok` -> `OK pour planification`
- `planned` -> `Planifie`
- `moved_export` -> `Deplace au magasin export`
- `boarding_ok` -> `OK mise a bord`
- `received_correspondent` -> `Recu correspondant`
- `received_recipient` -> `Recu destinataire`

## 2) Couverture navigateur adaptee (TDD)

Fichier:

- `wms/tests/core/tests_ui.py`

Modifications:

- renforcement du test `test_next_shipment_create_selects_use_business_labels_without_id_prefix`:
  - verification de l'absence des labels anglais (`Planning OK`, `Moved export`, `Received correspondent`, `Received recipient`),
  - verification des 6 labels metier attendus dans le select `Statut suivi`.
- renforcement du test `test_next_shipments_tracking_route_workflow`:
  - verification des 6 labels metier attendus dans le select `Statut suivi`.

## Validation executee

- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_selects_use_business_labels_without_id_prefix wms.tests.core.tests_ui.NextUiTests.test_next_shipments_tracking_route_workflow -v 2` -> OK
- `make test-next-ui` -> OK (32 tests)
- `.venv/bin/ruff check wms/tests/core/tests_ui.py` -> OK

## Reste Sprint B (Phase 3)

- poursuivre l'alignement micro-libelles/help texts restants sur `shipment-create`,
- consolider la recette metier manuelle complete ecran par ecran,
- preparer la cloture Sprint B et cadrage Sprint C.
