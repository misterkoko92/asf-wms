# Legacy UI Wave 4A Imports Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Simplify the legacy scan imports page by decomposing it into workflow-local partials while preserving the existing import handlers, selector data, and product-match review behavior.

**Architecture:** Keep `templates/scan/imports.html` as the route entry point and asset host. Split the page into readable includes under `templates/scan/includes/`, reuse the existing stable wrapper contracts (`ui-comp-card`, `ui-comp-form`, `ui-comp-actions`), and keep all POST action names, field names, IDs, download links, and `scan-import-selector-data` unchanged. This wave stays `En convergence`: no new shared `wms_ui` primitive and no new `UI Lab` contract.

**Tech Stack:** Django templates, Django TestCase, existing handlers in `wms/scan_import_handlers.py`, Bootstrap bridge classes, static import selector assets

---

### Task 1: Lock the wave 4A imports UI contracts with failing tests

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `templates/scan/imports.html`
- Verify: `wms/scan_import_handlers.py`

**Step 1: Write the failing test**

Add assertions that describe the target imports page structure:

```python
def test_scan_import_page_breaks_into_named_workflow_sections(self):
    self.client.force_login(self.superuser)

    response = self.client.get(reverse("scan:scan_import"))

    self.assertContains(response, 'id="scan-imports-intro"')
    self.assertContains(response, 'id="scan-imports-products"')
    self.assertContains(response, 'id="scan-imports-locations"')
    self.assertContains(response, 'id="scan-imports-categories"')
    self.assertContains(response, 'id="scan-imports-warehouses"')
    self.assertContains(response, 'id="scan-imports-contacts"')
    self.assertContains(response, 'id="scan-imports-users"')
```

Add a second assertion set that proves the stable wrappers survive the split:

```python
self.assertContains(response, "ui-comp-card", count=7)
self.assertContains(response, "ui-comp-form")
self.assertContains(response, "ui-comp-actions")
self.assertContains(response, 'id="scan-import-selector-data"')
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL on the new imports-section markers because the page is still one large template with no named section boundaries.

**Step 3: Write minimal implementation**

No production implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL only on the newly added imports-structure assertions.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "test: lock legacy ui wave 4a imports contracts"
```

### Task 2: Extract the intro and product-match review into explicit workflow includes

**Files:**
- Modify: `templates/scan/imports.html`
- Create: `templates/scan/includes/imports_intro_card.html`
- Create: `templates/scan/includes/imports_product_match_review.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Extend the red tests to require two top-level workflow markers:

```python
self.assertContains(response, 'id="scan-imports-intro"')
self.assertContains(response, 'id="scan-imports-product-review"')
```

Also assert that the review block still keeps the product-review POST contract:

```python
self.assertContains(response, 'name="action" value="product_confirm"')
self.assertContains(response, 'name="pending_token"')
self.assertContains(response, 'name="cancel" value="1"')
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL because the named includes and review wrapper IDs do not exist yet.

**Step 3: Write minimal implementation**

Move the top page card and the optional product-match review block into dedicated includes and keep the entry template as a simple orchestration shell:

```django
{% include "scan/includes/imports_intro_card.html" %}

{% if product_match_pending %}
  {% include "scan/includes/imports_product_match_review.html" %}
{% endif %}
```

Inside the review include, keep all existing field names and review controls untouched:

```django
<section id="scan-imports-product-review" class="scan-card card border-0 ui-comp-card">
  <form method="post" class="scan-filters ui-comp-form">
    <input type="hidden" name="action" value="product_confirm">
    <input type="hidden" name="pending_token" value="{{ product_match_pending.token }}">
  </form>
</section>
```

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS for the intro/review structure assertions.

**Step 5: Commit**

```bash
git add templates/scan/imports.html templates/scan/includes/imports_intro_card.html templates/scan/includes/imports_product_match_review.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "refactor: split imports intro and product review panels"
```

### Task 3: Extract the products import card while preserving selector and stock-mode contracts

**Files:**
- Modify: `templates/scan/imports.html`
- Create: `templates/scan/includes/imports_products_card.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `wms/static/scan/import_selectors.js`
- Verify: `wms/static/scan/import_selectors.css`

**Step 1: Write the failing test**

Add assertions that the products section is isolated and still keeps its product-specific hooks:

```python
self.assertContains(response, 'id="scan-imports-products"')
self.assertContains(response, 'name="action" value="product_single"')
self.assertContains(response, 'name="action" value="product_file"')
self.assertContains(response, 'id="product_file"')
self.assertContains(response, 'name="stock_mode"')
self.assertContains(response, reverse("scan:scan_import") + "?export=products")
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL because the dedicated products section marker does not exist yet.

