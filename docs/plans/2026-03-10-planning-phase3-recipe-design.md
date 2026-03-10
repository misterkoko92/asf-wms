# Planning Phase 3 Recipe Design

## Contexte

Le module planning dans `asf-wms` a maintenant franchi les etapes structurantes:
- domaine `planning` natif
- solveur OR-Tools avec golden cases legacy stricts `s10` et `s11`
- cockpit operateur sur [`/planning/versions/<id>/`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-phase3-recipe/templates/planning/version_detail.html)
- brouillons de communication versionnes
- export workbook de transition
- smoke test fonctionnel bout en bout sur le flux nominal

Le prochain besoin n'est plus principalement un ajout de brique technique. Le vrai enjeu devient:

> verifier qu'un operateur peut executer un cycle planning reel dans `asf-wms`, sur une vraie semaine, avec les bons garde-fous et une sortie exploitable.

Cette phase 3 doit donc transformer l'etat actuel du projet en une recette reelle, structuree et evaluable.

## Decisions confirmees

Le cadrage utilisateur a valide les points suivants:
- objectif: centraliser l'usage quotidien du planning dans `asf-wms`
- ordre de priorite:
  1. communications operateur
  2. recette reelle
  3. parite Excel supplementaire si necessaire
- approche de recette:
  - d'abord base isolee/copied
  - ensuite PythonAnywhere avec vraies donnees
- pas d'envoi reel des communications dans ce premier passage
- la recette doit etre documentee et executable, pas seulement theorique
- la phase doit se conclure par une decision explicite sur l'etat d'exploitation du module

## Objectif

Concevoir et livrer un protocole de recette operateur planning de bout en bout, utilisable:
- une premiere fois sur une base isolee
- une deuxieme fois sur PythonAnywhere avec vraies donnees

Ce protocole doit permettre de dire clairement si le module est:
- pret pour usage encadre
- pret avec reserves
- ou pas encore pret

## Probleme a resoudre

### 1. Le module est techniquement avance, mais pas encore "preuve d'exploitation"

Les tests et le smoke flow montrent que le chemin nominal fonctionne. En revanche, ils ne suffisent pas a etablir:
- que la sequence operateur est confortable
- que les ecrans donnent assez d'information pour decider
- que les sorties sont exploitables dans le contexte reel

### 2. Le passage direct a la vraie base serait trop abrupt

Une recette en production reelle sans palier preparatoire ferait courir trois risques:
- decouvrir un trou de workflow trop tard
- brouiller les donnees d'exploitation
- perdre du temps a improviser la methode pendant la recette

### 3. Il manque une decision de readiness explicite

Le projet a besoin d'un livrable de phase qui ne soit pas seulement "ca a l'air de marcher", mais une conclusion operationalisable:
- go usage encadre
- go avec reserves
- no-go

## Approches considerees

### Option 1: checklist manuelle seule

Idee:
- rediger une liste de controles et laisser l'operateur l'executer

Avantages:
- rapide a produire
- tres peu de code ou de docs supplementaires

Inconvenients:
- execution heterogene
- peu de traçabilite
- risque d'oubli des points critiques

### Option 2: outillage technique d'abord

Idee:
- ajouter des scripts, commandes ou vues d'aide avant de formaliser la recette

Avantages:
- peut reduire certains frottements
- utile si de vrais trous techniques apparaissent

Inconvenients:
- premature sans protocole
- risque d'outiller les mauvais besoins

### Option 3: recette guidee + outillage minimal

Idee:
- formaliser d'abord un protocole operateur clair
- n'ajouter qu'un outillage minimal si un point reel le justifie

Avantages:
- colle au besoin immediat
- limite la sur-construction
- permet une evaluation claire de readiness

Inconvenients:
- demande une discipline documentaire
- peut conduire a un second lot technique apres la premiere execution

Recommendation:
- retenir l'option 3

## Design cible

### 1. Deux paliers de recette

#### Palier A: base isolee/copied

But:
- valider la methode complete sans risque operationnel

La recette doit y verifier:
- creation du run
- generation du planning
- revue du cockpit
- ajustements manuels
- publication `v1`
- regeneration des brouillons
- creation puis publication d'une `v2`
- verification du diff
- export workbook

Sortie attendue:
- liste de frictions reelles
- ajustements documentaires ou techniques necessaires avant passage au reel

