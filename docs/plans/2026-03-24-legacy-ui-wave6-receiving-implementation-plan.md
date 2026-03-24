# Legacy UI Wave 6 Receiving Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Simplify the legacy receiving surfaces by splitting `receive_pallet`, `receive`, and `receive_association` into workflow-local sections while preserving all current handlers, forms, stage flows, and local JavaScript hooks.

**Architecture:** Keep each route template as the shell for route-local scripts and JSON payloads. Move only the dense HTML workflow sections into `templates/scan/includes/`, add explicit section IDs for UI-governance visibility, and preserve all existing form boundaries, field names, POST actions, datalist IDs, `pending_token` flows, and local data attributes. This wave stays `En convergence`: no shared receiving component and no promotion to `UI Lab`.

**Tech Stack:** Django templates, Django TestCase, legacy scan receipt views, Bootstrap bridge classes, route-local JavaScript

---

### Task 1: Lock the wave 6 receiving section contracts with failing UI tests

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `templates/scan/receive_pallet.html`
- Verify: `templates/scan/receive.html`
- Verify: `templates/scan/receive_association.html`

**Step 1: Write the failing test**

Add one structure test for `receive_pallet`:

```python
def test_scan_receive_pallet_breaks_into_named_workflow_sections(self):
    response = self.client.get(reverse("scan:scan_receive_pallet"))

    self.assertContains(response, 'id="scan-receive-pallet-create-card"')
    self.assertContains(response, 'id="scan-receive-pallet-listing-upload-card"')
```

Extend it with conditional-stage markers and current hooks:

```python
self.assertContains(response, 'id="listing_file"')
self.assertContains(response, 'id="id_listing_file_type_pdf"')
self.assertContains(response, "scan-receive-pallet-primary-row")
self.assertContains(response, "scan-receive-pallet-actions-inline")
```

Add a second test for the remaining receiving screens:

```python
def test_scan_receive_surfaces_break_into_named_workflow_sections(self):
    receive_response = self.client.get(reverse("scan:scan_receive"))
    association_response = self.client.get(reverse("scan:scan_receive_association"))

    self.assertContains(receive_response, 'id="scan-receive-select-card"')
    self.assertContains(receive_response, 'id="scan-receive-create-card"')
    self.assertContains(receive_response, 'id="scan-receive-empty-card"')
    self.assertContains(association_response, 'id="scan-receive-association-create-card"')
```

Keep the existing route-specific markers:

```python
self.assertContains(receive_response, 'name="action" value="select_receipt"')
self.assertContains(receive_response, 'name="action" value="create_receipt"')
self.assertContains(association_response, "scan-receive-association-primary-row")
self.assertContains(association_response, 'id="association-lines-data"')
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_receive_pallet_breaks_into_named_workflow_sections wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_receive_surfaces_break_into_named_workflow_sections -v 2`

Expected: FAIL on the new section IDs because the receiving templates still render their large workflow blocks inline.

**Step 3: Write minimal implementation**

No production implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run the targeted tests above and confirm only the missing section markers fail.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "test: lock legacy ui wave 6 receiving contracts"
```

### Task 2: Extract `receive_pallet` into route-local workflow cards

**Files:**
- Modify: `templates/scan/receive_pallet.html`
- Create: `templates/scan/includes/receive_pallet_create_card.html`
- Create: `templates/scan/includes/receive_pallet_listing_upload_card.html`
- Create: `templates/scan/includes/receive_pallet_mapping_card.html`
- Create: `templates/scan/includes/receive_pallet_review_card.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Extend the `receive_pallet` structure test to require:

```python
self.assertContains(response, 'id="scan-receive-pallet-create-card"')
self.assertContains(response, 'id="scan-receive-pallet-listing-upload-card"')
```

Keep the stage and file-type contracts:

```python
self.assertContains(response, 'id="listing_file"')
self.assertContains(response, 'id="id_listing_file_type_pdf"')
self.assertContains(response, 'id="id_listing_file_type_excel"')
self.assertContains(response, 'id="id_listing_file_type_csv"')
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_receive_pallet_breaks_into_named_workflow_sections -v 2`

Expected: FAIL because the named wrappers do not exist yet.

**Step 3: Write minimal implementation**

Keep `receive_pallet.html` as the shell and script host:

```django
{% include "scan/includes/receive_pallet_create_card.html" %}
{% include "scan/includes/receive_pallet_listing_upload_card.html" %}
{% if listing_stage == "mapping" %}
  {% include "scan/includes/receive_pallet_mapping_card.html" %}
{% endif %}
{% if listing_stage == "review" %}
  {% include "scan/includes/receive_pallet_review_card.html" %}
{% endif %}
```

Inside the new includes:
- preserve `pallet_create`, `listing_upload`, `listing_map`, `listing_confirm`, and `listing_cancel`,
- preserve `listing_file`, `pending_token`, `listing_match`, and `data-field` / `data-lock`,
- do not move the file-options or listing-match scripts out of the route shell.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_receive_pallet_breaks_into_named_workflow_sections -v 2`

Expected: PASS for the new section and hook assertions.

**Step 5: Commit**

```bash
git add templates/scan/receive_pallet.html templates/scan/includes/receive_pallet_create_card.html templates/scan/includes/receive_pallet_listing_upload_card.html templates/scan/includes/receive_pallet_mapping_card.html templates/scan/includes/receive_pallet_review_card.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "refactor: split receive pallet workflow cards"
```

### Task 3: Extract `receive` into named local cards for selection, creation, and active work

**Files:**
- Modify: `templates/scan/receive.html`
- Create: `templates/scan/includes/receive_select_card.html`
- Create: `templates/scan/includes/receive_create_card.html`
- Create: `templates/scan/includes/receive_active_summary_card.html`
- Create: `templates/scan/includes/receive_add_line_card.html`
- Create: `templates/scan/includes/receive_lines_card.html`
- Create: `templates/scan/includes/receive_empty_card.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Extend the receiving structure test to require:

