# Scan Import Current Contract Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align the legacy `/scan/import/` page, contact/user import reference files, and CSV exports with the current supported import contract.

**Architecture:** Keep the existing Scan import route and handlers, then make the smallest set of changes needed to bring the UI, static CSV templates, selector payloads, and exports into sync. Drive the work with targeted Django view, import-service, and export tests so the documented contract and the actual import behavior stay locked together.

**Tech Stack:** Django templates, Django settings, legacy Scan JS/CSS, Django TestCase, CSV export helpers

---

### Task 1: Add failing import page tests for current UI defaults

**Files:**
- Modify: `wms/tests/views/tests_views_imports.py`
- Verify: `templates/scan/imports.html`
- Verify: `wms/static/scan/import_selectors.css`
- Verify: `wms/scan_import_handlers.py`

**Step 1: Write the failing test**

Add view tests that prove the current page contract:

```python
def test_scan_import_defaults_product_update_checkbox_and_exposes_current_contact_fields(self):
    self.client.force_login(self.superuser)
    response = self.client.get(self.url)
    self.assertContains(response, 'id="product_update"')
    self.assertContains(response, 'id="product_update" name="update_existing" value="1" checked')
    self.assertContains(response, 'name="destinations"')
    self.assertContains(response, 'name="linked_shippers"')
    self.assertContains(response, 'name="organization"')
    self.assertContains(response, 'name="use_organization_address"')
```

Add a second test for the user password requirement:

```python
@override_settings(IMPORT_DEFAULT_PASSWORD="configured-by-settings")  # pragma: allowlist secret
def test_scan_import_user_password_is_not_required_when_default_password_is_configured(self):
    self.client.force_login(self.superuser)
    response = self.client.get(self.url)
    self.assertContains(response, 'id="user_password" name="password"')
    self.assertNotContains(response, 'id="user_password" name="password" required')
```

Also add the inverse assertion without `IMPORT_DEFAULT_PASSWORD` so the form still requires a password when no default exists.

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_imports -v 2`

Expected: FAIL because the product checkbox is not checked by default, the single-contact form does not yet expose the current contact fields, and the user password input is always required in the template.

**Step 3: Write minimal implementation**

No implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run: `.venv/bin/python manage.py test wms.tests.views.tests_views_imports -v 2`

Expected: FAIL only on the missing import page contract assertions.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_imports.py
git commit -m "test: cover scan import current page contract"
```

### Task 2: Implement the import page UI and selector changes

**Files:**
- Modify: `templates/scan/imports.html`
- Modify: `wms/static/scan/import_selectors.css`
- Modify: `wms/static/scan/import_selectors.js`
- Modify: `wms/scan_import_handlers.py`

**Step 1: Write the failing test**

Use the red tests from Task 1 as the starting point.

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_imports -v 2`

Expected: FAIL on missing checked/default/current-contract form fields and on the password requirement mismatch.

**Step 3: Write minimal implementation**

Implement the approved page changes:

```html
<input type="checkbox" id="product_update" name="update_existing" value="1" checked>
```

Expand the single-contact form to expose the current supported fields:
- `organization`
- `destinations`
- `linked_shippers`
- `use_organization_address`

Update the contact selector payload in `wms/scan_import_handlers.py` so records include:

```python
{
    "organization": contact.organization.name if contact.organization else "",
    "destinations": "|".join(...),
    "linked_shippers": "|".join(...),
    "use_organization_address": bool(contact.use_organization_address),
}
```

Update `wms/static/scan/import_selectors.js` so contact autocomplete fills those fields, and change `wms/static/scan/import_selectors.css` so the stock-mode radio options render inline with centered radio + label alignment rather than the current stacked/grid presentation.

Make the user password field conditional:

```python
context["default_password_configured"] = bool(getattr(settings, "IMPORT_DEFAULT_PASSWORD", None))
```

```html
<input type="text" id="user_password" name="password" {% if not default_password_configured %}required{% endif %}>
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_imports -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add templates/scan/imports.html wms/static/scan/import_selectors.css wms/static/scan/import_selectors.js wms/scan_import_handlers.py wms/tests/views/tests_views_imports.py
git commit -m "feat: align scan import page with current contract"
```

### Task 3: Add failing contract tests for CSV templates and exports

**Files:**
- Modify: `wms/tests/exports/tests_exports.py`
- Modify: `wms/tests/imports/tests_import_services_contacts_extra.py`
- Verify: `wms/static/scan/import_templates/contacts.csv`
- Verify: `wms/static/scan/import_templates/users.csv`
- Verify: `wms/exports.py`
- Verify: `wms/import_services_contacts.py`

**Step 1: Write the failing test**

Add one test that reads the static template headers and locks the approved fields:

```python
def test_static_contact_and_user_import_templates_use_current_headers(self):
    self.assertEqual(contact_header, [
        "contact_type", "title", "first_name", "last_name", "name",
        "organization", "role", "email", "email2", "phone", "phone2",
        "use_organization_address", "tags", "destinations", "linked_shippers",
        "destination", "siret", "vat_number", "legal_registration_number",
        "asf_id", "address_label", "address_line1", "address_line2",
        "postal_code", "city", "region", "country", "address_phone",
        "address_email", "address_is_default", "notes",
    ])