**Step 3: Write minimal implementation**

Move the whole products block into a workflow-local include and keep the page entry template explicit:

```django
{% include "scan/includes/imports_products_card.html" %}
```

In the new include:
- keep `action="product_single"` and `action="product_file"`,
- keep `product_file`, `product_update`, `stock_mode_movement`, `stock_mode_overwrite`,
- keep the template/export links,
- keep the `scan-import-radio-group` markup and the final `ui-comp-actions` group,
- do not move `scan-import-selector-data` or the script tag out of `imports.html`.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS for the products-section assertions.

**Step 5: Commit**

```bash
git add templates/scan/imports.html templates/scan/includes/imports_products_card.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "refactor: extract imports products workflow card"
```

### Task 4: Extract the locations, categories, and warehouses cards as separate local partials

**Files:**
- Modify: `templates/scan/imports.html`
- Create: `templates/scan/includes/imports_locations_card.html`
- Create: `templates/scan/includes/imports_categories_card.html`
- Create: `templates/scan/includes/imports_warehouses_card.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add assertions for the three named admin-import sections:

```python
self.assertContains(response, 'id="scan-imports-locations"')
self.assertContains(response, 'id="scan-imports-categories"')
self.assertContains(response, 'id="scan-imports-warehouses"')
self.assertContains(response, 'name="action" value="location_single"')
self.assertContains(response, 'name="action" value="category_single"')
self.assertContains(response, 'name="action" value="warehouse_single"')
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL because the named section wrappers do not exist yet.

**Step 3: Write minimal implementation**

Split each family into its own include without inventing a generic import-card abstraction:

```django
{% include "scan/includes/imports_locations_card.html" %}
{% include "scan/includes/imports_categories_card.html" %}
{% include "scan/includes/imports_warehouses_card.html" %}
```

Each include must:
- keep both single-entry and file-import forms,
- preserve all current field names and submit actions,
- keep the relevant template/export links,
- wrap the card with a stable section ID such as `scan-imports-locations`.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS for the locations/categories/warehouses assertions.

**Step 5: Commit**

```bash
git add templates/scan/imports.html templates/scan/includes/imports_locations_card.html templates/scan/includes/imports_categories_card.html templates/scan/includes/imports_warehouses_card.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "refactor: extract imports inventory setup cards"
```

### Task 5: Extract the contacts and users cards, then run final wave 4A verification

**Files:**
- Modify: `templates/scan/imports.html`
- Create: `templates/scan/includes/imports_contacts_card.html`
- Create: `templates/scan/includes/imports_users_card.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `wms/tests/scan/tests_scan_import_handlers.py`
- Verify: `wms/scan_import_handlers.py`

**Step 1: Write the failing test**

Add assertions for the last two sections and their special contracts:

```python
self.assertContains(response, 'id="scan-imports-contacts"')
self.assertContains(response, 'id="scan-imports-users"')
self.assertContains(response, reverse("scan:scan_admin_contacts"))
self.assertContains(response, 'name="action" value="contact_file"')
self.assertContains(response, 'name="action" value="user_single"')
self.assertContains(response, 'name="action" value="user_file"')
```

Record in the task notes that this wave does **not**:
- add a `UI Lab` example,
- add a shared import-section template tag,
- change any import handler behavior in `wms/scan_import_handlers.py`.

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL because the last two named wrappers do not exist yet.

**Step 3: Write minimal implementation**

Extract the last two blocks into workflow-local includes:

```django
{% include "scan/includes/imports_contacts_card.html" %}
{% include "scan/includes/imports_users_card.html" %}
```

Keep these contracts unchanged:
- contacts remain file-import-only and link back to `scan_admin_contacts`,
- users keep the `import_default_password_configured` behavior,
- `scan-import-selector-data` and the `import_selectors.js` script stay at the bottom of `imports.html`.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.scan.tests_scan_import_handlers -v 2`

Expected: PASS with the new section markers and no handler regression.

Run: `git diff --check`

Expected: PASS with no whitespace or conflict-marker errors.

**Step 5: Commit**

```bash
git add templates/scan/imports.html templates/scan/includes/imports_contacts_card.html templates/scan/includes/imports_users_card.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "refactor: deliver legacy ui wave 4a imports split"
```
