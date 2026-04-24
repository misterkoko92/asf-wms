# Scan Catalog And Ops Adjustments Design

## Contexte

Le lot demandé couvre un ensemble de corrections et d'évolutions réparties sur plusieurs cockpits `scan/`:

- `stock`
- `stock-update`
- `cartons`
- `receive-pallet`
- `receive-association`
- `pack`
- `shipment`
- `billing/editor`
- `faq`
- masthead et contrats UI partagés

La contrainte principale est de garder le delivery surface sur le legacy Django, sans rouvrir le scope Next/React ni le scope traduction. Le lot mélange des ajustements locaux et des contrats transverses; il faut donc éviter les patches écran par écran quand un comportement est partagé.

## Objectif

Livrer un lot cohérent qui:

- remplace les derniers ponts vers l'admin Django quand un vrai cockpit scan est attendu
- améliore l'ergonomie des flux magasin et expédition
- renforce la visibilité des actions en attente
- homogénéise les contrats UI globaux
- introduit un changelog utilisateur maintenable depuis le repo

## Décisions validées

### 1. Cockpit catalogue unique

Le pilotage des produits et kits doit converger vers un cockpit catalogue unique:

- `/scan/admin/products/` devient l'index catalogue
- `/scan/admin/products/<id>/` devient le dossier produit/kit
- les boutons `Ouvrir` depuis `/scan/stock/` et l'index catalogue pointent vers ce dossier scan
- on conserve le modèle `Product` existant; un kit reste un `Product`
- la section `Composition du kit` n'apparait que pour les fiches concernées

Le cockpit catalogue doit couvrir les actions opérationnelles courantes sans imposer un retour dans l'admin Django:

- identité produit
- logistique et emplacement par défaut
- tarification
- QR et étiquettes
- composition de kit
- archivage / réactivation / suppression quand autorisé
- visibilité des usages qui bloquent la suppression

### 2. Contrats transverses

Les changements globaux doivent être traités comme des contrats partagés:

- les champs obligatoires affichent systématiquement un `*` rouge à côté du libellé
- les boutons de calendrier deviennent une icône seule via le composant date partagé
- le masthead scan expose un indicateur persistant d'actions en attente, indépendant du fait qu'une notification ait déjà été vue
- le changelog FAQ repose sur une source structurée dans le repo, avec une entrée par PR

### 3. Flux métier

Les décisions fonctionnelles validées sont:

- `scan/stock/`: `Inclure les produits à 0` par défaut sur oui
- `scan/stock-update/`: carte `MAJ stock` ouverte par défaut
- `scan/receive-pallet/`: switch `Non conforme` positionné juste au-dessus d'`Observation`
- `scan/receive-association/`: préremplissage du coût d'enlèvement depuis un service annexe par défaut, avec checkbox pour activer/désactiver l'usage de cette valeur
- `scan/pack/` et fiche colis: possibilité de retirer un produit
- `scan/cartons/`: nouveaux codes colis sans zéros non significatifs, sans migration des anciens codes
- `scan/shipment/`: regroupement des colis disponibles en 4 groupes et ajout du forçage du nombre de colis
- `scan/shipment/<id>/edit/`: hiérarchie visuelle plus claire des boutons du dossier
- `scan/billing/editor/`: taux prérempli affiché avec 2 décimales, tout en acceptant une saisie manuelle plus longue

## Architecture retenue

## A. Catalogue: index + dossier

### Index `/scan/admin/products/`

L'index catalogue reste le point d'entrée superuser, mais évolue d'une simple passerelle admin vers un cockpit scan:

- recherche `nom / SKU / barcode / EAN`
- filtre de type `tous / produits / kits`
- filtre de statut `actif / archivé`
- actions `Ouvrir`, `Créer produit`, `Créer kit`
- suppression gardée si autorisée

L'index n'a pas vocation à devenir une page d'édition dense. Son rôle est le triage et l'accès rapide au dossier.

### Dossier `/scan/admin/products/<id>/`

Le dossier suit le pattern des dossiers scan existants:

- en-tête avec identité, statut, type et actions principales
- cartes séparées par domaine métier
- actions d'édition ciblées par formulaire sur la même page

Cartes prévues:

1. `Synthèse`
2. `Identité`
3. `Logistique`
4. `Tarification`
5. `QR / étiquettes`
6. `Composition du kit`
7. `Pilotage`
8. `Danger zone`

