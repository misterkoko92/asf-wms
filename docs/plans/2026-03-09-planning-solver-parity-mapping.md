# Planning Solver Parity Mapping

## Purpose
Ce document sert de table de passage entre le solveur historique de `../asf_scheduler/new_repo` et le contrat solveur deja present dans `asf-wms`.

Il a deux usages:
- eviter de porter des contraintes sans leurs donnees d'entree
- rendre explicites les ecarts encore volontaires avant le port complet OR-Tools

## Current WMS Contract
Point d'entree actuel:
- `wms/planning/snapshots.py`
- `wms/planning/rules.py`
- `wms/planning/solver.py`

Contrat deja stable cote WMS:
- entree: `PlanningRun` en statut `ready`
- sortie: `PlanningVersion` + `PlanningAssignment`
- traces: `run.solver_payload` + `run.solver_result`

## Legacy Solver Inputs
Sources principales cote legacy:
- `scheduler/solver_ortools_common.py`
- `scheduler/solver_ortools.py`
- `scheduler/solver_ortools_v3.py`
- `tests/test_solver_contracts.py`
- `tests/test_solver_v3_strict_capacity.py`
- `tests/test_solver_v3_branches.py`

## Mapping Table
### Shipments
- Legacy `BE_Numero`
  - WMS: `PlanningShipmentSnapshot.shipment_reference`
  - Statut: deja porte
- Legacy `Destination`
  - WMS: `PlanningShipmentSnapshot.destination_iata`
  - Statut: deja porte
- Legacy `Priorite`
  - WMS: `PlanningShipmentSnapshot.priority`
  - Statut: deja porte
- Legacy `BE_Nb_Colis`
  - WMS: `PlanningShipmentSnapshot.carton_count`
  - Statut: deja porte
- Legacy `Equiv_Colis`
  - WMS: `PlanningShipmentSnapshot.equivalent_units`
  - Statut: deja porte
- Legacy type et expediteur
  - WMS: `PlanningShipmentSnapshot.payload`
  - Statut: present mais non encore exploite par le solveur

### Flights
- Legacy `Numero_Vol`
  - WMS: `PlanningFlightSnapshot.flight_number`
  - Statut: deja porte
- Legacy `Date_Vol`
  - WMS: `PlanningFlightSnapshot.departure_date`
  - Statut: deja porte
- Legacy `Heure_Vol`
  - WMS: `PlanningFlightSnapshot.departure_time`
  - Statut: present cote modele, sous-utilise cote rules
- Legacy `IATA` ou destination vol
  - WMS: `PlanningFlightSnapshot.destination_iata`
  - Statut: deja porte
- Legacy `Routing`
  - WMS: `PlanningFlightSnapshot.routing`
  - Statut: a porter dans le payload solveur
- Legacy `Route_Pos`
  - WMS: `PlanningFlightSnapshot.route_pos`
  - Statut: a porter dans le payload solveur
- Capacite equivalente vol
  - WMS: `PlanningFlightSnapshot.capacity_units`
  - Statut: deja porte
- Cle de vol physique derivee de numero/date/routing
  - WMS: a calculer dans `wms/planning/rules.py`
  - Statut: absente du payload actuel

### Volunteers
- Legacy `ID`
  - WMS: `PlanningVolunteerSnapshot.external_id`
  - Statut: deja porte dans le snapshot
- Legacy `Benevole`
  - WMS: `PlanningVolunteerSnapshot.volunteer_label`
  - Statut: deja porte
- Legacy `Max_Colis_Vol`
  - WMS: `PlanningVolunteerSnapshot.max_colis_vol`
  - Statut: deja porte et exploite
- Legacy disponibilites date + heures
  - WMS: `PlanningVolunteerSnapshot.availability_summary`
  - Statut: date exploitee, fenetres horaires encore a exploiter
- Autres limites hebdomadaires
  - WMS: `PlanningVolunteerSnapshot.payload`
  - Statut: non encore exploitees

### Destination Rules
- Legacy `Max_Colis_Par_Vol`
  - WMS: `PlanningDestinationRule.max_cartons_per_flight`
  - Statut: present cote modele, non encore porte dans le payload actuel
- Legacy `Freq_Semaine`
  - WMS: `PlanningDestinationRule.weekly_frequency`
  - Statut: present cote modele, non encore porte dans le payload actuel
- Priorites ou flags destination additionnels
  - WMS: `PlanningDestinationRule.payload`
  - Statut: a inventorier cas par cas

## Constraint Mapping for This Phase
Contraintes a porter dans la phase solveur:
- compatibilite destination/vol
- capacite equivalente par vol
- limite `max_colis_vol` par benevole
- limite `max_colis_par_vol` par destination
- compatibilite horaire benevole/vol
- exclusivite benevole sur meme vol physique multi-stop
- frequence hebdomadaire destination si elle affecte les choix du legacy

## Objective Inputs to Preserve
Donnees a porter avant le CP-SAT final:
- priorite expedition
- equivalent_units
- carton_count
- ordre de routing ou `route_pos`

Ces donnees pilotent les arbitrages du prototype OR-Tools deja present dans `codex/planning-ortools-solver`.

## Known Gaps After Task 1
Gaps acceptes a ce stade:
- `wms/planning/rules.py` ne porte pas encore `routing`, `route_pos`, frequence hebdomadaire ni `max_cartons_per_flight`
- `wms/planning/solver.py` reste en `greedy_v1`
- aucun cas de semaine de reference reelle n'est encore encode dans les tests WMS

## Explicit Out-of-Scope for This Phase
- client API vols concret
- parite complete `Planning.xlsx`
- automatisation des communications
- logique de verrous manuels dans le solveur
