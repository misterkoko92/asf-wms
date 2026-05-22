# Account Onboarding Stopover Indications Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add validated stopover indications and contact-field corrections to public account creation, with Scan-side review visibility and no new operational restrictions.

**Architecture:** Extend the existing Django account request flow with compatibility-preserving data capture on `PublicAccountRequest`, keep unsupported stopovers in `StopoverFeasibilityRequest`, and expose the new data through the existing Scan account validation pages. Avoid building the future stopover cockpit in this change.

**Tech Stack:** Django models, migrations, form handlers, Django templates, page-local JavaScript, Scan templates, Django tests.

---

### Task 1: Add Structured Shipper Stopover Storage

**Files:**
- Modify: `wms/models_domain/portal.py`
- Modify: `wms/models.py`
- Create: `wms/migrations/<next>_public_account_request_stopover_indications.py`
- Test: `wms/tests/core/tests_models_methods.py`

**Step 1: Write the failing test**

Add coverage that a `PublicAccountRequest` can store selected served stopover ids or labels without changing `destination`.

**Step 2: Run the focused test**

Run: `env DJANGO_SECRET_KEY=codex-local-dev-key-not-production-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ./.venv/bin/python manage.py test wms.tests.core.tests_models_methods -v 2`

Expected: fail until the field exists.

**Step 3: Implement minimal model field**

Add a JSON field such as `shipper_stopover_indications = models.JSONField(default=list, blank=True)` on `PublicAccountRequest`.

**Step 4: Create migration**

Run: `env DJANGO_SECRET_KEY=codex-local-dev-key-not-production-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ./.venv/bin/python manage.py makemigrations wms`

**Step 5: Rerun the focused test**

Expected: pass.

**Step 6: Commit**

Proposed message: `feat: store shipper stopover indications`

### Task 2: Capture And Validate Public Signup Fields

**Files:**
- Modify: `wms/account_request_handlers.py`
- Test: `wms/tests/admin/tests_account_request_handlers.py`
- Test: `wms/tests/views/tests_views_public_account.py`

**Step 1: Write failing tests**

Cover:
- structure phone is required for shipper and recipient requests
- shipper selected stopovers are persisted as indicative data
- only `Autre escale` still creates a feasibility request when submitted through the stopover request action
- account requests with served stopovers plus `Autre escale` can create both account request context and feasibility request when the form action submits the account request path

**Step 2: Run focused tests**

Run: `env DJANGO_SECRET_KEY=codex-local-dev-key-not-production-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ./.venv/bin/python manage.py test wms.tests.admin.tests_account_request_handlers wms.tests.views.tests_views_public_account -v 2`

Expected: fail until extraction and validation are updated.

**Step 3: Implement extraction and validation**

Update account form extraction to read stopover checkbox values, format labels as `Ville (IATA), Pays`, and store them on the request. Add required structure phone validation. Keep feasibility requests separate from operational provisioning.

**Step 4: Rerun focused tests**

Expected: pass.

**Step 5: Commit**

Proposed message: `feat: capture account stopover indications`

### Task 3: Update Public Account Request UI

**Files:**
- Modify: `templates/scan/includes/public_account_request_association_fields.html`
- Modify: `templates/scan/public_account_request.html`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_views_public_account.py`

**Step 1: Write failing template tests**

Cover:
- served stopovers render as `Ville (IATA), Pays`
- stopovers are sorted by city then country
- shipper signup displays `Escales envisagées`
- active form controls use the white form-control styling
- admin and preparation contact address fields are visible
- first recipient is labeled optional

**Step 2: Run focused tests**

Run: `env DJANGO_SECRET_KEY=codex-local-dev-key-not-production-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_public_account -v 2`

Expected: fail until template and JavaScript are updated.

**Step 3: Implement template and JavaScript changes**

Add the shipper checkbox list, `Autre escale` toggle behavior, visible contact address fields, required attributes, white field styling, and clearer first-recipient optional copy.

**Step 4: Rerun focused tests**

Expected: pass.

**Step 5: Commit**

Proposed message: `feat: refine public account signup form`

### Task 4: Expose Stopover Indications In Scan Validation

**Files:**
- Modify: `wms/views_scan_account_validations.py`
- Modify: `templates/scan/account_validation_list.html`
- Modify: `templates/scan/includes/account_validation_request_summary.html`
- Test: `wms/tests/views/tests_views_scan_account_validations.py`

**Step 1: Write failing tests**

Cover:
- pending account validation list displays shipper indicative stopovers
- a query filter can return requests that indicated a given served stopover
- detail summary displays selected stopovers

**Step 2: Run focused tests**

Run: `env DJANGO_SECRET_KEY=codex-local-dev-key-not-production-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_account_validations -v 2`

Expected: fail until Scan list/detail are updated.

**Step 3: Implement Scan list/detail visibility**

Add a simple stopover filter to the pending validation list and render selected stopovers in list and detail views.

**Step 4: Rerun focused tests**

Expected: pass.

**Step 5: Commit**

Proposed message: `feat: show account stopovers in scan review`

### Task 5: Documentation And Regression Sweep

**Files:**
- Modify: `docs/repo-reference/04-shared-contracts/04-portal-parties.md`
- Modify: `wms/faq_changelog.py`

**Step 1: Update docs**

Document that shipper stopover indications are review/history data and not order constraints. Add FAQ changelog entry because signup and Scan validation behavior are user-visible.

**Step 2: Run the combined verification**

Run: `env DJANGO_SECRET_KEY=codex-local-dev-key-not-production-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ./.venv/bin/python manage.py test wms.tests.admin.tests_account_request_handlers wms.tests.views.tests_views_public_account wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_account_validations wms.tests.portal.tests_stopover_feasibility_requests wms.tests.emailing.tests_stopover_feasibility_requests -v 2`

Expected: pass.

**Step 3: Run a system check**

Run: `env DJANGO_SECRET_KEY=codex-local-dev-key-not-production-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ./.venv/bin/python manage.py check`

Expected: no errors.

**Step 4: Commit**

Proposed message: `docs: document account stopover indications`