La page doit fonctionner en lecture seule pilotée, avec des panneaux d'édition ciblés sur la même page. Elle ne doit pas renvoyer vers l'admin Django pour les opérations courantes.

## B. Champ obligatoire partagé

Le repo a déjà un mix de labels manuels et de logique JS spécifique à certains formulaires. La solution retenue est de faire porter le marquage obligatoire au niveau partagé:

- les primitives réutilisables, en particulier `ui_field`, doivent pouvoir afficher automatiquement le marqueur rouge si le champ est obligatoire
- les formulaires écrits à la main doivent converger vers une règle commune simple, pour limiter les exceptions
- les écrans déjà pilotés par JS (`admin contacts`, `account validations`) conservent leur logique conditionnelle, mais doivent produire le même rendu visuel final

Le but n'est pas de réécrire tous les templates en primitives en une fois, mais d'étendre le contrat partagé puis d'aligner les surfaces touchées par ce lot.

## C. Bouton calendrier partagé

Le bouton calendrier est aujourd'hui injecté par l'enhancement JS commun sur tous les `input[type="date"]`. Le changement doit donc rester dans ce contrat partagé:

- remplacer le texte `Calendrier` par une icône
- conserver l'accessibilité avec un `aria-label` explicite
- garder le même mécanisme `showPicker()` / fallback calendrier custom

Ce choix garantit la propagation sur tous les domaines et tous les comptes sans reprendre chaque template.

## D. Indicateur persistant d'actions en attente dans le masthead

Le masthead scan expose déjà des compteurs limités pour certaines validations. Le besoin ici est plus large: afficher qu'il reste des actions à faire même quand elles ont déjà été consultées.

La source la plus cohérente est la même famille de données que le dashboard scan:

- commandes en attente de validation
- blocages workflow non résolus
- validations en attente
- éventuellement autres actions déjà synthétisées par le dashboard

Le masthead doit afficher:

- un indicateur visible dès qu'il existe au moins une action ouverte
- un compteur total
- un lien vers la file la plus utile, ou vers le dashboard si l'agrégat couvre plusieurs files

Le contrat retenu est un indicateur d'état opérationnel, pas un centre de notifications "vu / non vu".

## E. Changelog FAQ structuré

Le changelog utilisateur ne doit pas être saisi à la main dans le template.

Source retenue:

- fichier structuré dans le repo, lisible côté Django
- une entrée par PR
- champs: `date`, `pr`, `summary`

Affichage retenu dans `/scan/faq/`:

- rubrique `Change Log`
- tri décroissant par date d'ajout
- résumé fonctionnel court, non technique

Décision de scope:

- le changelog démarre avec cette PR et les suivantes
- pas de reconstitution rétroactive de tout l'historique ancien dans ce lot

## F. Réception association et service annexe par défaut

Le besoin n'est pas de générer automatiquement une ligne de facturation lors de la réception. Le besoin est de préremplir un coût d'enlèvement cohérent côté opérationnel.

Solution retenue:

- introduire dans les paramètres de facturation un service annexe identifiable comme valeur par défaut pour l'enlèvement
- sur `scan/receive-association/`, ajouter une checkbox cochée par défaut du type `Utiliser le tarif enlèvement par défaut`
- si cochée: montant et devise sont préremplis depuis le service
- si décochée: saisie libre
- le montant reste toujours éditable, même quand il est prérempli

Ce choix permet de guider l'opérateur sans verrouiller le champ, et sans coupler prématurément réception et génération de ligne de facturation.

## G. Suppression de produit dans pack et fiche colis

Le besoin couvre deux moments différents:

- avant validation du packing: retirer une ligne du draft
- après création du colis: retirer un produit déjà packé depuis la fiche colis

Solution retenue:

- ajout d'une action locale de suppression de ligne dans l'UI pack
- ajout d'une mutation serveur côté fiche colis pour retirer une ligne produit / lot d'un colis existant
- restauration correcte du stock lors du retrait depuis un colis persistant

Cette logique doit rester cohérente avec les garde-fous existants autour des colis verrouillés et des expéditions non modifiables.

## H. Nouveau format d'affichage des codes colis

Les nouveaux colis ne doivent plus afficher les zéros non significatifs.

Décision:

