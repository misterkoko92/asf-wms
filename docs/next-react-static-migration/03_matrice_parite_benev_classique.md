# 03 - Matrice de parité Benev/Classique

## Légende statut

- `TODO`: non démarré.
- `IN_PROGRESS`: en cours.
- `DONE`: validé fonctionnel + visuel.

## A. Scan (opérations internes)

| Priorité | Legacy URL | Vue legacy | Route Next cible | Données/API | Statut |
|---|---|---|---|---|---|
| P1 | `/scan/dashboard/` | dashboard | `/app/scan/dashboard` | KPI + actions attente | TODO |
| P1 | `/scan/stock/` | vue stock | `/app/scan/stock` | stock list + filtres | TODO |
| P1 | `/scan/stock-update/` | maj stock | `/app/scan/stock/update` | update stock + audit | TODO |
| P1 | `/scan/shipment/` | création expédition | `/app/scan/shipment/create` | expédition + docs | TODO |
| P1 | `/scan/pack/` | création colis | `/app/scan/carton/create` | colis + contenu | TODO |
| P1 | `/scan/shipments-tracking/` | suivi expéditions | `/app/scan/shipment/tracking` | timeline/events | TODO |
| P1 | `/scan/cartons/` | vue colis prêts | `/app/scan/cartons` | cartons statuts | TODO |
| P1 | `/scan/shipments-ready/` | vue expéditions prêtes | `/app/scan/shipments-ready` | shipments prêts | TODO |
| P1 | `/scan/orders-view/` | vue commandes | `/app/scan/orders` | commandes + alertes | TODO |
| P2 | `/scan/orders/` | gestion commande | `/app/scan/order` | détail commande | TODO |
| P2 | `/scan/receipts/` | vue réceptions | `/app/scan/receipts` | mouvements entrée | TODO |
| P2 | `/scan/receive/` | réception produit | `/app/scan/receive` | scan réception | TODO |
| P2 | `/scan/receive-pallet/` | réception palette | `/app/scan/receive-pallet` | palette + lots | TODO |
| P2 | `/scan/receive-association/` | ajout stock association | `/app/scan/receive-association` | entrée manuelle | TODO |
| P2 | `/scan/out/` | sortie stock | `/app/scan/out` | décrément + motifs | TODO |
| P2 | `/scan/settings/` | paramètres | `/app/scan/settings` | runtime settings | TODO |
| P2 | `/scan/faq/` | documentation | `/app/scan/faq` | contenu statique | TODO |
| P3 | `/scan/import/` | imports admin | `/app/scan/import` | import CSV | TODO |
| P3 | `/scan/templates/` | liste templates docs | `/app/scan/templates` | types de docs | TODO |
| P3 | `/scan/templates/<doc_type>/` | édition template | `/app/scan/templates/edit?docType=` | template HTML | TODO |

## B. Scan (routes métiers dynamiques)

> En mode statique, route cible recommandée: page stable + query params.

| Priorité | Legacy URL | Fonction | Route Next cible | Stratégie |
|---|---|---|---|---|
| P1 | `/scan/shipment/<id>/edit/` | édition expédition | `/app/scan/shipment/edit?id=<id>` | param query |
| P1 | `/scan/shipment/track/<token>/` | suivi token | `/app/scan/shipment/track?token=<token>` | param query |
| P1 | `/scan/shipment/track/<ref>/` | suivi legacy ref | `/app/scan/shipment/track?ref=<ref>` | param query |
| P1 | `/scan/shipment/<id>/doc/<type>/` | doc expédition | `/app/scan/shipment/doc?shipmentId=<id>&type=<type>` | conserver rendu serveur PDF |
| P2 | `/scan/shipment/<id>/carton/<id>/doc/` | doc carton expédition | `/app/scan/shipment/carton/doc?...` | conserver rendu serveur PDF |
| P2 | `/scan/carton/<id>/doc/` | doc carton | `/app/scan/carton/doc?id=<id>` | conserver rendu serveur PDF |
| P2 | `/scan/carton/<id>/picking/` | picking carton | `/app/scan/carton/picking?id=<id>` | endpoint dédié |
| P2 | `/scan/shipment/<id>/documents/upload/` | upload doc | `/app/scan/shipment/documents/upload?id=<id>` | multipart API |
| P2 | `/scan/shipment/<id>/documents/<id>/delete/` | delete doc | `/app/scan/shipment/documents/delete?...` | action API |
| P2 | `/scan/shipment/<id>/labels/` | labels expédition | `/app/scan/shipment/labels?id=<id>` | backend labels |
| P2 | `/scan/shipment/<id>/labels/<carton_id>/` | label carton | `/app/scan/shipment/label?...` | backend labels |
| P3 | `/scan/public-order/<token>/...` | flux public | hors périmètre v1 interne | conserver legacy |

## C. Portal (associations)

| Priorité | Legacy URL | Vue legacy | Route Next cible | Données/API | Statut |
|---|---|---|---|---|---|
| P1 | `/portal/` | dashboard portail | `/app/portal/dashboard` | commandes + états | TODO |
| P1 | `/portal/orders/new/` | création commande | `/app/portal/orders/create` | formulaire complet | TODO |
| P1 | `/portal/orders/<id>/` | détail commande | `/app/portal/orders/detail?id=<id>` | détail + historique | TODO |
| P2 | `/portal/recipients/` | destinataires | `/app/portal/recipients` | contacts + filtres | TODO |
| P2 | `/portal/account/` | compte | `/app/portal/account` | profil + préférences | TODO |
| P2 | `/portal/change-password/` | mdp | `/app/portal/change-password` | action sécurisée | TODO |
| P2 | `/portal/login/` | login | `/app/portal/login` | session Django | TODO |
| P2 | `/portal/logout/` | logout | `/app/portal/logout` | session Django | TODO |
| P3 | `/portal/request-account/` | demande compte | `/app/portal/request-account` | workflow externe | TODO |
| P3 | `/portal/set-password/<uid>/<token>/` | set password | `/app/portal/set-password?...` | token sécurisé | TODO |

## D. Critères de parité par écran (checklist)

Pour passer `DONE`, chaque écran doit valider:

- [ ] mêmes champs obligatoires,
- [ ] mêmes validations bloquantes,
- [ ] mêmes permissions par rôle,
- [ ] mêmes statuts métier,
- [ ] mêmes actions principales (et idéalement moins de clics),
- [ ] même logique de messages succès/erreur,
- [ ] rendu visuel Benev/Classique reproduit.

## E. Flux E2E obligatoires (validation finale)

- [ ] Dashboard -> vue stock -> MAJ stock -> confirmation.
- [ ] Création colis -> création expédition -> affectation colis.
- [ ] Ajout documents -> publication (warning si docs manquants).
- [ ] Suivi expédition -> gestion incident -> clôture.
- [ ] Retour global instantané vers interface legacy.
