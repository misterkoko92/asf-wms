# Preparateur Pack And Product Flow - Design

## Contexte

Le scope reste strictement sur la stack Django legacy `scan`.

Le compte `Preparateur` existe deja, avec un shell `scan` reduit et une whitelist de vues, mais le flux actuel ne couvre pas correctement:

- un masthead adapte au preparateur,
- un menu preparateur oriente "commande a preparer",
- la selection d une commande deja validee,
- l ajout immediat d un produit inconnu depuis `Preparer des colis`,
- la notification de revue admin/superuser quand un preparateur cree un produit.

Le repo a deja des briques utiles:

- le shell scan et la navigation dans `templates/scan/base.html` et `templates/scan/includes/scan_sidebar_navigation.html`,
- le flux pack dans `wms/views_scan_shipments.py`, `wms/pack_handlers.py`, `templates/scan/pack.html`, `wms/static/scan/scan.js`,
- le modele `Product.is_incomplete`,
- les formulaires et vues de complementation produit incomplet,
- les helpers de localisation et de mise en stock.

Le travail n ouvre ni le scope traduction ni le scope Next/React.

## Objectif

Rendre le compte preparateur operable en continu pour la preparation:

1. adapter le shell preparateur au besoin reel terrain,
2. permettre de choisir une commande deja validee a preparer,
3. permettre de creer un produit inconnu directement depuis `Preparer des colis`,
4. rendre ce produit utilisable tout de suite en creant aussi un stock initial,
5. notifier les admins et superusers pour revue du nouveau produit.

## Decision Validee

La solution retenue est:

- masthead preparateur specifique dans le shell scan legacy,
- menu preparateur remanie avec:
  - `Choisir une commande`
  - `Voir dernier colis`
  - `Changer de compte`
  - `Deconnexion`
- retrait du bouton `?` et du menu compte du masthead preparateur,
- ajout d une vue preparateur ciblee de selection de commandes deja validees,
- ajout d une popup `Nouveau produit` dans `Preparer des colis` quand un scan ne matche aucun produit,
- creation d un `Product` marque `is_incomplete=True`,
- creation immediate d un stock initial sur un emplacement choisi par le preparateur via selecteurs structures,
- notification email/queue vers admins et superusers,
- maintien d une revue ulterieure du produit dans le cockpit produits incomplets.

## Alternatives Ecartees

### Alternative A - Exposer tout `/scan/orders/` au preparateur

Avantages:

- peu de nouvelles routes

Inconvenients:

- ecran trop large pour le besoin,
- expose creation/edition de commande hors besoin preparateur,
- augmente le risque de derive fonctionnelle.

Verdict:

- rejetee

### Alternative B - Creer le produit sans stock initial

Avantages:

- plus simple cote backend

Inconvenients:

- le produit n est pas utilisable tout de suite,
- contredit le besoin exprime.

Verdict:

- rejetee

### Alternative C - Autoriser la preparation sans stock pour un produit nouveau

Avantages:

- donne une impression d immediatete

Inconvenients:

- casse l invariant stock,
- cree des ecarts d inventaire difficiles a tracer,
- complique les controles ulterieurs.

Verdict:

- rejetee

### Alternative D - Emplacement saisi librement dans la popup

Avantages:

- implementation courte

Inconvenients:

- erreurs de saisie,
- doublons d emplacements,
- non alignement avec les contrats existants du repo.

Verdict:

- rejetee

## Experience Utilisateur Cible

### Shell Preparateur

Pour `request.scan_is_preparateur`:

- ligne 1 du masthead:
  - gauche: `Bonjour XXX`
  - droite: fleches historique
- ligne 2 du masthead:
  - gauche: bouton `Menu`
  - droite: logo + `Messagerie Medicale`
- plus de bouton `?`
- plus de dropdown compte en haut

Le menu preparateur n affiche plus `Runs magasin`.

Il affiche:

- `Choisir une commande`
- `Voir dernier colis`
- `Changer de compte`
- `Deconnexion`

### Choisir Une Commande

Le preparateur ouvre une vue reduite, reservee a son besoin:

- liste de commandes deja validees / approuvees,
- ouverture ou selection explicite d une commande a preparer,
- retour ensuite vers `Preparer des colis` avec le contexte commande selectionne.

La vue ne permet pas:

- de creer une commande,
- de modifier les metadonnees de commande,
- d ouvrir des ecrans admin.

### Voir Dernier Colis

Le raccourci ouvre la fiche du dernier `Carton` prepare par l utilisateur courant, via `prepared_by`.

Si aucun colis n existe encore:

- retour sur `Preparer des colis`,
- message explicite `Aucun colis prepare recemment.`

### Produit Inconnu Dans Preparer Des Colis

Quand un code scanne ou saisi ne correspond a aucun produit connu:

- une popup `Nouveau produit` s ouvre,
- le preparateur peut soit annuler, soit creer le produit sans quitter le flux pack.

Champs minimaux obligatoires:

- `Nom du produit`
- un identifiant scannable:
  - `barcode`, ou
  - `ean`, ou
  - `sku`
- `Type MM/CN`
- `Quantite initiale`
- emplacement choisi via selecteurs:
  - `Entrepot`
  - `Zone`
  - `Allee`
  - `Etagere / Bac`

Champs optionnels:

