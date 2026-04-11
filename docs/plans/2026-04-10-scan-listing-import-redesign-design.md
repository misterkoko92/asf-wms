# Scan Listing Import Redesign - Design

## Contexte

Le flux listing vit aujourd hui dans `templates/scan/receive_pallet.html` et melange deux usages:
- la creation manuelle de `Reception palette`
- l import de listing avec etapes `upload -> mapping -> review -> confirmation`

La logique d import est deja relativement isolee dans:
- `wms/receipt_pallet_state.py`
- `wms/pallet_listing_handlers.py`
- `wms/pallet_listing.py`
- `wms/import_utils.py`
- `wms/import_services_pallet.py`

Le besoin valide est de sortir le listing dans une vraie surface `scan` du bloc `Reception`, avec un focus fort sur le PDF qui sera de loin la source principale. Le flux doit aussi accepter des listings incomplets, ou seules des informations partielles produit sont disponibles, typiquement `EAN`, `nom`, `quantite`.

Le travail doit rester sur la stack Django legacy `scan`, sans rouvrir le scope Next/React ni le scope traduction.

## Objectif

Ajouter une nouvelle page `Listing` dans le groupe `Reception`, garder un raccourci depuis `Reception palette`, preserver les logiques actuelles Excel/CSV, renforcer fortement le pipeline PDF, et permettre l import avec creation de produits incomplets suivie d un cockpit de completion unitaire et en masse.

## Decisions Validees

- la nouvelle entree vit dans le groupe `Reception`
- `Reception palette` garde un lien/raccourci vers `Listing`
- `Listing` devient le point d entree unique pour `PDF`, `Excel`, `CSV`
- Excel et CSV conservent le pipeline actuel autant que possible
- le PDF a un flux dedie avec etape d analyse avant mapping
- l import ne doit plus bloquer quand toutes les informations produit ne sont pas disponibles
- les produits crees a partir de donnees partielles doivent etre traces comme `incomplets`
- l absence d emplacement final ne doit plus bloquer la reception; un emplacement tampon de reception doit exister
- les produits incomplets doivent etre pilotables depuis un tableau recapitulatif avec edition unitaire et actions en masse
- les champs identifiants (`nom`, `SKU`, `EAN`, `barcode`) doivent etre proteges par des garde-fous plus stricts dans les actions en masse

## Perimetre Du Premier Slice

Le premier slice doit livrer un flux complet et exploitable:
- nouvelle page `scan` `Listing`
- nouvelle entree sidebar `Reception > Listing`
- raccourci depuis `Reception palette`
- trois cartes distinctes `PDF`, `Excel`, `CSV`
- etapes `analyse -> mapping -> review -> confirmation` sur la nouvelle page
- pipeline PDF renforce sans OCR serveur obligatoire dans ce premier slice
- creation et reception de produits incomplets
- emplacement tampon automatique quand l emplacement final manque
- tableau des produits incomplets avec bouton `Ouvrir`
- actions en masse sur les champs partages

Hors scope confirme du premier slice:
- migration Next/React
- travail FR/EN specifique
- OCR serveur complet
- resolution automatique de PDF image par OCR lourd cote backend
- miroir API `api/v1/ui/`
- moteur de fusion produit dedupe automatique

## Experience Utilisateur

### Placement

Nouvelle entree dans `templates/scan/includes/scan_sidebar_navigation.html`:
- groupe: `Reception`
- ordre recommande: `Reception palette`, `Listing`, `Reception association`
- `active` dedie pour que le groupe `Reception` reste ouvert

Depuis `Reception palette`, ajouter un bouton tertiaire visible menant a `Listing`.

### Structure De La Page Listing

1. Carte `PDF`
- carte mise en avant visuellement
- upload du fichier
- metadonnees reception (date, donateur, transporteur, nombre de palettes, date demande transport)
- etape d analyse
- choix des pages apres diagnostic

2. Carte `Excel`
- conservation du flux actuel
- choix de feuille
- choix de ligne de titres

3. Carte `CSV`
- conservation du flux actuel
- mapping puis review

4. Zone `Produits incomplets a completer`
- tableau recapitulatif
- filtres simples
- actions en masse

### Etats De Review Listing

Chaque ligne doit exposer un statut clair:
- `match exact`
- `match a confirmer`
- `nouveau produit incomplet`
- `emplacement manquant`

