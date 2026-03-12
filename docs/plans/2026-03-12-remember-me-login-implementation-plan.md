# Remember Me Login Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an explicit `Rester connecté` option to the legacy home, portal, and volunteer login forms, with 14-day persistence when checked and browser-session expiry when unchecked, while leaving `/admin/` unchanged.

**Architecture:** Keep the existing legacy login flows and centralize session-expiry control in a Django `user_logged_in` receiver. Update the three custom login forms to post a support marker plus the checkbox value, and update the custom portal/volunteer views only enough to preserve form state on validation errors.

**Tech Stack:** Django legacy views/templates, Django auth signals, Django test client, legacy WMS tests.

---

### Task 1: Add failing tests for portal remember-me behavior

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_portal.py`

**Step 1: Write the failing tests**

Add tests asserting:
- the portal login page renders `remember_me`
- login with `remember_me` sets a persistent session expiry near `settings.SESSION_COOKIE_AGE`
- login without `remember_me` sets a browser-session expiry

**Step 2: Run test to verify it fails**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAuthViewsTests -v 2
```

Expected:
- failures on missing checkbox and unchanged session expiry handling

### Task 2: Add failing tests for volunteer remember-me behavior

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_volunteer.py`

**Step 1: Write the failing tests**

Add tests asserting:
- the volunteer login page renders `remember_me`
- login with `remember_me` persists the session
- login without `remember_me` uses browser-session expiry

**Step 2: Run test to verify it fails**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer.VolunteerAuthViewTests -v 2
```

Expected:
- failures on missing checkbox and expiry behavior

### Task 3: Add failing tests for home/staff remember-me behavior

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_home.py`

**Step 1: Write the failing tests**

Add tests asserting:
- the home page renders `remember_me`
- posting through `/admin/login/` with the support marker and checkbox persists the session
- posting through `/admin/login/` with the support marker and no checkbox uses browser-session expiry
- direct `/admin/login/` remains unaffected without the support marker

**Step 2: Run test to verify it fails**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_home -v 2
```

Expected:
- failures on missing checkbox and missing remember-me handling for staff login

### Task 4: Implement central remember-me session handling

**Files:**
- Create: `/Users/EdouardGonnu/asf-wms/wms/auth_session.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/signals.py`

**Step 1: Implement helper constants and logic**

Add helpers for:
- `remember_me_supported`
- `remember_me`
- computing the persistent expiry age from `settings.SESSION_COOKIE_AGE`

**Step 2: Register a `user_logged_in` receiver**

Behavior:
- ignore logins without the support marker
- set `request.session.set_expiry(settings.SESSION_COOKIE_AGE)` when checked
- set `request.session.set_expiry(0)` when unchecked

**Step 3: Run focused tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_home wms.tests.views.tests_views_portal.PortalAuthViewsTests wms.tests.views.tests_views_volunteer.VolunteerAuthViewTests -v 2
```

Expected:
- session expiry assertions start passing once forms are updated

### Task 5: Update legacy login forms and custom contexts

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_portal_auth.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_volunteer_auth.py`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/home.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/portal/login.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/benevole/login.html`

**Step 1: Expose remember-me state in portal and volunteer login contexts**

Ensure invalid POST rerenders keep the checkbox checked when appropriate.

**Step 2: Add the checkbox and support marker to all three forms**

Use the same field names everywhere:
- `remember_me_supported`
- `remember_me`

**Step 3: Re-run focused tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_home wms.tests.views.tests_views_portal.PortalAuthViewsTests wms.tests.views.tests_views_volunteer.VolunteerAuthViewTests -v 2
```

Expected:
- all remember-me tests green

### Task 6: Verify the final behavior

**Files:**
- No code changes expected

**Step 1: Run the full targeted verification suite**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_home wms.tests.views.tests_views_portal wms.tests.views.tests_views_volunteer -v 2
```

Expected:
- all tests pass

**Step 2: Review the diff**

Confirm:
- `/admin/` direct login was not changed
- only legacy Django home/portal/volunteer paths were touched
