# Planning Communications Cockpit Design

## Contexte

La phase cockpit operateur est maintenant mergee dans `main` via la page [`/planning/versions/<id>/`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/templates/planning/version_detail.html), qui affiche deja:
- le planning groupe par vol
- les non affectes
- les stats d'exploitation
- les exports
- l'historique de version
- un bloc `Communications`

Mais la partie communications reste encore trop proche d'un niveau technique:
- [`wms/planning/communications.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/wms/planning/communications.py) regenere encore les drafts par affectation
- le cockpit ne fait qu'un regroupement d'affichage par destinataire/canal via [`wms/planning/version_dashboard.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/wms/planning/version_dashboard.py)
- le bloc [`_version_communications_block.html`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/templates/planning/_version_communications_block.html) expose seulement un booleen `changed_since_parent`, sans distinguer `nouveau`, `modifie`, `annule`, `inchange`

Pour que `asf-wms` devienne vraiment le poste operateur central, il faut maintenant faire des communications un flux exploitable apres chaque publication et chaque `v2`, `v3`, etc.

## Decisions produit confirmees

Le cadrage utilisateur a deja valide les points suivants:
- priorite immediate: rendre les communications de planning vraiment exploitables dans `asf-wms`
- organisation du bloc `Communications` par destinataire, pas par affectation
- distinction visible entre `nouveau`, `modifie`, `annule`, `inchange`
- drafts editables et regenerables par `PlanningVersion`
- envoi toujours manuel par les operateurs
- comparaison toujours faite par rapport a `version.based_on`
- `inchange` replie par defaut
- pas de migration lourde imposee d'avance si une couche service suffit

## Objectif

Faire du bloc `Communications` de la page de version planning un veritable centre de rediffusion operateur:
- savoir qui recontacter
- savoir pourquoi
- voir un brouillon deja agrege et editable
- regenerer proprement les messages quand une nouvelle version est publiee

## Probleme actuel

### 1. Generation encore trop fine

La fonction [`generate_version_drafts(...)`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/wms/planning/communications.py) fait aujourd'hui:
- suppression de tous les drafts de la version
- iteration sur les affectations
- creation d'un draft par affectation et par template actif

Consequences:
- redondance forte quand un benevole a plusieurs affectations
- pas de concept explicite de communication agregee
- pas de place propre pour les messages d'annulation

### 2. Diff operateur trop pauvre

Le presenter de cockpit ne calcule aujourd'hui qu'une liste de destinataires "impactes" depuis la version parente.

Cela ne suffit pas pour l'operateur, qui doit distinguer:
- un nouveau message
- une modification
- une annulation
- un message inchange qui n'a pas besoin d'etre renvoye

### 3. Regeneration sans plan intermediaire

La regeneration actuelle produit directement des `CommunicationDraft`.

Il manque une etape metier intermediaire:
- construire un plan de communication version-centrique
- puis le materialiser en brouillons persistants

Sans cette couche, l'UI reste contrainte par une representation trop basse.

## Approches considerees

### Option 1: enrichir seulement l'UI actuelle

Idee:
- garder la generation par affectation
- mieux regrouper au rendu

Avantages:
- changement rapide
- peu de code de service

Inconvenients:
- la base logique reste fausse pour l'usage operateur
- difficile de produire des annulations propres
- beaucoup de drafts redondants a editer

### Option 2: remodeler tout de suite la base autour d'un nouveau modele DB

Idee:
- introduire un modele persistant type `CommunicationPlanItem`
- faire une migration de schema des maintenant

Avantages:
- modele plus explicite
- extension future facile

Inconvenients:
- cout de migration et d'administration premature
- pas necessaire pour la premiere version si le plan peut rester en service pur

### Option 3: couche service `communication plan` au-dessus du modele actuel

Idee:
- garder `CommunicationDraft`
- ajouter une couche de service qui construit des `CommunicationPlanItem`
- agreger ensuite un seul draft par destinataire et canal

Avantages:
- colle au besoin operateur
- evite une migration lourde immediate
- garde la persistence editable existante
- permet les statuts `nouveau/modifie/annule/inchange`

Inconvenients:
- ajoute une couche de service supplementaire
- demande un vrai diff de version cote communications

Recommendation:
- retenir l'option 3

## Design cible

### 1. Deux niveaux logiques

#### a. `CommunicationPlanItem`

Objet de service, pas necessairement un modele DB dans cette phase.

Chaque item represente:
- une `PlanningVersion`
- un destinataire
- un canal
- un statut de changement:
  - `new`
  - `changed`
  - `cancelled`
  - `unchanged`
- les affectations courantes concernees
- les affectations precedentes concernees quand il y a un parent
- un resume court de diff

#### b. `CommunicationDraft`

Reste l'objet persistant editable.

Changement de role:
- aujourd'hui: un draft technique par affectation
- cible: un draft operateur agrege par item de plan, donc en pratique par `(destinataire, canal)`

### 2. Nouvelle couche de service

