# P2 Report - Increment 4 (2026-02-23)

## Objectif

Realiser le sprint API-4 de P2 sur le scope:

- documents expedition (liste/upload/delete),
- labels expedition (liste + label carton),
- templates impression (liste, detail, sauvegarde/reinit versionnee).

Ce sprint reste **parallelise** au legacy: aucune route `/scan/*` existante n'est modifiee.

## Livrables

## 1) Endpoints `api/v1/ui/shipments/*` pour documents et labels

Fichiers:

- `api/v1/ui_views.py`
- `api/v1/urls.py`

Nouveaux endpoints:

- `GET /api/v1/ui/shipments/<shipment_id>/documents/`
- `POST /api/v1/ui/shipments/<shipment_id>/documents/`
- `DELETE /api/v1/ui/shipments/<shipment_id>/documents/<document_id>/`
- `GET /api/v1/ui/shipments/<shipment_id>/labels/`
- `GET /api/v1/ui/shipments/<shipment_id>/labels/<carton_id>/`

Comportements:

- reutilisation des liens de rendu legacy (`/scan/shipment/.../doc/...`, `/scan/shipment/.../labels/...`),
- upload limite aux extensions autorisees (`ALLOWED_UPLOAD_EXTENSIONS`),
- suppression reservee aux docs additionnels (`DocumentType.ADDITIONAL`),
- reponses JSON homogeenes pour succes/erreurs.

## 2) Endpoints `api/v1/ui/templates/*` (superuser)

Fichiers:

- `api/v1/ui_views.py`
- `api/v1/serializers.py`
- `api/v1/urls.py`

Nouveaux endpoints:

- `GET /api/v1/ui/templates/`
- `GET /api/v1/ui/templates/<doc_type>/`
- `PATCH /api/v1/ui/templates/<doc_type>/`

Regles:

- endpoint reserve superuser (en plus de `is_staff`),
- payload mutation via `UiPrintTemplateMutationSerializer` (`action: save|reset`, `layout` JSON),
- versionning automatique (`PrintTemplateVersion`) a chaque changement effectif,
- reset = layout vide (`{}`), avec fallback auto vers `DEFAULT_LAYOUTS`.

## 3) Client API Next et typage

Fichiers:

- `frontend-next/app/lib/api/client.ts`
- `frontend-next/app/lib/api/types.ts`
- `frontend-next/app/lib/api/ui.ts`

Ajouts:

- support HTTP `DELETE`,
- support upload `multipart/form-data` (`apiPostFormData`),
- wrappers shipment documents/labels,
- wrappers templates impression (list/detail/update),
- types DTO associes.

## 4) Couverture tests API

Fichier:

- `api/tests/tests_ui_endpoints.py`

Nouveaux cas verifies:

- permission + flux complet upload/delete document expedition,
- endpoints labels expedition et gestion carton introuvable,
- templates: restriction superuser, lecture detail, save/reset versionne.

## Validation executee

- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints` -> OK (24 tests)
- `.venv/bin/python manage.py test api.tests` -> OK (62 tests)
- `cd frontend-next && npm run build` -> OK

## Reste a faire pour P2

- brancher les ecrans Next sur ces nouveaux endpoints (upload doc, template editor, labels),
- ajouter tests E2E front pour ces parcours,
- cloturer matrice de parite ecran par ecran (status `DONE`).
