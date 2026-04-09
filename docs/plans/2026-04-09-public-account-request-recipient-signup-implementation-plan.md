# Public Account Request Recipient Signup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** add explicit shipper vs recipient public account requests, require one destination for recipients, and provision recipient-only portal access with automatic ASF binding after approval.

**Architecture:** extend the public account request schema with a destination pointer and richer account types, keep the public form dynamic but still server-validated, then branch the approval flow so recipient requests create shipment-party runtime data plus a recipient-only `PortalAccessGrant`. Reuse existing default-shipper binding helpers so ASF remains the single default shipper policy rather than duplicating recipient-link logic in approval code.

**Tech Stack:** Django models/views/templates, legacy portal auth/access helpers, Django TestCase, Bootstrap legacy templates

---

### Task 1: Add the failing model and handler tests for recipient account requests

**Files:**
- Modify: `wms/tests/admin/tests_account_request_handlers.py`
- Modify: `wms/tests/portal/tests_portal_role_review_gate.py`
- Modify: `wms/tests/portal/tests_portal_access_grants.py`

**Step 1: Write the failing tests**

Add coverage for:

- recipient public requests require a destination
- shipper public requests do not require a destination
- approving a recipient request creates:
  - a validated `ShipmentRecipientOrganization`
  - an active `PortalAccessGrant` with `recipient_admin`
  - no `AssociationProfile`
  - an ASF shipper link

**Step 2: Run the targeted tests to confirm failure**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.admin.tests_account_request_handlers \
  wms.tests.portal.tests_portal_role_review_gate \
  wms.tests.portal.tests_portal_access_grants -v 2
```

Expected:

- failures on missing `destination` field support
- failures on missing recipient approval branch

**Step 3: Commit checkpoint**

```bash
git add wms/tests/admin/tests_account_request_handlers.py wms/tests/portal/tests_portal_role_review_gate.py wms/tests/portal/tests_portal_access_grants.py
git commit -m "test: cover recipient public account request flow"
```

### Task 2: Add schema support for recipient requests

**Files:**
- Modify: `wms/models_domain/portal.py`
- Create: migration under `wms/migrations/`
- Modify: `wms/tests/core/tests_models_methods.py` if enum or string behavior needs direct model assertions

**Step 1: Write the minimal model change**

Implement:

- `PublicAccountRequestType.SHIPPER`
- `PublicAccountRequestType.RECIPIENT`
- keep `USER`
- add `destination = models.ForeignKey("wms.Destination", ...)` nullable/blank on `PublicAccountRequest`
- keep backward compatibility for legacy `association` rows in string/display logic where needed

**Step 2: Generate migration**

Run:

```bash
./.venv/bin/python manage.py makemigrations
```

Expected:

- one migration adding the destination FK and updated choices

**Step 3: Run the model-related tests**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.admin.tests_account_request_handlers \
  wms.tests.portal.tests_portal_role_review_gate -v 2
```

Expected:

- some tests still failing on form and approval behavior, but schema errors resolved

**Step 4: Commit checkpoint**

```bash
git add wms/models_domain/portal.py wms/migrations
git commit -m "feat: store destination on recipient account requests"
```

### Task 3: Add public form support for shipper vs recipient selection

**Files:**
- Modify: `wms/account_request_handlers.py`
- Modify: `templates/scan/public_account_request.html`
- Modify: `templates/scan/includes/public_account_request_association_fields.html`
- Modify: `templates/scan/includes/public_account_request_intro.html`
- Add tests in: `wms/tests/admin/tests_account_request_handlers.py`
- Add bootstrap/UI assertions in: `wms/tests/views/tests_portal_bootstrap_ui.py` if needed

**Step 1: Write the failing form/UI assertions**

Add assertions for:

- `Expediteur` and `Destinataire` choices rendered
- recipient POST without `destination_id` returns a validation error
- recipient POST with `destination_id` persists it on `PublicAccountRequest`

**Step 2: Run the focused tests**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.admin.tests_account_request_handlers \
  wms.tests.views.tests_portal_bootstrap_ui -v 2
