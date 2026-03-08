# Benevole Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrer un portail benevole legacy sous `/benevole/` dans `asf-wms`, avec une V1 admin-managed puis une V1.5 a demande de compte approuvee par superuser.

**Architecture:** Garder `asf-wms` comme unique projet Django, ajouter un domaine interne `volunteer` branche sur le `User` existant, isoler la surface utilisateur dans des URLs et templates `benevole`, et reutiliser les briques portal existantes pour l'authentification, le changement de mot de passe et les emails de premier acces. Le travail avance en phases courtes: domaine, auth, vues metier V1, puis flux de demande de compte V1.5.

**Tech Stack:** Django 4.2, ORM Django, formulaires Django, templates Django legacy, admin Django, `manage.py test`.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:systematic-debugging`, `@superpowers:verification-before-completion`, `@superpowers:requesting-code-review`, `@superpowers:using-git-worktrees`.

### Task 1: Poser le domaine volunteer et ses exports

**Files:**
- Create: `wms/models_domain/volunteer.py`
- Modify: `wms/models.py`
- Create: `wms/tests/volunteer/tests_volunteer_models.py`
- Modify: `wms/migrations/` via `makemigrations`

**Step 1: Write the failing test**

Ajouter les tests de modele qui couvrent le domaine minimal.

```python
from datetime import time

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from wms.models import VolunteerAvailability, VolunteerProfile, VolunteerUnavailability


