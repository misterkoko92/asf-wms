# Planning Module Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrer dans `asf-wms` un module `planning` legacy Django capable de charger expeditions, benevoles et vols, d'appliquer les regles metier, d'executer le solveur, de permettre des ajustements manuels, de versionner les diffusions et de regenerer exports et brouillons de communication par version.

**Architecture:** Ajouter un vrai domaine `planning` dans `asf-wms` plutot qu'un portage de l'application Streamlit. Le coeur technique repose sur des modeles de domaine explicites, des services internes `wms/planning/*` pour snapshots, validation, regles, solveur, exports et communications, puis des vues Django legacy sous `/planning/` pour piloter runs, versions et ajustements manuels. `ParamDest` devient planning-owned. `ParamBenev` vient du domaine benevole. `ParamExpediteur` vient du domaine portal ou contacts. `ParamBE` devient un referentiel partage avec un point d'entree transverse hors module facturation.

**Tech Stack:** Django 4.2, ORM Django, formulaires Django, templates Django legacy, OR-Tools deja utilise par `../asf_scheduler/new_repo`, import Excel Python existant, `manage.py test`.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:systematic-debugging`, `@superpowers:verification-before-completion`, `@superpowers:requesting-code-review`, `@superpowers:using-git-worktrees`.

### Task 1: Poser le domaine planning et ses contraintes de base

**Files:**
- Create: `wms/models_domain/planning.py`
- Modify: `wms/models.py`
- Modify: `wms/admin.py`
- Create: `wms/tests/planning/tests_models_planning.py`
- Modify: `wms/migrations/` via `makemigrations`

**Step 1: Write the failing test**

Ajouter les tests de modele qui couvrent au minimum:
- creation d'un `PlanningRun`
- numerotation auto de `PlanningVersion`
- interdiction d'editer une version publiee
- conservation du lien `based_on` entre versions

```python
from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.models import PlanningRun, PlanningVersion


class PlanningModelTests(TestCase):
    def test_version_number_increments_per_run(self):
        user = get_user_model().objects.create_user(
            username="planner@example.com",
            email="planner@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            created_by=user,
        )
        v1 = PlanningVersion.objects.create(run=run, created_by=user)
        v2 = PlanningVersion.objects.create(run=run, created_by=user)
        self.assertEqual(v1.number, 1)
        self.assertEqual(v2.number, 2)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.planning.tests_models_planning -v 2`
Expected: FAIL because the planning models do not exist yet.

**Step 3: Write minimal implementation**

- Ajouter dans `wms/models_domain/planning.py`:
  - `PlanningParameterSet`
  - `PlanningDestinationRule`
  - `FlightSourceBatch`
  - `Flight`
  - `PlanningRun`
  - `PlanningIssue`
  - `PlanningShipmentSnapshot`
  - `PlanningVolunteerSnapshot`
  - `PlanningFlightSnapshot`
  - `PlanningVersion`
  - `PlanningAssignment`
  - `PlanningArtifact`
  - `CommunicationTemplate`
  - `CommunicationDraft`
- Exporter les modeles depuis `wms/models.py`
- Enregistrer les modeles utiles dans `wms/admin.py`
- Generer la migration:

```bash
./.venv/bin/python manage.py makemigrations wms
```

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.planning.tests_models_planning -v 2`
- `./.venv/bin/python manage.py test wms.tests.management.tests_management_makemigrations_check -v 2`

Expected: PASS and no unexpected migration drift.

**Step 5: Commit**

```bash
git add wms/models_domain/planning.py wms/models.py wms/admin.py wms/tests/planning/tests_models_planning.py wms/migrations
git commit -m "feat(planning): add planning domain models"
```

### Task 2: Completer le referentiel benevole pour les besoins du solveur

**Files:**
- Modify: `wms/models_domain/volunteer.py`
- Modify: `wms/forms_volunteer.py`
- Modify: `wms/views_volunteer.py`
- Modify: `templates/benevole/constraints.html`
- Create: `wms/tests/planning/tests_volunteer_planning_inputs.py`
- Modify: `wms/migrations/` via `makemigrations`

**Step 1: Write the failing test**

Ajouter un test qui verifie que `VolunteerConstraint` porte les champs indispensables au planning, notamment `max_colis_vol`.

