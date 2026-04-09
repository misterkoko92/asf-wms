# Recipient Portal Profile Editing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let recipient-scoped portal users edit their recipient structure profile, main contact, and structure documents directly from the recipient portal.

**Architecture:** Add a recipient-scoped profile-edit route and template linked from the recipient dashboard, reuse the existing recipient-form validation contract where it fits, and persist updates onto the active runtime recipient organization plus its legacy compatibility projections. Keep destination read-only and keep product preferences on their existing dedicated page.

**Tech Stack:** Django views, Django templates, Django TestCase, shipment-party use cases in `wms/application/parties/use_cases.py`, portal dashboard payloads in `wms/application/portal/dashboard_queries.py`

---

### Task 1: Document the recipient-scoped edit contract in tests

**Files:**
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Write the failing tests**

- Add a view test asserting recipient scope home exposes a `Modifier mes informations` link.
- Add a view test asserting the new recipient-scoped profile page renders for an active recipient grant.
- Add a view test asserting shipper scope is denied on the new route.
- Add a Bootstrap UI test asserting the new page exposes the expected intro card, form controls, read-only destination field, file inputs, and actions.

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAccountViewsTests wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests -v 2
```

Expected:

- failures because the route, CTA, and new page contract do not exist yet

**Step 3: Write minimal implementation**

- Add the route, export, view stub, and template needed to satisfy the new GET and CTA tests.

**Step 4: Run tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAccountViewsTests wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests -v 2
```

Expected:

- the new recipient portal profile-page contract tests pass

### Task 2: Add failing persistence tests for recipient profile updates

**Files:**
- Modify: `wms/tests/views/tests_views_portal.py`

**Step 1: Write the failing tests**

- Add a POST test asserting recipient scope can update structure name, legal form, beneficiary count, address, notes, and main contact fields.
- Add a POST test asserting uploaded documents are upserted on the active recipient organization and queued for scan.
- Add a POST test asserting the home payload reflects the updated values after redirect.

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAccountViewsTests -v 2
```

Expected:

- failures around missing save logic and missing document upload behavior

**Step 3: Write minimal implementation**

- Implement recipient-scope-specific form bootstrapping and save logic in `wms/views_portal_account.py`.
- Reuse shared validation helpers for contact/address/structure fields.
- Upsert structure documents with `upsert_recipient_structure_documents(..., queue_scan=True)`.
- Refresh legacy projections so shipper surfaces stay aligned.

**Step 4: Run tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAccountViewsTests -v 2
```

Expected:

- recipient-scoped update tests pass

### Task 3: Wire the recipient dashboard CTA and editing template

**Files:**
- Modify: `templates/portal/recipient_scope_home.html`
- Create: `templates/portal/recipient_profile.html`
- Modify: `wms/portal_urls.py`
- Modify: `wms/views_portal.py`
- Modify: `wms/views.py`

**Step 1: Write the failing tests**

- Assert the CTA is present on the recipient home page.
- Assert the new edit page keeps portal Bootstrap form and card conventions.

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests -v 2
```

Expected:

- markup assertions fail before the template and route changes land

**Step 3: Write minimal implementation**

- Add the CTA to the recipient home page.
- Build the dedicated recipient profile template with the shared contact and flags partials plus document upload fields.

**Step 4: Run tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests -v 2
```

Expected:

- recipient portal profile-page markup assertions pass

### Task 4: Update repo-reference docs for the new recipient maintenance surface

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Write the failing check**

- Re-read the portal recipient scope and shared shipment-party sections to confirm the recipient portal is no longer read-only for shared profile data.

**Step 2: Verify doc gap**

- Confirm the current reference does not mention the recipient-scoped profile-edit route.

**Step 3: Write minimal documentation update**

- Document the new recipient-scoped maintenance page and its shared data propagation expectations.

**Step 4: Re-read to verify consistency**

- Confirm the updated text matches the implemented route and save behavior.

### Task 5: Final verification

**Files:**
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Modify: `wms/views_portal_account.py`
- Modify: `wms/views_portal.py`
- Modify: `wms/views.py`
- Modify: `wms/portal_urls.py`
- Modify: `templates/portal/recipient_scope_home.html`
- Create: `templates/portal/recipient_profile.html`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Run focused portal tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAccountViewsTests wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests -v 2
```

**Step 2: Run the closest portal permission regression tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.portal.tests_portal_access_grants wms.tests.portal.tests_portal_permissions -v 2
```

**Step 3: Inspect the diff**

Run:

```bash
git diff -- docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md wms/portal_urls.py wms/views.py wms/views_portal.py wms/views_portal_account.py templates/portal/recipient_scope_home.html templates/portal/recipient_profile.html wms/tests/views/tests_views_portal.py wms/tests/views/tests_portal_bootstrap_ui.py docs/plans/2026-04-09-recipient-portal-profile-editing-design.md docs/plans/2026-04-09-recipient-portal-profile-editing-implementation-plan.md
```

**Step 4: Commit**

```bash
git add docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md wms/portal_urls.py wms/views.py wms/views_portal.py wms/views_portal_account.py templates/portal/recipient_scope_home.html templates/portal/recipient_profile.html wms/tests/views/tests_views_portal.py wms/tests/views/tests_portal_bootstrap_ui.py docs/plans/2026-04-09-recipient-portal-profile-editing-design.md docs/plans/2026-04-09-recipient-portal-profile-editing-implementation-plan.md
git commit -m "feat: add recipient portal profile editing"
```
