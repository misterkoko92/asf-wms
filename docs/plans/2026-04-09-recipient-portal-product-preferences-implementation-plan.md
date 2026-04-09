# Recipient Portal Product Preferences Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let recipient-scoped portal users manage product preferences individually from a dedicated portal page linked from the recipient home.

**Architecture:** Add a recipient-scoped preference-maintenance route and page that reuses the existing shared preference form helpers already used by the shipper recipient detail page. Keep the recipient dashboard as a read-only summary surface and cover the new route with focused Django view and Bootstrap UI tests.

**Tech Stack:** Django views, Django templates, Django TestCase, existing portal preference helpers in `wms/views_portal_account.py`

---

### Task 1: Document the recipient-scoped route contract in tests

**Files:**
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Write the failing tests**

- Add a view test asserting recipient scope home exposes a `Gérer les préférences produits` link.
- Add a view test asserting the new recipient-scoped preferences page renders.
- Add a view test asserting recipient-scoped POST creates or updates a product preference.
- Add a view test asserting recipient-scoped POST can delete an explicit preference.
- Add a Bootstrap UI test asserting the new page exposes the expected cards, actions, form fields, and delete action.

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAccountViewsTests wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests -v 2
```

Expected:

- failures or errors because the new route, CTA, and template contract do not exist yet

**Step 3: Write minimal implementation**

- Add the route, view, and template needed to satisfy the new tests.

**Step 4: Run tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAccountViewsTests wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests -v 2
```

Expected:

- all newly added recipient preference tests pass

### Task 2: Reuse shared preference helpers for recipient scope

**Files:**
- Modify: `wms/views_portal_account.py`
- Modify: `wms/views_portal.py`
- Modify: `wms/portal_urls.py`

**Step 1: Write the failing tests**

- Extend the new view tests to assert add, update, invalid input preservation, and delete behaviors match the existing preference flow.

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAccountViewsTests -v 2
```

Expected:

- failures around missing route handling or missing save/delete behavior

**Step 3: Write minimal implementation**

- Extract or reuse context-building logic for recipient product rows.
- Gate the new view to active `recipient_admin` scope.
- Reuse the same save helpers and validation messages already used by the shipper-side detail view.
- Add an explicit delete action by preference id.

**Step 4: Run tests to verify it passes**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAccountViewsTests -v 2
```

Expected:

- the recipient-scoped preference lifecycle tests pass

### Task 3: Wire the recipient home CTA and template contract

**Files:**
- Modify: `templates/portal/recipient_scope_home.html`
- Create: `templates/portal/recipient_preferences.html`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Write the failing tests**

- Assert the CTA is present on the recipient home page.
- Assert the new page keeps portal Bootstrap card/table conventions.

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests -v 2
```

Expected:

- markup assertions fail before template changes

**Step 3: Write minimal implementation**

- Add the CTA to the home page.
- Build the new dedicated template with consistent portal styling and explicit save/delete actions.

**Step 4: Run tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests -v 2
```

Expected:

- markup assertions pass for the new recipient-scoped page

### Task 4: Update repo-reference docs if the maintained contract changed

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Write the failing check**

- Re-read the portal recipient scope and shared portal recipient preference sections to confirm the route contract changed.

**Step 2: Verify doc gap**

- Confirm the current reference only mentions the summary home or shipper detail flow and does not mention the recipient-scoped maintenance page.

**Step 3: Write minimal documentation update**

- Document the recipient-scoped preference-management route and its relation to the shared preference runtime contract.

**Step 4: Re-read to verify consistency**

- Confirm the updated text matches the implemented route and current tests.

### Task 5: Final verification

**Files:**
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Modify: `wms/views_portal_account.py`
- Modify: `wms/views_portal.py`
- Modify: `wms/portal_urls.py`
- Modify: `templates/portal/recipient_scope_home.html`
- Create: `templates/portal/recipient_preferences.html`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Run focused portal tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAccountViewsTests wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests -v 2
```

**Step 2: Run the closest portal access and shipment-party regression tests if needed**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.portal.tests_portal_access_grants wms.tests.portal.tests_portal_permissions -v 2
```

**Step 3: Inspect the diff**

Run:

```bash
git diff -- docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md wms/portal_urls.py wms/views_portal.py wms/views_portal_account.py templates/portal/recipient_scope_home.html templates/portal/recipient_preferences.html wms/tests/views/tests_views_portal.py wms/tests/views/tests_portal_bootstrap_ui.py
```

**Step 4: Commit**

```bash
git add docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md wms/portal_urls.py wms/views_portal.py wms/views_portal_account.py templates/portal/recipient_scope_home.html templates/portal/recipient_preferences.html wms/tests/views/tests_views_portal.py wms/tests/views/tests_portal_bootstrap_ui.py docs/plans/2026-04-09-recipient-portal-product-preferences-design.md docs/plans/2026-04-09-recipient-portal-product-preferences-implementation-plan.md
git commit -m "feat: add recipient portal preference management"
```
