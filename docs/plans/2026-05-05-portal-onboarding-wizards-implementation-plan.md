# Portal Onboarding Wizards Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add role-specific portal onboarding wizards for shipper and recipient users, shown automatically once per login/session while enabled and always available from the portal masthead.

**Architecture:** Keep the implementation on the legacy Django portal stack. Store onboarding preferences per user and active portal scope, build wizard payloads in a small `wms/application/portal/` helper, and render a Bootstrap modal from the existing portal shell without changing portal business rules.

**Tech Stack:** Django models/migrations/views/templates, Bootstrap 5 modal, vanilla portal JavaScript, Django test runner.

---

## Global Constraints

- Do not touch `frontend-next/`, `wms/views_next_frontend.py`, or Next migration files.
- Do not modify `locale/`; translation scope remains paused.
- The wizard is informational only. It must not change account review, recipient validation, product preference semantics, order validation, access grants, or billing behavior.
- Automatic display happens only after an active portal scope exists. Do not auto-display on `/portal/scope-select/`.
- Automatic display should happen once per session per scope while enabled. If the user leaves the checkbox checked, it should show again on the next login/session, not on every page navigation.
- Commit steps below require explicit user approval before execution, per `AGENTS.md`.

## Preflight

Run:

```bash
git status --short
sed -n '1,220p' docs/repo-reference/03b-impact-portal.md
sed -n '1,220p' docs/repo-reference/04-shared-contracts/02-ui-shell-contracts.md
sed -n '1,220p' docs/repo-reference/04-shared-contracts/04-portal-parties.md
```

Expected:

- note any unrelated dirty files and leave them untouched
- confirm the change is limited to portal UI/access-shell behavior

## Task 1: Add Portal Onboarding Preference Model

**Files:**

- Modify: `wms/models_domain/portal.py`
- Modify: `wms/models.py`
- Create: `wms/migrations/0126_portalonboardingpreference.py` via `makemigrations`
- Test: `wms/tests/portal/tests_portal_onboarding.py`

**Step 1: Write failing model tests**

Create `wms/tests/portal/tests_portal_onboarding.py` with tests shaped like:

```python
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    AssociationProfile,
    PortalAccessRole,
    PortalOnboardingPreference,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentValidationStatus,
)


class PortalOnboardingPreferenceModelTests(TestCase):
    def test_shipper_preference_defaults_to_show_on_next_login(self):
        user = get_user_model().objects.create_user(
            username="portal-onboarding-shipper",
            email="portal-onboarding-shipper@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        organization = Contact.objects.create(
            name="Association Onboarding",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper = ShipmentShipper.objects.create(
            organization=organization,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )

        preference = PortalOnboardingPreference.objects.create(
            user=user,
            role=PortalAccessRole.SHIPPER_ADMIN,
            shipper=shipper,
        )

        self.assertTrue(preference.show_on_next_login)

    def test_preference_requires_exactly_one_scope_target(self):
        user = get_user_model().objects.create_user(
            username="portal-onboarding-invalid",
            email="portal-onboarding-invalid@example.com",
            password="pass1234",  # pragma: allowlist secret
        )

        preference = PortalOnboardingPreference(
            user=user,
            role=PortalAccessRole.SHIPPER_ADMIN,
        )

        with self.assertRaises(ValidationError):
            preference.full_clean()
```

Add tests for:

- recipient scope target
- legacy `AssociationProfile` fallback target
- duplicate preference blocked for the same user/role/scope

**Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python manage.py test wms.tests.portal.tests_portal_onboarding -v 2
```

Expected:

- FAIL because `PortalOnboardingPreference` does not exist.

**Step 3: Add model**

Add `PortalOnboardingPreference` in `wms/models_domain/portal.py`.

Use fields:

```python
class PortalOnboardingPreference(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portal_onboarding_preferences",
    )
    role = models.CharField(max_length=40, choices=PortalAccessRole.choices)
    shipper = models.ForeignKey(
        "wms.ShipmentShipper",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="portal_onboarding_preferences",
    )
    recipient_organization = models.ForeignKey(
        "wms.ShipmentRecipientOrganization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="portal_onboarding_preferences",
    )
    association_profile = models.ForeignKey(
        "wms.AssociationProfile",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="portal_onboarding_preferences",
    )
    show_on_next_login = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

Add validation:

- exactly one of `shipper`, `recipient_organization`, `association_profile`
- `recipient_organization` only with `recipient_admin`
- `shipper` or `association_profile` only with `shipper_admin`

Add conditional unique constraints:

- `["user", "role", "shipper"]` where `shipper__isnull=False`
- `["user", "role", "recipient_organization"]` where `recipient_organization__isnull=False`
- `["user", "role", "association_profile"]` where `association_profile__isnull=False`

