# Page Gestion > Etiquette Produit (Legacy Scan) - Design

## Contexte

Aujourd'hui, l'admin Django (`wms.ProductAdmin`) permet deja:
- generation de QR code produit (`generate_qr_codes`),
- impression des etiquettes produit (`print_product_labels`),
- impression des QR produits (`print_product_qr_labels`).

Le besoin est d'exposer ces actions directement dans l'interface site, onglet `Gestion`, sans utiliser Next (en standby), tout en conservant strictement le comportement actuel:
- rack color selon `RackColor`/zone,
- layouts templates existants,
- generation QR manquants avant impression QR.

## Objectif

Ajouter une page `Gestion > Etiquette Produit` pour superuser uniquement, permettant:
- impression a l'unite (1 produit = 1 etiquette/1 QR),
- impression sur une selection de produits,
- impression sur tous les produits filtres,
- 3 actions: `Imprimer etiquettes`, `Imprimer QR`, `Imprimer les deux`.

Templates modifiables:
- conserver le flux actuel via `Gestion > Templates` (edition XLSX existante),
- ajouter des liens rapides vers les templates produit concernes.

## Decisions Validees

- Acces: superuser uniquement.
- Selection: option 1 (multi-selection avec recherche + tout selectionner).
- Actions: 2 boutons separes + un 3e bouton "les deux".
- Mode unitaire: option 1 (1 exemplaire par produit selectionne).
- Bouton "les deux": ouvre 2 impressions separees (etiquettes + QR), pas de page fusionnee.

## UX Cible

Page `scan/product-labels/` (nom de route a definir) dans l'onglet `Gestion`:
- barre de recherche (nom, SKU, barcode, EAN),
- tableau de produits avec checkbox,
- mode d'application:
  - `selection` (IDs coches),
  - `all_filtered` (tous les produits du filtre courant),
- boutons submit:
  - `print_labels`,
  - `print_qr`,
  - `print_both`.

Comportement:
- `print_labels` -> template `print/product_labels.html`.
- `print_qr` -> template `print/product_qr_labels.html`.
- `print_both` -> ouverture client de deux onglets/fenetres vers les deux actions.

## Architecture Technique

### 1. Factoriser la logique metier d'impression produit

Creer un service partage (ex: `wms/product_label_printing.py`) qui contient la logique actuellement dupliquee dans l'admin:
- resolution `RackColor` pour etiquettes produit,
- application layout override (`get_template_layout`) + fallback (`DEFAULT_LAYOUTS`),
- construction des pages via `build_label_pages`,
- generation QR manquants avant rendu QR,
- rendu vers templates print existants.

API cible du service:
- `render_product_labels_response(request, products)`
- `render_product_qr_labels_response(request, products)`

### 2. Reutilisation dans deux points d'entree

- `wms/admin.py` delegue ses actions `print_product_labels` / `print_product_qr_labels` au service.
- nouvelle vue scan `Gestion > Etiquette Produit` appelle le meme service.

Impact: alignement fonctionnel garanti entre admin et page scan.

### 3. Nouvelle vue scan (legacy)

Dans `wms/views_scan_admin.py`:
- nouvelle vue superuser-only (`scan_staff_required` + `_require_superuser`).
- GET: affiche liste filtree + selection courante.
- POST:
  - determine le set produits selon mode (`selection` ou `all_filtered`),
  - route vers action demandee (`print_labels` / `print_qr`),
  - retourne rendu print.

Pour `print_both`:
- la page principale reste une page de pilotage,
- un formulaire/JS ouvre deux requetes cibles (une labels, une QR) dans 2 onglets.

### 4. Navigation

Ajouter `Etiquette Produit` dans l'onglet `Gestion`:
- menu bootstrap (`templates/scan/base.html` partie nav desktop),
- menu legacy non-bootstrap (`templates/scan/base.html` partie nav scan-nav).

Etat `active` dedie (ex: `product_labels`).

### 5. Templates modifiables

La nouvelle page expose:
- lien vers `Gestion > Templates` (liste),
- liens directs vers edition des templates produit (`product_label` et `product_qr`).

Note: l'edition XLSX reste centralisee, sans nouveau moteur a ce stade.

## Donnees / Regles

- Base queryset: `Product` actifs par defaut (decision implementation), tri par nom.
- Recherche: `name`, `sku`, `barcode`, `ean`.
- Impression unitaire: aucune quantite custom, 1 contexte par produit.
- Absence de selection en mode `selection`: message warning + retour page.

## Tests

### Vues scan admin

Etendre `wms/tests/views/tests_views_scan_admin.py`:
- acces page produit etiquettes:
  - anonyme -> redirect login,
  - staff non superuser -> 403,
  - superuser -> 200.
- rendu de la page:
  - presence des 3 boutons,
  - presence des liens templates.
- impression labels/QR:
  - selection explicite,
  - mode all_filtered,
  - warning quand selection vide.

### Non regression admin

- verifier que les actions admin utilisent le service partage (ou conservent strictement le rendu attendu).

## Evolution Future

Le besoin futur (template unique avec QR + code barre + emplacement) est compatible avec cette architecture:
- il suffira d'ajouter un nouveau doc_type/layout,
- potentiellement un 4e bouton et/ou remplacement progressif du bouton `les deux`.