```python
from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.models import VolunteerConstraint, VolunteerProfile


class VolunteerPlanningInputTests(TestCase):
    def test_constraint_stores_max_colis_vol(self):
        user = get_user_model().objects.create_user(
            username="volunteer@example.com",
            email="volunteer@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        profile = VolunteerProfile.objects.create(user=user)
        constraint = VolunteerConstraint.objects.create(
            volunteer=profile,
            max_colis_vol=4,
        )
        self.assertEqual(constraint.max_colis_vol, 4)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.planning.tests_volunteer_planning_inputs -v 2`
Expected: FAIL because the field does not exist yet.

**Step 3: Write minimal implementation**

- Ajouter a `VolunteerConstraint` les champs planning manquants, en commencant par `max_colis_vol`
- Exposer ces champs dans `wms/forms_volunteer.py`, `wms/views_volunteer.py` et `templates/benevole/constraints.html`
- Generer la migration

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.planning.tests_volunteer_planning_inputs -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer -v 2`

Expected: PASS with no regression on volunteer UI.

**Step 5: Commit**

```bash
git add wms/models_domain/volunteer.py wms/forms_volunteer.py wms/views_volunteer.py templates/benevole/constraints.html wms/tests/planning/tests_volunteer_planning_inputs.py wms/migrations
git commit -m "feat(planning): extend volunteer constraints for solver inputs"
```

### Task 3: Extraire l'equivalence partagee et migrer `ParamDest`

**Files:**
- Create: `wms/models_domain/equivalence.py`
- Create: `wms/unit_equivalence.py`
- Modify: `wms/models.py`
- Modify: `wms/models_domain/billing.py`
- Modify: `wms/admin_billing.py`
- Modify: `wms/views_scan_billing.py`
- Create: `wms/planning/parameter_import.py`
- Create: `wms/management/commands/import_planning_parameters.py`
- Create: `wms/tests/planning/tests_parameter_import.py`
- Create: `wms/tests/planning/tests_unit_equivalence_shared.py`
- Modify: `wms/models_domain/planning.py`
- Modify: `wms/admin.py`
- Modify: `wms/billing_calculations.py`

**Step 1: Write the failing test**

Ajouter un test d'import qui lit un fichier fixture minimal et cree un `PlanningParameterSet` avec des lignes `PlanningDestinationRule`, puis un test qui verifie que l'equivalence partagee est resolue via un point d'entree transverse.

```python
from django.core.management import call_command
from django.test import TestCase

from wms.billing_calculations import ShipmentUnitInput
from wms.models import PlanningDestinationRule, PlanningParameterSet, ShipmentUnitEquivalenceRule
from wms.unit_equivalence import resolve_shipment_unit_count


class PlanningParameterImportTests(TestCase):
    def test_import_command_creates_parameter_rows(self):
        call_command(
            "import_planning_parameters",
            "wms/tests/fixtures/planning_parameters_minimal.xlsx",
            "--name",
            "Bootstrap mars 2026",
        )
        param_set = PlanningParameterSet.objects.get(name="Bootstrap mars 2026")
        self.assertTrue(
            PlanningDestinationRule.objects.filter(parameter_set=param_set).exists()
        )

    def test_billing_equivalence_rules_are_reused_for_planning_units(self):
        ShipmentUnitEquivalenceRule.objects.create(label="Defaut", units_per_item=2)
        total_units = resolve_shipment_unit_count(
            items=[ShipmentUnitInput(product=None, quantity=3)],
            rules=ShipmentUnitEquivalenceRule.objects.all(),
        )
        self.assertEqual(total_units, 6)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.planning.tests_parameter_import -v 2`
Expected: FAIL because the command and importer do not exist yet.

**Step 3: Write minimal implementation**

- Deplacer `ShipmentUnitEquivalenceRule` hors `wms/models_domain/billing.py` vers `wms/models_domain/equivalence.py`
- Creer `wms/unit_equivalence.py` comme point d'entree transverse pour `resolve_unit_equivalence_rule` et `resolve_shipment_unit_count`
- Faire consommer ce point d'entree par la facturation sans regression d'UI dans `scan/billing/equivalence`
- Creer `wms/planning/parameter_import.py` pour lire `ParamDest` uniquement
- Creer `wms/management/commands/import_planning_parameters.py`
- Ajouter une fixture Excel minimale dans `wms/tests/fixtures/`
- Rendre `PlanningDestinationRule` modifiable dans l'admin planning
- Laisser `ParamBenev` et `ParamExpediteur` venir de leurs domaines maitres, sans les dupliquer dans le planning

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.planning.tests_parameter_import -v 2`
- `./.venv/bin/python manage.py test wms.tests.planning.tests_unit_equivalence_shared -v 2`
- `./.venv/bin/python manage.py test wms.tests.management.tests_management_runtime_dependencies -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.test_views_scan_billing -v 2`

