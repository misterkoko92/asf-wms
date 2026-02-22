# P0 - Analyse des gaps API (legacy -> Next statique)

## 1) API disponible aujourd'hui (`/api/v1`)

Source: `api/v1/urls.py`, `api/v1/views.py`

Endpoints existants:

- `GET /api/v1/products/` (read-only + filtres)
- `GET /api/v1/orders/` / `GET /api/v1/orders/<id>/` (read-only)
- `POST /api/v1/orders/<id>/reserve/`
- `POST /api/v1/orders/<id>/prepare/`
- `POST /api/v1/stock/receive/`
- `POST /api/v1/pack/`
- `GET /api/v1/integrations/shipments/`
- `GET /api/v1/integrations/destinations/`
- `GET|POST|PATCH /api/v1/integrations/events/`

## 2) Couverture vs écrans cibles Next

Écrans prioritaires demandés:

- dashboard,
- vue stock,
- création expédition.

Constat:

- l'API actuelle ne couvre qu'une partie du besoin opérationnel,
- beaucoup de logique est encore exposée uniquement via vues Django HTML + handlers.

## 3) Gaps API bloquants pour parité front

## Dashboard

Manquant:

- endpoint KPI consolidés (activité, expéditions, cartons, stock bas, litiges, SLA),
- endpoint widgets "actions en attente" / blocages.

Impact:

- impossible de reproduire dashboard legacy sans reconsommer HTML.

## Vue stock

Partiel:

- `products` existe, mais pas de payload prêt à l'emploi identique à `build_stock_context`.

Manquant:

- endpoint stock view agrégé (filtres catégorie/entrepôt/tri + mouvements récents),
- endpoint MAJ stock "legacy-compatible" (incluant logique `default_location`, donor, audit),
- endpoint `stock out`.

## Création/édition expédition

Manquant:

- endpoint de création expédition multi-lignes (colis existants + création mono-produit),
- endpoint save draft (`EXP-TEMP-XX`),
- endpoint édition expédition avec règles de verrouillage/litige,
- endpoint données de formulaire (destinations + contacts filtrés + cartons disponibles),
- endpoint documents expédition (upload/list/delete),
- endpoint labels/documents générés (liens + métadonnées).

## Affectation / statut colis

Manquant:

- endpoint list/filtre cartons prêts,
- endpoint changement statut colis,
- endpoint affectation batch colis -> expédition.

## Suivi / clôture expédition

Manquant:

- endpoint transitions tracking autorisées,
- endpoint update tracking (avec validation métier),
- endpoint set/resolve dispute,
- endpoint clôture expédition avec garde-fous.

## Portal

Manquant:

- endpoint création commande portail avec mêmes validations (destination/recipient/stock),
- endpoint upload multi-doc commande,
- endpoint CRUD destinataires association,
- endpoint update profil + contacts portail.

## 4) Plan API minimal pour P1/P2 (parité)

## 4.1 Principe

- Ne pas casser API actuelle.
- Ajouter une couche `api/v1/ui/*` dédiée au front Next.
- Réutiliser handlers/services existants pour garder la logique métier unique.

## 4.2 Propositions d'endpoints (V1)

- `GET /api/v1/ui/dashboard`
- `GET /api/v1/ui/stock`
- `POST /api/v1/ui/stock/update`
- `POST /api/v1/ui/stock/out`
- `GET /api/v1/ui/shipment/form-options`
- `POST /api/v1/ui/shipments`
- `POST /api/v1/ui/shipments/<id>/draft`
- `PATCH /api/v1/ui/shipments/<id>`
- `GET /api/v1/ui/shipments/tracking`
- `POST /api/v1/ui/shipments/<id>/tracking-events`
- `POST /api/v1/ui/shipments/<id>/dispute`
- `POST /api/v1/ui/shipments/<id>/resolve-dispute`
- `POST /api/v1/ui/shipments/<id>/close`
- `POST /api/v1/ui/shipments/<id>/documents`
- `DELETE /api/v1/ui/shipments/<id>/documents/<docId>`
- `GET /api/v1/ui/portal/orders`
- `POST /api/v1/ui/portal/orders`
- `GET /api/v1/ui/portal/recipients`
- `POST /api/v1/ui/portal/recipients`
- `PATCH /api/v1/ui/portal/recipients/<id>`
- `PATCH /api/v1/ui/portal/account`

## 5) Sécurité/API contracts à figer

- Auth session Django + CSRF obligatoire.
- Contrôle permissions au niveau endpoint (staff, association profile, superuser).
- Payloads versionnés stables (`v1`) pour éviter les regressions de front.
- Erreurs structurées:
  - `field_errors`,
  - `non_field_errors`,
  - `code`,
  - `message`.

## 6) Découpage de livraison recommandé

- Sprint API-1 (P1): dashboard, stock view/update, shipment form-options.
- Sprint API-2 (P1): create/edit shipment + tracking update.
- Sprint API-3 (P2): portal create order + recipients/account.
- Sprint API-4 (P2): documents/labels/templates.
