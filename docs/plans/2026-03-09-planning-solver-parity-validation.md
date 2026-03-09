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

## Residual Gap Log
Tant que le corpus de semaines reelles n'est pas encore branche, documenter chaque ecart important selon ce format:
- `week`: identifiant ou periode
- `legacy_behavior`: decision historique
- `wms_behavior`: decision WMS
- `impact`: faible, moyen, fort
- `reason`: contrainte manquante, objectif different, donnee manquante, autre
- `next_action`: test, port de regle, ou acceptation explicite