Expected: PASS and no unexpected runtime dependency regression.

**Step 5: Commit**

```bash
git add wms/models_domain/equivalence.py wms/unit_equivalence.py wms/models.py wms/models_domain/billing.py wms/admin_billing.py wms/views_scan_billing.py wms/planning/parameter_import.py wms/management/commands/import_planning_parameters.py wms/tests/planning/tests_parameter_import.py wms/tests/planning/tests_unit_equivalence_shared.py wms/tests/fixtures/planning_parameters_minimal.xlsx wms/models_domain/planning.py wms/admin.py wms/billing_calculations.py
git commit -m "feat(planning): import planning parameter sets from Excel"
```

### Task 4: Construire les sources internes, snapshots et validations du run

**Files:**
- Create: `wms/planning/__init__.py`
- Create: `wms/planning/sources.py`
- Create: `wms/planning/snapshots.py`
- Create: `wms/planning/validation.py`
- Create: `wms/tests/planning/tests_run_preparation.py`
- Modify: `wms/models_domain/planning.py`
- Modify: `wms/billing_calculations.py`

**Step 1: Write the failing test**

Ajouter un test de preparation de run qui:
- recupere des expeditions eligibles
- recupere des benevoles et disponibilites
- recupere les references expediteur depuis le domaine portal ou contacts
- fige les snapshots
- calcule la quantite equivalente de chaque expedition a partir du point d'entree partage d'equivalence
- produit une erreur bloquante si une destination n'a pas de regle planning

```python
from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.models import PlanningIssue, PlanningParameterSet, PlanningRun
from wms.planning.snapshots import prepare_run_inputs


class PlanningRunPreparationTests(TestCase):
    def test_prepare_run_records_issue_for_missing_destination_rule(self):
        user = get_user_model().objects.create_user(
            username="planner@example.com",
            email="planner@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        parameter_set = PlanningParameterSet.objects.create(name="Semaine 11", is_current=True)
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            parameter_set=parameter_set,
            created_by=user,
        )
        prepare_run_inputs(run)
        self.assertTrue(PlanningIssue.objects.filter(run=run, severity="error").exists())
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.planning.tests_run_preparation -v 2`
Expected: FAIL because the services do not exist yet.

**Step 3: Write minimal implementation**

- Implementer `wms/planning/sources.py` pour lire expeditions, destinations, benevoles et disponibilites depuis l'ORM
- Lire aussi les references expediteur utiles depuis `AssociationProfile`, `OrganizationContact` ou les objets portal ou contacts pertinents
- Implementer `wms/planning/snapshots.py` pour creer les snapshots de run et y figer les quantites equivalentes resolues
- Implementer `wms/planning/validation.py` pour produire les `PlanningIssue`
- Reutiliser `resolve_shipment_unit_count` pour la capacite vol plutot qu'une logique planning dupliquee
- Mettre a jour le statut du run selon le resultat de validation

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.planning.tests_run_preparation -v 2`
- `./.venv/bin/python manage.py test wms.tests.volunteer.tests_volunteer_models wms.tests.views.tests_views_tracking_dispute -v 2`

Expected: PASS and no regression on planning-related shipment status flows.

**Step 5: Commit**

```bash
git add wms/planning/__init__.py wms/planning/sources.py wms/planning/snapshots.py wms/planning/validation.py wms/tests/planning/tests_run_preparation.py wms/models_domain/planning.py wms/billing_calculations.py
git commit -m "feat(planning): add run snapshots and validation services"
```

### Task 5: Integrer les sources de vols hybrides API et Excel

**Files:**
- Create: `wms/planning/flight_sources.py`
- Create: `wms/tests/planning/tests_flight_sources.py`
- Modify: `wms/models_domain/planning.py`
- Modify: `wms/runtime_settings.py`

**Step 1: Write the failing test**

Ajouter des tests qui verifient:
- import d'un batch Excel minimal
- selection du mode `hybrid`
- normalisation des champs de vol avant snapshot

```python
from django.test import TestCase

from wms.planning.flight_sources import import_excel_flights