```python
self.assertContains(receive_response, 'id="scan-receive-select-card"')
self.assertContains(receive_response, 'id="scan-receive-create-card"')
self.assertContains(receive_response, 'id="scan-receive-empty-card"')
```

Keep the current receipt contracts:

```python
self.assertContains(receive_response, 'value="select_receipt"')
self.assertContains(receive_response, 'value="create_receipt"')
self.assertContains(receive_response, "ui-comp-status-pill")
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_receive_surfaces_break_into_named_workflow_sections -v 2`

Expected: FAIL because the new receive wrappers do not exist yet.

**Step 3: Write minimal implementation**

Keep `receive.html` as the route shell and choose explicit includes:

```django
{% include "scan/includes/receive_select_card.html" %}
{% include "scan/includes/receive_create_card.html" %}
{% if selected_receipt %}
  {% include "scan/includes/receive_active_summary_card.html" %}
  {% include "scan/includes/receive_add_line_card.html" %}
  {% include "scan/includes/receive_lines_card.html" %}
{% else %}
  {% include "scan/includes/receive_empty_card.html" %}
{% endif %}
```

Inside the new includes:
- preserve `select_receipt`, `create_receipt`, `add_line`, and `receive_lines`,
- keep `product-data` JSON and `product-options` datalist attached to the add-line workflow,
- preserve all existing status-pill and pending-count behaviors.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_receive_surfaces_break_into_named_workflow_sections -v 2`

Expected: PASS for the receive section assertions.

**Step 5: Commit**

```bash
git add templates/scan/receive.html templates/scan/includes/receive_select_card.html templates/scan/includes/receive_create_card.html templates/scan/includes/receive_active_summary_card.html templates/scan/includes/receive_add_line_card.html templates/scan/includes/receive_lines_card.html templates/scan/includes/receive_empty_card.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "refactor: split receive workflow cards"
```

### Task 4: Extract `receive_association` into creation and allocation cards

**Files:**
- Modify: `templates/scan/receive_association.html`
- Create: `templates/scan/includes/receive_association_create_card.html`
- Create: `templates/scan/includes/receive_association_allocations_card.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Extend the receiving structure test to require:

```python
self.assertContains(association_response, 'id="scan-receive-association-create-card"')
```

Keep the local dynamic markers:

```python
self.assertContains(association_response, "scan-receive-association-primary-row")
self.assertContains(association_response, "scan-receive-association-actions-inline")
self.assertContains(association_response, 'id="association-lines-data"')
self.assertContains(association_response, 'id="association-lines-errors"')
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_receive_surfaces_break_into_named_workflow_sections -v 2`

Expected: FAIL because the association wrappers do not exist yet.

**Step 3: Write minimal implementation**

Keep `receive_association.html` as the shell and script host:

```django
{% include "scan/includes/receive_association_create_card.html" %}
{% if selected_receipt %}
  {% include "scan/includes/receive_association_allocations_card.html" %}
{% endif %}
```

Inside the new includes:
- preserve the single create form boundary,
- keep the hors-format subsection inside the create card,
- preserve `add_allocation`, `receipt_id`, and the allocations table,
- do not move the hors-format `json_script` payloads or JS out of the route shell.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_receive_surfaces_break_into_named_workflow_sections -v 2`

Expected: PASS for the association section assertions.

**Step 5: Commit**

```bash
git add templates/scan/receive_association.html templates/scan/includes/receive_association_create_card.html templates/scan/includes/receive_association_allocations_card.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "refactor: split receive association workflow cards"
```

### Task 5: Run final wave 6 verification and land the receiving wave

**Files:**
- Verify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `wms/tests/views/tests_views_scan_receipts.py`
- Verify: `wms/tests/views/tests_views.py`

**Step 1: Write the failing test**

No new test in this task. Use the tests added above as the final regression gate.

**Step 2: Run test to verify it fails**

Not applicable.

**Step 3: Write minimal implementation**

No new production implementation in this task.

**Step 4: Run test to verify it passes**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_views_scan_receipts \
  wms.tests.views.tests_views \
  -v 2
git diff --check
```

Expected: PASS and no diff-check output.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-24-legacy-ui-wave6-receiving-design.md docs/plans/2026-03-24-legacy-ui-wave6-receiving-implementation-plan.md templates/scan/receive_pallet.html templates/scan/receive.html templates/scan/receive_association.html templates/scan/includes/receive_pallet_create_card.html templates/scan/includes/receive_pallet_listing_upload_card.html templates/scan/includes/receive_pallet_mapping_card.html templates/scan/includes/receive_pallet_review_card.html templates/scan/includes/receive_select_card.html templates/scan/includes/receive_create_card.html templates/scan/includes/receive_active_summary_card.html templates/scan/includes/receive_add_line_card.html templates/scan/includes/receive_lines_card.html templates/scan/includes/receive_empty_card.html templates/scan/includes/receive_association_create_card.html templates/scan/includes/receive_association_allocations_card.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "refactor: deliver legacy ui wave 6 receiving split"
```
