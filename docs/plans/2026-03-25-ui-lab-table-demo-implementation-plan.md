# UI Lab Table Demo Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add one recommended dense table demo to `scan/ui-lab/` so the team can evaluate the contract on desktop and mobile before any production adoption.

**Architecture:** Keep the demo isolated inside `UI Lab` as a staff-only, non-runtime reference. Extend the existing `scan/ui-lab/` template and local stylesheet with one dedicated dense-table example that remains structurally tabular on all breakpoints and uses a responsive wrapper for mobile compatibility.

**Tech Stack:** Django templates, Bootstrap legacy UI, local `scan/ui-lab.css`, Django test suite

---

### Task 1: Add failing UI Lab assertions for the recommended dense table demo

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add a new focused test for the table demo contract with assertions such as:

```python
self.assertContains(response, 'id="ui-lab-table-demo"')
self.assertContains(response, 'id="ui-lab-table-demo-caption"')
self.assertContains(response, 'id="ui-lab-table-demo-table"')
self.assertContains(response, 'id="ui-lab-table-demo-action-1"')
self.assertContains(response, "ui-comp-status-pill")
```

Also assert that the demo does not introduce selection controls:

```python
self.assertNotContains(response, 'type="checkbox"')
```

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_ui_lab_exposes_recommended_table_demo_contract -v 2
```

Expected:
- failure because the table demo markup is not rendered yet

**Step 3: Keep the test narrowly scoped**

Do not add production assertions. Only define the dedicated `UI Lab` contract.

**Step 4: Re-run until the failure is the expected one**

Confirm the test fails because the new demo IDs and content are missing, not because of a typo or unrelated setup issue.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "test: add ui lab table demo coverage"
```

### Task 2: Add the recommended dense table demo markup

**Files:**
- Modify: `templates/scan/ui_lab.html`
- Optional Modify: `wms/views_scan_misc.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Add a dedicated UI Lab article for the table demo**

Create a new article separate from:
- the minimal table example
- the recommended toolbar demo

Use stable IDs for:
- demo container
- caption
- table element
- at least one row action

Keep the demo read-only and self-contained.

**Step 2: Build the dense business shape**

Use a responsive wrapper and a realistic column set, for example:
- reference
- association
- destination
- priority or volume
- status
- action

Use one lightweight row action only, such as `Voir`.

**Step 3: Add any missing static labels through local context only if needed**

If the template becomes noisy, add small helper strings in `wms/views_scan_misc.py`. Keep them demo-only.

**Step 4: Run targeted tests**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 1
```

Expected:
- the new dedicated test passes once the markup is in place
- no existing `UI Lab` assertions regress

**Step 5: Commit**

```bash
git add templates/scan/ui_lab.html wms/views_scan_misc.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add ui lab table demo markup"
```

### Task 3: Add local styling for the dense-table demo

**Files:**
- Modify: `wms/static/scan/ui-lab.css`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Add dedicated demo-local classes**

Add classes such as:

```css
.ui-lab-table-demo-shell { ... }
.ui-lab-table-demo-table-wrap { ... }
.ui-lab-table-demo-meta { ... }
.ui-lab-table-demo-status { ... }
.ui-lab-table-demo-action { ... }
```

Focus on:
- minimum table width
- compact but legible cell rhythm
- balanced status and action cells
- clean caption spacing

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
- narrow tablet width
- mobile width with horizontal overflow still usable

Confirm:
- the table remains visibly tabular
- status is easy to scan
- the row action stays secondary

**Step 5: Commit**

```bash
git add wms/static/scan/ui-lab.css
git commit -m "style: add responsive ui lab table demo"
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
- does not add bulk actions, selection, or document workflows

**Step 3: Record manual review notes**

Capture brief notes for:
- desktop scanability
- mobile overflow behavior
- any evidence that still keeps `Table` in convergence

**Step 4: Commit**

```bash
git add -A
git commit -m "docs: finalize ui lab table demo"
```

**Step 5: Prepare review**

Open a PR only after the verification outputs are clean and the scope remains strictly limited to the demo.
