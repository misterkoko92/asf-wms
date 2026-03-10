# Planning Operator Cockpit Design

## Contexte

Le module `planning` de `asf-wms` couvre deja:
- la creation des runs
- la preparation des snapshots
- le solveur
- l'edition manuelle de base
- le versioning
- les brouillons de communication
- les exports `Planning.xlsx`
- les statistiques minimales

Mais la vue [`/planning/versions/<id>/`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-operator-cockpit/templates/planning/version_detail.html) reste encore une page technique:
- table plate d'affectations
- stats sommaires
- exports minimaux
- brouillons listes sans priorisation operateur

L'objectif produit valide pour cette phase est de faire de `asf-wms` le cockpit operateur principal, et de releguer `Planning.xlsx` au rang de sortie transitoire.

Decisions produit confirmees pendant le cadrage:
- `asf-wms` doit devenir le poste operateur principal du planning
- `Planning.xlsx` reste un export de transition, pas l'outil maitre
- la page `/planning/versions/<id>/` devient le cockpit central
- l'organisation cible reste une seule page structuree en blocs
- la vue principale du planning est orientee `vol`
- les ajustements manuels restent simples et robustes
- les communications restent preparees dans `asf-wms`, mais l'envoi reste manuel
- le diff entre versions est prioritaire pour savoir quoi rediffuser

## Objectif

Transformer [`/planning/versions/<id>/`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-operator-cockpit/templates/planning/version_detail.html) en vrai cockpit operateur, capable de couvrir la lecture, les ajustements, les explications des non-affectes, la preparation des communications, les stats d'exploitation, les exports de transition et l'historique des versions sans repasser par Excel.

## Approches considerees

### Option 1: garder la page actuelle et enrichir seulement l'export Excel

Avantages:
- plus rapide
- peu de changements UI

Inconvenients:
- ne centralise pas vraiment le travail dans `asf-wms`
- laisse Excel comme support principal implicite
- ne traite pas le besoin de lecture, diff et communication dans le web

### Option 2: multiplier les ecrans specialises

Avantages:
- separation claire par fonction
- potentiellement plus evolutif a long terme

Inconvenients:
- plus de navigation
- plus de charge cognitive pour les operateurs
- trop lourd pour cette phase de convergence

### Option 3: cockpit unique structure en blocs

Avantages:
- colle au besoin de centralisation
- garde un flux operateur simple
- permet de conserver Excel comme sortie sans lui laisser le role principal

Inconvenients:
- demande un vrai travail de composition de vue
- risque de page trop dense si elle n'est pas bien structuree

Recommendation:
- retenir l'option 3

## Design cible

### 1. Page centrale de version

La page [`/planning/versions/<id>/`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-operator-cockpit/templates/planning/version_detail.html) devient l'ecran principal operateur.

Elle s'organise autour de deux niveaux:

1. un en-tete d'exploitation
2. des blocs metier lisibles sur la meme page

L'en-tete d'exploitation doit afficher:
- semaine
- numero de version
- statut
- source vols utilisee
- auteur
- date de generation
- date de publication
- actions principales

Les actions principales restent:
- publier la version
- creer une nouvelle version a partir de la version courante
- regenerer les brouillons de communication
- exporter `Planning.xlsx`

### 2. Bloc Planning

Le bloc `Planning` devient la vue metier principale.

Le regroupement par defaut est:
- par date
- puis par vol

Chaque carte ou groupe de vol doit presenter:
- numero de vol
- destination
- heure
- capacite
- benevole affecte
- expeditions / BE affectes
- charge consommee
- alertes utiles

Des filtres simples sont acceptes:
- par benevole
- par destination

Mais la vue principale reste `vol`.

Les ajustements manuels couverts dans cette phase sont limites a:
- reaffecter une expedition a un autre vol compatible
- changer le benevole d'un vol parmi les benevoles compatibles
- retirer une affectation
- ajouter une affectation manuelle compatible

Ne sont pas cibles dans cette phase:
- drag and drop complexe
- edition multi-vol avancee
- verrous solveur

### 3. Bloc Non affectes

Le bloc `Non affectes` doit rendre visible ce qui reste hors planning.

Chaque ligne doit montrer:
- reference expedition / BE
- destination
- priorite
- quantite
- motif principal de non-affectation

Le but n'est pas encore d'expliquer exhaustivement toute la matrice solveur, mais de donner une raison exploitable par l'operateur:
- pas de vol compatible
- pas de benevole compatible
- capacite insuffisante
- non selectionne par arbitrage solveur

