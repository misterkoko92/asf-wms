# Planning Phase 3 Recipe Dataset Design

## Contexte

La phase 3 de recette planning a maintenant:
- un runbook operateur
- un export planning limite et pseudonymise
- une semaine cible definie: `2026-03-09 -> 2026-03-15`

Le blocage n'est plus technique sur le flux planning lui-meme. Il est lie a l'absence de donnees d'exploitation sur PythonAnywhere:
- pas de vraie expedition
- pas de vrai parameter set
- seulement des donnees `DEMO`

Pour tester la chaine de bout en bout avant d'avoir de vraies donnees metier, il faut creer un jeu de recette jetable, suffisamment riche pour couvrir les cas operateur critiques, puis pouvoir le purger proprement.

## Decisions confirmees

Le cadrage valide avec l'utilisateur est le suivant:
- utiliser un jeu **purement fictif mais realiste**
- le jeu doit etre **jetable**
- il faut une commande de creation et une commande de purge
- tout doit etre **namespaced** pour une suppression sure
- le scenario cible est `phase3-s11-recipe`

Cas metier a couvrir obligatoirement:
- trop de colis a planifier sur une destination
- pas assez de benevoles pour prendre tous les vols d'une destination
- au moins une contrainte `ParamDest` forte
- deux benevoles compatibles pour un meme vol, avec arbitrage observable
- un vol multi-troncon portant deux destinations candidates
- au moins une expedition non affectee
- au moins un ajustement manuel plausible apres generation

## Objectif

Ajouter un jeu de recette jetable `phase3-s11-recipe` qui permette de valider tout le flux planning dans `asf-wms`:
- creation du run
- generation
- relecture cockpit
- publication `v1`
- generation des brouillons
- creation d'une `v2`
- lecture du diff
- export workbook

Le jeu doit pouvoir etre cree rapidement sur PythonAnywhere puis purge sans ambigüite.

## Approches considerees

### Option 1: etendre `seed_planning_demo_data`

Idee:
- ajouter un mode plus riche dans la commande demo existante

Avantages:
- moins de nouveaux fichiers

Inconvenients:
- melange le seed de verification technique et le seed de recette operateur
- rend la commande demo plus lourde et plus confuse
- la purge deviendrait moins claire

### Option 2: creer des fixtures JSON manuelles

Idee:
- versionner un gros fixture de recette et le charger via `loaddata`

Avantages:
- reproductible

Inconvenients:
- fragile a maintenir
- peu lisible pour faire evoluer les cas metier
- pas de purge sure native

### Option 3: commandes dediees `seed_planning_recipe_data` et `purge_planning_recipe_data`

Idee:
- creer un scenario de recette applicatif, structure et purgeable

Avantages:
- separation claire entre demo technique et recette operateur
- scenario lisible et evolutif
- purge sure par namespace
- testable en Django

Inconvenients:
- un peu plus de structure initiale

Recommendation:
- retenir l'option 3

## Design cible

### 1. Deux commandes dediees

Je recommande:
- [`wms/management/commands/seed_planning_recipe_data.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-phase3-recipe/wms/management/commands/seed_planning_recipe_data.py)
- [`wms/management/commands/purge_planning_recipe_data.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-phase3-recipe/wms/management/commands/purge_planning_recipe_data.py)

#### `seed_planning_recipe_data`

Entrees minimales:
- `--scenario phase3-s11-recipe`
- `--solve` optionnel

Par defaut:
- semaine `2026-03-09 -> 2026-03-15`
- donnees namespaced avec le label `RECIPE phase3-s11`

#### `purge_planning_recipe_data`

Entrees minimales:
- `--scenario phase3-s11-recipe`

Par defaut:
- `dry-run`

Securite:
- suppression reelle uniquement avec `--yes`

### 2. Service applicatif unique