```

Expected:

- failures on missing form fields and missing validation

**Step 3: Implement the handler/template changes**

Implement:

- new handler constants for shipper/recipient/user
- destination payload extraction and validation
- destination queryset for template context
- dynamic template select + JS section toggle
- keep legacy lock behavior sane for routes that still force association-like requests

**Step 4: Re-run the focused tests**

Run the same command and expect form/UI tests to pass while approval tests may still fail.

**Step 5: Commit checkpoint**

```bash
git add wms/account_request_handlers.py templates/scan/public_account_request.html templates/scan/includes/public_account_request_association_fields.html templates/scan/includes/public_account_request_intro.html wms/tests/admin/tests_account_request_handlers.py wms/tests/views/tests_portal_bootstrap_ui.py
git commit -m "feat: add recipient option to public account request form"
```

### Task 4: Implement recipient approval provisioning

**Files:**
- Modify: `wms/admin_account_request_approval.py`
- Modify: `wms/shipment_party_setup.py` only if a tiny helper extraction is needed
- Modify: `wms/default_shipper_bindings.py` only if approval needs a direct reusable entry point
- Add tests in: `wms/tests/portal/tests_portal_role_review_gate.py`
- Add tests in: `wms/tests/admin/tests_account_request_handlers.py`

**Step 1: Write/extend failing approval assertions**

Explicitly assert:

- recipient approval creates no `AssociationProfile`
- recipient approval creates/reuses user and runtime recipient org on the selected destination
- recipient approval creates one minimal recipient contact
- recipient approval creates one active `PortalAccessGrant(recipient_admin)`
- recipient approval auto-binds to ASF

**Step 2: Run the approval tests to confirm failure**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.admin.tests_account_request_handlers \
  wms.tests.portal.tests_portal_role_review_gate -v 2
```

Expected:

- failures on missing recipient branch and missing grant/runtime creation

**Step 3: Implement the minimal approval branch**

Implement recipient approval logic that:

- builds or reuses the org contact + address
- creates/reuses the Django user
- creates/reuses `ShipmentRecipientOrganization`
- creates/reuses one `ShipmentRecipientContact`
- creates/reactivates one `PortalAccessGrant` with role `recipient_admin`
- triggers default ASF binding and fails explicitly if ASF cannot be resolved

**Step 4: Re-run the approval tests**

Run the same command and expect approval tests to pass.

**Step 5: Commit checkpoint**

```bash
git add wms/admin_account_request_approval.py wms/default_shipper_bindings.py wms/shipment_party_setup.py wms/tests/admin/tests_account_request_handlers.py wms/tests/portal/tests_portal_role_review_gate.py
git commit -m "feat: approve recipient account requests into portal scope"
```

### Task 5: Verify portal access behavior for approved recipient users

**Files:**
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/portal/tests_portal_access_grants.py`
- Modify production code only if tests expose a missing compatibility branch

**Step 1: Add the failing login/access test**

Add a test that an approved recipient request user with one recipient grant:

- resolves one scope
- is redirected directly to the recipient dashboard after login

**Step 2: Run the focused portal tests**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_portal \
  wms.tests.portal.tests_portal_access_grants -v 2
```

Expected:

- either passes immediately or exposes one missing compatibility path

**Step 3: Implement only the minimal fix if needed**

Do not widen portal access behavior beyond what the tests require.

**Step 4: Re-run the portal tests**

Expect the targeted portal access tests to pass.

**Step 5: Commit checkpoint**

```bash
git add wms/tests/views/tests_views_portal.py wms/tests/portal/tests_portal_access_grants.py wms/views_portal_auth.py wms/portal_access.py
git commit -m "test: cover recipient signup portal access flow"
```

### Task 6: Update repo-reference docs and design traceability

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Create: `docs/plans/2026-04-09-public-account-request-recipient-signup-design.md`
- Create: `docs/plans/2026-04-09-public-account-request-recipient-signup-implementation-plan.md`

**Step 1: Update the flow docs**

Document:

- new public signup choice
- recipient destination requirement
- recipient-only access grant on approval
- ASF default binding dependency

**Step 2: Run a quick grep/self-check**

Run:

```bash
rg -n "account request|recipient_admin|destination" docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md
```

Expected:

- the updated docs mention the new flow and shared contract

**Step 3: Commit checkpoint**

```bash
git add docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md docs/plans/2026-04-09-public-account-request-recipient-signup-design.md docs/plans/2026-04-09-public-account-request-recipient-signup-implementation-plan.md
git commit -m "docs: record recipient public signup flow"
```

### Task 7: Run end-to-end targeted verification

**Files:**
- No production edits expected

**Step 1: Run the final targeted suite**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.admin.tests_account_request_handlers \
  wms.tests.portal.tests_portal_role_review_gate \
  wms.tests.portal.tests_portal_access_grants \
  wms.tests.views.tests_views_portal \
  wms.tests.views.tests_portal_bootstrap_ui -v 2
```

Expected:

- all targeted tests PASS

**Step 2: If any regression appears, fix the smallest failing slice and re-run only the affected subset, then re-run the full targeted suite**

**Step 3: Commit final checkpoint**

```bash
git add -A
git commit -m "feat: add recipient public account request flow"
```
