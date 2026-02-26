# P3 Sprint C - Recette metier manuelle globale (2026-02-26)

## Statut

- Statut execution: PENDING (checklist preparee, execution terrain non lancee).
- Portee: tous ecrans/boutons/fonctions de la matrice (`scan` + `portal` + routes dynamiques).
- Roles cibles: staff, association, admin.

## Regles de validation

- Un scenario est `OK` si le comportement Next est equivalent au legacy sur actions/validations/permissions.
- Toute anomalie devient un item dans `p3_sprint_c_gap_register_2026-02-26.md`.
- Le pilote ne peut pas demarrer tant que des scenarios bloquants restent ouverts.

## Checklist par route

| Priorite | Legacy | Next | Role | Scenario a executer | Resultat | Preuve | Bloquant |
|---|---|---|---|---|---|---|---|
| P1 | `/scan/dashboard/` | `/app/scan/dashboard/` | staff,association,admin | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P1 | `/scan/stock/` | `/app/scan/stock/` | staff,association,admin | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P1 | `/scan/stock-update/` | `/app/scan/stock/` (zone MAJ inline cible) | staff,association,admin | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P1 | `/scan/out/` | `/app/scan/stock/` (zone sortie cible) | staff,association,admin | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P1 | `/scan/shipment/` | `/app/scan/shipment-create/` | staff,association,admin | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P1 | `/scan/shipments-tracking/` | `/app/scan/shipments-tracking/` | staff,association,admin | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P1 | `/scan/shipment/<id>/close` (logique legacy) | `/app/scan/shipments-tracking/` (integration transitoire) | staff,association,admin | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P1 | `/scan/pack/` | `/app/scan/shipment-create/` (integration transitoire) | staff,association,admin | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P1 | `/scan/cartons/` | `/app/scan/cartons/` | staff,association,admin | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P1 | `/scan/shipments-ready/` | `/app/scan/shipments-ready/` | staff,association,admin | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P2 | `/scan/orders-view/` | `/app/scan/orders/` | staff,admin | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |
| P2 | `/scan/orders/` | `/app/scan/order/` | staff,admin | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |
| P2 | `/scan/receipts/` | `/app/scan/receipts/` | staff,admin | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |
| P2 | `/scan/receive/` | `/app/scan/receive/` | staff,admin | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |
| P2 | `/scan/receive-pallet/` | `/app/scan/receive-pallet/` | staff,admin | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |
| P2 | `/scan/receive-association/` | `/app/scan/receive-association/` | staff,admin | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |
| P2 | `/scan/settings/` | `/app/scan/settings/` | staff,admin | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |
| P2 | `/scan/faq/` | `/app/scan/faq/` | staff,admin | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |
| P3 | `/scan/import/` | `/app/scan/import/` | staff | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |
| P2 | `/scan/shipment/<id>/documents/upload/` | `/app/scan/shipment-documents/` | staff,admin | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P2 | `/scan/shipment/<id>/documents/<id>/delete/` | `/app/scan/shipment-documents/` | staff,admin | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P2 | `/scan/shipment/<id>/labels/` | `/app/scan/shipment-documents/` | staff,admin | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P2 | `/scan/shipment/<id>/labels/<carton_id>/` | `/app/scan/shipment-documents/` | staff,admin | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P3 | `/scan/templates/` | `/app/scan/templates/` | staff | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P3 | `/scan/templates/<doc_type>/` | `/app/scan/templates/` | staff | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P1 | `/portal/` | `/app/portal/dashboard/` | staff,association,admin | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P1 | `/portal/orders/new/` | `/app/portal/dashboard/` (integration transitoire) | staff,association,admin | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P1 | `/portal/orders/<id>/` | `/app/portal/orders/detail/?id=<id>` | staff,association,admin | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PARTIAL | `NextUiTests.test_next_portal_order_detail_route_displays_selected_order` | Oui (recette manuelle multi-role reste a faire) |
| P2 | `/portal/recipients/` | `/app/portal/dashboard/` (integration transitoire) | staff,admin | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P2 | `/portal/account/` | `/app/portal/dashboard/` (integration transitoire) | staff,admin | Verifier flux nominal + validations + erreurs metier + permissions. | PENDING | - | - |
| P2 | `/portal/change-password/` | `/app/portal/change-password/` | staff,admin | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |
| P2 | `/portal/login/` | `/app/portal/login/` | staff,admin | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |
| P2 | `/portal/logout/` | `/app/portal/logout/` | staff,admin | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |
| P3 | `/portal/request-account/` | `/app/portal/request-account/` | staff | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |
| P3 | `/portal/set-password/<uid>/<token>/` | `/app/portal/set-password/?...` | staff | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |
| P2 | `/scan/shipment/<id>/edit/` | `/app/scan/shipment/edit/?id=<id>` | staff,admin | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |
| P2 | `/scan/shipment/track/<token>/` | `/app/scan/shipment/track/?token=<token>` | staff,admin | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |
| P2 | `/scan/shipment/track/<ref>/` | `/app/scan/shipment/track/?ref=<ref>` | staff,admin | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |
| P2 | `/scan/carton/<id>/doc/` | `/app/scan/carton/doc/?id=<id>` | staff,admin | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |
| P2 | `/scan/carton/<id>/picking/` | `/app/scan/carton/picking/?id=<id>` | staff,admin | Verifier route creee, actions disponibles, validations, permissions et erreurs. | PENDING | - | - |

## Journal d execution

| Date | Responsable | Lot | Resultat | Notes |
|---|---|---|---|---|
| 2026-02-26 | - | Preparation checklist | PENDING | Execution terrain a planifier |
