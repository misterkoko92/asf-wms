# Pack Unknown Product And Import Product Card - Design

## Contexte

Le legacy Django `scan` couvre deja:

- la preparation de colis via `/scan/pack/`
- l edition d un colis existant via `/scan/carton/<id>/edit/`
- l import manuel et fichier via `/scan/import/`

Le comportement actuel presente deux limites UX:

- dans `pack`, un produit inconnu n est detecte qu au submit serveur avec `Produit introuvable.`
- la carte `Import produits` n expose qu une partie du contrat produit actuel, alors que les services backend savent deja creer des categories, emplacements, SKU auto, dimensions, poids, conditions de stockage, et plusieurs champs de completude

Le travail reste strictement sur la stack Django legacy `scan`, sans rouvrir le scope Next/React ni le scope traduction.

## Objectif

Ameliorer le flux operateur de creation produit autour de deux surfaces:

1. dans `/scan/pack/` et `/scan/carton/<id>/edit/`, proposer immediatement la creation d un produit inconnu avec confirmation explicite et redirection vers `/scan/import/`
2. dans `/scan/import/`, mettre a niveau la carte `Import produits` pour refleter le contrat produit actuel du repo et permettre une creation produit plus complete

## Decision Validee

La recommandation retenue est:

- ajout d un pop up de confirmation sur les ecrans `pack` lorsqu une saisie ou un scan ne correspond a aucun produit connu
- ajout d un bouton visible `Creer un nouveau produit` sur `pack` et `edition colis`
- redirection des deux actions vers `/scan/import/`
- absence de sauvegarde implicite du colis en cours avant cette redirection
- conservation du garde fou serveur actuel `Produit introuvable.` en cas de POST invalide
- mise a niveau de la carte `Import produits` avec combobox triees A-Z, saisie libre conservee, auto affichage de `rack_color`, validation d unicite de couleur par entrepot, et ajout des champs utiles a un produit complet

## Alternatives Ecartees

### Alternative A - laisser uniquement l erreur serveur sur produit inconnu

Avantages:

- cout faible
- aucun changement JS

Inconvenients:

- pas de reponse immediate au scan
- UX pauvre pour la recherche texte
- ne couvre pas la demande explicite `Accepter / Refuser`

Verdict:

- rejetee

### Alternative B - redirection automatique vers `/scan/import/` sans confirmation

Avantages:

- implementation courte

Inconvenients:

- trop agressive
- risque de sortie involontaire du flux pack
- ne respecte pas le besoin de confirmation explicite

Verdict:

- rejetee

### Alternative C - reimplementer un mini formulaire produit directement dans `pack`

Avantages:

- moins de navigation entre pages

Inconvenients:

- duplication forte avec `/scan/import/`
- plus de dette de maintenance
- scope trop large pour un besoin deja couvert par une page existante

Verdict:

- rejetee

## Experience Utilisateur Cible

### Pack Et Edition Colis

Sur `/scan/pack/` et `/scan/carton/<id>/edit/`:

- quand une ligne produit contient une valeur non vide qui ne matche aucun produit connu, un overlay s ouvre
- message:
  - `Souhaitez-vous creer ce produit dans la base ?`
  - `Le colis en cours ne sera pas sauvegarde.`
- actions:
  - `Accepter`
  - `Refuser`

Effets:

- `Accepter` redirige vers `/scan/import/`
- `Refuser` ferme le pop up, vide le champ produit concerne, remet le focus sur ce champ, et laisse l operateur sur sa page actuelle

Les deux surfaces affichent aussi un bouton direct:

- `Creer un nouveau produit`

Ce bouton redirige directement vers `/scan/import/`.

### Import Produits

Sur `/scan/import/`, la carte produit doit conserver la creation rapide unitaire, mais devenir plus complete et plus guidee.

Changements UX retenus:

- `Categorie L1..L4`
  - combobox triees A-Z
  - saisie libre autorisee
  - creation backend conservee via les services actuels
- `Marque`
  - suggestions dediees de marques distinctes
  - tri A-Z
  - saisie libre autorisee
- `Entrepot`, `Rack`, `Etagere`, `Bac`
  - suggestions triees A-Z
  - saisie libre autorisee
  - filtrage dependant du contexte saisi quand possible
- `Couleur rack`
  - si le rack existe deja dans l entrepot choisi, la couleur connue s affiche automatiquement
  - si le rack est nouveau, le champ reste libre
  - la couleur ne peut pas etre reutilisee par un autre rack du meme entrepot