Je recommande de centraliser le scenario dans:
- [`wms/planning/recipe_dataset.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-phase3-recipe/wms/planning/recipe_dataset.py)

Ce module porterait:
- le namespace du scenario
- les specs des destinations, vols, benevoles et expeditions
- les helpers de creation
- les helpers de comptage/purge

Objectif:
- garder les commandes minces
- rendre les tests plus simples

### 3. Structure exacte du scenario `phase3-s11-recipe`

#### Destinations

- `NSI` Yaounde
  - `ParamDest`: vols autorises le jeudi uniquement
  - `weekly_frequency = 1`
  - `max_cartons_per_flight = 6`
- `DLA` Douala
  - `weekly_frequency = 2`
  - `max_cartons_per_flight = 5`
- `ABJ` Abidjan
  - `weekly_frequency = 1`
  - `max_cartons_per_flight = 8`

#### Vols

- mardi `AF945` `CDG-NSI`
  - doit etre ignore pour `NSI` a cause de `ParamDest`
- jeudi `AF982` `CDG-NSI-DLA`
  - vol multi-troncon
  - une seule destination doit etre retenue
  - resultat attendu: `NSI`
- samedi `AF968` `CDG-DLA` `09:00`
- samedi `AF969` `CDG-DLA` `11:00`
- samedi `AF704` `CDG-ABJ` `13:00`

#### Benevoles

- un benevole jeudi compatible `NSI`
- deux benevoles compatibles pour un meme vol `DLA`
- un benevole compatible uniquement avec le vol `DLA` matinal
- un benevole limite par `max_colis_vol`
- un benevole compatible `ABJ`

#### Expeditions

- `NSI`: expeditions qui ne peuvent partir que le jeudi
- `DLA`: assez de colis pour deux vols mais pas assez de benevoles pour tous les prendre
- `ABJ`: trop de colis pour un seul vol, avec au moins un non-affecte

### 4. Cas metier attendus

Le scenario doit produire de maniere observable:

#### a. Saturation capacitaire

Au moins une destination doit avoir plus de colis que la capacite de ses vols autorises.

#### b. Saturation benevole

Au moins une destination doit avoir assez de colis pour plusieurs vols mais pas assez de benevoles exploitables.

#### c. Contrainte `ParamDest`

`NSI` ne doit pas utiliser le vol du mardi, seulement le jeudi.

#### d. Tie-break benevole

Deux benevoles doivent etre compatibles pour un meme vol, avec un resultat stable du solveur et une explication attendue dans la recette.

#### e. Multi-troncon

Le vol `CDG-NSI-DLA` ne doit servir qu'une seule destination.

#### f. Non-affecte

Au moins une expedition doit rester non planifiee avec motif lisible.

#### g. Ajustement manuel

Le scenario doit inclure un cas plausible de modification manuelle apres generation.

### 5. Namespace et purge sure

Je recommande de marquer tous les objets crees avec le meme scenario:
- `PlanningParameterSet.name = "RECIPE phase3-s11-recipe"`
- `FlightSourceBatch.source = "recipe"`
- `FlightSourceBatch.file_name = "phase3-s11-recipe"`
- references expeditions: `RECIPE-PHASE3-S11-...`
- contacts et profils: prefixe `"[RECIPE phase3-s11]"`
- emails dedies `.recipe`

La purge doit d'abord calculer:
- runs
- versions
- assignments
- drafts
- artefacts
- vols et batchs
- expeditions et graphe cartons/produits
- benevoles
- contacts / profils / portal contacts
- regles planning du scenario

Puis afficher ces volumes avant toute suppression.

### 6. Garde-fous de purge

Je recommande:
- `dry-run` par defaut
- `--yes` obligatoire pour la suppression reelle
- aucune suppression d'objet non namespace
- sortie de commande lisible avec comptage par type

### 7. Verification attendue

Une fois le seed execute:
- un run peut etre genere
- le solveur produit une `v1`
- on observe bien au moins un non-affecte
- le cas `ParamDest` est visible
- le cas multi-troncon est visible
- le cas tie-break benevole est visible
- une `v2` avec ajustement manuel peut etre faite

Une fois la purge executee:
- le comptage redevient nul pour le scenario
- aucune donnee hors scenario n'est touchee

## Risques et garde-fous

### Risque 1: dataset trop artificiel

Garde-fou:
- le scenario doit rester petit mais contraint par de vrais cas operateur

### Risque 2: purge dangereuse

Garde-fou:
- namespace strict + `dry-run` + `--yes`

### Risque 3: seed trop proche du demo existant

Garde-fou:
- commandes separees
- structure scenario specifique a la recette operateur

## Definition du done

Le lot est termine si:
- `seed_planning_recipe_data` existe
- `purge_planning_recipe_data` existe
- le scenario `phase3-s11-recipe` couvre tous les cas metier valides avec l'utilisateur
- la purge est sure et testee
- la doc d'usage est en place

Le lot n'est pas termine si:
- le dataset doit encore etre bricole a la main
- la purge n'est pas fiable
- certains cas metier listes par l'utilisateur restent absents