- `Lot`
- `Date de peremption`
- `Marque`
- `Notes`

Apres validation:

- le produit est cree en base,
- il est marque `is_incomplete=True`,
- le stock initial est cree sur l emplacement choisi,
- la ligne pack est alimentee automatiquement avec ce produit,
- le preparateur peut l utiliser immediatement dans le colis,
- un email / evenement notifie les admins et superusers pour revue.

## Contrat Metier

### Produit Cree Par Un Preparateur

- un produit cree depuis `pack` reste un produit a revoir,
- `is_incomplete=True` reste la source de verite de cette revue,
- le produit peut toutefois etre utilise immediatement si un stock initial a ete cree,
- la creation n ouvre pas de passe-droit sur la revue admin ulterieure.

### Stock Initial

- le stock initial est obligatoire si l operateur veut utiliser le produit tout de suite,
- l emplacement est selectionne uniquement via des selecteurs structures,
- aucune saisie libre d emplacement n est acceptee dans cette popup,
- si la quantite initiale est invalide ou absente, la creation doit echouer proprement.

### Categorie MM/CN

- le preparateur n a pas a naviguer toute l arborescence categorie,
- il choisit un type simple `MM` ou `CN`,
- le backend rattache ce choix a la categorie racine attendue ou bloque si la configuration racine manque.

### Notification De Revue

- les destinataires sont:
  - tous les superusers actifs avec email,
  - les users staff du groupe de validation si pertinent,
  - sans doublons
- la notification contient au minimum:
  - le produit cree,
  - l identifiant saisi / scanne,
  - le preparateur createur,
  - l emplacement et la quantite initiale,
  - un lien utile vers la surface de revue.

## Architecture Recommandee

### Shell Et Navigation

Sources principales:

- `templates/scan/base.html`
- `templates/scan/includes/scan_sidebar_navigation.html`
- `wms/static/scan/scan-bootstrap.css`
- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `docs/repo-reference/04-shared-contracts.md`

Approche:

- conserver le shell scan legacy,
- specialiser uniquement le rendu preparateur,
- ne pas changer le contrat des autres profils staff.

### Vue Preparateur De Selection De Commande

Sources principales:

- `wms/scan_permissions.py`
- `wms/views_scan_orders.py`
- `wms/order_scan_state.py`
- `templates/scan/`
- `wms/tests/views/tests_views.py`
- `wms/tests/views/tests_views_scan_orders.py`

Approche:

- ajouter une vue dediee preparateur a partir des briques commandes existantes,
- filtrer sur commandes validees / approuvees,
- rediriger ensuite vers `scan_pack` avec le contexte de commande choisi,
- conserver une whitelist preparateur stricte.

### Popup Nouveau Produit Dans Pack

Sources principales:

- `templates/scan/pack.html`
- `wms/static/scan/scan.js`
- `wms/views_scan_shipments.py`
- `wms/pack_handlers.py`
- `wms/tests/views/tests_views_scan_shipments.py`
- `wms/tests/views/tests_scan_bootstrap_ui.py`

Approche:

- detection front d un produit inconnu sur la ligne pack,
- ouverture d une popup locale,
- soumission vers une nouvelle action scan dediee,
- remise a jour de la page pack avec le nouveau produit disponible.

### Creation Produit + Stock Initial

Sources principales:

- `wms/forms.py`
- `wms/models_domain/catalog.py`
- `wms/import_services_products.py`
- `wms/domain/stock.py`
- `wms/scan_location_helpers.py`
- `wms/scan_product_helpers.py`
- `wms/views_scan_shipments.py`
- `wms/tests/orders/tests_pack_handlers.py`

Approche:

- ne pas reutiliser le flux import complet,
- introduire un petit formulaire serveur dedie au pack preparateur,
- creer:
  - le `Product`,
  - le `Location` deja existant via selection,
  - le stock initial via les services de stock existants,
- laisser le produit en `is_incomplete=True`.

### Notification

Sources principales:

- `wms/emailing.py`
- `wms/events/outbox.py`
- `wms/context_processors.py`
- `wms/tests/emailing/`

Approche:

- reutiliser `send_or_enqueue_email_safe`,
- dedupliquer les emails via helpers existants,
- rester sur un producteur simple, sans nouveau systeme de notification.

## Validation

### Navigation Preparateur

Verifier:

- absence du bouton `?`,
- absence du dropdown compte,
- presence de `Bonjour XXX`,
- presence des fleches en ligne 1,
- presence de `Menu` a gauche et marque a droite en ligne 2,
- menu contenant les nouvelles entrees,
- absence de `Runs magasin`.

### Choisir Une Commande

Verifier:

- la vue est accessible au preparateur,
- seules les commandes validees sont proposees,
- la selection renvoie bien vers `scan_pack`,
- aucune creation/edition complete de commande n est exposee.

### Popup Nouveau Produit

Verifier:

- scan inconnu => popup,
- annulation => retour propre sur la ligne,
- creation valide => produit cree, stock cree, ligne pack alimentee,
- emplacement uniquement via selecteurs,
- produit marque `is_incomplete=True`,
- notification envoyee ou queuee.

## Propagation Et Docs

Ce changement doit mettre a jour:

- `docs/repo-reference/04-shared-contracts.md` pour le contrat navigation preparateur,
- la documentation de surface si le comportement pack / commande devient un contrat recurrent.
