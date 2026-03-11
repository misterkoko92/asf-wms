# Planning Week View And Summary Design

## Goal

Ajouter dans `/planning/versions/<id>/` deux cartes repliables et dynamiques sous l'en-tête de version:

- `Vue Semaine`
- `Bilan Planning`

Ces deux vues doivent se recalculer à partir de l'état courant de la version brouillon ou publiée, donc refléter immédiatement les suppressions, modifications et ajouts d'affectations.

## Legacy Reference

Les références métier viennent de `asf-planning`:

- `ui_week_data.py`
  - `Disponibilités bénévoles (vue semaine)`
  - `Vols disponibles (vue semaine)`
- `ui_simulation.py` / `ui_version.py`
  - bilan bénévoles enrichi avec `Nb_Dispo`, `Nb_Jours_Affectes`, `Nb_Vols_Affectes`, `Nb_BE_Affectes`

## Target UI

### 1. Carte `Vue Semaine`

Position: juste sous la carte `Planning Semaine XX ...`

Contenu:

- un sous-tableau `Disponibilités bénévoles (vue semaine)`
- un sous-tableau `Vols disponibles (vue semaine)`

Comportement:

- carte repliée par défaut
- contenu recalculé depuis les snapshots du run + les affectations de la version courante
- mise à jour au reload après toute mutation opérateur déjà existante

### 2. Carte `Bilan Planning`

Position: sous `Vue Semaine`

Contenu:

- un tableau de synthèse par bénévole
- métriques minimales:
  - `Benevole`
  - `Nb_Dispo`
  - `Nb_Jours_Affectes`
  - `Nb_Vols_Affectes`
  - `Nb_BE_Affectes`
  - `Disponibilites`

Comportement:

- carte repliée par défaut
- calculée depuis les disponibilités du snapshot bénévole et les affectations de la version
- mise à jour après toute mutation opérateur

## Data Sources In WMS

- `PlanningVolunteerSnapshot.availability_summary`
- `PlanningFlightSnapshot.departure_date`
- `PlanningFlightSnapshot.payload`
- `PlanningAssignment`
- `PlanningShipmentSnapshot`

Le calcul reste entièrement côté WMS. Aucun appel à `asf-planning` n'est fait à runtime.

## Approach

Étendre `wms/planning/version_dashboard.py` pour exposer:

- `week_view`
  - `volunteer_table`
  - `flight_table`
- `planning_summary`
  - `volunteer_summary_rows`

Le template `planning/version_detail.html` insérera ensuite:

- `_version_week_view_block.html`
- `_version_planning_summary_block.html`

## Non-Goals

- pas de parité visuelle Streamlit exacte
- pas d'édition inline dans ces deux nouvelles cartes
- pas de refonte du solveur ou des règles opérateur existantes