#### Palier B: PythonAnywhere avec vraies donnees

But:
- rejouer le meme protocole sur un cas reel

Garde-fous:
- pas de diffusion reelle
- pas d'action irreversible non maitrisee
- suivi explicite du run de recette

Sortie attendue:
- statut de readiness du module
- reserves precises si elles existent

### 2. Une semaine reelle unique comme scenario de reference

Je recommande de choisir une seule semaine reelle a la fois.

La phase 3 ne doit pas essayer de couvrir:
- plusieurs semaines d'un coup
- plusieurs modes d'exploitation concurrents
- toute la variabilite historique

Pourquoi:
- une recette de production doit rester executable
- l'objectif est d'identifier les derniers trous de workflow, pas de lancer une campagne de non-regression massive

### 3. Protocole operateur cible

Le protocole doit suivre exactement ce deroule:

1. Preparation
- choisir la semaine
- verifier la presence des parametres et donnees de reference
- verifier la source vols retenue

2. Generation initiale
- creer le `PlanningRun`
- lancer `Generer le planning`
- verifier l'absence d'issues bloquantes
- ouvrir `v1`

3. Relecture
- bloc `Planning`
- bloc `Non affectes`
- bloc `Stats`

4. Ajustements
- modifier quelques affectations representatives
- verifier la persistance des modifications
- publier `v1`

5. Communications
- regenerer les brouillons
- verifier regroupement, lisibilite, priorisation

6. Changement simule
- cloner `v1` vers `v2`
- faire une modification representative
- publier `v2`
- regenerer les brouillons
- verifier `new / changed / cancelled / unchanged`

7. Sorties
- generer l'export workbook
- verifier qu'il reste exploitable comme sortie de transition

8. Conclusion
- consigner ecarts et blocages
- classer la recette

### 4. Livrables de la phase

Je recommande quatre livrables:

#### a. Un protocole de recette

Fichier versionne dans `docs/plans/` ou `docs/runbooks/` selon la forme retenue.

Contenu:
- prerequis
- sequence exacte
- checkpoints
- commandes utiles
- regles de prudence

#### b. Une grille d'observation

But:
- noter rapidement ce qui est:
  - bloque
  - acceptable avec reserve
  - satisfaisant

Cette grille peut rester simple, par exemple:
- `etat`
- `impact`
- `contournement`
- `action de suivi`

#### c. Une note de resultat de recette isolee

Elle doit consigner:
- la semaine cible
- ce qui a ete execute
- les frictions constatees
- la decision pour passage au palier B

#### d. Une note de resultat PythonAnywhere reel

Meme structure, mais avec conclusion finale de readiness.

### 5. Mode d'execution recommande

Je recommande que cette phase commence par de la documentation et de l'outillage minimal, pas par des modifications produit non justifiees.

Ordre propose:
1. formaliser protocole + grille + notes de resultat
2. identifier si un tout petit outillage est necessaire pour rendre la recette executable
3. seulement ensuite lancer la premiere execution reelle

### 6. Outillage minimal acceptable dans cette phase

Je recommande de ne tolerer que des aides qui reduisent un vrai frottement de recette, par exemple:
- commande d'extraction d'un recap planning utile
- aide pour marquer un run comme "recette"
- note standard de post-recette

Je ne recommande pas dans cette phase:
- automatisation lourde
- nouveau moteur
- refonte UI

## Risques et garde-fous

### Risque 1: phase trop documentaire, sans valeur pratique

Garde-fou:
- la phase doit produire une execution reelle sur base isolee, puis sur PythonAnywhere

### Risque 2: phase trop technique, qui repart en developpement produit

Garde-fou:
- limiter l'outillage a ce qui bloque reellement la recette

### Risque 3: recette reelle ambiguë

Garde-fou:
- imposer une conclusion explicite:
  - pret pour usage encadre
  - pret avec reserves
  - pas encore pret

## Definition du done

La phase sera consideree terminee si:
- un protocole de recette operateur est documente
- une premiere execution sur base isolee est consignée
- une seconde execution sur PythonAnywhere reel est consignée
- une note d'ecarts existe
- une decision explicite de readiness est rendue

La phase ne sera pas consideree terminee si:
- on s'arrete a une checklist theorique
- aucune vraie semaine n'est rejouee
- les ecarts ne sont pas traces
- la conclusion finale reste floue
