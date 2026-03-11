# Planning Version Operator Parity Design

## Contexte

La page [`/planning/versions/<id>/`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/templates/planning/version_detail.html) est deja le cockpit principal du module `planning`, mais elle reste orientee technique:
- header minimal
- tableau d'affectations simplifie
- non-affectes en lecture seule
- brouillons de communication generiques

La recette phase 3 sur PythonAnywhere a confirme que:
- le flux nominal `run -> v1 -> publication -> v2` tient
- l'UI legacy Django est exploitable
- plusieurs flux operateur restent cependant trop pauvres par rapport au besoin reel

Le besoin confirme par l'utilisateur est de transformer cette page en vrai poste operateur hebdomadaire:
- lecture du planning en tableau detaille par expedition affectee
- edition inline sur brouillon
- passage naturel `v1` brouillon -> `v1` publiee -> `v2` brouillon
- ajout manuel depuis les non-affectes
- synthese operateur lisible en tete
- families de communications alignees sur `asf-planning`

Contrainte de scope:
- implementation strictement sur le stack Django legacy
- aucun travail sur `frontend-next/` ni sur la migration Next/React en pause

## Objectif

Faire de [`/planning/versions/<id>/`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/templates/planning/version_detail.html) l'ecran operateur principal pour une version de planning, avec:
- une synthese hebdomadaire lisible
- un tableau `Planning` detaille et editable
- un tableau `Non affectes` actionnable
- une carte `Communications` alignee sur les formats legacy `asf-planning`

## Decisions produit validees

- l'ecran central reste `/planning/versions/<id>/`
- une version publiee reste immuable
- toute modification apres publication passe par creation d'une nouvelle version brouillon (`v2`, `v3`, etc.)
- le planning propose par le run doit etre modifiable avant publication
- les mises a jour manuelles doivent rafraichir toutes les cartes du cockpit
- `asf-planning` est l'oracle de parite pour les formats de communication legacy

## Approches considerees

### Option 1: etendre le cockpit actuel

Conserver l'URL et la page actuelles, puis enrichir les cartes `Version`, `Planning`, `Non affectes` et `Communications`.

Avantages:
- garde le flux operateur deja en place
- reemploi maximal de [`wms/views_planning.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/views_planning.py), [`wms/planning/version_dashboard.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/planning/version_dashboard.py) et des templates planning
- transition progressive sans nouvel ecran

Inconvenients:
- demande une vraie refonte du presenter et des formulaires

### Option 2: creer un ecran d'edition separe

Ajouter un ecran distinct pour l'edition detaillee et laisser le cockpit surtout en lecture.

Avantages:
- separation plus nette des responsabilites

Inconvenients:
- plus de navigation
- moins proche du workflow de l'equipe

### Option 3: grille riche type quasi-Excel

Ajouter une interface fortement dynamique avec beaucoup de JS sur la page actuelle.

Avantages:
- tres proche du ressenti workbook

Inconvenients:
- trop lourd pour le stack legacy actuel
- risque de fragilite UI eleve

### Recommendation

Retenir l'option 1: etendre le cockpit actuel.

## Design cible

### 1. Carte `Version vXX`

Remplacer l'en-tete actuel par:

- titre: `Planning Semaine XX (du 09/03/26 au 15/03/26)`
- badge de statut visible: `Brouillon`, `Publiee`, `Supplantee`
- ligne meta:
  - `Cree par`
  - `Creation`
  - `Publication`
  - `Periode`
- tableau de synthese:
  - `Mode vols`
  - `Nb vols utilises`
  - `Nb colis disponibles`
  - `Nb colis affectes`
  - `Nb benevoles disponibles`
  - `Nb benevoles affectes`

