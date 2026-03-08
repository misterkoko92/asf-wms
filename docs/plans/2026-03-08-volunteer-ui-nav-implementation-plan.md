# Volunteer UI Navigation And Availability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ameliorer la navigation du portail benevole et rendre l'ecran hebdomadaire de disponibilites plus lisible, plus guide et pre-rempli a partir des donnees existantes.

**Architecture:** Garder la pile Django legacy et concentrer le changement sur les templates benevoles, le formulaire hebdomadaire de disponibilites et la vue de construction du formset. La logique de pre-remplissage reste cote serveur, avec un JavaScript leger cote template pour masquer ou afficher les heures selon l'etat choisi.

**Tech Stack:** Django 4.2, templates Django, formulaires Django, JavaScript inline leger, tests `manage.py test`.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:systematic-debugging`, `@superpowers:verification-before-completion`, `@superpowers:using-git-worktrees`.

### Task 1: Couvrir la navigation benevole et le nouveau rendu de disponibilites

**Files:**
- Modify: `wms/tests/views/tests_views_volunteer.py`

**Step 1: Write the failing tests**

Ajouter des tests qui couvrent:
- presence des onglets `Accueil`, `Profil`, `Contraintes`, `Disponibilites`, `Recap`
- presence du switch langue dans le header benevole
- pre-remplissage de la page hebdomadaire avec la derniere disponibilite du jour
- pre-remplissage `Indisponible` quand une indisponibilite existe
- presence des quarts d'heure `00`, `15`, `30`, `45`

**Step 2: Run test to verify it fails**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer -v 2`

Expected: FAIL sur les nouvelles assertions de navigation et de pre-remplissage.

**Step 3: Commit**

```bash
git add wms/tests/views/tests_views_volunteer.py
git commit -m "test(volunteer): cover navigation and weekly availability ui"
```

### Task 2: Implementer la navigation commune benevole

**Files:**
- Modify: `templates/benevole/base.html`

**Step 1: Add tabs and move language switch**

Ajouter:
- ligne header avec marque a gauche et switch langue a droite
- seconde ligne avec onglets benevoles
- classes d'etat actif basees sur `request.resolver_match.url_name`

**Step 2: Run targeted test**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer.VolunteerProfileViewTests -v 2`

Expected: PASS sur les assertions de navigation.

**Step 3: Commit**

```bash
git add templates/benevole/base.html
git commit -m "feat(volunteer): add portal navigation tabs"
```

### Task 3: Pre-remplir la semaine et moderniser les champs horaires

**Files:**
- Modify: `wms/forms_volunteer.py`
- Modify: `wms/views_volunteer.py`
- Modify: `templates/benevole/availability_week_form.html`

**Step 1: Implement server-side prefill**

Dans `wms/views_volunteer.py`:
- charger les disponibilites et indisponibilites de la semaine
- choisir la derniere disponibilite par jour
- injecter les `initial` appropries dans le formset

**Step 2: Replace weekly time widgets**

Dans `wms/forms_volunteer.py`:
- introduire un widget `Select` pour les quarts d'heure
- l'utiliser uniquement sur `VolunteerAvailabilityWeekForm`

**Step 3: Update template**

Dans `templates/benevole/availability_week_form.html`:
- deplacer le selecteur de semaine sous le sous-titre
- elargir le selecteur
- masquer/afficher les champs heures selon la radio
- ajouter un JavaScript minimal pour piloter l'etat a l'ouverture et au changement

**Step 4: Run tests**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/forms_volunteer.py wms/views_volunteer.py templates/benevole/availability_week_form.html
git commit -m "feat(volunteer): improve weekly availability ui"
```

### Task 4: Verify formatting and clean diff

**Files:**
- Modify: none expected

**Step 1: Run verification**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python -m ruff check wms/forms_volunteer.py wms/views_volunteer.py wms/tests/views/tests_views_volunteer.py`
- `git diff --check`

Expected: PASS.

**Step 2: Final commit if needed**

If hooks or formatters changed files:

```bash
git add -A
git commit -m "chore(volunteer): finalize ui nav polish"
```
