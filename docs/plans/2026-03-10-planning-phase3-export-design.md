# Planning Phase 3 Export Design

## Contexte

La phase 3 de recette planning a maintenant:
- un runbook operateur
- une grille d'observation
- deux notes de resultat pour les paliers A et B

Le blocage actuel n'est pas documentaire. Il est lie aux donnees:
- le worktree de recette n'a pas de base planning exploitable
- la base locale principale ne contient pas une vraie semaine rejouable pour `2026-03-09 -> 2026-03-15`

Le palier A doit pourtant etre execute sur une base isolee/copied avant toute recette sur PythonAnywhere reel.

Il faut donc construire une methode d'extraction de donnees de recette depuis PythonAnywhere.

## Decisions confirmees

Le cadrage valide avec l'utilisateur est le suivant:
- semaine cible: `2026-03-09 -> 2026-03-15`
- source: PythonAnywhere
- type de copie: export limite, pas dump brut complet
- confidentialite: pseudonymisation/anonymisation stable recommandee
- objectif: obtenir un jeu local rejouable pour le planning, pas une copie generale du WMS

## Objectif

Ajouter un outillage minimal permettant de produire, depuis PythonAnywhere, un jeu de recette planning:
- limite a une semaine donnee
- pseudonymise de maniere deterministe
- suffisamment complet pour etre recharge en local et rejouer la recette phase 3

## Probleme a resoudre

### 1. Un dump SQL brut serait trop large

Il embarquerait:
- trop de donnees hors scope
- trop de donnees personnelles
- trop de bruit pour une recette planning

### 2. Un simple `dumpdata` ad hoc serait trop fragile

Risques:
- oublier des dependances
- exporter des objets inutiles
- casser la reproductibilite entre deux extractions

### 3. Il faut garder la lisibilite operateur

Une anonymisation trop forte casserait:
- la lecture des brouillons
- la lecture du cockpit
- la comprehension du flux par l'operateur

Il faut donc viser une pseudonymisation stable:
- meme personne = meme alias dans tout le jeu

## Approches considerees

### Option 1: dumpdata cible + nettoyage manuel

Idee:
- faire un export Django manuel des modeles utiles
- retraiter ensuite le JSON

Avantages:
- rapide a bricoler

Inconvenients:
- peu fiable
- depend fortement de la personne qui l'execute
- difficile a rejouer proprement

### Option 2: extraction SQL ciblee

Idee:
- selectionner directement les lignes MySQL utiles

Avantages:
- controle fin du volume

Inconvenients:
- logique metier deplacee en SQL
- maintenance plus fragile
- plus difficile a tester dans le repo

### Option 3: commande Django dediee `planning_recipe_export`

Idee:
- utiliser les modeles Django et la logique applicative pour construire un export de recette coherent

Avantages:
- perimetre metier explicite
- pseudonymisation centralisee
- reexecution simple sur d'autres semaines
- testable dans `wms/tests/management/`

Inconvenients:
- demande un peu plus de structuration initiale

Recommendation:
- retenir l'option 3

## Design cible

### 1. Une commande dediee

Je recommande une commande de gestion:
- [`wms/management/commands/planning_recipe_export.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-phase3-recipe/wms/management/commands/planning_recipe_export.py)

Entrees minimales:
- `--week-start 2026-03-09`
- `--week-end 2026-03-15`
- `--output /tmp/planning_recipe_s11_2026.json`

Entrees optionnelles:
- `--parameter-set-id`
- `--parameter-set-name`
- `--include-flight-batches`
- `--no-anonymize`

Par defaut:
- anonymisation active
- export planning minimal

### 2. Format de sortie

Je recommande un JSON unique, structure et rechargeable, par exemple:
- meta
- selection
- fixtures

#### `meta`
- date de generation
- semaine cible
- mode anonymisation
- compte source ou environnement si utile

#### `selection`
- resume volumetrique:
  - nb vols
  - nb expeditions
  - nb benevoles
  - nb destinations
  - nb contacts pseudonymises

#### `fixtures`
- liste d'objets Django serialises ou structure equivalentement chargeable

Je recommande de viser un format compatible avec un futur chargement via une commande soeur plutot qu'un `loaddata` brut strict, afin de garder la souplesse sur l'anonymisation et les dependances.

### 3. Perimetre des objets exportes

Le jeu doit contenir uniquement ce qui est necessaire pour rejouer le planning:

#### a. Referentiels planning
- `PlanningParameterSet`
- `PlanningDestinationRule`
- `ShipmentUnitEquivalenceRule`

#### b. Donnees vols
- `Flight` de la semaine cible
- `FlightSourceBatch` seulement si utile a la trace et a la relecture

#### c. Donnees expeditions
- `Shipment` candidates a la semaine
- seulement les champs utiles au planning et a la lisibilite operateur
- les relations minimales necessaires vers destination / contacts

#### d. Donnees benevoles
- `VolunteerProfile`
- `VolunteerAvailability`
- `VolunteerConstraint`
- `VolunteerUnavailability` si elle joue un role sur la semaine

#### e. Referentiels metier relies
- `Destination`
- contacts/associations uniquement si necessaires a la logique planning ou a l'affichage operateur

Exclusion explicite:
- documents
- queues
- artefacts historiques
- versions planning historiques
- tout ce qui n'est pas necessaire a la semaine de recette

### 4. Strategie de pseudonymisation

Je recommande une pseudonymisation stable, pas une suppression brute.

Regles:
- benevole `Alice Martin` -> `VOL-001`
- contact expediteur `Association X` -> `SHIPPER-001`
- emails -> alias deterministes
- noms affiches -> alias lisibles

Conserver:
- dates
- vols
- destinations
- quantites
- contraintes
- parametres metier

But:
- garder la structure du planning lisible
- supprimer les donnees directement identifiantes

### 5. Determinisme

Le meme export relance sur le meme perimetre doit produire:
- le meme alias pour une meme personne
- le meme sous-ensemble logique

Je recommande d'utiliser une fonction de mapping stable en memoire d'export, basee sur les PK sources des objets retenus.

### 6. Recharge locale

Je recommande de prevoir des maintenant la cible de recharge, meme si l'implementation peut venir en deuxieme lot:
- soit une commande `planning_recipe_import`
- soit une commande `planning_recipe_load`

But:
- reconstruire une base locale de recette sans exposer les PK source originales dans des chemins fragiles

Le design d'export doit donc produire un fichier exploitable par une recharge applicative, pas seulement lisible par l'humain.

### 7. Verification attendue

Une fois exporte puis recharge en local, on doit pouvoir:
- creer un `PlanningRun`
- lancer `Generer le planning`
- publier `v1`
- generer les brouillons
- cloner `v2`
- lire le diff
- generer le workbook

Sans cela, l'export n'est pas considere comme bon.

## Risques et garde-fous

### Risque 1: export encore trop large

Garde-fou:
- selectionner les objets a partir de la semaine et des dependances planning strictes

### Risque 2: anonymisation qui casse la lecture operateur

Garde-fou:
- alias stables et lisibles

### Risque 3: export impossible a recharger

Garde-fou:
- penser l'export pour une commande de recharge, pas pour un simple archivage

## Definition du done

Cette sous-phase sera consideree terminee si:
- une commande `planning_recipe_export` existe
- elle exporte uniquement le sous-ensemble utile a la semaine
- elle pseudonymise de maniere stable
- elle produit un fichier rechargeable localement
- une doc courte d'usage existe

Elle ne sera pas consideree terminee si:
- on fait un dump trop large
- l'anonymisation n'est pas deterministe
- la recharge locale ne permet pas de rejouer le planning
