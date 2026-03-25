# UI Lab DocumentActions Demo Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add one recommended document-actions demo to `scan/ui-lab/` so the team can evaluate a grouped-document-access contract on desktop and mobile before any production adoption.

**Architecture:** Keep the demo isolated inside `UI Lab` as a staff-only, non-runtime reference. Extend the existing `scan/ui-lab/` template and local stylesheet with one dedicated document-actions example that stays compact, homogeneous, and clearly distinct from page-level or workflow actions.

**Tech Stack:** Django templates, Bootstrap legacy UI, local `scan/ui-lab.css`, Django test suite

---

### Task 1: Add failing UI Lab assertions for the recommended document-actions demo

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add a focused test for the document-actions demo contract with assertions such as:

```python
self.assertContains(response, 'id="ui-lab-document-actions-demo"')
self.assertContains(response, 'id="ui-lab-document-actions-demo-title"')
self.assertContains(response, 'id="ui-lab-document-actions-demo-body"')
self.assertContains(response, 'id="ui-lab-document-actions-demo-action-1"')
```

Also assert that the demo does not drift into primary or upload behavior:

```python
self.assertNotContains(response, 'id="ui-lab-document-actions-demo-primary-action"')
self.assertNotContains(response, 'id="ui-lab-document-actions-demo-upload"')
```

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_ui_lab_exposes_recommended_document_actions_demo_contract -v 2
```

Expected:
- failure because the document-actions demo markup is not rendered yet

**Step 3: Keep the test narrowly scoped**

Do not test production shipment or tracking panels. Only define the dedicated `UI Lab` contract.

**Step 4: Re-run until the failure is the expected one**

Confirm the test fails because the new demo markup is missing, not because of unrelated setup.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "test: add ui lab document actions demo coverage"
```

### Task 2: Add the recommended document-actions demo markup

**Files:**
- Modify: `templates/scan/ui_lab.html`
- Optional Modify: `wms/views_scan_misc.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Add a dedicated UI Lab article for the document-actions demo**

Create a new article separate from:
- the toolbar demo
- the table demo
- the empty-state demo
- the page-header demo

Use stable IDs for:
- demo container
- title
- body
- at least one document action

**Step 2: Build the grouped-document shape**

Use a realistic operational example, such as:
- one group title
- one short help line
- three or four tertiary document actions

Keep the demo read-only and self-contained.

**Step 3: Add any missing static labels through local context only if needed**

If the template becomes noisy, add tiny helper strings in `wms/views_scan_misc.py`. Keep them demo-only.

**Step 4: Run targeted tests**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 1
```

Expected:
- the dedicated document-actions test passes
- no existing `UI Lab` assertions regress

**Step 5: Commit**

```bash
git add templates/scan/ui_lab.html wms/views_scan_misc.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add ui lab document actions demo markup"
```

### Task 3: Add local styling for the document-actions demo

**Files:**
- Modify: `wms/static/scan/ui-lab.css`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Add dedicated demo-local classes**

Add classes such as:

```css
.ui-lab-document-actions-demo-shell { ... }
.ui-lab-document-actions-demo-card { ... }
.ui-lab-document-actions-demo-copy { ... }
.ui-lab-document-actions-demo-actions { ... }
```

Focus on:
- compact grouped layout
- clear hierarchy
- responsive wrapping
- no page-header or toolbar feel

**Step 2: Keep all styling local**

Do not move any of these rules into shared production CSS. Keep them in `wms/static/scan/ui-lab.css`.

**Step 3: Run targeted tests**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 1
```

Expected:
- all relevant tests pass

**Step 4: Manually inspect the demo**

Open `scan/ui-lab/` and verify:
- desktop readability
- mobile wrapping
- clear distinction from the page-header and toolbar demos

**Step 5: Commit**

```bash
git add wms/static/scan/ui-lab.css
git commit -m "style: add ui lab document actions demo"
```

### Task 4: Final verification and governance check

**Files:**
- Modify: none
- Test: `wms/tests/views/tests_views_scan_misc.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Run the full targeted verification set**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc wms.tests.views.tests_scan_bootstrap_ui -v 1
git diff --check
git status --short --branch
```

Expected:
- tests pass
- no diff hygiene issues
- branch only contains intended demo changes

**Step 2: Review against governance**

Verify manually that the work:
- stays inside `UI Lab`
- does not introduce a new shared primitive
- does not drift into a primary action cluster or upload block

**Step 3: Record manual review notes**

Capture brief notes for:
- desktop readability
- mobile wrapping
- any evidence that still keeps `DocumentActions` in convergence

**Step 4: Commit**

```bash
git add -A
git commit -m "docs: finalize ui lab document actions demo"
```

**Step 5: Prepare review**

Open a PR only after the verification outputs are clean and the scope remains strictly limited to the demo.
