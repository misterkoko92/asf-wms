# Planning Solver Parity Design

## Context
Le module `planning` de `asf-wms` existe deja sur la pile Django legacy:
- `wms/planning/snapshots.py` prepare les snapshots et la validation de run
- `wms/planning/rules.py` compile aujourd'hui un payload solveur minimal
- `wms/planning/solver.py` persiste `PlanningVersion` et `PlanningAssignment`, mais s'appuie encore sur un solveur `greedy_v1`
- `wms/views_planning.py` et `templates/planning/*` exposent deja le flux operateur de creation de run, generation, edition et publication

Le repo historique `../asf_scheduler/new_repo` reste la reference metier pour les arbitrages solveur. Les briques les plus structurantes sont:
- `scheduler/solver_ortools_common.py`
- `scheduler/solver_ortools.py`
- `scheduler/solver_ortools_v3.py`
- `scheduler/solver_router.py`
- les tests `tests/test_solver_contracts.py`, `tests/test_solver_v3_strict_capacity.py`, `tests/test_solver_v3_branches.py`, `tests/test_solver_ortools_common_branches.py`

Objectif valide: adapter ces regles et ce comportement dans `asf-wms` afin d'obtenir des resultats exploitables en production proches de l'outil planning historique, sans copier-coller brut et sans sortir de la pile Django legacy.

## Problem Statement
Le socle planning actuel dans `asf-wms` est operationnel, mais il reste loin de la parite solveur:
- le payload compile dans `wms/planning/rules.py` ne porte pas encore toutes les metadonnees utiles
- les contraintes metier sont sous-modelees
- `wms/planning/solver.py` optimise localement par glouton, pas par recherche sous contraintes
- les diagnostics d'ecart avec le legacy ne sont pas encore explicites

Si on enrichit seulement l'UI ou les exports avant cette phase, on risque de stabiliser des sorties qui ne sont pas encore bonnes metierement.

## Goal
Porter dans `asf-wms` un solveur OR-Tools et les regles associees, de maniere guidee par la parite metier avec le repo planning historique, tout en conservant le contrat `PlanningRun -> PlanningVersion -> PlanningAssignment` deja expose dans le WMS.

## Non-Goals
- reproduire integralement `Planning.xlsx` pendant cette phase
- automatiser les communications
- refondre les vues planning deja mergees
- ouvrir le scope Next/React
- "ameliorer" le solveur au-dela du legacy avant d'avoir prouve une parite suffisante

## Current State in `asf-wms`
### Points deja en place
- domaine planning persistant avec runs, snapshots, versions, affectations, artefacts et brouillons
- parametres destination importables via `PlanningParameterSet` et `PlanningDestinationRule`
- `max_colis_vol` porte par le domaine benevole
- source d'equivalence partagee pour les quantites equivalents
- bouton UI `Generer le planning` qui prepare le run puis appelle le solveur

### Limites a corriger
- `wms/planning/rules.py` ne modele que:
  - compatibilite destination/vol
  - `max_colis_vol`
  - disponibilite benevole par date
- `wms/planning/solver.py` marque `solver="greedy_v1"`
- le resultat solveur ne fournit pas encore les diagnostics riches attendus pour comparer les ecarts legacy vs WMS

## Legacy Oracle Strategy
Le repo `../asf_scheduler/new_repo` doit servir d'oracle fonctionnel, pas de base de merge brut.

Principe:
1. identifier les entrees solveur et contraintes qui pilotent effectivement les decisions du legacy
2. reproduire ces informations dans les snapshots et le payload WMS
3. adapter le solveur OR-Tools autour du contrat de persistance WMS
4. comparer les sorties sur un corpus de semaines de reference

Cette approche evite deux ecueils:
- merger une branche divergee avec du bruit non solveur
- reecrire un solveur "propre" mais metierement different

## Reference Corpus
La parite sera mesuree sur `3 a 5` semaines de reference maximum dans un premier temps.

Chaque semaine doit figer:
- expeditions candidates
- benevoles, contraintes et disponibilites
- vols
- parametres actifs (`ParamDest`, equivalence, donnees expeditrices, donnees benevoles)
- resultat brut du planning historique
- si possible la version finalement diffusee quand elle differe du solveur brut

Profils de semaine a couvrir:
- semaine nominale
- semaine tendue en capacite ou en benevoles
- semaine avec vols multi-stop ou arbitrages de routing
- semaine avec corrections manuelles significatives
- eventuellement une semaine avec republication entre jeudi et vendredi

## Parity Definition
La parite n'est pas definie uniquement par un score ou un nombre d'affectations.

Une semaine est consideree comme suffisamment paritaire si:
- les regles bloquantes sont respectees des deux cotes
- les expeditions affectees ou non affectees sont coherentes avec le legacy
- les affectations a benevole et vol sont majoritairement similaires ou les ecarts sont expliques
- les raisons d'absence d'affectation sont auditables

La comparaison doit donc couvrir:
- expedition -> affectee ou non
- expedition -> vol retenu
- expedition -> benevole retenu
- diagnostics des expeditions non affectees
- occupation des vols et usage benevoles

