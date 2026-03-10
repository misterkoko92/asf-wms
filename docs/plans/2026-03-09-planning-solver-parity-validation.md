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
- `legacy_session_s10_2026` (assertion ciblee sur l'affectation mono-BE `260098`)
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

Iteration supplementaire de cette phase:
- le solveur WMS ne repose plus sur le modele simplifie `shipment/flight/volunteer` unique
- il utilise maintenant un coeur `x/y/z` plus proche du legacy:
  - `x`: expedition -> vol
  - `y`: benevole -> vol
  - `z`: expedition -> benevole -> vol
- un tie-break explicite sur les options benevoles compatibles est ajoute avant les tie-breaks finaux
- le tie-break artificiel qui favorisait les `z` crees le plus tard a ete retire
- un post-traitement limite aux vols mono-BE tranche maintenant avec la fin de disponibilite du benevole sur le jour du vol, apres stabilisation des vols multi-BE
- la verification locale reste verte sur:
  - `wms.tests.planning`
  - `wms.tests.views.tests_views_planning`
  - `wms.tests.management.tests_management_makemigrations_check`
  - `wms.tests.management.tests_management_seed_planning_demo_data`

## Secondary Real-Week Probe
La session legacy suivante a ete rejouee comme deuxieme candidat de golden case:
- `session_d2010257-bd54-4896-ba39-5726e035cb3e`
- semaine detectee: `2026-03-02 -> 2026-03-08`
- sortie extraite: `/tmp/legacy_session_s10_small.json`

Etat actuel apres retrait du tie-break `z` non legacy et ajout du tie-break mono-BE:
- le nombre d'affectations WMS reste correct (`5`)
- le choix legacy critique `260098 -> AF908 -> COURTOIS Alain` est maintenant aligne et assert dans le harnais
- le mini-probe reste volontairement non-golden pour le sous-ensemble `RUN` sur `AF652`, car plusieurs matchings equivalents subsistent sur ce corpus reduit
- `ParamDest` est porte dans les fixtures de reference et injecte dans le `PlanningRun`

Ecarts encore assumes sur ce probe:
- le sous-ensemble exact de BE `RUN` retenu sur `AF652` n'est pas encore traite comme une parite forte
- cet ecart est considere comme non conclusif tant que le corpus `s10` reste reduit et non rejoue sous forme de golden case hebdomadaire complet

Note importante:
- un mini-corpus synthetique derive de `s10` a servi de smoke test pendant le refactor
- il ne doit pas etre traite comme golden case metier complet, car la reduction du contexte hebdomadaire change deja certaines decisions legacy
- `legacy_session_s10_2026` sert maintenant de reference reelle partielle pour le cas mono-BE `NSI`
- la prochaine preuve utile reste donc un deuxieme golden case reel complet sur semaine entiere, pas un durcissement excessif du mini-corpus

## Residual Gap Log
Tant que le corpus de semaines reelles n'est pas encore branche, documenter chaque ecart important selon ce format:
- `week`: identifiant ou periode
- `legacy_behavior`: decision historique
- `wms_behavior`: decision WMS
- `impact`: faible, moyen, fort
- `reason`: contrainte manquante, objectif different, donnee manquante, autre
- `next_action`: test, port de regle, ou acceptation explicite
