# Scan Listing Entry Flow Redesign - Design

## Contexte

Le ticket `scan listing import redesign` a deja sorti le listing de `Reception palette` vers une page dediee `Listing`, ajoute le pipeline PDF renforce, et introduit le cockpit des produits incomplets.

Le retour utilisateur valide maintenant un second palier UX:

- la page `Listing` doit s ouvrir sur un bloc d entree unique
- l operateur doit d abord choisir le type de fichier a traiter
- il peut rattacher le listing a une reception palette existante, ou preparer une reception a creer dans le meme flux
- les cartes `PDF`, `Excel`, `CSV` ne doivent plus embarquer les champs de reception devenus redondants
- la carte `Produits incomplets` doit rester visible en permanence en bas de page

Le travail reste sur la stack Django legacy `scan`, sans rouvrir le scope Next/React ni le scope traduction.

## Objectif

Transformer `Listing` en un flux en deux etages:

1. un ecran d entree simple pour choisir `CSV / Excel / PDF` et lier le flux a une reception palette existante ou a une reception a creer
2. un ecran de travail qui n affiche ensuite que la carte utile au type choisi, tout en conservant le cockpit `Produits incomplets`

## Decision Validee

La recommandation retenue est:

- suppression du bouton secondaire `Creer une reception` dans le bloc d entree
- conservation de l acces manuel a `Reception palette` via la sidebar `Reception`
- si aucune reception existante n est choisie, le flux `Listing` affiche une carte `Reception a creer`
- cette carte est editable directement dans `Listing`
- la vraie `Receipt` n est creee qu au moment de l import final

## Alternatives Ecartees

### Alternative A - conserver les champs de reception dans chaque carte type

Avantages:
- faible cout de migration

Inconvenients:
- repetition des memes champs dans `PDF`, `Excel`, `CSV`
- lisibilite mediocre
- confusion entre parametres de fichier et metadonnees de reception

Verdict:
- rejetee

### Alternative B - bouton `Creer une reception` qui sort vers `Reception palette`

Avantages:
- reutilise l ecran manuel existant

Inconvenients:
- casse la continuite du flux `Listing`
- cree un detour inutile pour l operateur
- devient redondant si `Reception a creer` est editable sur place

Verdict:
- rejetee

### Alternative C - mini ecran `Ouvrir` pour `Reception a creer`

Avantages:
- symetrie apparente avec `Produits incomplets`

Inconvenients:
- une seule reception brouillon par flux, donc pas de benefice reel
- ajoute une etape sans valeur

Verdict:
- rejetee

## Experience Utilisateur Cible

### Bloc D Entree

La page `Listing` doit toujours commencer par une carte `Parametrer l import`.

Champs:

- `Type de fichier`
  - obligatoire
  - rendu en `select`
  - tri A-Z par libelle rendu
  - valeurs: `CSV`, `Excel`, `PDF`
- `Lier a une reception`
  - optionnel
  - rendu en `select`
  - tri antichronologique
  - premiere option vide: `Creer une nouvelle reception`
  - libelle: `11/04/2026 - 3 palettes - Donateur A - Transporteur B`

Action:

- bouton principal `Valider`

Effet:

- memoriser le type choisi dans la session du flux listing
- memoriser l identifiant de reception selectionne si present
- afficher ensuite uniquement la carte correspondant au type choisi

### Cartes Type-Specifiques

Apres validation:

- si `PDF` est choisi: afficher la carte PDF uniquement
- si `Excel` est choisi: afficher la carte Excel uniquement
- si `CSV` est choisi: afficher la carte CSV uniquement

Les cartes type-specifiques ne doivent plus contenir:

- `Date reception`
- `Nombre de palettes`
- `Date demande transport`
- `Donateur`
- `Transporteur`

Les cartes gardent uniquement les champs utiles au type traite.

### Carte `Reception a creer`

Si aucune reception existante n est selectionnee dans le bloc d entree, afficher une carte `Reception a creer`.

La carte doit contenir:

- un statut visuel `Complete` ou `A completer`
- les champs minimum editables directement:
  - `Date reception`
  - `Nombre de palettes`
  - `Donateur`
  - `Transporteur`
- des options avancees repliables:
  - `Date demande transport`
  - `Observation`
  - `Non conforme`

Cette carte joue le role de brouillon de reception pour le flux listing. Elle ne cree rien en base tant que l import final n est pas confirme.