class FlightSourceTests(TestCase):
    def test_import_excel_flights_creates_batch_and_rows(self):
        batch = import_excel_flights("wms/tests/fixtures/flights_minimal.xlsx")
        self.assertEqual(batch.source, "excel")
        self.assertEqual(batch.flights.count(), 1)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.planning.tests_flight_sources -v 2`
Expected: FAIL because the source adapter does not exist yet.

**Step 3: Write minimal implementation**

- Implementer l'import Excel minimal dans `wms/planning/flight_sources.py`
- Ajouter un client API injectable pour le mode vols API
- Definir les reglages necessaires dans `wms/runtime_settings.py`
- Persister les `FlightSourceBatch` et `Flight`

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.planning.tests_flight_sources -v 2`
- `./.venv/bin/python manage.py test api.tests.tests_integration_filters api.tests.tests_permissions -v 2`

Expected: PASS with no regression on integration access patterns.

**Step 5: Commit**

```bash
git add wms/planning/flight_sources.py wms/tests/planning/tests_flight_sources.py wms/models_domain/planning.py wms/runtime_settings.py wms/tests/fixtures/flights_minimal.xlsx
git commit -m "feat(planning): add hybrid flight sources"
```

### Task 6: Porter les regles metier et brancher le solveur

**Files:**
- Create: `wms/planning/rules.py`
- Create: `wms/planning/solver.py`
- Create: `wms/tests/planning/tests_solver_contracts.py`
- Modify: `wms/planning/snapshots.py`
- Modify: `wms/models_domain/planning.py`
- Modify: `wms/billing_calculations.py`

**Step 1: Write the failing test**

Porter un test de contrat derive de `../asf_scheduler/new_repo/tests/test_solver_contracts.py` qui verifie qu'un run valide cree une version brouillon et des `PlanningAssignment`.

```python
from django.test import TestCase

from wms.models import PlanningAssignment, PlanningRun, PlanningVersion
from wms.planning.solver import solve_run


class PlanningSolverContractTests(TestCase):
    def test_solve_run_creates_draft_version_and_assignments(self):
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            status="ready",
        )
        version = solve_run(run)
        self.assertIsInstance(version, PlanningVersion)
        self.assertEqual(version.status, "draft")
        self.assertTrue(PlanningAssignment.objects.filter(version=version).exists())
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.planning.tests_solver_contracts -v 2`
Expected: FAIL because the rule compiler and solver adapter do not exist yet.

**Step 3: Write minimal implementation**

- Creer `wms/planning/rules.py` pour compiler les snapshots et regles en payload solveur
- Creer `wms/planning/solver.py` comme facade vers le solveur OR-Tools existant
- Copier ou adapter seulement les modules metier necessaires depuis `../asf_scheduler/new_repo/scheduler/`
- Utiliser `PlanningDestinationRule` comme source planning-owned pour les contraintes destination
- Utiliser les donnees `/benevole` comme source des contraintes benevole
- Utiliser les donnees `/portal` ou contacts comme source des caracteristiques expediteur
- Reutiliser les quantites equivalentes calculees depuis le point d'entree partage d'equivalence pour les contraintes de capacite vol
- Enregistrer dans le run le payload et le resultat solveur
- Creer la `PlanningVersion` brouillon initiale et les `PlanningAssignment`

**Step 4: Run tests to verify it passes**

Run:
- `ASF_TMP_DIR=/tmp/asf_wms_planning ./.venv/bin/python manage.py test wms.tests.planning.tests_solver_contracts -v 2`
- `ASF_TMP_DIR=/tmp/asf_wms_planning ./.venv/bin/python manage.py test wms.tests.planning.tests_run_preparation -v 2`

Expected: PASS with deterministic contract coverage around the solver adapter.

**Step 5: Commit**

```bash
git add wms/planning/rules.py wms/planning/solver.py wms/tests/planning/tests_solver_contracts.py wms/planning/snapshots.py wms/models_domain/planning.py wms/billing_calculations.py
git commit -m "feat(planning): port planning rules and solver"
```

### Task 7: Exposer les ecrans legacy Django pour les runs et la revue

**Files:**
- Create: `wms/planning_urls.py`
- Create: `wms/views_planning.py`
- Create: `wms/forms_planning.py`
- Modify: `asf_wms/urls.py`
- Create: `templates/planning/base.html`
- Create: `templates/planning/run_list.html`
- Create: `templates/planning/run_create.html`
- Create: `templates/planning/run_detail.html`
- Create: `wms/tests/views/tests_views_planning.py`

**Step 1: Write the failing test**

Ajouter les tests de vues pour:
- lister les runs
- creer un run
- afficher les issues et le bouton de lancement solveur

