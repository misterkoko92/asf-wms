# Scan Assisted Product Suggestions - Design

## Contexte

Le flux `Listing` a deja ete recentre sur une page dediee, avec:

- un intake gate obligatoire `type de fichier + reception`
- un pipeline PDF renforce
- un cockpit `Produits incomplets` reutilise dans `Listing` et `MAJ Stock`
- une logique additive des quantites importees

Le retour utilisateur valide maintenant un second palier de productivite:

- neutraliser d autres erreurs courantes de formats PDF/CSV/Excel
- deduire des informations manquantes quand le signal est suffisamment fort
- assister a la fois le flux temporaire de revue `Listing` et le cockpit persistant `MAJ Stock`

Le travail reste sur la stack Django legacy `scan`, sans rouvrir le scope Next/React ni le scope traduction.

## Objectif

Ajouter une V1 de deduction assistee pour les produits incomplets avec la regle suivante:

- `EAN exact` peut etre applique automatiquement
- tout le reste reste en suggestion explicite
- les suggestions doivent etre visibles:
  - ligne par ligne
  - sous forme globale dans une carte `Suggestions detectees`
  - dans `Listing`
  - dans `MAJ Stock`

## Scope V1

### Champs cibles

La V1 couvre uniquement:

- `Marque`
- `Categorie`
- `TVA`
- `Emplacement`

Le champ `Nom` n est pas un champ de suggestion autonome. Il peut etre ajuste uniquement comme effet secondaire d une suggestion `Marque`, en retirant un prefixe de marque detecte et valide.

### Sources de deduction

La V1 combine:

- `Base`
  - produits deja connus
  - categories, TVA, emplacements deja en base
- `Batch`
  - repetitons detectees dans le fichier courant ou dans le lot affiche
- `Base + Batch`
  - croisement des deux signaux pour monter la confiance

### Hors scope V1

On ne traite pas dans cette version:

- `Perissable`
- `Quarantaine`
- `Conditions de stockage`
- fuzzy matching large a partir de noms proches
- auto-application hors `EAN exact`
- ecrasement d une valeur deja renseignee

## Decision Validee

La recommandation retenue est:

- moteur unique de suggestions partage entre `Listing` et `MAJ Stock`
- auto-match strict seulement pour `EAN exact`
- carte globale `Suggestions detectees` en haut de la zone de travail
- chaque suggestion globale ouvre un tableau compact des lignes concernees pour controle visuel rapide
- suggestions ligne par ligne conservees dans le tableau principal
- application des suggestions limitee aux champs vides en V1
- suggestions recalculees a l affichage, non persistees comme objets metier

## Alternatives Ecartees

### Alternative A - tout laisser en correction manuelle

Avantages:

- zero complexite supplementaire

Inconvenients:

- perte de temps sur les imports volumineux
- aucun effet de levier sur les produits incomplets repetitifs
- peu coherent avec la qualite de detection deja attendue sur les PDF

Verdict:

- rejetee

### Alternative B - auto-application de toutes les suggestions fortes

Avantages:

- gain de temps maximal

Inconvenients:

- trop de risque de propager une mauvaise hypothese
- faible explicabilite pour l operateur
- difficile a corriger apres coup sur des imports volumineux

Verdict:

- rejetee

### Alternative C - suggestions uniquement ligne par ligne

Avantages:

- implementation plus simple

Inconvenients:

- peu exploitable sur des lots de dizaines de lignes
- oblige a repeter les memes validations
- ne couvre pas le besoin de controle global rapide

Verdict:

- rejetee

## Durcissement Import A Integrer En Amont

La deduction assistee ne doit pas reposer sur des donnees bruitees. La V1 inclut donc un durcissement a faible risque du parsing.

### Normalisation de formats

Le parseur doit accepter au minimum:

- valeurs monetaires `3,75 EUR`, `3,75 EUR HT`, `3.75EUR`, `3,75EUR`
- pourcentages `20 %`, `5,5%`, `TVA 20%`
- quantites `x12`, `12 pcs`, `12 unites`, `12,00`
- EAN/barcodes avec espaces parasites ou separateurs legers

### Filtrage des lignes non produit

Le flux doit exclure des suggestions et, si possible, de l import:

- `TOTAL`
- `SOUS-TOTAL`
- `VALORISATION`
- `VALORISATION DU DON`
- `FRAIS DE TRANSPORT`
- `TRANSPORT`
- `PORT`
- `MANUTENTION`
- repetitions d en-tete entre pages

Quand une ligne est ecartee pour cette raison, le systeme doit preferer:

- un ignore explicite
- ou un avertissement non bloquant

plutot qu une erreur d import qui parasite tout le lot.

## Architecture Recommandee

### Module Dedie

Creer un module dedie, par exemple `wms/incomplete_product_suggestions.py`, pour separer:

- l analyse
- la construction des suggestions
- l application validee

des vues et templates.

### Couche Analyse

La couche analyse prend une liste de lignes candidates et renvoie:

- `auto_matches`
- `line_suggestions`
- `group_suggestions`

Chaque suggestion doit contenir au minimum:

- `field_name`
- `proposed_value`
- `confidence`
- `source`
- `reason`
- `row_keys` ou `product_ids`

### Reutilisation Sur Deux Surfaces

`Listing` et `MAJ Stock` doivent consommer le meme moteur, avec seulement une difference de source:

- `Listing`
  - lignes de revue d import encore en memoire/session