Re-export from `wms/models.py` following the existing domain model import pattern.

**Step 4: Create migration**

Run:

```bash
.venv/bin/python manage.py makemigrations wms
```

Expected:

- creates the next migration after `0125_shipment_planned_carton_count.py`
- migration contains only `PortalOnboardingPreference`

**Step 5: Run model tests**

Run:

```bash
.venv/bin/python manage.py test wms.tests.portal.tests_portal_onboarding -v 2
```

Expected:

- PASS

**Step 6: Prepare commit after explicit approval**

```bash
git add wms/models_domain/portal.py wms/models.py wms/migrations/0126_portalonboardingpreference.py wms/tests/portal/tests_portal_onboarding.py
git commit -m "feat: store portal onboarding preferences"
```

## Task 2: Add Onboarding Application Helper

**Files:**

- Create: `wms/application/portal/onboarding.py`
- Modify: `wms/application/portal/__init__.py`
- Test: `wms/tests/portal/tests_portal_onboarding.py`

**Step 1: Write failing helper tests**

Extend `wms/tests/portal/tests_portal_onboarding.py` with tests for:

- shipper scope returns shipper wizard payload
- recipient scope returns recipient wizard payload
- missing preference is created with `show_on_next_login=True`
- session key suppresses repeated automatic display in the same session
- clearing the session allows automatic display again when preference is still checked
- unchecked preference disables future automatic display

Use request factory or a minimal request object with:

```python
request.user = user
request.portal_scope = scope
request.session = self.client.session
```

Expected helper names:

```python
build_portal_onboarding_context(request)
mark_portal_onboarding_seen(request, *, show_on_next_login)
```

**Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python manage.py test wms.tests.portal.tests_portal_onboarding -v 2
```

Expected:

- FAIL because `wms.application.portal.onboarding` does not exist.

**Step 3: Implement helper**

Create `wms/application/portal/onboarding.py`.

Implementation responsibilities:

- derive scope target from `PortalScope`
- `get_or_create` the matching `PortalOnboardingPreference`
- build a serializable payload:

```python
{
    "role": "shipper_admin",
    "auto_open": True,
    "title": "Tutoriel expéditeur",
    "steps": [...],
}
```

- include all approved shipper and recipient wizard copy
- set `auto_open=False` when the current session already recorded this scope as seen
- expose `mark_portal_onboarding_seen(...)` to:
  - update `show_on_next_login`
  - update `last_seen_at`
  - set a session marker for the current scope

Use a stable session dictionary key:

```python
PORTAL_ONBOARDING_SEEN_SESSION_KEY = "portal_onboarding_seen"
```

Use a stable scope key such as:

- `shipper:<id>`
- `recipient:<id>`
- `association_profile:<id>`

**Step 4: Export helper**

Update `wms/application/portal/__init__.py` to export only the public helper functions needed by views.

**Step 5: Run helper tests**

Run:

```bash
.venv/bin/python manage.py test wms.tests.portal.tests_portal_onboarding -v 2
```

Expected:

- PASS

**Step 6: Prepare commit after explicit approval**

```bash
git add wms/application/portal/onboarding.py wms/application/portal/__init__.py wms/tests/portal/tests_portal_onboarding.py
git commit -m "feat: build portal onboarding wizard payloads"
```

## Task 3: Add Protected Preference Update Endpoint

**Files:**

- Modify: `wms/views_portal_misc.py`
- Modify: `wms/views_portal.py`
- Modify: `wms/portal_urls.py`
- Test: `wms/tests/views/tests_views_portal.py`

**Step 1: Write failing endpoint tests**

Add tests in `wms/tests/views/tests_views_portal.py` covering:

- POST updates active shipper scope preference
- POST updates active recipient scope preference
- POST requires login
- POST requires active portal scope
- POST only updates the current user's active scope
- checked value keeps `show_on_next_login=True`
- unchecked value sets `show_on_next_login=False`

Expected URL name:

```python
reverse("portal:portal_onboarding_preference")
```

**Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAuthViewsTests wms.tests.views.tests_views_portal.PortalRecipientScopeViewsTests -v 2
```

Expected:

- FAIL because the URL/view does not exist.

**Step 3: Implement endpoint**

In `wms/views_portal_misc.py`, add:

```python
@login_required(login_url="portal:portal_login")
@portal_scope_required
@require_http_methods(["POST"])
def portal_onboarding_preference(request):
    show_on_next_login = request.POST.get("show_on_next_login") == "1"
    mark_portal_onboarding_seen(
        request,
        show_on_next_login=show_on_next_login,
    )
    return JsonResponse({"ok": True})
```