Calculs recommandes:
- `Nb vols utilises`: nombre de `PlanningFlightSnapshot` distincts utilises dans la version
- `Nb colis disponibles`: somme des `carton_count` sur tous les `PlanningShipmentSnapshot` du run
- `Nb colis affectes`: somme des `assigned_carton_count` sur les assignments de la version
- `Nb benevoles disponibles`: nombre de `PlanningVolunteerSnapshot` du run
- `Nb benevoles affectes`: nombre de benevoles distincts utilises dans la version

### 2. Carte `Planning`

Le tableau principal devient une ligne par expedition affectee, avec ces colonnes:

- `Date_Vol`
- `Heure_Vol`
- `Numero_Vol`
- `Destination`
- `Routing`
- `BE_Numero`
- `BE_Nb_Colis`
- `BE_Nb_Equiv`
- `Benevole`
- `BE_Type`
- `BE_Expediteur`
- `BE_Destinataire`
- `Actions`

Sources de donnees:
- `PlanningAssignment`
- `PlanningShipmentSnapshot`
- `PlanningVolunteerSnapshot`
- `PlanningFlightSnapshot`
- `payload` snapshot pour les champs non encore portes directement

Format d'affichage cible:
- `Lundi 09/03/2026`
- `11h10`
- `AF 908`
- `CDG-NSI`

Actions par ligne:
- `Supprimer`
- `Modifier`

`Modifier` ouvre une edition inline sous la ligne avec:
- selecteur `Benevole`
- selecteur `Date du vol`
- selecteur `Vol`

Regles:
- edition uniquement sur version `draft`
- sur version `published`, afficher une action `Creer une nouvelle version de travail`
- la date du vol n'est pas un calendrier libre
- la date du vol n'affiche que les dates ayant au moins un vol pour la destination du BE
- le selecteur `Vol` est filtre par destination + date

### 3. Couleurs et semantique des selecteurs

#### Benevole

- vert clair: benevole disponible et sans conflit
- orange clair: benevole disponible mais deja affecte sur un creneau incompatible avec une marge de `2h30`
- rouge clair: benevole marque indisponible
- sans fond: aucune information

#### Date du vol

Le selecteur liste uniquement les dates ayant au moins un vol pour la destination du BE.

Couleurs:
- vert clair: au moins un vol de cette date est compatible et non tendu
- orange clair: des vols existent et peuvent encore prendre le BE, mais le jour est deja entame / tendu
- rouge clair: des vols existent, mais aucun n'a une capacite restante suffisante pour ce BE

#### Vol

Le selecteur liste uniquement les vols de la destination choisie a la date choisie.

Chaque option affiche au minimum:
- date
- heure
- numero
- routing

Couleurs:
- vert clair: capacite restante suffisante et situation propre
- orange clair: capacite restante suffisante mais vol deja utilise / tendu
- rouge clair: capacite restante insuffisante

### 4. Carte `Non affectes`

Le tableau `Non affectes` devient actionnable avec ces colonnes:
- `Destination`
- `BE_Numero`
- `BE_Nb_Colis`
- `BE_Nb_Equiv`
- `BE_Type`
- `BE_Expediteur`
- `BE_Destinataire`
- `Motif`
- `Action`

Action:
- bouton `Ajouter au planning`

Au clic:
- expansion inline
- selecteur `Affecter un benevole` avec la meme semantique de couleur que dans `Planning`
- selecteur `Affecter un vol` direct, deja filtre sur la destination du BE, avec la meme semantique de couleur
- bouton `Valider`

Effet:
- creation d'un `PlanningAssignment` manuel dans la version brouillon
- refresh complet du cockpit par cycle POST/redirect/GET

### 5. Regles de versioning operateur

Flux attendu:
- `v1` brouillon: edition libre avant publication
- `v1` publiee: figee
- action `Modifier cette version`: cree `v2` brouillon pre-remplie a partir de `v1`
- meme schema pour `v3`, `v4`, etc.

Il n'y a pas de modification directe d'une version publiee en place.

### 6. Carte `Communications`

La carte doit presenter six families:
- `WhatsApp benevoles`
- `Mail ASF interne`
- `Mail Air France`
- `Mail Correspondants`
- `Mail Expediteurs`
- `Mail Destinataires`