### Carte `Produits incomplets`

La carte `Produits incomplets` reste toujours visible en fin de page, quel que soit:

- le type choisi
- la presence ou non d une reception liee
- l etat du flux `analyse / mapping / review`

## Contrat Metier

### Reception Existante

Si une reception palette existante est selectionnee:

- tous les mouvements de l import final se rattachent a cette `Receipt`
- aucune nouvelle reception n est creee
- la carte `Reception a creer` n apparait pas

### Reception A Creer

Si aucune reception existante n est selectionnee:

- le flux conserve un brouillon de reception dans la session `pallet_listing_pending`
- ce brouillon doit contenir les memes metadonnees minimum que `ScanReceiptPalletForm`
- la creation de la vraie `Receipt` est differee jusqu a la confirmation finale de l import

Au moment de l import final:

- si le brouillon est complet, creer la `Receipt` palette puis rattacher l import
- si le brouillon est incomplet, bloquer l import final avec des erreurs de validation explicites

## Architecture Recommandee

### Etat D Entree Listing

Ajouter un petit etat d entree dedie, distinct du formulaire d upload:

- type de fichier choisi
- reception existante selectionnee ou vide
- resume de la reception selectionnee pour l affichage

Ce choix doit etre porte:

- dans la vue `scan_receive_listing`
- dans le contexte `build_receive_listing_context`
- dans la session `pallet_listing_pending` pour survivre aux etapes `analyse -> mapping -> review`

### Reutilisation Des Formulaires

Deux familles de formulaires sont utiles:

- un formulaire d entree `Listing` pour `type de fichier` + `reception existante`
- un formulaire de brouillon `Reception a creer`, base sur le contrat de `ScanReceiptPalletForm`

La logique d upload par type reste ensuite dans les handlers listing existants.

### Handlers

Le handler listing doit maintenant distinguer:

- `listing_configure`: valide l entree du flux
- `listing_upload`: traite le fichier pour le type choisi
- `listing_pdf_extract`: continue le flux PDF
- `listing_confirm_import`: importe les lignes et decide s il faut creer une nouvelle `Receipt`

### Construction Du Libelle Reception

Le `select` de receptions existantes doit etre alimente par une liste triee par:

- `received_on DESC`
- puis `created_at DESC`

Le libelle rendu doit reutiliser les donnees de `Receipt` deja presentes:

- date
- nombre de palettes
- donateur
- transporteur

## Validation

### Bloc D Entree

Regles:

- `Type de fichier` obligatoire
- `Lier a une reception` facultatif

### Carte `Reception a creer`

Regles:

- requise uniquement si aucune reception existante n est selectionnee
- champs obligatoires pour creation finale:
  - `Date reception`
  - `Nombre de palettes`
  - `Donateur`
  - `Transporteur`
- `Observation` devient obligatoire si `Non conforme` est coche, conformement au contrat actuel

### Import Final

Regles:

- impossible de confirmer l import final sans reception existante ou brouillon complet
- le message d erreur doit rester oriente action operateur

## Impact Attendu

Surfaces runtime:

- `templates/scan/receive_listing.html`
- `templates/scan/includes/receive_pallet_listing_upload_card.html` ou ses remplaçants plus specialises
- `wms/views_scan_receipts.py`
- `wms/receipt_listing_state.py`
- `wms/pallet_listing_handlers.py`
- `wms/forms.py`

Tests minimum a tenir a jour:

- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/views/tests_views_scan_receipts.py`
- `wms/tests/receipt/tests_receipt_listing.py`
- `wms/tests/pallet/tests_pallet_listing_handlers.py`

Documentation de reference a revoir pendant l implementation:

- `docs/repo-reference/04-shared-contracts.md`
- potentiellement `docs/repo-reference/02-key-flows-and-living-tests.md` si le contrat visible change sur la page `Listing`

## Critere De Sortie

Le redesign est considere termine quand:

- `Listing` s ouvre sur un bloc d entree unique
- le type de fichier est obligatoire avant affichage de la carte type-specifique
- le select de receptions existantes est optionnel et trie antichronologiquement
- l import peut utiliser une reception existante ou une reception brouillon a creer
- les cartes `PDF / Excel / CSV` n exposent plus les champs de reception
- la carte `Produits incomplets` reste visible en permanence
- les tests de vues et de handlers couvrent le nouveau contrat
