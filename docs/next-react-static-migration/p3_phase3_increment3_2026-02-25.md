# P3 Report - Increment 3 (2026-02-25)

## Objectif

Poursuivre Sprint B (Phase 3 parite stricte) en reduisant l'integration transitoire sur `shipment-create`:

- ajouter une route Next dediee au suivi expedition,
- deplacer les actions tracking/cloture sur cet ecran dedie,
- valider le flux navigateur sur la nouvelle route.

## Livrables

## 1) Route Next dediee suivi expeditions

Fichiers:

- `frontend-next/app/scan/shipments-tracking/page.tsx`
- `frontend-next/app/components/scan-shipment-tracking-live.tsx`

Ajouts:

- nouvelle route statique `/app/scan/shipments-tracking/`,
- formulaire live tracking:
  - `Shipment ID (Tracking)`
  - `Status tracking`
  - `Actor name`
  - `Actor structure`
  - bouton `Envoyer tracking`,
- formulaire live cloture:
  - `Shipment ID (Cloture)`
  - bouton `Cloturer expedition`,
- feedback uniforme API (`Suivi mis a jour.`, `Dossier cloture.`, erreurs normalisees).

## 2) Navigation et bascule legacy

Fichiers:

- `frontend-next/app/components/app-shell.tsx`
- `frontend-next/app/components/mode-switch.tsx`

Ajouts:

- entree menu scan `Suivi expeditions` vers `/scan/shipments-tracking`,
- mapping `ModeSwitch` vers legacy `/scan/shipments-tracking/`.

## 3) Couverture navigateur dediee

Fichier:

- `wms/tests/core/tests_ui.py`

Ajout:

- `test_next_shipments_tracking_route_workflow`.

Scenario:

- ouvrir `/app/scan/shipments-tracking/`,
- pousser deux etapes de tracking (`received_correspondent`, `received_recipient`),
- cloturer le dossier,
- verifier `closed_at` en base.

## Validation executee

- `cd frontend-next && npm run build` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipments_tracking_route_workflow` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_shipment_create_tracking_close_workflow` -> OK

## Reste Sprint B (Phase 3)

- renforcer la parite visuelle/UX des ecrans prioritaires,
- traiter l'ecran dedie `shipments-ready` (encore absent cote Next),
- lancer la recette metier manuelle ecran par ecran.
