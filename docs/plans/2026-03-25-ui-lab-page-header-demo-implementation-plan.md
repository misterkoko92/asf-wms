# UI Lab PageHeader Demo Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add one recommended page-header demo to `scan/ui-lab/` so the team can evaluate the `title + context + actions` contract on desktop and mobile before any production adoption.

**Architecture:** Keep the demo isolated inside `UI Lab` as a staff-only, non-runtime reference. Extend the existing `scan/ui-lab/` template and local stylesheet with one dedicated page-header example that stays compact, operational, and clearly separate from toolbar behavior.

**Tech Stack:** Django templates, Bootstrap legacy UI, local `scan/ui-lab.css`, Django test suite

---

### Task 1: Add failing UI Lab assertions for the recommended page-header demo

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add a focused test for the page-header demo contract with assertions such as:

```python
self.assertContains(response, 'id="ui-lab-page-header-demo"')
self.assertContains(response, 'id="ui-lab-page-header-demo-title"')
self.assertContains(response, 'id="ui-lab-page-header-demo-body"')
self.assertContains(response, 'id="ui-lab-page-header-demo-primary-action"')
```

Also assert that the demo does not drift into toolbar/breadcrumb content:

```python
self.assertNotContains(response, 'id="ui-lab-page-header-demo-breadcrumbs"')
self.assertNotContains(response, 'id="ui-lab-page-header-demo-search"')
```

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_ui_lab_exposes_recommended_page_header_demo_contract -v 2
```

Expected:
- failure because the page-header demo markup is not rendered yet

**Step 3: Keep the test narrowly scoped**

Do not test global app headers. Only define the dedicated `UI Lab` contract.

**Step 4: Re-run until the failure is the expected one**

Confirm the test fails because the new demo markup is missing, not because of unrelated setup.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "test: add ui lab page header demo coverage"
```

### Task 2: Add the recommended page-header demo markup

**Files:**
- Modify: `templates/scan/ui_lab.html`
- Optional Modify: `wms/views_scan_misc.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Add a dedicated UI Lab article for the page-header demo**

Create a new article separate from:
- the toolbar demo
- the table demo
- the empty-state demo

Use stable IDs for:
- demo container
- title
- body
- primary action

**Step 2: Build the page-work shape**

Use a realistic operational example, such as:
- one title
- one short context line
- one primary action
- one or two secondary actions

Keep the demo read-only and self-contained.

**Step 3: Add any missing static labels through local context only if needed**

If the template becomes noisy, add tiny helper strings in `wms/views_scan_misc.py`. Keep them demo-only.

**Step 4: Run targeted tests**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 1
```

Expected:
- the dedicated page-header test passes
- no existing `UI Lab` assertions regress

**Step 5: Commit**

```bash
git add templates/scan/ui_lab.html wms/views_scan_misc.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add ui lab page header demo markup"
```

### Task 3: Add local styling for the page-header demo

**Files:**
- Modify: `wms/static/scan/ui-lab.css`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Add dedicated demo-local classes**

Add classes such as:

```css
.ui-lab-page-header-demo-shell { ... }
.ui-lab-page-header-demo-card { ... }
.ui-lab-page-header-demo-copy { ... }
.ui-lab-page-header-demo-actions { ... }
```

Focus on:
- compact layout
- clear hierarchy
- responsive action wrapping
- no hero feel

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
- desktop compactness
- mobile stacking
- clear distinction from the toolbar demo directly below or above it

**Step 5: Commit**

```bash
git add wms/static/scan/ui-lab.css
git commit -m "style: add ui lab page header demo"
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
- does not drift into toolbar, breadcrumbs, or hero territory

**Step 3: Record manual review notes**

Capture brief notes for:
- desktop readability
- mobile stacking
- any evidence that still keeps `PageHeader` in convergence

**Step 4: Commit**

```bash
git add -A
git commit -m "docs: finalize ui lab page header demo"
```

**Step 5: Prepare review**

Open a PR only after the verification outputs are clean and the scope remains strictly limited to the demo.
