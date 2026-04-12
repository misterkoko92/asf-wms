# Scan Account Validations Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a dedicated `/scan` operator workflow for reviewing public account requests, including one-screen type correction and approval, while keeping Django admin as a minimal fallback.

**Architecture:** Add lightweight review-audit fields on `PublicAccountRequest`, extract a shared approval service that accepts reviewed payload overrides, then build a new scan list/detail flow on top of that service. Keep phase 1 bounded: operator review becomes scan-first, but `/scan/admin/contacts/` remains superuser-only and only the minimal admin fallback is added.

**Tech Stack:** Django legacy scan views/templates, `PublicAccountRequest` model and approval services, Bootstrap legacy templates, Django TestCase

---

### Task 1: Lock the operator review contract with failing tests

**Files:**
- Create: `wms/tests/views/tests_views_scan_account_validations.py`
- Modify: `wms/tests/admin/tests_account_request_handlers.py`
- Modify: `wms/tests/portal/tests_portal_role_review_gate.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add view coverage for:

- list page shows pending account requests
- detail page shows requested type and editable final type
- validator-group staff can access the new routes
- non-validator staff are denied
- POST can correct `shipper` to `recipient` and requires recipient fields

Add approval-service assertions for:

- corrected review preserves the original requested type
- final approved type drives the runtime provisioning branch
- review snapshot stores destination and allowed shipper ids

Example snippets:

```python
def test_scan_account_validation_list_shows_pending_requests(self):
    response = self.client.get(reverse("scan:scan_account_validation_list"))
    self.assertContains(response, "Validations comptes")
    self.assertContains(response, pending_request.association_name)

def test_scan_account_validation_detail_can_correct_shipper_to_recipient(self):
    response = self.client.post(
        reverse("scan:scan_account_validation_detail", args=[request_obj.id]),
        {
            "action": "approve_request",
            "final_account_type": "recipient",
            "destination_id": str(self.destination.id),
            "allowed_shipper_ids": [str(self.shipper_contact.id)],
            "legal_form": "association",
            "beneficiary_count": "120",
            "first_name": "Alice",
            "last_name": "Martin",
        },
    )
    self.assertRedirects(response, reverse("scan:scan_account_validation_list"))
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_account_validations wms.tests.admin.tests_account_request_handlers wms.tests.portal.tests_portal_role_review_gate wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL because the routes, permission helper, review metadata, and corrected approval path do not exist yet.

**Step 3: Write minimal implementation**

No production code in this task.

**Step 4: Run test to verify it still fails for the expected reasons**

Re-run the same command and confirm the failures are limited to the missing review feature.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_scan_account_validations.py wms/tests/admin/tests_account_request_handlers.py wms/tests/portal/tests_portal_role_review_gate.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "test: lock scan account validation workflow"
```

### Task 2: Add request review audit fields and validator access helpers

**Files:**
- Modify: `wms/models_domain/portal.py`
- Create: `wms/migrations/0113_publicaccountrequest_review_fields.py`
- Modify: `wms/view_permissions.py`
- Modify: `wms/context_processors.py`
- Verify: `wms/account_request_handlers.py`

**Step 1: Write the failing test**

Use the tests from Task 1 and add narrow model assertions if needed:

```python
def test_public_account_request_can_store_requested_type_and_review_snapshot(self):
    request_obj.requested_account_type = "shipper"
    request_obj.review_snapshot = {"final_account_type": "recipient"}
    request_obj.save()
    self.assertEqual(request_obj.requested_account_type, "shipper")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.admin.tests_account_request_handlers wms.tests.views.tests_views_scan_account_validations -v 2`

Expected: FAIL because the new fields and validator helper do not exist.

**Step 3: Write minimal implementation**

In `wms/models_domain/portal.py`, add:

```python
requested_account_type = models.CharField(max_length=20, blank=True, default="")
review_snapshot = models.JSONField(default=dict, blank=True)
```

In `wms/view_permissions.py`, add a new helper/decorator that allows:

- superusers
- staff members in `ACCOUNT_REQUEST_VALIDATION_GROUP_NAME`

In `wms/context_processors.py`, expose pending validation count for authorized validators, not just superusers.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.admin.tests_account_request_handlers wms.tests.views.tests_views_scan_account_validations -v 2`