```python
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class PlanningViewTests(TestCase):
    def test_staff_can_open_planning_run_list(self):
        user = get_user_model().objects.create_superuser(
            username="admin@example.com",
            email="admin@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.client.force_login(user)
        response = self.client.get(reverse("planning:run_list"))
        self.assertEqual(response.status_code, 200)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_planning -v 2`
Expected: FAIL because the URLs and views do not exist yet.

**Step 3: Write minimal implementation**

- Monter `path("planning/", include("wms.planning_urls"))` dans `asf_wms/urls.py`
- Ajouter les vues de liste, creation, detail et lancement solveur dans `wms/views_planning.py`
- Ajouter les formulaires associes dans `wms/forms_planning.py`
- Ajouter les templates legacy Django sous `templates/planning/`

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_planning -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_portal_bootstrap_ui -v 2`

Expected: PASS and no shell-level template regression.

**Step 5: Commit**

```bash
git add wms/planning_urls.py wms/views_planning.py wms/forms_planning.py asf_wms/urls.py templates/planning/base.html templates/planning/run_list.html templates/planning/run_create.html templates/planning/run_detail.html wms/tests/views/tests_views_planning.py
git commit -m "feat(planning): add planning run views"
```

### Task 8: Ajouter l'edition manuelle, la publication et le diff entre versions

**Files:**
- Create: `wms/planning/versioning.py`
- Modify: `wms/views_planning.py`
- Modify: `wms/forms_planning.py`
- Create: `templates/planning/version_detail.html`
- Create: `templates/planning/version_diff.html`
- Create: `wms/tests/planning/tests_versioning.py`
- Modify: `wms/tests/views/tests_views_planning.py`

**Step 1: Write the failing test**

Ajouter un test qui verifie:
- duplication de `v1` vers `v2`
- modification manuelle d'une affectation
- publication de `v2`
- affichage du diff entre `v1` et `v2`

```python
from django.test import TestCase

from wms.models import PlanningVersion
from wms.planning.versioning import clone_version


class PlanningVersioningTests(TestCase):
    def test_clone_version_creates_new_draft_with_based_on_link(self):
        original = PlanningVersion.objects.create(number=1, status="published")
        clone = clone_version(original, created_by=None, change_reason="Maj vendredi")
        self.assertEqual(clone.status, "draft")
        self.assertEqual(clone.based_on, original)
```

**Step 2: Run test to verify it fails**

Run:
- `./.venv/bin/python manage.py test wms.tests.planning.tests_versioning -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_planning -v 2`

Expected: FAIL because version cloning and manual editing flows do not exist yet.

**Step 3: Write minimal implementation**

- Implementer `clone_version`, `publish_version` et `diff_versions` dans `wms/planning/versioning.py`
- Ajouter les formulaires et vues d'edition manuelle d'affectation
- Rendre une version publiee immutable
- Ajouter l'ecran de diff entre versions

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.planning.tests_versioning -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_planning -v 2`

Expected: PASS with manual edition and publication flows covered.

**Step 5: Commit**

```bash
git add wms/planning/versioning.py wms/views_planning.py wms/forms_planning.py templates/planning/version_detail.html templates/planning/version_diff.html wms/tests/planning/tests_versioning.py wms/tests/views/tests_views_planning.py
git commit -m "feat(planning): add manual editing and versioning"
```

### Task 9: Generer exports, brouillons de communication et statistiques par version

**Files:**
- Create: `wms/planning/communications.py`
- Create: `wms/planning/exports.py`
- Create: `wms/planning/stats.py`
- Create: `wms/tests/planning/tests_outputs.py`
- Modify: `wms/views_planning.py`
- Modify: `wms/models_domain/planning.py`

**Step 1: Write the failing test**

Ajouter des tests qui verifient:
- generation de `CommunicationDraft` pour une version publiee
- regeneration d'une nouvelle serie de brouillons pour `v2`
- creation d'un `PlanningArtifact` Excel
- calcul d'un resume statistique simple

```python
from django.test import TestCase

from wms.models import CommunicationDraft, PlanningArtifact
from wms.planning.communications import generate_version_drafts
from wms.planning.exports import export_version_workbook


class PlanningOutputTests(TestCase):
    def test_generate_drafts_and_excel_artifact_for_version(self):
        version = self.make_published_version()
        generate_version_drafts(version)
        artifact = export_version_workbook(version)
        self.assertTrue(CommunicationDraft.objects.filter(version=version).exists())
        self.assertIsInstance(artifact, PlanningArtifact)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.planning.tests_outputs -v 2`
