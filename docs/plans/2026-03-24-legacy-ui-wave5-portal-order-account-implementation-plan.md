# Legacy UI Wave 5 Portal Order And Account Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Simplify the dense legacy portal order creation and account pages by decomposing them into workflow-local sections and includes while preserving the current Django view contracts, JSON script hooks, and portal contact/document behaviors.

**Architecture:** Keep `templates/portal/order_create.html` and `templates/portal/account.html` as route entry points and asset hosts. Split only workflow-local sections under `templates/portal/includes/`, keep `order_create` as one logical form with local card sections, preserve `json_script` payloads and inline JS, and keep `account` forms and `ui_button` calls intact. This wave stays `En convergence`: no new shared portal primitive and no expansion of `wms_ui`.

**Tech Stack:** Django templates, Django TestCase, legacy portal views, Bootstrap bridge classes, inline portal JavaScript, existing `ui_button` template tag

---

### Task 1: Lock the wave 5 portal section contracts with failing UI tests

**Files:**
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Verify: `templates/portal/order_create.html`
- Verify: `templates/portal/account.html`

**Step 1: Write the failing test**

Add one structure test for `portal_order_create`:

```python
def test_portal_order_create_breaks_into_named_workflow_sections(self):
    response = self.client.get(reverse("portal:portal_order_create"))

    self.assertContains(response, 'id="portal-order-create-intro"')
    self.assertContains(response, 'id="portal-order-create-routing-card"')
    self.assertContains(response, 'id="portal-order-create-ready-cartons-card"')
    self.assertContains(response, 'id="portal-order-create-ready-kits-card"')
    self.assertContains(response, 'id="portal-order-create-unit-products-card"')
```

Extend it with stable contract assertions:

```python
self.assertContains(response, 'id="portal-order-create-form"')
self.assertContains(response, 'id="portal-category-filters"')
self.assertContains(response, 'id="portal-recipient-options-data"')
self.assertContains(response, 'id="portal-product-data"')
```

Add one structure test for `portal_account`:

```python
def test_portal_account_breaks_into_named_workflow_sections(self):
    response = self.client.get(reverse("portal:portal_account"))

    self.assertContains(response, 'id="portal-account-intro"')
    self.assertContains(response, 'id="portal-account-profile-card"')
    self.assertContains(response, 'id="portal-account-billing-card"')
    self.assertContains(response, 'id="portal-account-documents-card"')
```

Keep the existing contact-row and document-upload markers:

```python
self.assertContains(response, 'id="portal-account-form"')
self.assertContains(response, 'id="portal-contact-row-template"')
self.assertContains(response, 'name="action" value="request_billing_preferences"')
self.assertContains(response, 'name="action" value="upload_account_docs"')
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests.test_portal_order_create_breaks_into_named_workflow_sections wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests.test_portal_account_breaks_into_named_workflow_sections -v 2`

Expected: FAIL on the new section IDs because both templates still render their large workflow blocks inline.

**Step 3: Write minimal implementation**

No production implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run the targeted tests above and confirm the failure is only on the missing section markers.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_portal_bootstrap_ui.py
git commit -m "test: lock legacy ui wave 5 portal contracts"
```

### Task 2: Extract portal order_create into a sectioned form shell

**Files:**
- Modify: `templates/portal/order_create.html`
- Create: `templates/portal/includes/order_create_intro_card.html`
- Create: `templates/portal/includes/order_create_routing_card.html`
- Create: `templates/portal/includes/order_create_ready_cartons_card.html`
- Create: `templates/portal/includes/order_create_ready_kits_card.html`
- Create: `templates/portal/includes/order_create_unit_products_card.html`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Write the failing test**

Extend the order-create structure test to require:

```python
self.assertContains(response, 'id="portal-order-create-form"')
self.assertContains(response, 'id="portal-order-create-routing-card"')
self.assertContains(response, 'id="portal-order-create-ready-cartons-card"')
self.assertContains(response, 'id="portal-order-create-ready-kits-card"')
self.assertContains(response, 'id="portal-order-create-unit-products-card"')
self.assertContains(response, 'id="portal-category-filters"')
```

Keep the existing product-table hooks:

```python
self.assertContains(response, 'data-ready-carton-key=')
self.assertContains(response, 'data-product-id=')
self.assertContains(response, 'id="ready-carton-estimate-total"')
self.assertContains(response, 'id="carton-estimate-total"')
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests.test_portal_order_create_breaks_into_named_workflow_sections -v 2`

Expected: FAIL because the new form-section wrappers do not exist yet.

**Step 3: Write minimal implementation**

Keep the page entry template responsible for:
- opening and closing the single `<form>` with `id="portal-order-create-form"`,
- hosting the `json_script` payloads,
- hosting the inline JavaScript.

Move the HTML sections into local includes:

```django
{% include "portal/includes/order_create_intro_card.html" %}
<form method="post" novalidate class="ui-comp-form" id="portal-order-create-form">
  {% include "portal/includes/order_create_routing_card.html" %}
  {% include "portal/includes/order_create_ready_cartons_card.html" %}
  {% include "portal/includes/order_create_ready_kits_card.html" %}
  {% include "portal/includes/order_create_unit_products_card.html" %}
