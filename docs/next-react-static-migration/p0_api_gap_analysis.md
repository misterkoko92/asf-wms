# P0 - Analyse des gaps API (legacy -> Next statique)

## Contexte du document

Ce document a ete cree en P0 (2026-02-22), puis remis a jour au 2026-02-23 pour refleter les livraisons P1/P2 deja effectuees.

## 1) Baseline P0 (historique)

Constat initial P0:

- API `api/v1` existante partielle pour un front Next complet.
- logique metier majoritairement exposee via vues Django templates.
- besoin d'une couche API dediee au nouveau front (`/api/v1/ui/*`).

## 2) Endpoints UI effectivement livres (etat reel)

Source de verite: `api/v1/urls.py`, `api/v1/ui_views.py`, `api/tests/tests_ui_endpoints.py`.

- `GET /api/v1/ui/dashboard/`
- `GET /api/v1/ui/stock/`
- `POST /api/v1/ui/stock/update/`
- `POST /api/v1/ui/stock/out/`
- `GET /api/v1/ui/shipments/form-options/`
- `POST /api/v1/ui/shipments/`
- `PATCH /api/v1/ui/shipments/<shipment_id>/`
- `POST /api/v1/ui/shipments/<shipment_id>/tracking-events/`
- `POST /api/v1/ui/shipments/<shipment_id>/close/`
- `GET|POST /api/v1/ui/shipments/<shipment_id>/documents/`
- `DELETE /api/v1/ui/shipments/<shipment_id>/documents/<document_id>/`
- `GET /api/v1/ui/shipments/<shipment_id>/labels/`
- `GET /api/v1/ui/shipments/<shipment_id>/labels/<carton_id>/`
- `GET /api/v1/ui/templates/`
- `GET|PATCH /api/v1/ui/templates/<doc_type>/`
- `GET /api/v1/ui/portal/dashboard/`
- `POST /api/v1/ui/portal/orders/`
- `GET|POST /api/v1/ui/portal/recipients/`
- `PATCH /api/v1/ui/portal/recipients/<recipient_id>/`
- `GET|PATCH /api/v1/ui/portal/account/`

## 3) Couverture des besoins initiaux P0

| Domaine | Besoin P0 | Etat 2026-02-23 | Notes |
|---|---|---|---|
| Dashboard | KPI consolides + actions en attente | IN_PROGRESS | endpoint disponible, parite UI stricte restante |
| Stock | liste/filtres/tri + MAJ + sortie | IN_PROGRESS | endpoints disponibles, UI actions 1-clic a finaliser |
| Creation expedition | create/update + options + validations | IN_PROGRESS | endpoints disponibles, UI complete non branchee |
| Suivi/cloture expedition | transitions + close guardrails | IN_PROGRESS | endpoints disponibles, page tracking Next manquante |
| Documents/labels | upload/list/delete + labels | IN_PROGRESS | endpoints + ecran Next presents, UX finale restante |
| Templates impression | liste/detail/save/reset/version | IN_PROGRESS | endpoints + ecran Next presents (JSON editor MVP) |
| Portal commande | create order + validations | API_READY | endpoint disponible, ecran Next create non livre |
| Portal recipients/account | CRUD destinataires + compte | API_READY | endpoints disponibles, ecrans Next non livres |

## 4) Gaps API encore ouverts (avant parite stricte)

Gaps confirms a traiter:

- endpoint detail commande portal (`GET /api/v1/ui/portal/orders/<id>/`) absent,
- endpoint(s) listes operationnelles dediees (cartons prets, expeditions pretes, commandes scan) absents,
- validation permissions complete par role metier a etendre (tests role matrix),
- audit trail homogene sur toutes mutations UI a consolider.

## 5) Contrat API a conserver

- auth session Django + CSRF,
- payload erreur uniforme (`ok`, `code`, `message`, `field_errors`, `non_field_errors`),
- logique metier unique cote Django (pas de duplication front),
- compatibilite legacy preservee (`/scan/*`, `/portal/*` inchanges).

## 6) Priorisation API recommandee (suite P2/P3)

1. Completer endpoints manquants pour ecrans P1 (tracking detail, portal order detail).
2. Etendre endpoints listes pour modules scan restants (cartons, shipments-ready, orders view).
3. Ajouter batterie de tests permissions role par role.
4. Conserver retro-compatibilite stricte sur contrats existants deja consommes par `frontend-next`.