Expected: FAIL because the output services do not exist yet.

**Step 3: Write minimal implementation**

- Implementer `wms/planning/communications.py` avec `CommunicationTemplate` et `CommunicationDraft`
- Implementer `wms/planning/exports.py` pour produire un `Planning.xlsx` de transition
- Implementer `wms/planning/stats.py` pour les indicateurs de base par version
- Brancher ces actions dans `wms/views_planning.py`

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.planning.tests_outputs -v 2`
- `./.venv/bin/python manage.py test wms.tests.emailing.tests_emailing -v 2`

Expected: PASS and no regression on email queue behavior.

**Step 5: Commit**

```bash
git add wms/planning/communications.py wms/planning/exports.py wms/planning/stats.py wms/tests/planning/tests_outputs.py wms/views_planning.py wms/models_domain/planning.py
git commit -m "feat(planning): add exports, communication drafts, and stats"
```

### Task 10: Brancher les mises a jour expedition et la compatibilite transitoire

**Files:**
- Create: `wms/planning/shipment_updates.py`
- Create: `wms/tests/planning/tests_shipment_updates.py`
- Modify: `wms/views_planning.py`
- Optional Modify: `api/v1/views.py`
- Optional Modify: `api/v1/serializers.py`
- Optional Modify: `api/v1/urls.py`

**Step 1: Write the failing test**

Ajouter un test qui verifie qu'une version publiee peut appliquer les mises a jour expeditions autorisees sans ecraser les versions precedentes, et un test optionnel de compatibilite API si l'ancien scheduler doit encore cohabiter.

```python
from django.test import TestCase

from wms.planning.shipment_updates import apply_version_updates


class PlanningShipmentUpdateTests(TestCase):
    def test_apply_version_updates_marks_shipments_planned(self):
        version = self.make_published_version()
        apply_version_updates(version, actor_name="planner")
        self.assertShipmentStatusesUpdated(version)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.planning.tests_shipment_updates -v 2`
Expected: FAIL because the shipment update service does not exist yet.

**Step 3: Write minimal implementation**

- Implementer `wms/planning/shipment_updates.py`
- Rattacher les evenements metier aux expeditons concernees
- Brancher l'action dans `wms/views_planning.py`
- Si coexistence transitoire avec l'ancien scheduler necessaire, ajouter des endpoints de compatibilite en `api/v1/` pour benevoles, references expediteur portal ou contacts, destinations planning et equivalence partagee

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.planning.tests_shipment_updates -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_tracking_dispute api.tests.tests -v 2`

Expected: PASS with planning-side updates and no integration regression.

**Step 5: Commit**

```bash
git add wms/planning/shipment_updates.py wms/tests/planning/tests_shipment_updates.py wms/views_planning.py api/v1/views.py api/v1/serializers.py api/v1/urls.py
git commit -m "feat(planning): connect shipment updates and migration compatibility"
```

### Task 11: Verification finale et documentation operateur

**Files:**
- Modify: `docs/plans/2026-03-08-planning-module-design.md`
- Modify: `docs/plans/2026-03-08-planning-module-implementation-plan.md`
- Create: `docs/plans/2026-03-08-planning-module-verification.md`

**Step 1: Write the failing test**

Pas de test unitaire a ecrire ici. Definir a la place une check-list de verification manuelle:
- creation de run
- validation bloquante
- solveur
- correction manuelle
- publication v1
- duplication v2
- regeneration des brouillons
- export Excel

**Step 2: Run verification commands**

Run:
- `ASF_TMP_DIR=/tmp/asf_wms_planning ./.venv/bin/python manage.py test wms.tests.planning -v 2`
- `ASF_TMP_DIR=/tmp/asf_wms_planning ./.venv/bin/python manage.py test wms.tests.views.tests_views_planning wms.tests.views.tests_views_volunteer api.tests.tests -v 2`

Expected: PASS on the new planning suite and key legacy integrations.

**Step 3: Write verification note**

- Documenter les commandes executees, les resultats et les limites restantes dans `docs/plans/2026-03-08-planning-module-verification.md`
- Mettre a jour si besoin le design et le plan avec les ecarts reels observes

**Step 4: Commit**

```bash
git add docs/plans/2026-03-08-planning-module-design.md docs/plans/2026-03-08-planning-module-implementation-plan.md docs/plans/2026-03-08-planning-module-verification.md
git commit -m "docs(planning): add verification notes"
```