- `MAJ Stock`
  - produits incomplets deja persistes en base

### Separation Analyse / Application

La couche analyse:

- ne modifie pas la base
- ne persiste pas des objets de suggestion
- ne fait que produire un contexte testable

La couche application:

- applique un auto-match `EAN exact` dans la revue `Listing`
- ou remplit des champs vides apres validation utilisateur

Cette separation est obligatoire pour garder le systeme explicable et maintenable.

## UX Cible

### Listing

Dans `Listing`, apres mapping et avant l import final:

- afficher une carte `Suggestions detectees`
- garder le tableau principal de revue
- afficher les badges `Match auto EAN` sur les lignes auto-resolues

Chaque suggestion globale affiche:

- champ cible
- valeur proposee
- nombre de lignes concernees
- niveau de confiance `Forte` ou `Moyenne`
- source `Base`, `Batch`, `Base + Batch`
- actions:
  - `Voir les lignes`
  - `Appliquer aux lignes proposees`

Le panneau `Voir les lignes` ouvre un tableau compact avec:

- `checkbox`
- `EAN`
- `nom source`
- `valeur actuelle`
- `valeur proposee`
- `produit lie` si auto-match EAN

### MAJ Stock

Dans `MAJ Stock`, la meme carte `Suggestions detectees` apparait au-dessus du tableau `Produits incomplets`.

Les suggestions:

- se calculent sur les produits filtres par reception si le filtre est actif
- permettent une validation globale avec previsualisation
- n ecrivent en base qu apres action explicite

### Suggestions Ligne Par Ligne

Le tableau principal garde des suggestions unitaires pour les cas qui ne meritent pas une suggestion globale.

Ces suggestions doivent rester visibles meme si une carte globale existe, mais sans doubler inutilement la meme information.

## Regles De Deduction

### Pre-filtrage

Avant toute deduction:

- normaliser textes, nombres, EAN et quantites
- exclure lignes non produit et lignes quasi vides

### Auto-match EAN

L auto-match est autorise uniquement si:

- un `EAN` normalise est present
- un seul produit en base correspond exactement
- la ligne n est pas detectee comme non produit

Effets:

- `selection = product:<id>` par defaut dans `Listing`
- badge `Match auto EAN`
- ligne toujours modifiable manuellement

Pas d auto-match si:

- plusieurs produits partagent l EAN
- l EAN est manifestement invalide

### Suggestions Marque

Sources:

- `Base`
- `Batch`
- `Base + Batch`

Signal batch minimal:

- prefixe repete au debut de plusieurs noms produits

Conditions:

- au moins 3 lignes coherentes
- proposition du meme prefixe / de la meme marque

Effets:

- remplir `Marque` sur champs vides
- proposer `Nom = nom source sans prefixe marque` dans `Listing`

### Suggestions Categorie

Conditions:

- consensus fort depuis la base
- ou base + batch tres coherents

Effets:

- remplissage des champs de categorie vides uniquement

### Suggestions TVA

Conditions:

- consensus tres fort depuis la base
- regle plus stricte que `Marque`

Effets:

- suggestion uniquement, jamais auto
- champs vides uniquement

### Suggestions Emplacement

Conditions:

- produit exact connu
- ou consensus clair sur une famille homogene connue

Effets:

- remplissage des champs d emplacement vides uniquement

### Confiance

La V1 n expose que deux niveaux:

- `Forte`
- `Moyenne`

Si le signal est plus faible, aucune suggestion n est affichee.

## Persistance Et Effets Metier

### Listing

- les suggestions sont recalculees a partir de l etat courant de revue
- elles ne sont pas persistees en base
- l application d une suggestion ne met a jour que l etat de revue courant
- l import final continue de creer ou completer les produits comme aujourd hui

### MAJ Stock

- les suggestions sont recalculees a l affichage
- l application validee ecrit en base
- uniquement sur les produits selectionnes
- uniquement sur les champs encore vides en V1

## Tests Attendus

### Tests unitaires

- auto-match EAN unique
- pas d auto-match si doublon EAN
- detection de prefixe de marque repete
- calcul des suggestions globales `Marque`
- calcul des suggestions `Categorie`, `TVA`, `Emplacement` avec consensus
- exclusion des lignes non produit

### Tests Listing

- badge `Match auto EAN`
- rendu de la carte `Suggestions detectees`
- affichage du tableau de previsualisation des lignes concernees
- application d une suggestion globale sur sous-ensemble coche
- non ecrasement d une valeur deja renseignee

### Tests MAJ Stock

- rendu de la meme carte de suggestions
- recalcul sous filtre `reception`
- application en base sur les produits selectionnes
- pas d ecriture sur champs deja remplis

## Propagation Et Documentation

Ce changement modifie un contrat partage sur:

- `/scan/receive-listing/`
- `/scan/stock-update/`
- le cockpit partage `Produits incomplets`

Il devra mettre a jour dans le meme batch:

- `docs/repo-reference/02-key-flows-and-living-tests.md`
- `docs/repo-reference/04-shared-contracts.md`

## Recommandation Finale

La V1 doit etre utile mais conservative:

- peu de suggestions
- signal fort seulement
- auto seulement pour `EAN exact`
- validation explicite partout ailleurs

Si le moteur reste precis et explicable, il sera credible pour l operateur. Si on cherche a trop deviner trop tot, l outil perdra cette credibilite.
