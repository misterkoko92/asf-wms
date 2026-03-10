# Planning Smoke Test Design

## Contexte

Le portage du planning dans `asf-wms` a deja livre les briques principales:
- domaine `planning` et versions
- solveur avec golden cases legacy `s10` et `s11`
- cockpit operateur sur [`/planning/versions/<id>/`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/templates/planning/version_detail.html)
- communications versionnees en cours de finalisation dans la PR [#24](https://github.com/misterkoko92/asf-wms/pull/24)

La couverture de tests est deja large, mais elle reste repartie entre:
- tests de seed
- tests de solveur
- tests de vues planning
- tests d'exports
- tests de communications

Il manque encore un garde-fou simple et lisible qui verifie que le flux principal planning tient de bout en bout, sans repasser par une recette manuelle complete.

## Objectif

Ajouter un smoke test Django deterministic qui rejoue le flux nominal principal du planning dans `asf-wms`:
- creation d'un jeu de donnees de demo
- resolution du run
- publication de la version
- generation des brouillons de communication
- generation de l'export workbook
- affichage du cockpit version

Ce test doit jouer le role de filet de securite bout en bout, pas de test de parite fine.

## Decisions confirmees

Le cadrage valide avec l'utilisateur est le suivant:
- priorite: ajouter maintenant un smoke test complet plutot que de nouveaux developpements fonctionnels
- type de test: `Django/CI` deterministe et rapide
- cible technique: un seul test de fumee principal, pas une nouvelle matrice E2E
- flux couvert:
  - `seed`
  - `solve`
  - `publish`
  - `generate drafts`
  - `export workbook`
  - `GET cockpit`
- assertions attendues:
  - une version existe
  - au moins une affectation existe
  - au moins un draft existe
  - au moins un export existe
  - la page cockpit repond en `200`
- exclusions explicites:
  - pas de verification de matching solveur exact
  - pas de verification detaillee du contenu des messages
  - pas de verification detaillee de la structure du workbook
  - pas de dependance a une API vols externe
- cible de branche recommandee: la branche de la PR [#24](https://github.com/misterkoko92/asf-wms/pull/24), car elle contient le flux communications le plus recent

## Probleme actuel

### 1. Pas de spec unique du flux nominal

Le flux principal existe deja dans le code, mais il n'existe pas encore de test lisible qui fasse comprendre en une seule lecture:
- comment un run planning est amene jusqu'a une version exploitable
- comment les communications et exports s'enchainent
- que le cockpit final s'affiche bien sur le resultat

### 2. La couverture actuelle est trop morcelee pour jouer un role de smoke test

Les tests existants couvrent bien des composants precis, mais ils ne repondent pas en une seule execution a la question:

> "Le workflow planning principal fonctionne-t-il encore apres une modification transversale ?"

### 3. Le prochain usage reel va dependre de ce flux

La prochaine phase produit vise a centraliser l'usage quotidien du planning dans `asf-wms`.

Avant de pousser d'autres evolutions, il faut un garde-fou court et stable sur le chemin nominal.

## Approches considerees

### Option 1: smoke test Django/CI deterministe

Idee:
- ecrire un test d'integration metier dans la suite Django existante
- utiliser les services planning et le seed de demo
- faire seulement des assertions structurelles

Avantages:
- rapide en CI
- deterministe
- pas de dependance externe
- proche du vrai code metier

Inconvenients:
- ne teste pas les clics UI eux-memes
- ne remplace pas une vraie recette operateur

### Option 2: smoke test UI complet

Idee:
- rejouer le flux entier via client HTTP ou navigateur, avec interactions proches de l'operateur

Avantages:
- plus proche du geste reel
- bon filet sur les regressions de templates/formulaires

Inconvenients:
- plus fragile
- plus lent
- plus couteux a maintenir

### Option 3: commande de smoke test

Idee:
- ajouter une commande de gestion type `planning_smoke_check`

Avantages:
- pratique pour l'ops
- facile a lancer a la main

Inconvenients:
- moins naturelle comme garde-fou de test
- risque de dupliquer des chemins deja couverts par Django tests

Recommendation:
- retenir l'option 1

## Design cible

### 1. Un test unique de fumee metier

Je recommande un seul fichier de test:
- [`wms/tests/planning/tests_smoke_planning_flow.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/wms/tests/planning/tests_smoke_planning_flow.py)

Il contiendra un test nominal principal qui joue le role de spec executable du workflow planning.

Le test sera volontairement court, pour rester lisible et stable.

### 2. Flux couvert par le test

Le test doit rejouer ce chemin:

1. lancer [`seed_planning_demo_data`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/wms/management/commands/seed_planning_demo_data.py) avec un scenario dedie, en mode `solve`
2. recuperer le `PlanningRun` cree pour ce scenario
3. verifier qu'il est en etat `solved`
4. recuperer la `PlanningVersion` creee par le solveur
5. publier cette version via le service de versioning ou la vue selon le niveau le plus robuste
6. generer les brouillons de communication pour cette version
7. generer l'export workbook de transition
8. charger la page [`/planning/versions/<id>/`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/templates/planning/version_detail.html) avec un client staff

### 3. Assertions a garder

Le smoke test doit verifier seulement des invariants structurels:
- le run existe
- une version existe pour ce run
- `version.assignments.exists()`
- `version.status == published` apres publication
- `version.communication_drafts.exists()`
- un artefact export est rattache a la version
- le cockpit version repond en `200`
- les objets crees dans le test pointent tous vers la meme version

Ces assertions suffisent pour jouer le role de garde-fou transversal sans redoubler les tests metier plus precis.

### 4. Assertions a exclure

Le smoke test ne doit pas verifier:
- le matching solveur exact
- l'ordre precis des affectations
- le texte exact des brouillons
- le detail des badges de communication
- la structure fine du workbook
- les chemins d'erreur metier

Ces sujets sont deja mieux couverts ailleurs:
- golden cases solveur
- tests outputs
- tests cockpit
- tests de vues planning

### 5. Isolation et determinisme

Le test doit rester autonome:
- pas d'appel API vols
- pas de reseau
- pas de dependance a des donnees preexistantes
- scenario seed dedie, unique et lisible

Je recommande de reposer sur le seed de demo existant, en utilisant un slug de scenario explicite comme `smoke-e2e`.

### 6. Niveau de surface recommande

Je recommande un test hybride "services + vue finale":
- services pour `seed`, `publish`, `generate drafts`, `export`
- client Django pour la page finale

Pourquoi:
- c'est plus stable qu'un test UI complet
- cela verifie quand meme la surface HTTP la plus importante pour l'operateur

### 7. Integration a la suite

Le test doit s'inserer dans:
- la suite planning standard
- les commandes de verification locales habituelles
- la CI existante sans dependance particuliere

Il ne doit pas demander de configuration additionnelle ni de credentiel externe.

## Risques et garde-fous

### Risque 1: test trop bavard, trop fragile

Garde-fou:
- limiter les assertions a des invariants structurels

### Risque 2: duplication avec les tests existants

Garde-fou:
- ne pas re-verifier la parite solveur ni les contenus detailles
- garder le smoke test comme spec du chemin nominal seulement

### Risque 3: couplage a l'etat transitoire du seed

Garde-fou:
- utiliser un scenario dedie
- eviter tout assert dependant d'identifiants exacts ou de textes longs

## Definition du done

La phase sera consideree terminee si:
- un fichier [`wms/tests/planning/tests_smoke_planning_flow.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/wms/tests/planning/tests_smoke_planning_flow.py) existe
- il contient un smoke test principal deterministe
- ce test couvre `seed -> solve -> publish -> drafts -> export -> cockpit`
- il passe dans la suite Django standard sans reseau
- il est documente comme garde-fou fonctionnel et non comme test de parite

La phase ne sera pas consideree terminee si:
- le smoke test depend d'une API externe
- il essaye de revalider toute la logique solveur
- il se contente d'un test purement unitaire
- il ne couvre pas la publication et la generation de brouillons
