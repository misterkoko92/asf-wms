# Portal FAQ Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a shared FAQ entry point in the legacy Django portal so shipper and recipient users can see what actions are currently possible, and record deferred portal gaps for a later update.

**Architecture:** Add one read-only portal FAQ route and template rendered from the existing legacy portal shell so the same masthead button works in both portal scopes. Keep the content role-aware at the page level by documenting both shipper and recipient capabilities in separate sections, and record deferred feature gaps in a dedicated follow-up doc instead of the user-facing FAQ.

**Tech Stack:** Django views/templates/URL routing, legacy portal Bootstrap shell, Django tests, repo-reference docs

---

### Task 1: Add failing portal FAQ tests

**Files:**
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_portal.py`

**Step 1: Write the failing tests**

- Add a bootstrap/UI test asserting the portal masthead exposes a `FAQ` link for shipper scope and recipient scope.
- Add a view test asserting `portal:portal_faq` renders for a shipper user.
- Add a view test asserting `portal:portal_faq` renders for an active recipient scope and contains both FAQ sections.

**Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal -v 2`

Expected: failures because the portal FAQ route/view/template do not exist yet.

### Task 2: Implement the portal FAQ route, view, and masthead entry

**Files:**
- Modify: `wms/portal_urls.py`
- Modify: `wms/views_portal.py`
- Modify: `wms/views.py`
- Modify: `templates/portal/base.html`
- Create: `wms/views_portal_misc.py`
- Create: `templates/portal/faq.html`

**Step 1: Write minimal implementation**

- Add `portal_faq` to the portal routing/export chain.
- Render a simple FAQ page using `portal/base.html`.
- Add a shared `FAQ` utility link in the portal masthead so both shipper and recipient scopes can reach it.
- Keep the page read-only and document current capabilities only.

**Step 2: Run tests to verify they pass**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal -v 2`

Expected: the new FAQ tests pass with the existing portal suite still green.

### Task 3: Record deferred portal gaps and update repo-reference docs

**Files:**
- Create: `docs/deferred-follow-ups.md` or modify if present
- Modify: `docs/repo-reference/01-architecture-and-entrypoints.md`

**Step 1: Document the deferred gaps**

- Record the currently missing portal flows identified during analysis for the next update.
- Mention the new portal FAQ route in the repo reference because it changes portal entry points.

**Step 2: Run focused verification**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal -v 2`

Expected: green test run after docs/code changes.