```

Add export assertions that the contact export still emits `destinations`, `linked_shippers`, and `use_organization_address` in the approved order, and that the user export keeps the current `password` column as the final documented field.

Add or extend an import-service test that proves the current contact contract still works when a row uses:

```python
{
    "contact_type": "organization",
    "name": "Recipient A",
    "tags": "destinataire",
    "destinations": "Paris (CDG) - France|Abidjan (ABJ) - Cote d'Ivoire",
    "linked_shippers": "AVIATION SANS FRONTIERES",
}
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.exports.tests_exports wms.tests.imports.tests_import_services_contacts_extra -v 2`

Expected: FAIL if any static template header, export ordering, or current contact-contract behavior diverges from the approved schema.

**Step 3: Write minimal implementation**

No implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run the same command and confirm any failures point to contract mismatches, not unrelated import regressions.

**Step 5: Commit**

```bash
git add wms/tests/exports/tests_exports.py wms/tests/imports/tests_import_services_contacts_extra.py
git commit -m "test: lock current scan import csv contract"
```

### Task 4: Align the static CSV templates and export output

**Files:**
- Modify: `wms/static/scan/import_templates/contacts.csv`
- Modify: `wms/static/scan/import_templates/users.csv`
- Modify: `wms/exports.py`
- Modify: `wms/import_services_contacts.py` only if Task 3 proves a current-rule gap

**Step 1: Write the failing test**

Use the red tests from Task 3.

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.exports.tests_exports wms.tests.imports.tests_import_services_contacts_extra -v 2`

Expected: FAIL on the exact header/order/sample-data mismatch found in Task 3.

**Step 3: Write minimal implementation**

Update the static reference files so they document the current contract and remain practically usable:
- keep the approved header order
- use sample rows that illustrate the real contact scope fields now in use
- keep the user template aligned with the current final `password` column

Update `wms/exports.py` only where needed so exported headers and row ordering match the documented contract.

If the new contact-contract test exposed a real parser gap, patch `wms/import_services_contacts.py` minimally and keep legacy aliases tolerated.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.exports.tests_exports wms.tests.imports.tests_import_services_contacts_extra -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/static/scan/import_templates/contacts.csv wms/static/scan/import_templates/users.csv wms/exports.py wms/import_services_contacts.py wms/tests/exports/tests_exports.py wms/tests/imports/tests_import_services_contacts_extra.py
git commit -m "feat: align scan import csv references and exports"
```

### Task 5: Run focused regression coverage for the import lot

**Files:**
- Verify: `wms/tests/views/tests_views_imports.py`
- Verify: `wms/tests/scan/tests_scan_import_handlers.py`
- Verify: `wms/tests/imports/tests_import_services_contacts_extra.py`
- Verify: `wms/tests/imports/tests_import_services_users.py`
- Verify: `wms/tests/exports/tests_exports.py`

**Step 1: Write the failing test**

No new test required if Tasks 1-4 already cover the approved behavior.

**Step 2: Run targeted regression suite**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_imports wms.tests.scan.tests_scan_import_handlers wms.tests.imports.tests_import_services_contacts_extra wms.tests.imports.tests_import_services_users wms.tests.exports.tests_exports -v 2`

Expected: PASS.

**Step 3: Write minimal implementation**

Only if regressions appear. Fix the smallest possible page, selector, template, or export mismatch without expanding scope.

**Step 4: Run test to verify it passes**

Re-run the same command until clean, then run:

```bash
git diff --check
```

Expected: no test failures and no whitespace/errors in the diff.

**Step 5: Commit**

```bash
git add templates/scan/imports.html wms/static/scan/import_selectors.css wms/static/scan/import_selectors.js wms/scan_import_handlers.py wms/static/scan/import_templates/contacts.csv wms/static/scan/import_templates/users.csv wms/exports.py wms/tests/views/tests_views_imports.py wms/tests/scan/tests_scan_import_handlers.py wms/tests/imports/tests_import_services_contacts_extra.py wms/tests/imports/tests_import_services_users.py wms/tests/exports/tests_exports.py
git commit -m "test: verify scan import current contract regressions"
```
