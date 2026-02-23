# P2 Report - Increment 2 (2026-02-22)

## Objectif

Etendre la phase P2 avec les **mutations API prioritaires** pour le nouveau front Next:

- mise a jour stock,
- sortie stock,
- creation expedition,
- edition expedition,
- ajout d'evenement de suivi expedition,
- cloture expedition.

Inclure un format d'erreur API uniforme et une couverture de tests ciblee.

## Livrables

## 1) Format d'erreur API uniforme

Nouveau fichier:

- `api/v1/ui_api_errors.py`

Structure retour erreur:

- `ok` (false)
- `code`
- `message`
- `field_errors`
- `non_field_errors`

Ce format est maintenant utilise dans les endpoints mutation `api/v1/ui/*`.

## 2) Endpoints mutation `api/v1/ui/*`

Nouveaux endpoints:

- `POST /api/v1/ui/stock/update/`
- `POST /api/v1/ui/stock/out/`
- `POST /api/v1/ui/shipments/`
- `PATCH /api/v1/ui/shipments/<shipment_id>/`
- `POST /api/v1/ui/shipments/<shipment_id>/tracking-events/`
- `POST /api/v1/ui/shipments/<shipment_id>/close/`

Fichiers:

- `api/v1/ui_views.py`
- `api/v1/urls.py`

## 3) Contrats de payload (serializers)

Ajouts dans `api/v1/serializers.py`:

- `UiStockUpdateSerializer`
- `UiStockOutSerializer`
- `UiShipmentLineSerializer`
- `UiShipmentMutationSerializer`
- `UiShipmentTrackingEventSerializer`

## 4) Client API Next et typage

Mises a jour:

- `frontend-next/app/lib/api/client.ts`
  - ajout `ApiClientError`
  - support `GET/POST/PATCH`
  - parsing de l'enveloppe d'erreur API
- `frontend-next/app/lib/api/types.ts`
  - nouveaux types mutation stock/expedition/suivi/cloture
- `frontend-next/app/lib/api/ui.ts`
  - wrappers pour les nouveaux endpoints mutation

## 5) Tests API

Fichier:

- `api/tests/tests_ui_endpoints.py`

Couverture ajoutee:

- success + erreurs pour `stock/update` et `stock/out`,
- create shipment (carton existant + creation carton depuis produit),
- update shipment (verrouillage + reassignment de cartons),
- tracking event shipment (transition validee),
- close shipment (cas bloque + cas cloture autorisee),
- verification des permissions staff sur endpoints mutation,
- verification format d'erreur uniforme.

## Validation executee

- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints` -> OK (15 tests)
- `.venv/bin/python manage.py test api.tests` -> OK (53 tests)
- `cd frontend-next && npm run build` -> OK

## Reste a faire pour P2

- permissions fines par action (profil qualite/admin/expedition) si necessairement plus strictes que `is_staff`,
- endpoints documents/labels/templates (upload/delete/preview) pour parite complete scan,
- endpoints portal mutation (orders create, recipients/account update),
- branchement UI Next sur les nouvelles mutations (formulaires complets E2E).