class VolunteerModelTests(TestCase):
    def test_volunteer_profile_assigns_next_volunteer_id(self):
        user = get_user_model().objects.create_user(
            username="volunteer@example.com",
            email="volunteer@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        profile = VolunteerProfile.objects.create(user=user)
        self.assertEqual(profile.volunteer_id, 1)

    def test_availability_rejects_overlaps(self):
        user = get_user_model().objects.create_user(
            username="overlap@example.com",
            email="overlap@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        profile = VolunteerProfile.objects.create(user=user)
        VolunteerAvailability.objects.create(
            volunteer=profile,
            date="2026-03-09",
            start_time=time(9, 0),
            end_time=time(11, 0),
        )
        overlapping = VolunteerAvailability(
            volunteer=profile,
            date="2026-03-09",
            start_time=time(10, 0),
            end_time=time(12, 0),
        )
        with self.assertRaises(ValidationError):
            overlapping.full_clean()

    def test_unavailability_is_unique_per_day(self):
        user = get_user_model().objects.create_user(
            username="unique@example.com",
            email="unique@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        profile = VolunteerProfile.objects.create(user=user)
        VolunteerUnavailability.objects.create(volunteer=profile, date="2026-03-10")
        with self.assertRaises(Exception):
            VolunteerUnavailability.objects.create(volunteer=profile, date="2026-03-10")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.volunteer.tests_volunteer_models -v 2`
Expected: FAIL because the volunteer models do not exist yet.

**Step 3: Write minimal implementation**

- Ajouter `VolunteerProfile`, `VolunteerConstraint`, `VolunteerAvailability`, `VolunteerUnavailability`, `VolunteerAccountRequest` dans `wms/models_domain/volunteer.py`.
- Garder `contact` nullable sur `VolunteerProfile`.
- Exporter les classes dans `wms/models.py`.
- Generer la migration:

```bash
./.venv/bin/python manage.py makemigrations wms
```

Exemple de noyau pour `VolunteerProfile`:

```python
class VolunteerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="volunteer_profile",
    )
    contact = models.ForeignKey(
        "contacts.Contact",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="volunteer_profiles",
    )
    volunteer_id = models.PositiveIntegerField(unique=True, blank=True, null=True)
    must_change_password = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.volunteer_id:
            max_id = self.__class__.objects.aggregate(Max("volunteer_id")).get("volunteer_id__max") or 0
            self.volunteer_id = max_id + 1
        super().save(*args, **kwargs)
```

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.volunteer.tests_volunteer_models -v 2`
- `./.venv/bin/python manage.py test wms.tests.portal.tests_portal_permissions -v 2`

Expected: PASS for the new volunteer model tests and no regression on existing portal permission imports.

**Step 5: Commit**

```bash
git add wms/models_domain/volunteer.py wms/models.py wms/tests/volunteer/tests_volunteer_models.py wms/migrations
git commit -m "feat(volunteer): add volunteer domain models"
```

### Task 2: Ajouter les permissions volunteer et l'admin V1

**Files:**
- Modify: `wms/view_permissions.py`
- Modify: `wms/admin.py`
- Create: `wms/tests/volunteer/tests_volunteer_permissions.py`
- Create: `wms/tests/admin/tests_admin_volunteer.py`

**Step 1: Write the failing test**

Ajouter un test de permission et un test admin.

```python
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from wms.models import VolunteerProfile
from wms.view_permissions import volunteer_required


class VolunteerPermissionTests(TestCase):
    def test_volunteer_required_rejects_user_without_profile(self):
        user = get_user_model().objects.create_user(
            username="plain@example.com",
            email="plain@example.com",
            password="pass1234",  # pragma: allowlist secret
        )

        @volunteer_required
        def sample_view(request):
            return HttpResponse("ok")

        request = RequestFactory().get("/benevole/")
        request.user = user
        with self.assertRaises(PermissionDenied):
            sample_view(request)
```

```python
class VolunteerAdminTests(TestCase):
    def test_volunteer_profile_is_registered(self):
        self.assertIn(VolunteerProfile, admin.site._registry)
```

**Step 2: Run test to verify it fails**

Run:
- `./.venv/bin/python manage.py test wms.tests.volunteer.tests_volunteer_permissions -v 2`
- `./.venv/bin/python manage.py test wms.tests.admin.tests_admin_volunteer -v 2`

Expected: FAIL because no volunteer permission helper or admin registration exists yet.

**Step 3: Write minimal implementation**

- Ajouter `volunteer_required` dans `wms/view_permissions.py`.
- Verifier `request.user.volunteer_profile`, `profile.is_active` et `profile.must_change_password`.
- Enregistrer `VolunteerProfile`, `VolunteerConstraint`, `VolunteerAvailability`, `VolunteerUnavailability` dans `wms/admin.py`.
- Ajouter une action admin simple pour marquer `must_change_password=True`.

Exemple de decorateur:

```python
def volunteer_required(view):
    @login_required(login_url="volunteer:login")
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        profile = getattr(request.user, "volunteer_profile", None)
        if not profile or not profile.is_active:
            raise PermissionDenied
        if profile.must_change_password and request.path != reverse("volunteer:change_password"):
            return redirect("volunteer:change_password")
        request.volunteer_profile = profile
        return view(request, *args, **kwargs)

    return wrapped
```

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.volunteer.tests_volunteer_permissions -v 2`
- `./.venv/bin/python manage.py test wms.tests.admin.tests_admin_volunteer -v 2`

Expected: PASS with the decorator and admin registrations behaving as expected.

**Step 5: Commit**

```bash
git add wms/view_permissions.py wms/admin.py wms/tests/volunteer/tests_volunteer_permissions.py wms/tests/admin/tests_admin_volunteer.py
git commit -m "feat(volunteer): add volunteer permissions and admin"
```

### Task 3: Monter les URLs volunteer et l'authentification dediee

**Files:**
- Modify: `asf_wms/urls.py`
- Create: `wms/volunteer_urls.py`
- Create: `wms/views_volunteer_auth.py`
- Modify: `wms/views.py`
- Create: `templates/benevole/base.html`
- Create: `templates/benevole/login.html`
- Create: `templates/benevole/change_password.html`
- Create: `wms/tests/views/tests_views_volunteer.py`

**Step 1: Write the failing test**

Ajouter les premiers tests de login et de redirection.

```python
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from wms.models import VolunteerProfile


class VolunteerAuthViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="benevole@example.com",
            email="benevole@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.profile = VolunteerProfile.objects.create(
            user=self.user,
            must_change_password=False,
        )

    def test_login_accepts_email_and_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("volunteer:login"),
            {"identifier": "benevole@example.com", "password": "pass1234"},  # pragma: allowlist secret
        )
        self.assertRedirects(response, reverse("volunteer:dashboard"))

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("volunteer:dashboard"))
        self.assertRedirects(response, f"{reverse('volunteer:login')}?next={reverse('volunteer:dashboard')}")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer.VolunteerAuthViewTests -v 2`
Expected: FAIL because the volunteer URLs and auth views do not exist.

**Step 3: Write minimal implementation**

- Ajouter le prefixe `benevole/` dans `asf_wms/urls.py`.
- Creer `wms/volunteer_urls.py` avec `app_name = "volunteer"`.
- Creer `wms/views_volunteer_auth.py` en reprenant la logique email/password de `wms/views_portal_auth.py`.
- Re-exporter les vues utiles dans `wms/views.py`.

Exemple d'URL set:

```python
urlpatterns = [
    path("login/", views.volunteer_login, name="login"),
    path("logout/", views.volunteer_logout, name="logout"),
    path("change-password/", views.volunteer_change_password, name="change_password"),
    path("", views.volunteer_dashboard, name="dashboard"),
]
```

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer.VolunteerAuthViewTests -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_home -v 2`

