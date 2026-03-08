# Volunteer UI Navigation And Availability Design

## Context
Le portail benevole legacy existe maintenant sous `/benevole/`, mais sa navigation reste minimale et l'ecran de saisie des disponibilites n'est pas encore assez lisible ni assez guide pour un usage regulier.

Objectifs valides:
- ajouter des onglets de navigation sur toutes les pages `/benevole/*`
- deplacer `FR / ENG` tout en haut a droite du header
- rendre l'ecran `/benevole/disponibilites/` plus lisible et plus guidant
- preafficher automatiquement les disponibilites existantes de la semaine
- conserver la contrainte fonctionnelle: une seule disponibilite affichee par jour, et si plusieurs existent historiquement, retenir la derniere ajoutee

## Decision Summary
Decision retenue:
- conserver l'architecture Django legacy existante
- ameliorer `templates/benevole/base.html` pour la navigation commune
- faire evoluer `templates/benevole/availability_week_form.html`, `wms/forms_volunteer.py` et `wms/views_volunteer.py`
- ajouter un peu de JavaScript inline dans le template de disponibilites pour piloter l'affichage des champs horaires

Decision UX:
- navigation par onglets: `Accueil`, `Profil`, `Contraintes`, `Disponibilites`, `Recap`
- `FR / ENG` place en extremite droite de la ligne d'entete
- selecteur de semaine deplace sous le sous-titre de la carte d'introduction
- selecteur de semaine elargi pour garder les numeros sur deux chiffres lisibles
- quand `Indisponible` est coche, masquer labels + champs des heures
- quand `Disponible` est coche, afficher deux selects Bootstrap avec minutes limitees a `00`, `15`, `30`, `45`

## Availability Screen Behavior
### Initial state
- pour chaque jour de la semaine, le formulaire est pre-rempli depuis les donnees existantes
- si une indisponibilite existe, le jour s'ouvre en `Indisponible`
- sinon, si une ou plusieurs disponibilites existent, le jour s'ouvre en `Disponible`
- si plusieurs disponibilites existent pour le meme jour, seule la derniere ajoutee est utilisee pour le pre-remplissage
- sinon, le jour s'ouvre en `Indisponible` sans heures visibles

### Submission behavior
- la soumission garde la logique actuelle de remplacement par jour
- toutes les disponibilites existantes du jour sont supprimees avant recreation
- au final, le jour possede soit une indisponibilite, soit une seule disponibilite active

## Technical Approach
### Navigation
- calculer l'onglet actif directement dans le template via `request.resolver_match.url_name`
- reutiliser le header existant et y separer:
  - bloc marque `ASF WMS / Portail benevole`
  - switch langue aligne a droite
  - barre d'onglets sous le header principal

### Time selects
- remplacer l'usage `type="time"` sur le formulaire semaine uniquement
- utiliser `forms.Select` avec une liste de quarts d'heure (`00/15/30/45`)
- garder le formulaire d'edition simple existant hors scope

### Week prefill
- charger les disponibilites de la semaine cote vue
- regrouper par date
- choisir la derniere par `created_at` puis `id`
- injecter l'etat et les horaires dans les `initial` du formset

## Risks
- le masquage des champs horaires ne doit pas casser la validation serveur
- le pre-remplissage ne doit pas introduire de dependance a un ordre SQL implicite

Mesures:
- validation serveur conservee dans `VolunteerAvailabilityWeekForm.clean()`
- choix explicite de la "derniere" disponibilite par tri deterministe
