# P2 Report - Increment 3 (2026-02-23)

## Objectif

Completer la phase P2 sur le perimetre **portal mutations** pour le frontend Next:

- creation de commande portal,
- CRUD destinataires association (liste + ajout + edition),
- lecture/mise a jour du compte association,
- typage/wrappers API frontend alignes sur ces endpoints.

## Livrables

## 1) Endpoints `api/v1/ui/portal/*` ajoutes

Fichiers:

- `api/v1/ui_views.py`
- `api/v1/urls.py`

Nouveaux endpoints:

- `POST /api/v1/ui/portal/orders/`
- `GET /api/v1/ui/portal/recipients/`
- `POST /api/v1/ui/portal/recipients/`
- `PATCH /api/v1/ui/portal/recipients/<recipient_id>/`
- `GET /api/v1/ui/portal/account/`
- `PATCH /api/v1/ui/portal/account/`

Comportements clefs:

- verification destination/destinataire/produits lors de la creation de commande,
- creation shipment lie a la commande via `create_portal_order`,
- notifications portal declenchees apres creation commande,
- validation des emails destinataires + regles `notify_deliveries`,
- synchronisation destinataire <-> contact via `sync_association_recipient_to_contact`,
- mise a jour profil/contacts portal via `_save_profile_updates`,
- erreurs API uniformes (`api_error`) en cas de validation metier.

## 2) Contrats de payload (serializers)

Fichier:

- `api/v1/serializers.py`

Ajouts:

- `UiPortalOrderLineSerializer`
- `UiPortalOrderCreateSerializer`
- `UiPortalRecipientMutationSerializer`
- `UiPortalAccountContactSerializer`
- `UiPortalAccountUpdateSerializer`

## 3) Client API Next + types

Fichiers:

- `frontend-next/app/lib/api/types.ts`
- `frontend-next/app/lib/api/ui.ts`

Ajouts principaux:

- types d'entree/sortie pour `portal/orders`, `portal/recipients`, `portal/account`,
- wrappers:
  - `postPortalOrder`
  - `getPortalRecipients`
  - `postPortalRecipient`
  - `patchPortalRecipient`
  - `getPortalAccount`
  - `patchPortalAccount`

## 4) Couverture tests

Fichier:

- `api/tests/tests_ui_endpoints.py`

Tests verifies:

- creation commande portal (succes),
- creation commande portal (destination invalide),
- recipients API (list + create + patch),
- account API (patch succes + erreur contact sans type),
- non regression des tests P2 increment 1/2 existants.

## Validation executee

- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints` -> OK (20 tests)
- `.venv/bin/python manage.py test api.tests` -> OK (58 tests)
- `cd frontend-next && npm run build` -> OK

## Reste a faire pour P2

- endpoints documents/labels/templates (upload/delete/preview) pour parite scan complete,
- branchement UI Next sur les mutations portal (forms complets + feedback erreurs inline),
- scenarios E2E frontend sur workflows portal critiques.