Expected: PASS on field persistence and access-helper behavior, while the review pages still fail.

**Step 5: Commit**

```bash
git add wms/models_domain/portal.py wms/migrations/0113_publicaccountrequest_review_fields.py wms/view_permissions.py wms/context_processors.py
git commit -m "feat: add public account review metadata and validator access"
```

### Task 3: Extract a shared approval service that accepts reviewed payload overrides

**Files:**
- Create: `wms/account_request_review_service.py`
- Modify: `wms/admin_account_request_approval.py`
- Modify: `wms/account_request_handlers.py`
- Modify: `wms/tests/admin/tests_account_request_handlers.py`
- Modify: `wms/tests/portal/tests_portal_role_review_gate.py`

**Step 1: Write the failing test**

Add service-level coverage for:

- corrected final type writes `requested_account_type` once and updates `account_type`
- recipient review payload creates recipient runtime using reviewed destination and shipper ids
- admin approval still works with no overrides

Example:

```python
ok, _reason = approve_account_request(
    request=request,
    account_request=account_request,
    enqueue_email=lambda **kwargs: None,
    review_overrides={
        "final_account_type": "recipient",
        "destination_id": self.destination.id,
        "allowed_shipper_ids": [self.shipper_contact.id],
        "legal_form": "association",
        "beneficiary_count": 120,
    },
)
self.assertTrue(ok)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.admin.tests_account_request_handlers wms.tests.portal.tests_portal_role_review_gate -v 2`

Expected: FAIL because the approval path cannot yet consume reviewed payload overrides.

**Step 3: Write minimal implementation**

Create a shared service/dataclass pair, for example:

```python
@dataclass
class AccountRequestReviewPayload:
    final_account_type: str
    destination_id: int | None = None
    allowed_shipper_ids: list[int] | None = None
```

Refactor `approve_account_request(...)` so it:

- resolves the final account type from overrides or the request row
- persists `requested_account_type` if the type changes
- stores `review_snapshot`
- provisions the final runtime using the shared service
- keeps the existing email behavior

Do not duplicate shipper/recipient provisioning logic in the scan view.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.admin.tests_account_request_handlers wms.tests.portal.tests_portal_role_review_gate -v 2`

Expected: PASS with corrected-type approval supported and admin approval still stable.

**Step 5: Commit**

```bash
git add wms/account_request_review_service.py wms/admin_account_request_approval.py wms/account_request_handlers.py wms/tests/admin/tests_account_request_handlers.py wms/tests/portal/tests_portal_role_review_gate.py
git commit -m "feat: share account review approval service"
```

### Task 4: Add the scan account validation routes, forms, and views

**Files:**
- Create: `wms/forms_scan_account_validations.py`
- Create: `wms/views_scan_account_validations.py`
- Modify: `wms/scan_urls.py`
- Modify: `wms/views_scan.py`
- Modify: `wms/views.py`
- Modify: `wms/tests/views/tests_views_scan_account_validations.py`

**Step 1: Write the failing test**

Build tests for:

- list page filters pending requests
- detail page pre-fills request data
- detail POST validates recipient-only fields when final type is `recipient`
- approval redirects back to the list with a success message
- rejection updates status without provisioning runtime objects

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_account_validations -v 2`

Expected: FAIL because the views, URLs, and form do not exist yet.

**Step 3: Write minimal implementation**

In `wms/forms_scan_account_validations.py`, add an operator review form that captures:

- `final_account_type`
- structure/referent fields
- destination
- allowed shippers
- legal form
- beneficiary count
- address fields

In `wms/views_scan_account_validations.py`, add:

- `scan_account_validation_list`
- `scan_account_validation_detail`