Use the actual helper import from `wms.application.portal.onboarding`.

Update `wms/views_portal.py` exports and `wms/portal_urls.py`:

```python
path(
    "onboarding/preference/",
    views.portal_onboarding_preference,
    name="portal_onboarding_preference",
)
```

**Step 4: Run endpoint tests**

Run:

```bash
.venv/bin/python manage.py test wms.tests.views.tests_views_portal -v 2
```

Expected:

- PASS or only unrelated pre-existing failures documented with exact test names

**Step 5: Prepare commit after explicit approval**

```bash
git add wms/views_portal_misc.py wms/views_portal.py wms/portal_urls.py wms/tests/views/tests_views_portal.py
git commit -m "feat: update portal onboarding preferences"
```

## Task 4: Inject Wizard Payload Into Portal Shell

**Files:**

- Modify: `wms/view_permissions.py`
- Modify: `templates/portal/base.html`
- Create: `templates/portal/includes/onboarding_wizard.html`
- Modify: `templates/includes/secondary_shell_masthead.html`
- Test: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Write failing shell tests**

Add tests for:

- shipper portal pages include `id="portal-onboarding-wizard"`
- recipient portal pages include `id="portal-onboarding-wizard"`
- masthead includes `id="portal-tutorial-link"`
- scope-select page does not include auto onboarding payload
- manual tutorial link falls back to FAQ when JS is unavailable

Expected fallback link:

```html
<a id="portal-tutorial-link" href="{% url 'portal:portal_faq' %}" ...>
```

**Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui -v 2
```

Expected:

- FAIL because the shell does not include the wizard or tutorial link.

**Step 3: Set request payload after scope binding**

In `wms/view_permissions.py`, after `request.portal_scope = scope`, call the onboarding helper with a local import:

```python
from .application.portal.onboarding import build_portal_onboarding_context

request.portal_onboarding = build_portal_onboarding_context(request)
```

Keep this local to avoid unnecessary module import coupling.

Do not run this for `portal_scope_select`; that view is not decorated with `portal_scope_required`.

**Step 4: Add masthead tutorial link**

In `templates/includes/secondary_shell_masthead.html`, add a portal utility link near FAQ:

```html
<a
  id="portal-tutorial-link"
  class="portal-utility-link"
  href="{% url 'portal:portal_faq' %}"
  data-portal-onboarding-open="1"
>
  {% trans "Tutoriel" %}
</a>
```

This gives a graceful fallback to FAQ when JavaScript is unavailable.

**Step 5: Add wizard include**

Create `templates/portal/includes/onboarding_wizard.html`.

Use Bootstrap modal markup with:

- `id="portal-onboarding-wizard"`
- `data-portal-onboarding-auto-open="{{ request.portal_onboarding.auto_open|yesno:'1,0' }}"`
- `data-portal-onboarding-preference-url="{% url 'portal:portal_onboarding_preference' %}"`
- `data-portal-onboarding-role="{{ request.portal_onboarding.role }}"`
- step containers with `data-portal-onboarding-step`
- checkbox `id="portal-onboarding-show-next-login"` checked by default when preference is enabled

Include the modal from `templates/portal/base.html` only when `request.portal_onboarding` exists.

**Step 6: Run shell tests**

Run:

```bash
.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui -v 2
```

Expected:

- PASS

**Step 7: Prepare commit after explicit approval**

```bash
git add wms/view_permissions.py templates/portal/base.html templates/portal/includes/onboarding_wizard.html templates/includes/secondary_shell_masthead.html wms/tests/views/tests_portal_bootstrap_ui.py
git commit -m "feat: show portal onboarding wizard shell"
```

## Task 5: Add Portal Onboarding JavaScript And Styling

**Files:**

- Create: `wms/static/portal/portal_onboarding.js`
- Modify: `wms/static/portal/portal-bootstrap.css`
- Modify: `templates/portal/base.html`
- Test: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Write failing asset tests**

Add tests asserting:

- `portal_onboarding.js` is loaded on portal pages
- wizard step controls exist
- checkbox label appears as `Afficher à la prochaine connexion`
- modal contains close/previous/next/finish controls

**Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui -v 2
```

Expected:

- FAIL because JS and controls are missing.

**Step 3: Implement JavaScript**

Create `wms/static/portal/portal_onboarding.js`.

Behavior:

- find `#portal-onboarding-wizard`
- initialize a Bootstrap modal when available
- open automatically when `data-portal-onboarding-auto-open="1"`
- intercept `[data-portal-onboarding-open]` and prevent default to open the modal manually
- handle next/previous buttons
- on finish or close, POST `show_on_next_login=1` when the checkbox is checked and `0` when unchecked
- include CSRF token from the existing cookie
- fail silently without blocking page use