- `SKU`
  - aide explicite indiquant que laisser vide declenche une auto generation

Champs supplementaires a exposer pour un produit plus complet:

- `weight_g`
- `length_cm`
- `width_cm`
- `height_cm`
- `volume_cm3`
- `storage_conditions`
- `perishable`
- `quarantine_default`
- `photo` en option si le flux unitaire peut raisonnablement le supporter

## Contrat Metier

### Produit Inconnu Dans Pack

- un produit inconnu ne doit jamais creer implicitement un produit en base depuis `pack`
- la page `pack` ne sauvegarde rien avant la redirection volontaire vers `/scan/import/`
- si un POST arrive quand meme avec un `product_code` inconnu, la validation serveur continue a retourner `Produit introuvable.`

### Creation Produit Depuis Import

- les creations libres de categories et emplacements restent gerees par les services existants
- `brand` reste un champ texte libre, sans nouveau modele dedie
- si `sku` est vide, il reste auto genere par le modele `Product`
- la couleur de rack doit respecter une unicite par entrepot:
  - deux racks distincts d un meme entrepot ne peuvent pas partager la meme couleur
  - un rack existant peut conserver sa couleur actuelle

## Architecture Recommandee

### Overlay Pack

Ajouter un overlay specifique au pack en reutilisant les primitives visuelles `scan-choice-overlay` deja presentes sur d autres pages `scan`.

Le JS `setupPackLines()` devient le point d orchestration principal:

- detection d une valeur produit inconnue
- memorisation du champ concerne
- ouverture et fermeture de l overlay
- redirection vers l import ou remise a zero de la ligne selon l action choisie

### Contrat De Page Pack

`pack.html` doit exposer:

- l URL de destination vers `scan_import`
- le bouton `Creer un nouveau produit`
- l overlay de confirmation partage par creation et edition colis

Le backend `scan_pack` et `scan_carton_edit` restent peu modifies, car la logique principale est front.

### Carte Import Produits

Le backend `scan_import_handlers.py` doit enrichir les datasets de selection:

- marques distinctes
- structures de localisation suffisantes pour suggestions dependantes
- informations de rack connues par entrepot

Le JS `import_selectors.js` doit separer:

- autocompletion produit existant
- suggestions de marques
- suggestions de categories
- suggestions de localisation par niveau

La carte template doit exposer les nouveaux champs sans casser le flux d import fichier.

### Validation Rack Color

La regle `une couleur par rack dans un meme entrepot` doit vivre cote serveur, dans la logique d import produit et la logique de gestion des couleurs rack reutilisee par l import.

Le front peut aider, mais la source de verite doit rester serveur.

## Validation

### Pack

Regles:

- valeur produit vide: pas de pop up
- valeur produit connue: pas de pop up
- valeur produit inconnue: pop up affiche
- refus: le champ est vide et l utilisateur reste sur place
- acceptation: redirection vers `/scan/import/`
- POST serveur inconnu: `Produit introuvable.`

### Import Produits

Regles:

- les champs de suggestion gardent la saisie libre
- `rack_color` connu pour un rack existant s affiche automatiquement
- `rack_color` nouveau est refuse si deja utilise par un autre rack du meme entrepot
- `sku` vide reste acceptable et produit un SKU auto genere
- les nouveaux champs produit doivent suivre les validateurs existants du modele

## Tests

Tests minimum a couvrir:

- vues pack et edition colis:
  - bouton `Creer un nouveau produit` rendu
  - overlay de confirmation rendu avec l URL import
- JS pack:
  - detection produit inconnu
  - `Refuser` vide le champ et ferme l overlay
  - `Accepter` redirige vers l import
- backend pack:
  - l erreur `Produit introuvable.` reste presente
- import:
  - datasets de selecteurs enrichis
  - validation `rack_color` unique par entrepot
  - pre remplissage de couleur rack connue
  - auto generation SKU si vide
  - rendu et acceptation des nouveaux champs produit

## Impact Map

Verification de propagation requise sur:

- `templates/scan/pack.html`
- `wms/static/scan/scan.js`
- `wms/pack_handlers.py`
- `templates/scan/includes/imports_products_card.html`
- `wms/static/scan/import_selectors.js`
- `wms/scan_import_handlers.py`
- `wms/import_services_products.py`
- `wms/import_services_locations.py`
- tests `pack`, `scan import`, `views import`, et eventuellement docs repo reference si le contrat visible evolue
