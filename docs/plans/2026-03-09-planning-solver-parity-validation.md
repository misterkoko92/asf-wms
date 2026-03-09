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

Parite obtenue cote WMS apres alignement des contraintes:
- memes `4` expeditions affectees
- memes vols retenus (`AF652`, `AF910`)
- meme ensemble de benevoles mobilises (`PIERSON`, `GUEDON`, `CUBIZOLLES`)
- meme affectation pour `AF910`

Ecart residuel actuel:
- sur `AF652`, le legacy assigne `250722` et `250723` a `PIERSON` puis `250724` a `GUEDON`
- le solveur WMS assigne `250722` et `250723` a `GUEDON` puis `250724` a `PIERSON`

Interpretation:
- les contraintes principales semblent maintenant alignees
- l'ecart restant ressemble a un tie-break d'affectation intra-vol entre benevoles equivalemment valides
- ne pas versionner ce cas comme golden test strict tant que ce tie-break n'est pas clarifie

## Residual Gap Log
Tant que le corpus de semaines reelles n'est pas encore branche, documenter chaque ecart important selon ce format:
- `week`: identifiant ou periode
- `legacy_behavior`: decision historique
- `wms_behavior`: decision WMS
- `impact`: faible, moyen, fort
- `reason`: contrainte manquante, objectif different, donnee manquante, autre
- `next_action`: test, port de regle, ou acceptation explicite