**Step 4: Load JavaScript**

In `templates/portal/base.html`, after `portal_tables.js`, load:

```html
<script defer src="{% static 'portal/portal_onboarding.js' %}"></script>
```

**Step 5: Add minimal CSS**

In `wms/static/portal/portal-bootstrap.css`, add small scoped classes for:

- wizard progress
- hidden steps
- blocker list
- compact mobile layout

Keep CSS local to `.portal-bootstrap-enabled`.

**Step 6: Run asset tests**

Run:

```bash
.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui -v 2
```

Expected:

- PASS

**Step 7: Browser smoke check**

Start the development server:

```bash
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Manual smoke:

- login as shipper
- confirm wizard opens
- close with checkbox checked
- navigate to another portal page and confirm it does not reopen in the same session
- logout/login again and confirm it reopens
- uncheck checkbox and close
- logout/login again and confirm it does not reopen
- click `Tutoriel` and confirm it opens manually
- repeat for recipient scope

**Step 8: Prepare commit after explicit approval**

```bash
git add wms/static/portal/portal_onboarding.js wms/static/portal/portal-bootstrap.css templates/portal/base.html wms/tests/views/tests_portal_bootstrap_ui.py
git commit -m "feat: add portal onboarding wizard interactions"
```

## Task 6: Update FAQ, Changelog, And Verification

**Files:**

- Modify: `templates/portal/faq.html`
- Modify: `wms/faq_changelog.py`
- Recheck: `docs/repo-reference/03b-impact-portal.md`
- Recheck: `docs/repo-reference/04-shared-contracts/02-ui-shell-contracts.md`
- Recheck: `docs/repo-reference/04-shared-contracts/04-portal-parties.md`
- Test: `wms/tests/views/tests_views_portal.py`
- Test: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Test: `wms/tests/portal/tests_portal_onboarding.py`

**Step 1: Update portal FAQ**

Update `templates/portal/faq.html` so it remains aligned with wizard wording:

- mention that `Nouvelle commande` is the current entrypoint for shipment/transport requests
- mention the missing delivery recipient blocker
- mention the main preference validation rules
- mention pickup information requirements at a high level

**Step 2: Add FAQ changelog entry**

Add one user-visible behavior entry to `wms/faq_changelog.py`.

If PR number is not known yet, use a placeholder that must be filled before merge.

**Step 3: Run focused tests**

Run:

```bash
.venv/bin/python manage.py test \
  wms.tests.portal.tests_portal_onboarding \
  wms.tests.views.tests_views_portal \
  wms.tests.views.tests_portal_bootstrap_ui \
  -v 2
```

Expected:

- PASS or documented pre-existing failures with exact names

**Step 4: Run migration check**

Run:

```bash
.venv/bin/python manage.py makemigrations --check --dry-run
```

Expected:

- no model changes missing from migrations

**Step 5: Run Django system check**

Run:

```bash
.venv/bin/python manage.py check
```

Expected:

- PASS

**Step 6: Documentation drift check**

Re-open:

```bash
sed -n '1,220p' docs/repo-reference/03b-impact-portal.md
sed -n '1,220p' docs/repo-reference/04-shared-contracts/02-ui-shell-contracts.md
sed -n '1,220p' docs/repo-reference/04-shared-contracts/04-portal-parties.md
```

Expected:

- update only if the implementation changed the documented portal shell or portal behavior contract
- otherwise record in the PR summary: "Repo-reference checked; no contract update required."

**Step 7: Prepare commit after explicit approval**

```bash
git add templates/portal/faq.html wms/faq_changelog.py docs/repo-reference/03b-impact-portal.md docs/repo-reference/04-shared-contracts/02-ui-shell-contracts.md docs/repo-reference/04-shared-contracts/04-portal-parties.md
git commit -m "docs: document portal onboarding wizard behavior"
```

Only include repo-reference files if they actually changed.

## Final Verification

Run:

```bash
.venv/bin/python manage.py test \
  wms.tests.portal.tests_portal_onboarding \
  wms.tests.views.tests_views_portal \
  wms.tests.views.tests_portal_bootstrap_ui \
  wms.tests.portal.tests_portal_access_grants \
  -v 2
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py check
```

Expected:

- onboarding tests pass
- portal view/bootstrap regressions pass
- portal access grant regressions pass
- no missing migration
- Django system check passes

## Completion Checklist

- Propagation impact checked: portal UI shell, portal access, recipient/product-preference explanation only.
- Tests run and results recorded.
- Documentation impact handled.
- Permissions verified through active-scope endpoint tests.
- User-visible behavior documented.
- Operational safety preserved: no business-rule bypass and no order/recipient mutation semantics changed.