## Porting Strategy
### Phase 1: Parite des entrees solveur
But: alimenter le solveur WMS avec les memes informations utiles que le legacy.

A porter dans les snapshots ou le payload:
- equivalence unite ou carton
- capacite par vol
- `max_colis_par_vol` par destination
- frequence hebdomadaire par destination
- metadonnees vols utiles:
  - `routing`
  - `route_pos`
  - `origin_iata`
  - cle de vol physique
  - heure de depart exploitable
- disponibilites benevoles avec fenetres horaires
- priorites expedition ou destination necessaires a l'objectif

### Phase 2: Parite des contraintes
But: faire correspondre la definition d'une affectation valide.

Contraintes prioritaires:
- compatibilite destination/vol
- capacite equivalente par vol
- maximum de colis par vol
- limite `max_colis_vol` par benevole
- compatibilite temporelle benevole/vol
- exclusivite benevole sur un meme vol physique multi-stop
- contraintes de frequence destination si elles filtrent ou limitent les choix

### Phase 3: Parite de l'objectif d'optimisation
But: retrouver les memes arbitrages quand plusieurs solutions respectent les contraintes.

Elements attendus:
- meme ordre de priorites
- bonus ou malus comparables
- bonus de routing ou `route_pos` si utilise par le legacy
- diagnostics permettant d'expliquer pourquoi une solution differente a ete retenue

## Target Architecture
Le contrat applicatif WMS ne change pas:
- `prepare_run_inputs(run)` construit les snapshots
- `compile_solver_payload(run)` produit un payload solver-oriented
- `solve_run(run)` produit une `PlanningVersion` et des `PlanningAssignment`

Le coeur solveur evolue comme suit:
- `wms/planning/rules.py`
  - enrichit le payload et la compilation des candidats
  - expose des helpers de compatibilite reutilisables
- `wms/planning/solver.py`
  - remplace `greedy_v1` par un solveur CP-SAT OR-Tools
  - conserve la persistance existante
  - enrichit `run.solver_result`
- `wms/planning/snapshots.py`
  - veille a figer les informations necessaires a la reproductibilite
- `wms/tests/planning/tests_solver_contracts.py`
  - verrouille le contrat WMS
- nouveaux tests planning
  - verrouillent les contraintes portees du legacy

## Key Design Decisions
### 1. Garder le contrat WMS stable
Le solveur est un detail d'implementation. L'UI planning, la persistance et le versioning ne doivent pas etre recables pour cette phase.

### 2. Porter par morceaux, pas par merge brut
La branche historique `codex/planning-ortools-solver` sert de reference technique utile, mais ne doit pas etre mergee telle quelle sur `main`.

### 3. Comparer par cas de reference, pas a l'intuition
Toute contrainte portee doit etre rattachee a:
- un test unitaire ou integration cote WMS
- idealement un cas issu du repo historique ou du corpus reel

### 4. Distinguer "parite metier" et "parite implementation"
On cherche a conserver les decisions metier utiles du repo planning, pas a cloner sa structure Pandas ou ses details internes.

## Risks
### Risque: payload incomplet
Consequence: le solveur OR-Tools produit des solutions techniquement valides mais differente du legacy.
Mitigation: commencer par l'inventaire detaille des entrees solveur et verrouiller un mapping explicite.

### Risque: regression sur le contrat WMS
Consequence: l'UI planning ou les sorties versioning cassent.
Mitigation: conserver `solve_run(run)` et ses effets persistants, puis renforcer `tests_solver_contracts.py` et `tests_views_planning.py`.

### Risque: pseudo-parite sur jeux de donnees jouets seulement
Consequence: le solveur semble correct localement mais diverge sur semaines reelles.
Mitigation: introduire rapidement un corpus de semaines de reference et documenter les ecarts residuels.

### Risque: derive scope vers API vols ou Excel parity
Consequence: dispersion avant validation du coeur solveur.
Mitigation: limiter cette phase au solveur et aux donnees strictement necessaires a sa parite.

## Success Criteria
La phase solveur est consideree terminee quand:
- `wms/planning/solver.py` utilise OR-Tools au lieu de `greedy_v1`
- les contraintes principales du legacy sont reportees dans le moteur WMS
- un corpus de reference est rejouable ou, a defaut, des cas de comparaison representatifs sont implementes
- les sorties WMS vs planning legacy sont comparees et les ecarts significatifs sont documentes
- les tests planning et vues planning restent verts

## Deliverables
- un design doc de phase solveur
- un plan d'implementation detaille et executable
- une serie de commits concentres sur:
  - payload solveur
  - solveur CP-SAT
  - diagnostics et comparaison
  - documentation des ecarts

## Out of Scope Follow-Ups
Une fois la parite solveur suffisamment atteinte, les phases suivantes pourront traiter:
- le client API vols concret
- l'enrichissement de `Planning.xlsx`
- la recette operateur sur semaines reelles
- la reduction progressive des dependances Excel residuelles