Le review doit rester actionnable: l operateur peut confirmer l import d une ligne meme si tous les attributs produit ne sont pas encore connus.

## Produits Incomplets

### Regles De Matching

Ordre de matching recommande:
1. `EAN / barcode`
2. `SKU`
3. `nom + marque`
4. `nom seul`, mais jamais en auto-validation silencieuse si plusieurs candidats existent

La logique existante dans `wms/pallet_listing.py` doit etre etendue pour refleter cet ordre et ne plus dependre principalement de `nom + marque`.

### Modele De Donnees

Ajouter un marqueur persistant simple sur `Product`, recommande sous la forme:
- `is_incomplete`

Ce marqueur doit permettre:
- de retrouver rapidement les produits issus de listings incomplets
- de piloter la completion dans une file dediee
- d eviter qu un produit partiel soit traite comme un produit reference complet

Les produits minimaux crees depuis un listing doivent pouvoir exister avec:
- `name` obligatoire
- `ean` ou `barcode` si disponible
- `brand` si disponible
- `quantity` via la reception

Les champs absents ne doivent pas bloquer la creation ni la reception:
- marque
- categorie
- dimensions
- poids
- volume
- conditions de stockage
- emplacement final

### Emplacement Tampon

Si aucun emplacement final n est resolu ni sur la ligne ni sur le produit, la reception doit utiliser un emplacement tampon dedie.

Le comportement cible:
- l import palette ne bloque plus sur l absence d emplacement final
- la ligne de reception entre en stock sur une localisation tampon de reception
- la completion ulterieure du produit ou du rangement reste possible sans perdre la trace du mouvement initial

## Cockpit Des Produits Incomplets

### Tableau Recapitulatif

La nouvelle page `Listing` doit afficher un tableau des produits incomplets existants.

Colonnes recommandees:
- selection
- produit
- EAN / barcode
- SKU
- marque
- categorie
- emplacement par defaut
- date de creation
- origine recente / reference de reception si disponible
- champs manquants
- statut
- action `Ouvrir`

### Edition Unitaire

Le bouton `Ouvrir` doit mener vers une vraie fiche de completion cote `scan`, pre-remplie, et non vers un simple renvoi brut vers l admin Django.

Objectif:
- corriger un produit incomplet un par un
- renseigner les champs manquants
- sortir le produit du statut incomplet quand le minimum attendu est satisfait

### Actions En Masse

Le cockpit doit proposer une barre d actions activee par les cases a cocher.

Deux familles d actions:

1. `Definir / vider un champ partage`
- categorie
- marque
- emplacement par defaut
- conditions de stockage
- perissable
- quarantaine
- notes
- dimensions
- poids
- volume

2. `Corriger des champs identifiants avec validation specifique`
- nom
- SKU
- EAN
- barcode

Les champs identifiants ne doivent jamais recevoir aveuglement une valeur commune sans garde-fou, en particulier pour `EAN` et `barcode`.

## Flux PDF Renforce

### Position Produit

Le PDF n est pas un format secondaire. C est la voie critique du chantier.

Le design doit donc privilegier:
- une carte `PDF` mise en avant
- un pipeline dedie
- des diagnostics precoces
- une architecture extensible vers l OCR

### Etape D Analyse

Avant tout mapping, le flux PDF doit produire un diagnostic structure:
- nombre total de pages
- pages avec texte detecte
- pages vides ou suspectes
- mode estime `texte`, `mixte`, `image`
- apercu court du texte extrait par page

L objectif est de supprimer les imports PDF en boite noire.

### Choix Des Pages

La selection des pages doit etre plus ergonomique que le flux actuel:
- `toutes`
- `plage`
- extension future possible vers `pages detectees`

L operateur doit comprendre ce qui sera traite avant d entrer dans le mapping.

### Pipeline D Extraction

Strategie recommande en couches:
1. extraction de table native `pdfplumber`
2. extraction texte page par page
3. reconstruction tabulaire heuristique a partir du texte
4. fallback permissif pour laisser l operateur poursuivre si le PDF reste exploitable partiellement
5. si rien n est exploitable: message explicite `PDF scanne / image non exploitable automatiquement`

### Architecture OCR-Ready

Le premier slice ne depend pas d un OCR serveur complet, mais le code doit etre structure pour l ajouter proprement plus tard.