### 4. Bloc Communications

Le bloc `Communications` reste version-centrique.

Il doit permettre:
- de regenerer les brouillons pour la version courante
- de les grouper par canal et destinataire
- de les modifier avant diffusion
- d'indiquer, quand la version a un parent, quels brouillons concernent des changements depuis la version precedente

L'envoi reste hors scope:
- `asf-wms` prepare
- l'operateur diffuse manuellement

### 5. Bloc Stats

Le bloc `Stats` reste simple et operationnel.

Premiers indicateurs cibles:
- nombre d'affectations
- nombre de vols utilises
- nombre de benevoles mobilises
- total colis / equivalent
- expeditions non affectees
- repartition par destination
- charge par benevole
- ajustements manuels

### 6. Bloc Exports

Le bloc `Exports` conserve `Planning.xlsx` comme sortie de transition.

L'export doit devenir plus proche du legacy, sans chercher la reproduction 1:1 du workbook historique.

Priorites:
- structure plus exploitable pour lecture et diffusion
- rattachement explicite a la version
- historisation des artefacts generes

Les integrations desktop historiques ne sont pas reprises telles quelles.

### 7. Bloc Historique et diff

Le bloc `Historique des versions` doit rendre visibles:
- la version courante
- la version parente si elle existe
- le motif de changement
- la date
- l'auteur

Le diff rapide doit montrer:
- expeditions ajoutees
- expeditions retirees
- expeditions deplacees
- changement de benevole
- changements de vol

Le lien vers la page diff detaillee reste utile, mais la page cockpit doit deja afficher un resume exploitable.

## Architecture recommandee

### Presenter / view-model dedie

Je recommande de ne pas continuer a enrichir [`wms/views_planning.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-operator-cockpit/wms/views_planning.py) avec des calculs de presentation bruts.

La bonne structure pour cette phase est:
- conserver la vue Django comme orchestrateur HTTP
- ajouter un service de presentation dedie dans `wms/planning/`
- y construire les blocs UI:
  - en-tete
  - planning par vol
  - non affectes
  - stats
  - sorties
  - historique / diff resume

Cela permet:
- de tester la composition de la page sans surcharger la vue
- de garder les templates lisibles
- de faire evoluer le cockpit sans melanger logique metier et logique d'affichage

### Templates

Je recommande:
- garder `templates/planning/version_detail.html` comme template principal
- extraire des partiels pour les blocs si la page grossit

Exemples possibles:
- `templates/planning/_version_header.html`
- `templates/planning/_version_planning_block.html`
- `templates/planning/_version_unassigned_block.html`
- `templates/planning/_version_communications_block.html`
- `templates/planning/_version_stats_block.html`
- `templates/planning/_version_exports_block.html`
- `templates/planning/_version_history_block.html`

Ce decoupage reste compatible avec le stack Django legacy et avec la politique de pause Next/React.

## Risques et garde-fous

### Risque 1: page trop dense

Garde-fou:
- blocs clairement separes
- hierarchie visuelle forte
- prioriser la lecture rapide plutot que l'exhaustivite brute

### Risque 2: edition manuelle fragile

Garde-fou:
- limiter l'edition aux actions essentielles
- ne pas embarquer de drag and drop ni de logique solveur verrouillee

### Risque 3: confusion entre run et version

Garde-fou:
- toutes les sorties operateur sont rattachees a `PlanningVersion`
- la page expose clairement run, version, parent et statut

### Risque 4: Excel reste de fait l'outil principal

Garde-fou:
- le cockpit doit couvrir lecture, ajustement, diff, communications et stats
- Excel ne reste qu'un artefact d'export

## Verification attendue

La phase sera consideree validee si:
- `/planning/versions/<id>/` devient l'ecran principal operateur
- les affectations sont lisibles par vol
- les non-affectes sont visibles avec motif
- les communications sont regenerables et modifiables par version
- les stats d'exploitation de base sont visibles dans la page
- `Planning.xlsx` devient un export transitoire plus utile
- le diff entre versions est visible sans quitter le cockpit

## Hors scope

Cette phase ne vise pas:
- une reproduction exacte de tous les onglets du workbook legacy
- l'automatisation d'envoi email ou WhatsApp
- un drag and drop riche
- des verrous solveur
- la reprise des integrations desktop Outlook / AppleScript / COM