Expected: PASS for volunteer auth and no regression on root/home routing.

**Step 5: Commit**

```bash
git add asf_wms/urls.py wms/volunteer_urls.py wms/views_volunteer_auth.py wms/views.py templates/benevole/base.html templates/benevole/login.html templates/benevole/change_password.html wms/tests/views/tests_views_volunteer.py
git commit -m "feat(volunteer): add volunteer auth routes"
```

### Task 4: Porter le dashboard, le profil et les contraintes benevoles

**Files:**
- Create: `wms/forms_volunteer.py`
- Create: `wms/views_volunteer.py`
- Create: `templates/benevole/dashboard.html`
- Create: `templates/benevole/profile.html`
- Create: `templates/benevole/constraints.html`
- Modify: `wms/volunteer_urls.py`
- Modify: `wms/tests/views/tests_views_volunteer.py`

**Step 1: Write the failing test**

Ajouter les tests sur les vues connectees.

```python
class VolunteerProfileViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="profile@example.com",
            email="profile@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.profile = VolunteerProfile.objects.create(user=self.user, phone="+33601020304")
        self.client.force_login(self.user)

    def test_dashboard_renders_recent_availabilities(self):
        response = self.client.get(reverse("volunteer:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tableau de bord")

    def test_profile_update_persists_changes(self):
        response = self.client.post(
            reverse("volunteer:profile"),
            {
                "first_name": "Luc",
                "last_name": "Martin",
                "phone": "+33611223344",
                "address_line1": "10 rue Test",
                "postal_code": "75001",
                "city": "Paris",
                "country": "France",
            },
        )
        self.assertRedirects(response, reverse("volunteer:profile"))
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer.VolunteerProfileViewTests -v 2`
Expected: FAIL because the dashboard/profile/constraints views and forms are not implemented.

**Step 3: Write minimal implementation**

- Creer `AccountForm`, `VolunteerProfileForm`, `VolunteerConstraintForm` dans `wms/forms_volunteer.py`.
- Ajouter les vues `volunteer_dashboard`, `volunteer_profile`, `volunteer_constraints` dans `wms/views_volunteer.py`.
- Brancher les routes.
- Reprendre la logique metier de `asf-benev/volunteers/views.py` en l'adaptant a `VolunteerProfile`.

Exemple de vue:

```python
@volunteer_required
def volunteer_profile(request):
    profile = request.volunteer_profile
    if request.method == "POST":
        account_form = VolunteerAccountForm(request.POST, instance=request.user)
        profile_form = VolunteerProfileForm(request.POST, instance=profile)
        if account_form.is_valid() and profile_form.is_valid():
            account_form.save()
            profile_form.save()
            messages.success(request, "Coordonnees mises a jour.")
            return redirect("volunteer:profile")
    else:
        account_form = VolunteerAccountForm(instance=request.user)
        profile_form = VolunteerProfileForm(instance=profile)
    return render(request, "benevole/profile.html", {...})
```