- les nouveaux codes générés utilisent le même compteur interne par famille, mais l'affichage devient `MM-1`, `MM-2`, etc.
- les anciens codes restent inchangés
- aucune migration de données n'est lancée
- les lectures, tris, validations et recherches doivent accepter les deux formats

Ce choix limite le risque production en évitant toute réécriture des références existantes.

## I. Regroupement des colis disponibles dans la création d'expédition

La donnée existe déjà partiellement:

- compatibilité par destinataire
- préaffectation de destination
- source du colis

La nouvelle UI doit organiser cette donnée en 4 groupes:

1. compatibles et préaffectés à la destination choisie
2. compatibles sans préaffectation
3. compatibles mais préaffectés à une autre destination
4. incompatibles

Règles UX retenues:

- les groupes 3 et 4 restent sélectionnables
- une confirmation explicite protège les cas de conflit
- le code IATA de préaffectation d'une autre destination est mis en évidence

## J. Forçage du nombre de colis dans la création d'expédition

La logique existe déjà dans `pack`. Elle doit être reprise dans `shipment` avec le même contrat:

- champ numérique optionnel
- vide = calcul automatique
- valeur renseignée = nombre imposé
- warning si le forçage crée une incohérence opérateur

L'objectif est l'alignement des comportements, pas l'introduction d'une seconde règle métier.

## K. Hiérarchie visuelle des actions du dossier expédition

Le problème est visuel, pas métier. La solution retenue est donc un rebalancement des variants de boutons:

- action principale de travail: bouton primaire
- navigation secondaire: tertiaire
- action positive de validation: succès
- clôture: variante distincte selon état `bloqué / prêt / clôturé`

Le but est que la hiérarchie d'action soit lisible immédiatement sans changer le workflow existant.

## L. Taux de change dans l'éditeur de facturation

Le besoin combine lisibilité et souplesse:

- affichage par défaut arrondi visuellement à 2 décimales
- conservation de la précision si l'utilisateur saisit une valeur plus longue

Solution retenue:

- l'initialisation du champ côté vue affiche `format(rate, ".2f")`
- la validation du formulaire continue d'accepter jusqu'à 6 décimales
- la valeur saisie manuellement n'est pas raccourcie après POST si l'utilisateur a fourni plus précis

## Vérification et impact map

Ce lot touche plusieurs contrats de la `scan` surface. Les propagations minimales à vérifier sont:

- `wms/scan_urls.py`
- `wms/views_scan_stock.py`
- `wms/views_scan_receipts.py`
- `wms/views_scan_shipments.py`
- `wms/views_scan_admin.py`
- `templates/scan/`
- `wms/static/scan/modules/core.js`
- `wms/static/scan/scan.js`
- `wms/static/scan/scan-bootstrap.css`
- `wms/templatetags/wms_ui.py`
- tests scan, forms, carton, billing et bootstrap UI

Les docs de repo-reference ne nécessitent pas de changement structurel tant que les routes critiques et contrats décrits ne changent pas de nature. En revanche, le changelog FAQ et la règle repo associée devront être ajoutés dans le même travail si le lot est implémenté.

## Risques et garde-fous

- risque de dérive d'UI partagée: limiter les changements globaux aux primitives et aux enhanceurs date / masthead déjà partagés
- risque de casser les codes colis existants: ne jamais réécrire les anciennes références
- risque de surcoupler réception et facturation: préremplir seulement le coût, sans générer de ligne annexe automatiquement
- risque de réintroduire l'admin Django comme dépendance: privilégier les nouveaux dossiers scan comme point d'entrée normal

## Tests cibles

Le lot doit être validé au minimum par:

- tests de vues `scan_stock`, `scan_stock_update`, `scan_receive_association`, `scan_receive_pallet`, `scan_pack`, `scan_shipment_create`, `scan_shipment_edit`, `scan_admin_products`, `scan_faq`
- tests bootstrap UI pour les contrats date input, masthead, required marker et hiérarchie des boutons
- tests forms pour les champs obligatoires et le coût d'enlèvement
- tests domaine/carton pour la génération des nouveaux codes
- tests billing pour l'affichage et la conservation de la précision du taux

## Hors scope

- migration Next/React
- reprise du scope traduction FR/EN
- reconstitution historique complète du changelog ancien
- refonte complète de tous les formulaires legacy du repo en primitives partagées