Mapping legacy:
- `WhatsApp benevoles` = parite avec [`whatsapp_handler.py`](/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_communication/whatsapp_handler.py)
- `Mail ASF interne` = parite avec [`email_asf_handler.py`](/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_communication/email_asf_handler.py)
- `Mail Air France` = parite avec [`email_airfrance_handler.py`](/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_communication/email_airfrance_handler.py)
- `Mail Correspondants` = equivalent WMS des `Destinations` legacy via [`email_destinations_handler.py`](/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_communication/email_destinations_handler.py)
- `Mail Expediteurs` = parite avec [`email_expediteurs_handler.py`](/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_communication/email_expediteurs_handler.py)
- `Mail Destinataires` = nouvelle famille WMS, meme logique et meme format que `Expediteurs`, avec une source de contacts differente

Contrainte forte:
- chaque famille doit reprendre le formatage metier legacy tel quel quand il existe deja dans `asf-planning`
- `Destinataires` doit etre implantee comme miroir de `Expediteurs`

Je recommande de conserver `CommunicationDraft` comme persistance, mais d'ajouter une notion de `communication_family` et une generation dediee par famille.

### 7. Rafraichissement du cockpit

Toutes les mutations de l'ecran doivent utiliser:
- POST
- validation serveur
- redirect vers la meme page
- recalcul du dashboard

Cela garantit que les cartes `Version`, `Planning`, `Non affectes`, `Communications`, `Stats` et `Exports` restent coherentes sans logique front lourde.

## Architecture recommandee

### Presenter

Scinder le presenter actuel [`wms/planning/version_dashboard.py`](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/planning/version_dashboard.py) en sous-blocs plus explicites:
- `header`
- `planning_rows`
- `unassigned_rows`
- `communication_groups`
- `stats`
- `history`

### Services metier a ajouter

- service de classification des options benevoles et vols
- service d'update d'un assignment existant
- service de suppression d'un assignment
- service d'ajout manuel depuis un shipment non affecte
- service de generation des families de communication
- bridge de parite legacy avec `asf-planning` pour les formattages

### Forms

Le `modelformset` actuel est trop limite pour le nouveau flux.

Je recommande:
- conserver le formset simple comme base de compatibilite si utile
- ajouter des formulaires/POST actions dediees pour:
  - update d'une ligne
  - delete d'une ligne
  - add depuis non-affecte

## Impacts de donnees

Le tableau demande reutilise largement les snapshots existants, mais certains champs doivent etre exposes plus proprement depuis le `payload` ou promus en champs presenter:
- `routing`
- `BE_Type`
- `BE_Destinataire`
- informations expediteur / destinataire

Pour les communications, la persistance actuelle `CommunicationDraft` pourrait devoir etre etendue avec:
- `family`
- `recipient_role`

Cette decision peut etre prise pendant l'implementation, en fonction de la simplicite de l'adaptation.

## Strategie de test

Les tests a couvrir:
- presenter header et KPI
- tableau planning detaille
- suppression d'une ligne
- modification inline d'une ligne
- ajout depuis `Non affectes`
- classification couleur benevole
- classification couleur date/vol
- reroutage `published -> clone draft`
- generation des six families de communication
- parite de formatage legacy pour les families existantes
- regression smoke planning

## Done

La phase est terminee quand:
- la carte `Version vXX` affiche la synthese hebdomadaire cible
- la carte `Planning` expose le tableau detaille attendu
- une ligne peut etre supprimee ou modifiee en brouillon
- un non-affecte peut etre ajoute au planning
- les selecteurs suivent la semantique de couleur validee
- les versions publiees creent bien `v2/v3/...` de travail au lieu d'etre modifiees en place
- les six families de communication sont generees
- les families legacy reproduisent leur formatage `asf-planning`
- les tests et la recette UI planning restent verts sur le stack Django legacy