Use the new validator decorator instead of `_require_superuser`.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_account_validations -v 2`

Expected: PASS with operator pages live and guarded by validator access.

**Step 5: Commit**

```bash
git add wms/forms_scan_account_validations.py wms/views_scan_account_validations.py wms/scan_urls.py wms/views_scan.py wms/views.py wms/tests/views/tests_views_scan_account_validations.py
git commit -m "feat: add scan account validation pages"
```

### Task 5: Render the operator list/detail templates and wire the approval UX

**Files:**
- Create: `templates/scan/account_validation_list.html`
- Create: `templates/scan/account_validation_detail.html`
- Create: `templates/scan/includes/account_validation_request_summary.html`
- Create: `templates/scan/includes/account_validation_review_form.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_scan_account_validations.py`

**Step 1: Write the failing test**

Add UI assertions for:

- `Validations comptes` heading
- `Traiter` action on the list page
- requested-type warning on corrected detail pages
- recipient-required fields shown when final type is `recipient`
- document table rendered on the detail page

Example:

```python
self.assertContains(response, 'id="scan-account-validations-list"')
self.assertContains(response, "Requested as shipper, reviewed as recipient")
self.assertContains(response, 'name="allowed_shipper_ids"')
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_account_validations -v 2`

Expected: FAIL because the templates and operator copy do not exist yet.

**Step 3: Write minimal implementation**

Build the templates with four blocks:

- request summary
- operator qualification
- business data
- decision

Keep the JS minimal: only show/hide recipient-specific field groups based on final type.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_account_validations -v 2`

Expected: PASS with the list/detail markup and dynamic review fields rendered.

**Step 5: Commit**

```bash
git add templates/scan/account_validation_list.html templates/scan/account_validation_detail.html templates/scan/includes/account_validation_request_summary.html templates/scan/includes/account_validation_review_form.html wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_account_validations.py
git commit -m "feat: render scan account validation workflow"
```

### Task 6: Wire scan navigation, operator banner, and minimal Django admin fallback

**Files:**
- Modify: `templates/scan/includes/scan_sidebar_navigation.html`
- Modify: `templates/scan/base.html`
- Modify: `wms/admin.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/admin/tests_account_request_handlers.py`

**Step 1: Write the failing test**

Add assertions for:

- `Validations comptes` link under scan management
- pending-account banner links to `/scan/account-validations/` for authorized validators
- `PublicAccountRequestAdmin` exposes `destination`
- admin page exposes a readonly review link for pending rows

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.admin.tests_account_request_handlers -v 2`

Expected: FAIL because the nav, banner, and admin fallback link are not wired yet.

**Step 3: Write minimal implementation**

In the scan sidebar, add:

```html
<a href="{% url 'scan:scan_account_validation_list' %}" class="scan-sidebar-child-link{% if active == 'account_validations' %} active{% endif %}">
  Validations comptes
</a>
```

In `templates/scan/base.html`, retarget the pending banner to the scan review list when the user has validator access.

In `wms/admin.py`, add:

- `destination` to the fieldset
- a readonly scan-review link for pending requests

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.admin.tests_account_request_handlers -v 2`

Expected: PASS with operator-visible nav and a bounded admin fallback.

**Step 5: Commit**

```bash
git add templates/scan/includes/scan_sidebar_navigation.html templates/scan/base.html wms/admin.py wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/admin/tests_account_request_handlers.py
git commit -m "feat: wire account validations into scan navigation"
```

### Task 7: Update repo-reference docs for the new scan-first review contract

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Verify: `docs/repo-reference/03-impact-map.md`
- Verify: `docs/email_flows_target_matrix_2026-02-20.md`

**Step 1: Write the failing doc checklist**

Before editing, confirm the current docs do not mention:

- `/scan/account-validations/`
- validator-group access for account review
- the new scan-first banner/link contract

**Step 2: Run doc verification**

Run: `rg -n "account-validations|scan-first review|validator" docs/repo-reference docs/email_flows_target_matrix_2026-02-20.md`

Expected: no matching scan-review contract yet.

**Step 3: Write minimal implementation**

Document:

- the new scan list/detail review flow in `02-key-flows-and-living-tests.md`
- the public account request review contract and scan sidebar contract in `04-shared-contracts.md`

Only update `03-impact-map.md` or the email matrix if the final implementation materially changes the documented propagation rule.

**Step 4: Run doc verification**

Run: `rg -n "account-validations|Validations comptes|requested_account_type|review_snapshot" docs/repo-reference`

Expected: PASS with the new contract documented.

**Step 5: Commit**

```bash
git add docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md
git commit -m "docs: document scan account validation contract"
```
