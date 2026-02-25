# P2 Report - Increment 10 (2026-02-25)

## Objectif

Continuer Sprint A en couvrant en navigateur les mutations Portal manquantes sur l'ecran Next `/app/portal/dashboard/`:

- creation commande association,
- creation + modification destinataire,
- mise a jour compte association.

## Livrables

## 1) Ecran Portal Next branche aux mutations API

Fichier:

- `frontend-next/app/components/portal-dashboard-live.tsx`

Ajouts:

- chargement compose des donnees Portal (`dashboard`, `recipients`, `account`),
- formulaire mutation commande (`POST /ui/portal/orders/`),
- formulaire creation destinataire (`POST /ui/portal/recipients/`),
- formulaire edition destinataire (`PATCH /ui/portal/recipients/<id>/`),
- formulaire mise a jour compte (`PATCH /ui/portal/account/`),
- feedback inline succes/erreur et rechargement data apres mutation.

## 2) Test navigateur workflow Portal complet

Fichier:

- `wms/tests/core/tests_ui.py`

Ajouts:

- fixtures Portal dediees (produit + lot disponible + destinataire association),
- test `test_next_portal_order_recipient_account_workflow`.

Scenario:

- ouvrir `/app/portal/dashboard/` en session association,
- envoyer une commande valide,
- ajouter puis modifier un destinataire,
- mettre a jour le compte association,
- verifier en base commande creee + recipient modifie + profil maj.

## Validation executee

- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_portal_order_recipient_account_workflow` -> OK
- `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests` -> OK (8 tests)
- `make test-next-ui` -> OK
- `.venv/bin/ruff check wms/tests/core/tests_ui.py` -> OK
- `cd frontend-next && npm run build` -> OK

## Reste a faire pour Sprint A / P2

- brancher execution reguliere des scenarios Playwright sur environnement cible.