Le design doit separer:
- l analyse PDF
- les strategies d extraction
- le diagnostic page par page
- la transformation en tableau

Ainsi, un futur palier OCR pourra cibler uniquement les pages `image` sans re-ecrire tout le flux.

## Approche Technique

### Routing Et Views

Ajouter une nouvelle route `scan` recommandee:
- `scan/receive-listing/`
- nom recommande: `scan_receive_listing`

Le cablage devra aussi mettre a jour:
- `wms/scan_urls.py`
- `wms/views_scan_receipts.py`
- `wms/views_scan.py`
- `wms/views.py`

`scan_receive_pallet` doit etre simplifiee pour ne plus heberger le workflow listing complet, tout en gardant son raccourci.

### State Et Handlers

Le state listing actuellement nomme autour de `receive_pallet` doit devenir autonome.

Recommendation:
- extraire un state builder dedie a la page `Listing`
- decoupler les redirects `listing_*` actuellement hardcodes vers `scan_receive_pallet`
- enrichir la session pending avec le diagnostic PDF et les metadonnees d analyse

### Templates

Nouveaux templates recommandes:
- `templates/scan/receive_listing.html`
- `templates/scan/includes/receive_listing_pdf_card.html`
- `templates/scan/includes/receive_listing_excel_card.html`
- `templates/scan/includes/receive_listing_csv_card.html`
- `templates/scan/includes/receive_listing_mapping_card.html`
- `templates/scan/includes/receive_listing_review_card.html`
- `templates/scan/includes/receive_listing_incomplete_products_card.html`

La page doit rester dans les primitives `scan/bootstrap` existantes.

### Import Services

`wms/import_services_pallet.py` doit accepter:
- creation de produit minimal
- fallback vers emplacement tampon
- nettoyage plus riche des erreurs de ligne

`wms/import_services_products.py` doit fournir le socle de creation minimale et de completion sans forcer un produit complet des la premiere importation.

### Bulk Edit

Le bulk edit doit rester explicite et securise:
- action choisie
- valeur saisie
- validation par champ
- compte rendu du nombre de produits modifies

Pour les champs identifiants, la validation doit verifier les collisions et les incoherences avant application.

## Risques Et Garde-Fous

- risque de surcomplexite sur la page: reduit par trois cartes d import tres explicites et un cockpit separe en dessous
- risque de regressions Excel/CSV: limite en reemployant le pipeline existant au maximum
- risque de faux positifs PDF: reduit par l etape d analyse et les statuts de confiance
- risque de pollution du referentiel produit: reduit par `is_incomplete`, la file de completion, et les garde-fous sur les identifiants
- risque de blocage operationnel sur l emplacement: reduit par l emplacement tampon
- risque de bulk edit dangereux: reduit par la separation entre champs partages et champs identifiants

## Tests Cibles

- tests unitaires de diagnostic et extraction PDF dans `wms/tests/imports/tests_import_utils.py`
- tests handlers listing pour les nouveaux etats `analyse -> mapping -> review`
- tests metier pour:
  - matching par `EAN / barcode`
  - creation de produit incomplet
  - fallback emplacement tampon
  - completion unitaire
  - actions en masse
- tests de vue/UI pour:
  - la nouvelle route `Listing`
  - le lien sidebar `Reception > Listing`
  - le raccourci depuis `Reception palette`
  - les cartes `PDF`, `Excel`, `CSV`
  - les marqueurs du cockpit produits incomplets

## Impact Map

Changement sur une page `scan`:
- modifier `wms/scan_urls.py`
- modifier la vue staff `scan`
- ajouter un template `templates/scan/`
- ajouter ou etendre des handlers `wms/receipt_*` et `wms/pallet_listing_*`
- ajouter des tests `wms/tests/views/`, `wms/tests/pallet/`, `wms/tests/imports/`

Changement sur un contrat de navigation laterale scan:
- mettre a jour `templates/scan/includes/scan_sidebar_navigation.html`
- mettre a jour `docs/repo-reference/04-shared-contracts.md`
- mettre a jour les tests bootstrap scan

Changement sur un flux reception:
- re-verifier `docs/repo-reference/02-key-flows-and-living-tests.md`
- verifier si `docs/mvp_spec.md` doit mentionner `Listing` comme nouvelle surface operateur

Hors scope confirme:
- pas de page Next/React
- pas de travail FR/EN specifique
- pas de nouveau contrat API
