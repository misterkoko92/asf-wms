# UI Lab WorkflowActionBar Demo Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add one recommended workflow-action-bar demo to `scan/ui-lab/` so the team can evaluate an end-of-step action contract on desktop and mobile before any production adoption.

**Architecture:** Keep the demo isolated inside `UI Lab` as a staff-only, non-runtime reference. Extend the existing `scan/ui-lab/` template and local stylesheet with one dedicated workflow-action-bar example that stays compact, action-oriented, and clearly distinct from toolbar or document-access patterns.

**Tech Stack:** Django templates, Bootstrap legacy UI, local `scan/ui-lab.css`, Django test suite

---

### Task 1: Add failing UI Lab assertions for the recommended workflow-action-bar demo

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add a focused test for the workflow-action-bar demo contract with assertions such as:

```python
self.assertContains(response, 'id="ui-lab-workflow-action-bar-demo"')
self.assertContains(response, 'id="ui-lab-workflow-action-bar-demo-body"')
self.assertContains(response, 'id="ui-lab-workflow-action-bar-demo-primary-action"')
self.assertContains(response, 'id="ui-lab-workflow-action-bar-demo-secondary-action"')
```

Also assert that the demo does not drift into toolbar or document behavior:

```python
self.assertNotContains(response, 'id="ui-lab-workflow-action-bar-demo-search"')
self.assertNotContains(response, 'id="ui-lab-workflow-action-bar-demo-document-action"')
```

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_ui_lab_exposes_recommended_workflow_action_bar_demo_contract -v 2
```

Expected:
- failure because the workflow-action-bar demo markup is not rendered yet

**Step 3: Keep the test narrowly scoped**

Do not test production shipment or output forms. Only define the dedicated `UI Lab` contract.

**Step 4: Re-run until the failure is the expected one**

Confirm the test fails because the new demo markup is missing, not because of unrelated setup.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "test: add ui lab workflow action bar demo coverage"
```

### Task 2: Add the recommended workflow-action-bar demo markup

**Files:**
- Modify: `templates/scan/ui_lab.html`
- Optional Modify: `wms/views_scan_misc.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Add a dedicated UI Lab article for the workflow-action-bar demo**

Create a new article separate from:
- the page-header demo
- the document-actions demo
- the toolbar demo
- the table demo
- the empty-state demo

Use stable IDs for:
- demo container
- context/body
- primary action
- secondary action

**Step 2: Build the end-of-step action shape**

Use a realistic operational example, such as:
- one short context reminder
- one primary action
- one secondary action
- one low-emphasis fallback action

Keep the demo read-only and self-contained.

**Step 3: Add any missing static labels through local context only if needed**

If the template becomes noisy, add tiny helper strings in `wms/views_scan_misc.py`. Keep them demo-only.

**Step 4: Run targeted tests**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 1
```

Expected:
- the dedicated workflow-action-bar test passes
- no existing `UI Lab` assertions regress

**Step 5: Commit**

```bash
git add templates/scan/ui_lab.html wms/views_scan_misc.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add ui lab workflow action bar demo markup"
```

### Task 3: Add local styling for the workflow-action-bar demo

**Files:**
- Modify: `wms/static/scan/ui-lab.css`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Add dedicated demo-local classes**

Add classes such as:

```css
.ui-lab-workflow-action-bar-demo-shell { ... }
.ui-lab-workflow-action-bar-demo-card { ... }
.ui-lab-workflow-action-bar-demo-copy { ... }
.ui-lab-workflow-action-bar-demo-actions { ... }
```

Focus on:
- compact end-of-step layout
- clear action hierarchy
- responsive wrapping
- no toolbar or page-header feel

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
- clear distinction from the page-header and document-actions demos

**Step 5: Commit**

```bash
git add wms/static/scan/ui-lab.css
git commit -m "style: add ui lab workflow action bar demo"
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
- does not drift into toolbar or document-access territory

**Step 3: Record manual review notes**

Capture brief notes for:
- desktop readability
- mobile wrapping
- any evidence that still keeps `WorkflowActionBar` in convergence

**Step 4: Commit**

```bash
git add -A
git commit -m "docs: finalize ui lab workflow action bar demo"
```

**Step 5: Prepare review**

Open a PR only after the verification outputs are clean and the scope remains strictly limited to the demo.