**Step 4: Run tests to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer.VolunteerProfileViewTests -v 2`
Expected: PASS with dashboard, profile update and constraints editing working.

**Step 5: Commit**

```bash
git add wms/forms_volunteer.py wms/views_volunteer.py templates/benevole/dashboard.html templates/benevole/profile.html templates/benevole/constraints.html wms/volunteer_urls.py wms/tests/views/tests_views_volunteer.py
git commit -m "feat(volunteer): add volunteer dashboard profile and constraints"
```

### Task 5: Porter les disponibilites et le recap hebdomadaire

**Files:**
- Modify: `wms/forms_volunteer.py`
- Modify: `wms/views_volunteer.py`
- Create: `templates/benevole/availability_list.html`
- Create: `templates/benevole/availability_form.html`
- Create: `templates/benevole/availability_confirm_delete.html`
- Create: `templates/benevole/availability_recap.html`
- Modify: `wms/volunteer_urls.py`
- Modify: `wms/tests/views/tests_views_volunteer.py`

**Step 1: Write the failing test**

Ajouter les tests CRUD et recap.

```python
class VolunteerAvailabilityViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="availability@example.com",
            email="availability@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.profile = VolunteerProfile.objects.create(user=self.user)
        self.client.force_login(self.user)

    def test_create_weekly_availability_redirects_to_list(self):
        response = self.client.post(
            reverse("volunteer:availability_create"),
            {
                "form-TOTAL_FORMS": "7",
                "form-INITIAL_FORMS": "0",
                "form-0-date": "2026-03-09",
                "form-0-availability": "available",
                "form-0-start_time": "09:00",
                "form-0-end_time": "12:00",
            },
        )
        self.assertRedirects(response, reverse("volunteer:availability_list"))

    def test_recap_renders_week_rows(self):
        response = self.client.get(reverse("volunteer:availability_recap"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Semaine")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer.VolunteerAvailabilityViewTests -v 2`
Expected: FAIL because availability views and templates are missing.

**Step 3: Write minimal implementation**

- Ajouter `AvailabilityForm`, `AvailabilityWeekForm`, `VolunteerAvailabilityWeekFormSet` dans `wms/forms_volunteer.py`.
- Porter `_resolve_week_start`, `_iter_week_ranges`, `_build_week_days` dans `wms/views_volunteer.py`.
- Ajouter les vues `volunteer_availability_list`, `volunteer_availability_create`, `volunteer_availability_update`, `volunteer_availability_delete`, `volunteer_availability_recap`.
- Brancher les templates dedies `templates/benevole/*`.

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer.VolunteerAvailabilityViewTests -v 2`
- `./.venv/bin/python manage.py test wms.tests.volunteer.tests_volunteer_models -v 2`

Expected: PASS with creation, edition, suppression and recap covered.

**Step 5: Commit**

```bash
git add wms/forms_volunteer.py wms/views_volunteer.py templates/benevole/availability_list.html templates/benevole/availability_form.html templates/benevole/availability_confirm_delete.html templates/benevole/availability_recap.html wms/volunteer_urls.py wms/tests/views/tests_views_volunteer.py
git commit -m "feat(volunteer): add volunteer availability workflows"
```

### Task 6: Ajouter les helpers d'acces initial admin-managed

**Files:**
- Create: `wms/volunteer_access.py`
- Create: `templates/emails/volunteer_access_created.txt`
- Modify: `wms/admin.py`
- Create: `wms/tests/emailing/tests_volunteer_email_flows.py`
- Modify: `wms/tests/admin/tests_admin_volunteer.py`

**Step 1: Write the failing test**

Ajouter un test sur l'action admin ou helper de reset d'acces.

```python
class VolunteerAccessHelpersTests(TestCase):
    def test_builds_set_password_url_for_volunteer(self):
        user = get_user_model().objects.create_user(
            username="access@example.com",
            email="access@example.com",
        )
        profile = VolunteerProfile.objects.create(user=user, must_change_password=True)
        request = RequestFactory().get("/admin/")
        request.user = get_user_model().objects.create_superuser("admin", "admin@example.com", "pass1234")  # pragma: allowlist secret
        login_url, set_password_url = build_volunteer_urls(request=request, user=user)
        self.assertIn("/benevole/login/", login_url)
        self.assertIn("/benevole/set-password/", set_password_url)
```

**Step 2: Run test to verify it fails**

Run:
- `./.venv/bin/python manage.py test wms.tests.admin.tests_admin_volunteer -v 2`
- `./.venv/bin/python manage.py test wms.tests.emailing.tests_volunteer_email_flows -v 2`

Expected: FAIL because the access helper and volunteer email template do not exist.

**Step 3: Write minimal implementation**

- Creer `wms/volunteer_access.py` pour construire URLs login/set-password et envoyer l'email.
- Ajouter une route `volunteer_set_password` dans `wms/views_volunteer_auth.py`.
- Ajouter l'action admin "Envoyer acces benevole" ou "Reinitialiser acces benevole".
- Utiliser `default_token_generator` comme cote portail.

Exemple:

```python
def build_volunteer_urls(*, request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    login_url = request.build_absolute_uri(reverse("volunteer:login"))
    set_password_url = request.build_absolute_uri(reverse("volunteer:set_password", args=[uid, token]))
    return login_url, set_password_url
```

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.admin.tests_admin_volunteer -v 2`
- `./.venv/bin/python manage.py test wms.tests.emailing.tests_volunteer_email_flows -v 2`

Expected: PASS with access reset and email generation working.

**Step 5: Commit**

```bash
git add wms/volunteer_access.py wms/admin.py wms/views_volunteer_auth.py templates/emails/volunteer_access_created.txt wms/tests/admin/tests_admin_volunteer.py wms/tests/emailing/tests_volunteer_email_flows.py
git commit -m "feat(volunteer): add volunteer access reset flow"
```

### Task 7: Ajouter le modele `VolunteerAccountRequest` et son admin V1.5

**Files:**
- Modify: `wms/models_domain/volunteer.py`
- Create: `wms/volunteer_account_request_handlers.py`
- Modify: `wms/admin.py`
- Create: `templates/emails/volunteer_account_request_received.txt`
- Create: `templates/emails/volunteer_account_approved.txt`
- Create: `wms/tests/volunteer/tests_volunteer_account_requests.py`
- Modify: `wms/tests/admin/tests_admin_volunteer.py`
- Modify: `wms/migrations/` via `makemigrations`

**Step 1: Write the failing test**

Ajouter un test d'approbation.

```python
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from wms.models import VolunteerAccountRequest, VolunteerProfile
from wms.volunteer_account_request_handlers import approve_volunteer_account_request


class VolunteerAccountRequestTests(TestCase):
    def test_approving_request_creates_user_and_profile(self):
        admin_user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        request = RequestFactory().post("/admin/")
        request.user = admin_user
        account_request = VolunteerAccountRequest.objects.create(
            first_name="Lou",
            last_name="Durand",
            email="lou@example.com",
            status="pending",
        )
        ok, reason = approve_volunteer_account_request(request=request, account_request=account_request)
        self.assertTrue(ok)
        self.assertEqual(reason, "")
        self.assertTrue(VolunteerProfile.objects.filter(user__email="lou@example.com").exists())
```

**Step 2: Run test to verify it fails**

Run:
- `./.venv/bin/python manage.py test wms.tests.volunteer.tests_volunteer_account_requests -v 2`
- `./.venv/bin/python manage.py test wms.tests.admin.tests_admin_volunteer -v 2`

Expected: FAIL because the request model and approval handler are incomplete.

**Step 3: Write minimal implementation**

- Completer `VolunteerAccountRequest` avec statuts et metadonnees de revue.
- Creer `approve_volunteer_account_request` dans `wms/volunteer_account_request_handlers.py`.
- Enregistrer l'admin dedie avec actions `approve_requests` et `reject_requests`.
- Reutiliser `build_volunteer_urls` pour envoyer le lien de set-password.

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.volunteer.tests_volunteer_account_requests -v 2`
- `./.venv/bin/python manage.py test wms.tests.admin.tests_admin_volunteer -v 2`

Expected: PASS with approval, rejection and email generation handled.

**Step 5: Commit**

```bash
git add wms/models_domain/volunteer.py wms/volunteer_account_request_handlers.py wms/admin.py templates/emails/volunteer_account_request_received.txt templates/emails/volunteer_account_approved.txt wms/tests/volunteer/tests_volunteer_account_requests.py wms/tests/admin/tests_admin_volunteer.py wms/migrations
git commit -m "feat(volunteer): add volunteer account request approval flow"
```

### Task 8: Exposer la page publique `/benevole/request-account/` et fermer la boucle V1.5

**Files:**
- Create: `wms/views_volunteer_account_request.py`
- Modify: `wms/volunteer_urls.py`
- Modify: `wms/views.py`
- Modify: `wms/forms_volunteer.py`
- Create: `templates/benevole/request_account.html`
- Create: `templates/benevole/request_account_done.html`
- Create: `wms/tests/views/tests_views_volunteer_account_request.py`
- Modify: `templates/home.html`

**Step 1: Write the failing test**

Ajouter les tests publics de demande de compte.

```python
from django.test import TestCase
from django.urls import reverse

from wms.models import VolunteerAccountRequest


class VolunteerAccountRequestViewTests(TestCase):
    def test_public_request_creates_pending_request(self):
        response = self.client.post(
            reverse("volunteer:request_account"),
            {
                "first_name": "Lou",
                "last_name": "Durand",
                "email": "lou@example.com",
                "phone": "+33601020304",
                "address_line1": "10 rue Test",
                "postal_code": "75001",
                "city": "Paris",
                "country": "France",
            },
        )
        self.assertRedirects(response, reverse("volunteer:request_account_done"))
        self.assertEqual(VolunteerAccountRequest.objects.get().status, "pending")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer_account_request -v 2`
Expected: FAIL because the public volunteer request page and form do not exist.

**Step 3: Write minimal implementation**

- Creer `VolunteerAccountRequestForm` dans `wms/forms_volunteer.py`.
- Creer `wms/views_volunteer_account_request.py` avec une vue publique POST/GET.
- Ajouter les templates `request_account` et `request_account_done`.
- Brancher les URLs et un lien discret depuis `templates/home.html`.
- Throttler la creation par email et IP en reutilisant les patterns de `wms/account_request_handlers.py`.

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer_account_request -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer -v 2`
- `./.venv/bin/python manage.py test wms.tests.volunteer.tests_volunteer_account_requests -v 2`

Expected: PASS with public request creation, confirmation page and no regression on authenticated volunteer flows.

**Step 5: Commit**

```bash
git add wms/views_volunteer_account_request.py wms/volunteer_urls.py wms/views.py wms/forms_volunteer.py templates/benevole/request_account.html templates/benevole/request_account_done.html templates/home.html wms/tests/views/tests_views_volunteer_account_request.py
git commit -m "feat(volunteer): add public volunteer account request pages"
```

### Task 9: Executer la verification finale du lot benevole

**Files:**
- Modify: `docs/plans/2026-03-08-benevole-integration-design.md`
- Modify: `docs/plans/2026-03-08-benevole-integration-implementation-plan.md`

**Step 1: Write the failing test**

Il n'y a pas de nouveau test a ecrire ici. A la place, construire la checklist de verification finale a partir du design:
- routes `/benevole/*` presentes
- auth dediee
- V1 admin-managed complete
- V1.5 request-account complete
- aucun impact sur `/portal/` et `/scan/`

**Step 2: Run test to verify it fails**

Run:
- `./.venv/bin/python manage.py test wms.tests.volunteer -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer wms.tests.views.tests_views_volunteer_account_request -v 2`
- `./.venv/bin/python manage.py test wms.tests.admin.tests_admin_volunteer wms.tests.emailing.tests_volunteer_email_flows -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal -v 2`

Expected: at least one failure if any integration gap remains.

**Step 3: Write minimal implementation**

- Corriger uniquement les regressions constatees.
- Mettre a jour le design ou le plan si un ecart volontaire apparait pendant l'execution.
- Ne pas elargir le scope au-dela du portail benevole legacy.

**Step 4: Run tests to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.volunteer -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer wms.tests.views.tests_views_volunteer_account_request -v 2`
- `./.venv/bin/python manage.py test wms.tests.admin.tests_admin_volunteer wms.tests.emailing.tests_volunteer_email_flows -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal -v 2`

Expected: PASS with targeted volunteer coverage plus portal regression coverage.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-08-benevole-integration-design.md docs/plans/2026-03-08-benevole-integration-implementation-plan.md
git commit -m "docs: finalize benevole rollout verification notes"
```

## Execution Notes

Verification du 2026-03-08:
- `./.venv/bin/python manage.py test wms.tests.volunteer -v 2`: OK
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer wms.tests.views.tests_views_volunteer_account_request -v 2`: OK
- `./.venv/bin/python manage.py test wms.tests.admin.tests_admin_volunteer wms.tests.emailing.tests_volunteer_email_flows -v 2`: OK
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal -v 2`: 2 echecs hors scope benevole

Echecs `portal` verifies aussi sur le commit de base `c20bc55`, donc preexistants:
- `wms.tests.views.tests_views_portal.PortalAccountViewsTests.test_portal_recipients_post_creates_recipient_with_native_english_message`
- `wms.tests.views.tests_views_portal.PortalOrdersViewsTests.test_portal_order_create_post_success_uses_native_english_message`
