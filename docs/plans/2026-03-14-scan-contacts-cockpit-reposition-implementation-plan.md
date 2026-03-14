# Scan Contacts Cockpit Reposition Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the Scan contacts cockpit the main manual contacts entry under `Gestion`, and reduce `/scan/import/` contact handling to bulk-only actions.

**Architecture:** Keep the existing legacy route and org-role cockpit backend, then move the navigation entry, trim the contact import card, and fix the shipper filter source so the UI matches the current business reality. Drive the change with view-level and navigation-level tests plus a final browser QA pass.

**Tech Stack:** Django templates, legacy Scan views/helpers, Django TestCase, Bootstrap-based Scan UI

---

### Task 1: Add failing navigation and import-page tests

**Files:**
- Modify: `wms/tests/views/tests_views_scan_admin.py`
- Modify: `wms/tests/views/tests_views_imports.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `templates/scan/base.html`
- Verify: `templates/scan/imports.html`

**Step 1: Write the failing test**

Add assertions that lock the new information architecture:

```python
def test_scan_base_nav_places_contacts_under_gestion_not_admin(self):
    self.client.force_login(self.superuser)
    response = self.client.get(reverse("scan:scan_import"))
    html = response.content.decode("utf-8")
    self.assertIn(reverse("scan:scan_admin_contacts"), html)
    self.assertIn(">Contacts<", html)
    self.assertNotIn(
        '<li><a href="' + reverse("scan:scan_admin_contacts") + '" class="dropdown-item active">Contacts</a></li>',
        html,
    )
```

Add import-page assertions that the `Import contacts` card no longer renders a single-contact form while still rendering:
- upload input
- `Template contacts`
- `Exporter contacts`

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_imports wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL because `Contacts` is still in `Admin` and the single-contact import form still exists.

**Step 3: Write minimal implementation**

No implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run the same command and confirm the failures are limited to the intended nav/import assertions.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_scan_admin.py wms/tests/views/tests_views_imports.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "test: cover scan contacts cockpit repositioning"
```

### Task 2: Move `Contacts` to `Gestion` and simplify contact imports

**Files:**
- Modify: `templates/scan/base.html`
- Modify: `templates/scan/imports.html`
- Modify: `wms/tests/views/tests_views_scan_admin.py`
- Modify: `wms/tests/views/tests_views_imports.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Use the red tests from Task 1.

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_imports wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL on navigation placement and on the presence of the single-contact import form.

**Step 3: Write minimal implementation**

Update `templates/scan/base.html`:
- add `Contacts` to the `Gestion` dropdown
- remove `Contacts` from the `Admin` dropdown

Update `templates/scan/imports.html`:
- delete the single-contact `contact_single` form
- keep only the contact upload form and its template/export actions
- add short helper text pointing manual management to the contacts cockpit

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_imports wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add templates/scan/base.html templates/scan/imports.html wms/tests/views/tests_views_scan_admin.py wms/tests/views/tests_views_imports.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: move contacts cockpit to gestion"
```

### Task 3: Add failing tests for the shipper filter correction

**Files:**
- Modify: `wms/tests/views/tests_views_scan_admin_contacts_cockpit.py`
- Verify: `wms/scan_admin_contacts_cockpit.py`
- Verify: `templates/scan/admin_contacts.html`

**Step 1: Write the failing test**

Add a test that proves the `Destinataires d'un expéditeur` filter only lists active shipper organizations:

```python
def test_scan_admin_contacts_shipper_filter_lists_only_active_shippers(self):
    donor = Contact.objects.create(name="Donor Org", contact_type=ContactType.ORGANIZATION, is_active=True)
    response = self.client.get(reverse("scan:scan_admin_contacts"))
    select_markup = self._extract_select_markup(
        response=response,
        select_id="scan-admin-contacts-shipper-filter",
    )
    self.assertIn("Shipper Org", select_markup)
    self.assertNotIn("Recipient Org", select_markup)
    self.assertNotIn("Donor Org", select_markup)
```

Also add a test for inactive shippers if one does not already exist.

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`

Expected: FAIL because the filter currently uses all cockpit organizations.

**Step 3: Write minimal implementation**

No implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run the same command and confirm the failure points to the filter contents only.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_scan_admin_contacts_cockpit.py
git commit -m "test: restrict admin contacts shipper filter"
```

### Task 4: Restrict the shipper filter source

**Files:**
- Modify: `wms/scan_admin_contacts_cockpit.py`
- Modify: `templates/scan/admin_contacts.html`
- Modify: `wms/tests/views/tests_views_scan_admin_contacts_cockpit.py`

**Step 1: Write the failing test**

Use the red test from Task 3.

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`

Expected: FAIL on the shipper-filter contents.

**Step 3: Write minimal implementation**

In `wms/scan_admin_contacts_cockpit.py`, build a dedicated list such as:

```python
cockpit_filter_shipper_organizations = [
    organization for organization in organizations if organization.id in active_shipper_org_ids
]
```

Expose it in `build_cockpit_context`, then update `templates/scan/admin_contacts.html` so the filter uses that list instead of `cockpit_organizations`.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/scan_admin_contacts_cockpit.py templates/scan/admin_contacts.html wms/tests/views/tests_views_scan_admin_contacts_cockpit.py
git commit -m "fix: align contacts shipper filter with active roles"
```

### Task 5: Run focused regression coverage and browser QA

**Files:**
- Verify: `wms/tests/views/tests_views_scan_admin.py`
- Verify: `wms/tests/views/tests_views_imports.py`
- Verify: `wms/tests/views/tests_views_scan_admin_contacts_cockpit.py`
- Verify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `wms/tests/views/tests_i18n_language_switch.py`

**Step 1: Write the failing test**

No new test required if Tasks 1-4 already cover the approved behavior.

**Step 2: Run targeted regression suite**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_imports wms.tests.views.tests_views_scan_admin_contacts_cockpit wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_i18n_language_switch -v 2`

Expected: PASS.

**Step 3: Write minimal implementation**

Only if regressions appear. Fix the smallest possible nav/template/context issue without broadening scope.

**Step 4: Run test to verify it passes**

Re-run the same command until clean, then run:

```bash
git diff --check
```

Finally perform browser QA on:
- `/scan/import/`
- `/scan/admin/contacts/`

Expected:
- `Contacts` visible under `Gestion`
- `Contacts` absent from `Admin`
- contact import card shows bulk-only actions
- shipper filter lists only active shippers

**Step 5: Commit**

```bash
git add templates/scan/base.html templates/scan/imports.html templates/scan/admin_contacts.html wms/scan_admin_contacts_cockpit.py wms/tests/views/tests_views_scan_admin.py wms/tests/views/tests_views_imports.py wms/tests/views/tests_views_scan_admin_contacts_cockpit.py wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_i18n_language_switch.py
git commit -m "test: verify scan contacts cockpit repositioning"
```