Je recommande d'introduire un module dedie, par exemple:
- [`wms/planning/communication_plan.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/wms/planning/communication_plan.py)

Responsabilites:
- normaliser les affectations de la version courante
- normaliser les affectations de `based_on` si elle existe
- comparer les deux ensembles par destinataire/canal
- produire des `CommunicationPlanItem`
- fournir aussi un ordre d'affichage operateur

La fonction [`generate_version_drafts(...)`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/wms/planning/communications.py) deviendra alors un materializer:
- construire le plan
- supprimer seulement la serie de drafts de la version courante
- creer un draft agrege par item

### 3. Calcul de diff communication

Le diff ne doit pas etre limite a "destinataire impacte ou non".

Il faut comparer, pour chaque destinataire/canal:
- aucun item dans le parent + item dans la version courante -> `new`
- item dans les deux, mais contenu fonctionnel different -> `changed`
- item dans le parent, plus rien dans la version courante -> `cancelled`
- item dans les deux sans changement -> `unchanged`

Le "contenu fonctionnel different" doit etre determine a partir des affectations:
- vol
- destination
- date/heure
- references expedition / BE
- quantite colis
- benevole

Le diff doit etre base sur des payloads canoniques, pas sur les textes rendus, pour eviter les faux positifs lies a la mise en forme.

### 4. Regles de generation des messages

Chaque draft agrege doit contenir:
- le destinataire
- la semaine et le numero de version
- un resume de changement
- la liste structuree des vols concernes
- les expeditions / BE rattachees

Comportement par statut:
- `new`: message complet des nouvelles affectations
- `changed`: message centre sur ce qui change, avec avant/apres si utile
- `cancelled`: message court d'annulation
- `unchanged`: message conservable pour trace, mais non prioritaire

Le moteur doit continuer a utiliser [`CommunicationTemplate`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/wms/models_domain/planning.py) si des templates actifs existent, mais avec un contexte agrege.

Recommendation pragmatique:
- rester sur les templates actuels en premiere iteration
- etendre le contexte de rendu avec:
  - `change_status`
  - `change_summary`
  - `current_assignments`
  - `previous_assignments`
- si besoin, utiliser `template.scope` plus tard pour differencier `new/changed/cancelled`

### 5. UI cockpit cible

Le bloc [`_version_communications_block.html`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/templates/planning/_version_communications_block.html) doit evoluer vers:
- regroupement par destinataire et canal
- badge clair de statut
- resume de diff visible au-dessus du brouillon
- priorisation d'affichage:
  - `new`
  - `changed`
  - `cancelled`
  - `unchanged`
- `unchanged` replie par defaut

Il faut aussi garder:
- regeneration explicite des brouillons
- edition inline du sujet et du corps
- rattachement a la `PlanningVersion` uniquement

### 6. Semantique de regeneration

Regle recommandee:
- regenerer ecrase les drafts generes de la version courante
- les drafts des versions precedentes restent intacts

Pour rester simple dans cette phase:
- on ne garde pas d'historique intermediaire de regenerations a l'interieur d'une meme version
- on conserve en revanche le statut `edited` quand l'operateur modifie un draft apres generation

Point important:
- la classification `new/changed/cancelled/unchanged` est derivee du plan, pas du `status` d'edition du draft
- `CommunicationDraft.status` continue de porter l'etat editorial (`generated`, `edited`, etc.)

### 7. Impact sur le cockpit et les tests

Services a faire evoluer:
- [`wms/planning/communications.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/wms/planning/communications.py)
- [`wms/planning/version_dashboard.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/wms/planning/version_dashboard.py)
- [`wms/views_planning.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/wms/views_planning.py)
- [`wms/forms_planning.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/wms/forms_planning.py) si la presentation du formset doit etre adaptee

Tests cibles:
- nouveau module de test pour le plan de communication
- adaptation de [`wms/tests/planning/tests_outputs.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/wms/tests/planning/tests_outputs.py)
- adaptation de [`wms/tests/planning/tests_version_dashboard.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/wms/tests/planning/tests_version_dashboard.py)
- adaptation de [`wms/tests/views/tests_views_planning.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-communications-cockpit/wms/tests/views/tests_views_planning.py)

## Hors scope de cette phase

Ce lot ne doit pas couvrir:
- envoi automatique email ou WhatsApp
- nouveau modele DB persistant pour `CommunicationPlanItem`
- workflows desktop Outlook / AppleScript / PDF
- reporting avance de diffusion
- automatisation de "qui a effectivement recu quoi"

## Definition du done

La phase est terminee quand:
- les drafts sont generes par destinataire/canal et plus par affectation
- le cockpit distingue `nouveau`, `modifie`, `annule`, `inchange`
- l'operateur voit d'abord les messages a rediffuser
- les drafts restent editables par version
- une nouvelle version regenere proprement ses propres brouillons a partir de `based_on`
- les tests couvrent:
  - premiere publication
  - `v2` inchangee
  - `v2` modifiee
  - `v2` annulee
  - `v2` avec nouvel ajout

La phase n'est pas terminee si:
- un draft reste cree par affectation
- le statut de changement n'est pas visible dans le cockpit
- les annulations ne sont pas materialisees
- l'operateur ne sait toujours pas rapidement quoi renvoyer

## Notes de premiere implementation

Pour le premier rollout recommande:
- `CommunicationPlanItem` reste un objet de service, sans migration DB
- `CommunicationDraft` reste l'objet persistant editable
- les drafts sont regeneres par `(destinataire, canal)`
- les anciens placeholders de template (`volunteer`, `flight`, `shipment_reference`, `cartons`) restent alimentes pour compatibilite ascendante, en plus du contexte agrege
