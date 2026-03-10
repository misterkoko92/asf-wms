# Planning Solver Parity Validation

## Purpose
Ce document decrit le format minimum a comparer entre le planning legacy et `asf-wms` pendant la phase de parite solveur.

Le but n'est pas encore de prouver une equivalence parfaite, mais de rendre les ecarts lisibles et justifiables.

## WMS Evidence to Capture
Pour chaque `PlanningRun` resolu, capturer au minimum:
- `run.solver_payload`
- `run.solver_result`
- la liste des `PlanningAssignment`

Les champs `solver_result` les plus utiles pour la comparaison sont:
- `solver`
- `status`
- `assignment_count`
- `candidate_count`
- `assigned_shipment_snapshot_ids`
- `unassigned_shipment_snapshot_ids`
- `unassigned_reasons`
- `assignment_count_by_flight`
- `flight_usage`
- `volunteer_usage`
- `vols_diagnostics`

## Legacy Evidence to Capture
Pour la meme semaine cote planning historique, figer si possible:
- resultat brut solveur
- planning final diffuse si different
- liste des expeditions non affectees avec raison connue
- contexte manuel utile si une correction operateur a ete necessaire

## Comparison Axes
Comparer d'abord les decisions metier, pas les details d'implementation.

### Shipment-Level
- expedition affectee ou non
- vol choisi
- benevole choisi
- raison d'absence d'affectation

### Flight-Level
- nombre d'affectations par vol
- vols sans expedition compatible
- vols sans benevole compatible
- vols compatibles mais non utilises

### Volunteer-Level
- usage par benevole
- conflits multi-stop evites
- respect des limites `max_colis_vol`

## Minimal Acceptance Rules
Une semaine est acceptable pour la phase solveur si:
- aucune affectation invalide n'apparait cote WMS
- les expeditions non affectees ont une raison explicite
- les arbitrages majeurs legacy vs WMS sont explicables
- les ecarts restants sont documentes et classes

## Current Reference Cases
Le harnais `wms.tests.planning.tests_solver_reference_cases` couvre deja les cas legacy suivants:
- `legacy_multistop_first_stop`
- `legacy_multistop_first_stop_without_route_pos`
- `legacy_multistop_second_stop_without_conflict`
- `legacy_no_benevole_compatible`
- `legacy_session_s11_2026`

Le cas `missing_paramdest_stop` du legacy reste a porter avec un format d'assertion moins strict que l'egalite exacte des affectations, car le solveur peut retourner plusieurs matchings equivalents.

## Legacy Session Extraction
Le repo `asf_scheduler/new_repo` sait etre rejoue hors Streamlit a partir d'un dossier `session_*`.

Commande WMS disponible pour fabriquer une fixture JSON compatible avec le harnais:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py build_legacy_planning_reference_case \
  --case-name legacy_session_s11_2026 \
  --legacy-root /Users/EdouardGonnu/asf_scheduler/new_repo \
  --session-dir /Users/EdouardGonnu/asf_scheduler/new_repo/.tmp_asf/session_15e28a26-95f6-4d81-b680-b3af43a56bb2 \
  --output /Users/EdouardGonnu/asf-wms/wms/tests/planning/fixtures/solver_reference_cases/legacy_session_s11_2026.json
```

Le replay legacy exige un `ASF_TMP_DIR` ecrivable pour ses logs; la commande le positionne par defaut sous `/tmp`.

## Current Real-Week Probe
La session legacy suivante a ete rejouee avec succes:
- `session_15e28a26-95f6-4d81-b680-b3af43a56bb2`
- semaine detectee: `2026-03-09 -> 2026-03-15`
- sortie extraite: `/tmp/legacy_session_s11_2026.json`

Parite obtenue cote WMS apres alignement des contraintes et de l'affectation intra-vol:
- memes `4` expeditions affectees
- memes vols retenus (`AF652`, `AF910`)
- meme ensemble de benevoles mobilises (`PIERSON`, `GUEDON`, `CUBIZOLLES`)
- meme distribution BE -> benevole sur `AF652`
- meme affectation pour `AF910`

Correction appliquee:
- le solveur WMS conserve son choix CP-SAT des vols et du set de benevoles
- une etape deterministe de repartition intra-vol recompose ensuite `BE -> benevole`
- cette repartition suit l'ordre legacy des benevoles quand `payload.legacy_id` est disponible
- l'algorithme utilise un backtracking borne pour garder une affectation faisable sous contrainte de capacite

Statut:
- le probe reel `legacy_session_s11_2026` n'a plus d'ecart connu
- la fixture `wms/tests/planning/fixtures/solver_reference_cases/legacy_session_s11_2026.json` est maintenant versionnee
- le harnais `wms.tests.planning.tests_solver_reference_cases` l'assert en egalite stricte

## Secondary Real-Week Probe
La session legacy suivante a ete rejouee comme deuxieme candidat de golden case:
- `session_d2010257-bd54-4896-ba39-5726e035cb3e`
- semaine detectee: `2026-03-02 -> 2026-03-08`
- sortie extraite: `/tmp/legacy_session_s10_small.json`

Etat actuel apres correction du sens de priorite legacy et injection de `ParamBE` minimal:
- le nombre d'affectations WMS est correct (`5`)
- le set final n'est pas encore aligne sur le legacy
- le delta residuel est descendu a `4` affectations manquantes / `4` affectations en trop sur le probe minimal
- `ParamDest` est maintenant porte dans les fixtures de reference et injecte dans le `PlanningRun`, sans suppression de cet ecart

Ecarts observes:
- pour `NSI`, le legacy choisit `AF908` alors que WMS choisit encore `AF910`
- pour `RUN`, WMS ne retient pas exactement le meme sous-ensemble de BE sur `AF652`
- ces ecarts ne relevent plus du tie-break benevole intra-vol; ils pointent vers d'autres regles legacy encore manquantes

Hypotheses de root cause restantes:
- arbitrage legacy sur le choix du vol au-dela de `ParamDest`
- arbitrage legacy supplementaire sur la selection des BE a capacite contrainte
- eventuels overlays expediteur non encore modelises dans le payload solveur

## Residual Gap Log
Tant que le corpus de semaines reelles n'est pas encore branche, documenter chaque ecart important selon ce format:
- `week`: identifiant ou periode
- `legacy_behavior`: decision historique
- `wms_behavior`: decision WMS
- `impact`: faible, moyen, fort
- `reason`: contrainte manquante, objectif different, donnee manquante, autre
- `next_action`: test, port de regle, ou acceptation explicite
