# Portal Auth Recovery Options Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ajouter sur `/portal/login/` deux options visibles, `Premiere connexion` et `Mot de passe oublie`, avec des flux email securises pour envoyer un lien `set-password`.

**Architecture:** Conserver une seule logique technique de reinitialisation (token Django + route existante `portal_set_password`) et exposer deux parcours metier (`first` et `forgot`) via une vue portail dediee. Les deux parcours partagent la meme protection anti-enumeration et anti-spam (throttle cache), avec messages de succes generiques.

**Tech Stack:** Django templates/views (`wms`), auth token `default_token_generator`, cache Django pour throttling, emailing via `send_or_enqueue_email_safe`, tests Django `manage.py test`.

---

## Assumptions to validate

- `Premiere connexion` cible les comptes association actives avec profil portail et mot de passe non initialise (ou changement force).
- `Mot de passe oublie` cible les comptes association actives avec profil portail et mot de passe deja utilisable.
- En cas d'email inconnu/ineligible, l'UI renvoie la meme reponse de succes (pas de fuite d'information).

### Task 1: Define routes and page contract

**Files:**
- Modify: `wms/portal_urls.py`
- Modify: `wms/views_portal.py`
- Modify: `wms/views.py`

**Step 1: Write failing routing test**

- Add tests in `wms/tests/views/tests_views_portal.py` for:
  - `reverse("portal:portal_first_connection")`
  - `reverse("portal:portal_forgot_password")`
  - expected `200` on `GET`.

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAuthViewsTests -v 2`
Expected: FAIL with missing route/view names.

**Step 3: Add URL patterns and re-exports**

- Add `first-connection/` -> `portal_first_connection`.
- Add `forgot-password/` -> `portal_forgot_password`.
- Re-export new views in `wms/views_portal.py` and `wms/views.py`.

**Step 4: Re-run focused test**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAuthViewsTests -v 2`
Expected: route-related tests no longer fail.

### Task 2: Build shared recovery view logic

**Files:**
- Modify: `wms/views_portal_auth.py`

**Step 1: Write failing behavior tests**

Add tests in `wms/tests/views/tests_views_portal.py` for both flows:
- valid eligible account -> generic success message + email helper called.
- unknown email -> same generic success + no email helper call.
- ineligible account (no profile/inactive) -> same generic success + no email helper call.

**Step 2: Run tests to verify failure**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAuthViewsTests -v 2`
Expected: FAIL (missing view behavior).

**Step 3: Implement minimal shared helpers**

In `wms/views_portal_auth.py`:
- Add mode-safe constants (`first`, `forgot`).
- Add helper to normalize email and resolve eligible user/profile.
- Add helper to build absolute `portal_set_password` URL using `request.build_absolute_uri(...)`.
- Add helper to render a single template with mode-specific title/cta text.

**Step 4: Implement POST flow**

- If payload valid and throttle allows:
  - evaluate eligibility based on mode.
  - if eligible, generate token URL and send email.
- Always render same success message string regardless of result.

**Step 5: Re-run auth tests**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAuthViewsTests -v 2`
Expected: PASS for new behavior tests.

### Task 3: Add anti-enumeration and throttling

**Files:**
- Modify: `wms/views_portal_auth.py`
- Modify: `asf_wms/settings.py`

**Step 1: Write failing throttle test**

- Add test with `@override_settings(PORTAL_AUTH_RECOVERY_THROTTLE_SECONDS=300)`:
  - first POST accepted
  - immediate second POST for same email/IP blocked (generic success kept, email helper not called twice).

**Step 2: Run tests to verify failure**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAuthViewsTests -v 2`
Expected: FAIL for missing throttling.

**Step 3: Implement throttle keys and setting**

- Add setting default `PORTAL_AUTH_RECOVERY_THROTTLE_SECONDS = 300`.
- Add cache helpers mirroring existing `account_request` pattern:
  - key by mode + email + client IP
  - reserve with `cache.add`.

**Step 4: Re-run auth tests**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAuthViewsTests -v 2`
Expected: PASS including throttle case.

### Task 4: Add email templates and dispatch

**Files:**
- Create: `templates/emails/portal_first_connection.txt`
- Create: `templates/emails/portal_forgot_password.txt`
- Modify: `wms/views_portal_auth.py`

**Step 1: Write failing email-content test**

- Mock `wms.views_portal_auth.send_or_enqueue_email_safe` and assert:
  - subject differs by mode.
  - template contains generated `set_password_url`.

**Step 2: Run test to verify failure**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAuthViewsTests -v 2`
Expected: FAIL (no dispatch/template usage).

**Step 3: Implement dispatch**

- Use `render_to_string` with mode-specific templates.
- Use `send_or_enqueue_email_safe(...)` with recipient = submitted email.

**Step 4: Re-run tests**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAuthViewsTests -v 2`
Expected: PASS for email assertions.

### Task 5: Add UI options on login page

**Files:**
- Modify: `templates/portal/login.html`
- Create: `templates/portal/access_recovery.html`

**Step 1: Write failing template tests**

In `wms/tests/views/tests_views_portal.py` and `wms/tests/views/tests_portal_bootstrap_ui.py`:
- login page contains links:
  - `portal_first_connection`
  - `portal_forgot_password`
- recovery page uses existing component classes (`ui-comp-card`, `ui-comp-form`, `form-control`, `btn`).

**Step 2: Run tests to verify failure**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal -v 2`
Expected: FAIL on missing links/page markup.

**Step 3: Implement template changes**

- Add a compact link row below password field on login page.
- Build one shared recovery template receiving mode-specific labels.

**Step 4: Re-run tests**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal -v 2`
Expected: PASS.

### Task 6: Regression and non-functional validation

**Files:**
- Modify tests only if regressions surface.

**Step 1: Run targeted portal suite**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.views.tests_portal_bootstrap_ui -v 2`
Expected: PASS.

**Step 2: Run broader guardrail suite (legacy auth-related)**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views wms.tests.admin.tests_admin_extra -v 2`
Expected: PASS with no regression on existing `portal_set_password` and account approval email flows.

**Step 3: Manual QA checklist**

- `/portal/login/` shows both new options.
- First-connection request sends mail when account is eligible.
- Forgot-password request sends reset mail for eligible account.
- Unknown email returns same success text and no error leak.
- Rate limit prevents repeated submissions spam.
