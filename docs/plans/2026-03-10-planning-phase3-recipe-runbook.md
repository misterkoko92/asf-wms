# Planning Phase 3 Recipe Runbook

## But

Ce runbook sert a executer une vraie recette operateur planning dans `asf-wms` en deux paliers:
- palier A: base isolee/copied
- palier B: PythonAnywhere reel

Le but n'est pas de diffuser un planning reel, mais de verifier qu'un operateur peut mener un cycle complet dans `asf-wms`:
- generer un run
- relire et ajuster le planning
- publier `v1`
- regenerer les communications
- produire une `v2`
- lire le diff
- sortir le workbook de transition

## Decision attendue a la fin

La recette doit conclure sur une de ces trois decisions:
- `Pret pour usage encadre`
- `Pret avec reserves`
- `Pas encore pret`

## Portee

Cette recette couvre:
- une seule semaine reelle a la fois
- un seul operateur de recette
- un seul cycle `v1 -> v2`
- un envoi manuel seulement, donc sans diffusion effective

Cette recette ne couvre pas:
- l'envoi reel des mails ou messages
- plusieurs semaines en parallele
- une validation exhaustive de toutes les semaines legacy

## Aucune brique supplementaire requise

Pour ce premier passage, aucun outillage additionnel n'est requis.

La surface actuelle suffit deja pour executer la recette:
- creation de run via `/planning/runs/new/`
- generation via le bouton `Generer le planning`
- revue via `/planning/versions/<id>/`
- publication `v1`
- clonage `v2`
- regeneration des brouillons
- export `Planning.xlsx`
- lecture du diff `v1 / v2`

Si un frottement reel apparait pendant l'execution, il doit etre note dans la grille d'observation avant toute decision d'ajouter un outil.

## Prerequis

### Donnees
- une semaine reelle explicitement choisie
- un `PlanningParameterSet` exploitable pour cette semaine
- les donnees benevoles presentes et suffisamment renseignees
- les contacts expediteurs exploitables
- les vols disponibles dans le mode retenu

### Acces
- un compte staff capable d'acceder a `/planning/`
- acces a l'environnement isole ou a PythonAnywhere selon le palier

### Regles de prudence
- aucune diffusion reelle de message
- aucun envoi email/WhatsApp
- toute action doit rester dans un cadre de recette observable
- toute reserve ou ambiguite doit etre notee immediatement

## Choix de la semaine

Avant de commencer, consigner:
- semaine cible
- justification du choix
- source vols retenue (`excel`, `api`, `hybrid`)
- environnement de recette

Recommendation:
- commencer par une semaine que l'equipe connait bien
- preferer `hybrid` pour le premier passage reel si l'API vols n'est pas encore totalement banalisee

## Palier A: base isolee/copied

### Etape 1: preparation

Verifier:
- la semaine cible
- le `PlanningParameterSet`
- la source vols
- le compte staff utilise

Consigner ces informations dans la note:
- [phase3-isolated-result](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-phase3-recipe/docs/plans/2026-03-10-planning-phase3-isolated-result.md)

### Etape 2: creation du run

Depuis `/planning/runs/new/`:
- saisir `week_start`
- saisir `week_end`
- choisir le `PlanningParameterSet`
- choisir le mode vols

Point de controle:
- le run est cree sans erreur
- le detail du run est accessible

### Etape 3: generation initiale

Depuis `/planning/runs/<id>/`:
- cliquer `Generer le planning`

Points de controle:
- le run ne reste pas bloque en validation si les donnees sont correctes
- `v1` est creee
- les issues sont lisibles si quelque chose bloque

Si le run echoue:
- noter precisement l'issue
- ne pas contourner sans l'ecrire dans la grille d'observation

### Etape 4: relecture operateur de `v1`

Depuis `/planning/versions/<id>/`:
- relire le bloc `Planning`
- relire `Non affectes`
- relire `Stats`

Verifier:
- que le regroupement par vol est exploitable
- que les non affectes ont un motif comprehensible
- que la vue suffit pour une premiere decision operateur

### Etape 5: ajustements manuels de `v1`

Faire quelques ajustements realistes:
- changer un benevole sur un vol compatible
- deplacer une expedition si necessaire
- verifier la persistence des modifications

Points de controle:
- les modifications sont sauvegardees
- la source manuelle reste identifiable
- l'ecran reste lisible apres ajustement

### Etape 6: publication de `v1`

Depuis le header de version:
- cliquer `Publier la version`

Points de controle:
- `v1` devient non editable
- la date/heure de publication apparait

### Etape 7: communications de `v1`

Depuis le bloc `Communications`:
- generer les brouillons
- relire plusieurs brouillons

Verifier:
- regroupement par destinataire/canal
- lisibilite du texte
- adequation de la priorisation

### Etape 8: creation et test de `v2`

Depuis `v1`:
- creer `v2`
- faire une modification representative
- publier `v2`
- regenerer les brouillons
- consulter `Voir le diff`

Verifier:
- les statuts `Nouveau`, `Modifie`, `Annule`, `Inchange`
- la lisibilite du diff
- la capacite a identifier qui doit etre recontacte

### Etape 9: export workbook

Depuis le bloc `Exports`:
- regenerer `Planning.xlsx`

Verifier:
- l'artefact est genere
- il est exploitable comme sortie de transition

### Etape 10: conclusion du palier A

Classer les observations:
- bloque
- reserve
- satisfaisant

Rendre une decision intermediaire:
- `Palier B autorise`
- ou `Palier B a suspendre`

## Palier B: PythonAnywhere reel

Le palier B rejoue exactement le meme protocole sur la vraie base, avec ces garde-fous supplementaires:
- aucune diffusion effective
- aucune communication envoyee
- suivi explicite du run de recette

### Etape 1: preparation

Consigner dans la note:
- date exacte d'execution
- environnement PythonAnywhere
- semaine cible
- mode vols
- identite de l'operateur

### Etape 2: execution

Rejouer le meme cycle:
- creation du run
- generation
- revue `v1`
- ajustements
- publication
- brouillons
- `v2`
- diff
- export

### Etape 3: conclusion du palier B

Noter:
- ce qui marche sans reserve
- ce qui marche avec reserve
- ce qui bloque encore

Rendre la decision finale:
- `Pret pour usage encadre`
- `Pret avec reserves`
- `Pas encore pret`

## Checkpoints obligatoires

La recette n'est pas valide si un de ces checkpoints manque:
- une semaine cible explicitement choisie
- un `PlanningRun` cree
- une `v1` publiee
- des brouillons generes
- une `v2` publiee
- un diff consulte
- un workbook genere
- une conclusion redigee

## Traces a conserver

Pour chaque palier, consigner:
- semaine cible
- mode vols
- captures ou notes de contexte si utile
- obstacles
- contournements
- conclusion

Documents de sortie:
- [observation-grid](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-phase3-recipe/docs/plans/2026-03-10-planning-phase3-recipe-observation-grid.md)
- [isolated-result](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-phase3-recipe/docs/plans/2026-03-10-planning-phase3-isolated-result.md)
- [pythonanywhere-result](/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-phase3-recipe/docs/plans/2026-03-10-planning-phase3-pythonanywhere-result.md)

## Critere de succes de la phase

La phase 3 est consideree comme accomplie seulement si:
- le palier A est execute et consigne
- le palier B est execute et consigne
- une decision finale explicite est rendue