</form>
```

Inside the new includes:
- preserve `destination_id`, `recipient_id`, `portal-category-filters`, `ready_carton_*`, `ready_kit_*`, and `product_*_qty` names/IDs,
- keep all current empty states and line-error rendering,
- keep the final submit button in the unit-products card,
- do not move or rename any `json_script` IDs used by the inline JS.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests.test_portal_order_create_breaks_into_named_workflow_sections -v 2`

Expected: PASS for the new section and hook assertions.

**Step 5: Commit**

```bash
git add templates/portal/order_create.html templates/portal/includes/order_create_intro_card.html templates/portal/includes/order_create_routing_card.html templates/portal/includes/order_create_ready_cartons_card.html templates/portal/includes/order_create_ready_kits_card.html templates/portal/includes/order_create_unit_products_card.html wms/tests/views/tests_portal_bootstrap_ui.py
git commit -m "refactor: split portal order create workflow cards"
```

### Task 3: Extract portal account cards into local includes without changing form behavior

**Files:**
- Modify: `templates/portal/account.html`
- Create: `templates/portal/includes/account_intro_card.html`
- Create: `templates/portal/includes/account_profile_card.html`
- Create: `templates/portal/includes/account_billing_card.html`
- Create: `templates/portal/includes/account_documents_card.html`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Write the failing test**

Extend the account structure test to require:

```python
self.assertContains(response, 'id="portal-account-intro"')
self.assertContains(response, 'id="portal-account-profile-card"')
self.assertContains(response, 'id="portal-account-billing-card"')
self.assertContains(response, 'id="portal-account-documents-card"')
```

Keep the existing account workflow markers:

```python
self.assertContains(response, 'id="portal-account-form"')
self.assertContains(response, 'id="portal-contact-row-template"')
self.assertContains(response, 'id="add-contact-row"')
self.assertContains(response, 'name="action" value="request_billing_preferences"')
self.assertContains(response, 'name="action" value="upload_account_docs"')
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests.test_portal_account_breaks_into_named_workflow_sections -v 2`

Expected: FAIL because the new card wrappers do not exist yet.

**Step 3: Write minimal implementation**

Keep `account.html` as the page shell and script host:

```django
{% include "portal/includes/account_intro_card.html" %}
{% include "portal/includes/account_profile_card.html" %}
{% include "portal/includes/account_billing_card.html" %}
{% include "portal/includes/account_documents_card.html" %}
```

Inside the new includes:
- preserve `portal-account-form`, `contact_count`, and the `account_contact_row` template usage,
- preserve the `ui_button` calls and their existing label/context variables,
- keep the billing change-request table and document table/upload form unchanged except for the outer wrapper,
- do not move the contact-row inline script out of `account.html`.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests.test_portal_account_breaks_into_named_workflow_sections -v 2`

Expected: PASS for the new section and contract assertions.

**Step 5: Commit**

```bash
git add templates/portal/account.html templates/portal/includes/account_intro_card.html templates/portal/includes/account_profile_card.html templates/portal/includes/account_billing_card.html templates/portal/includes/account_documents_card.html wms/tests/views/tests_portal_bootstrap_ui.py
git commit -m "refactor: split portal account workflow cards"
```

### Task 4: Run final wave 5 verification and land the full portal wave

**Files:**
- Verify: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Verify: `wms/tests/views/tests_views_portal.py`
- Verify: `templates/portal/order_create.html`
- Verify: `templates/portal/account.html`

**Step 1: Write the failing test**

No new test in this task. Use the tests added above as the final regression gate.

**Step 2: Run test to verify it fails**

Not applicable.

**Step 3: Write minimal implementation**

No new production implementation in this task.

**Step 4: Run test to verify it passes**

Run the portal suites:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_portal_bootstrap_ui \
  wms.tests.views.tests_views_portal \
  -v 2
git diff --check
```

Expected: PASS and no diff-check output.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-24-legacy-ui-wave5-portal-order-account-implementation-plan.md templates/portal/order_create.html templates/portal/account.html templates/portal/includes/order_create_intro_card.html templates/portal/includes/order_create_routing_card.html templates/portal/includes/order_create_ready_cartons_card.html templates/portal/includes/order_create_ready_kits_card.html templates/portal/includes/order_create_unit_products_card.html templates/portal/includes/account_intro_card.html templates/portal/includes/account_profile_card.html templates/portal/includes/account_billing_card.html templates/portal/includes/account_documents_card.html wms/tests/views/tests_portal_bootstrap_ui.py
git commit -m "refactor: deliver legacy ui wave 5 portal split"
```
