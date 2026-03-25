# UI Lab Toolbar Demo Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add one recommended responsive toolbar demo to `scan/ui-lab/` so the team can evaluate the contract on desktop and mobile before any production adoption.

**Architecture:** Keep the demo isolated inside `UI Lab` as a staff-only, non-runtime reference. Extend the existing `scan/ui-lab/` template and local stylesheet with a single richer toolbar example above a lightweight fake list context, and lock the demo with targeted UI rendering tests.

**Tech Stack:** Django templates, Django view context, Bootstrap legacy UI, local `scan/ui-lab.css`, local `scan/ui-lab.js` only if absolutely required, Django test suite

---

### Task 1: Add failing UI Lab assertions for the recommended toolbar demo

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add assertions to the existing `scan_ui_lab` coverage for the new demo contract:

```python
self.assertContains(response, 'id="ui-lab-toolbar-demo"')
self.assertContains(response, 'id="ui-lab-toolbar-demo-query"')
self.assertContains(response, 'id="ui-lab-toolbar-demo-toggle"')
self.assertContains(response, 'id="ui-lab-toolbar-demo-primary-action"')
self.assertContains(response, 'id="ui-lab-toolbar-demo-chips"')
self.assertContains(response, 'id="ui-lab-toolbar-demo-table"')
```

Also assert that the filter toggle does not submit a runtime action:

```python
self.assertNotContains(response, 'name="action" value="filter"')
```

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 1
```

Expected:
- failure because the new demo IDs are not rendered yet

**Step 3: Write minimal implementation**

Do not change production templates yet. Only add the failing contract assertions first.

**Step 4: Run test to confirm the failure is the expected one**

Run the same command and confirm the missing demo markup is the cause.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "test: add ui lab toolbar demo coverage"
```

### Task 2: Add the recommended toolbar demo markup

**Files:**
- Modify: `templates/scan/ui_lab.html`
- Optional Modify: `wms/views_scan_misc.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Extend the UI Lab template with the new demo article**

Add a dedicated article after the current toolbar contract, for example:

```html
<article id="ui-lab-toolbar-demo" class="ui-lab-surface">
  <h4>Toolbar recommande</h4>
  <div class="ui-lab-toolbar-demo-shell">
    <!-- main line -->
    <!-- secondary filter panel -->
    <!-- active chips -->
    <!-- demo table -->
  </div>
</article>
```

Use stable IDs for:
- query input
- status select
- filter toggle
- secondary filter panel
- primary action
- chip list
- table shell

**Step 2: Add any missing static labels through local context only if necessary**

If template readability suffers, add small context helpers in `wms/views_scan_misc.py`. Keep them demo-only and translation-neutral to the current paused scope.

**Step 3: Run tests**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_misc -v 1
```

Expected:
- tests still fail until CSS or markup details required by assertions are complete
- no unrelated UI Lab regressions

**Step 4: Finish minimal markup until tests pass**

Keep the demo read-only:
- no real form target
- no runtime action names
- no business submit payload

**Step 5: Commit**

```bash
git add templates/scan/ui_lab.html wms/views_scan_misc.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add ui lab toolbar demo markup"
```

### Task 3: Add local responsive styling for the demo

**Files:**
- Modify: `wms/static/scan/ui-lab.css`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Add dedicated demo classes**

Add classes such as:

```css
.ui-lab-toolbar-demo-shell { ... }
.ui-lab-toolbar-demo-main { ... }
.ui-lab-toolbar-demo-search { ... }
.ui-lab-toolbar-demo-actions { ... }
.ui-lab-toolbar-demo-panel { ... }
.ui-lab-toolbar-demo-chips { ... }
```

Focus on:
- clean desktop alignment
- readable wrap on smaller widths
- visible primary action
- inline secondary filter panel spacing

**Step 2: Avoid creating shared production classes**

Do not move these styles into scan-wide shared CSS. Keep them local to `ui-lab.css`.

**Step 3: Run targeted tests**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 1
```

Expected:
- test suite passes

**Step 4: Manually inspect the demo**

Open `scan/ui-lab/` and verify:
- desktop width
- narrow tablet width
- mobile width

Confirm:
- primary action remains visible
- search and filters stay understandable
- the secondary filter panel reads correctly below the main line

**Step 5: Commit**

```bash
git add wms/static/scan/ui-lab.css
git commit -m "style: add responsive ui lab toolbar demo"
```

### Task 4: Add minimal toggle behavior only if markup-only demo is insufficient

**Files:**
- Optional Modify: `wms/static/scan/ui-lab.js`
- Modify: `templates/scan/ui_lab.html`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Decide if the demo already works without custom JS**

Prefer one of:
- always-visible secondary panel
- Bootstrap-native collapse markup

Only use custom JS if neither is acceptable for the demo.

**Step 2: If needed, add a minimal demo-only toggle**

Keep logic tiny and isolated:

```javascript
const toggle = document.getElementById("ui-lab-toolbar-demo-toggle");
const panel = document.getElementById("ui-lab-toolbar-demo-panel");
```

Toggle only:
- `hidden`
- `aria-expanded`

No persistence, no business logic, no shared helper.

**Step 3: Re-run tests**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc wms.tests.views.tests_scan_bootstrap_ui -v 1
```

Expected:
- all targeted tests pass

**Step 4: Keep the smallest working solution**

If Bootstrap-native collapse is enough, delete any extra custom JS before committing.

**Step 5: Commit**

```bash
git add templates/scan/ui_lab.html wms/static/scan/ui-lab.js wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add demo-only toolbar filter toggle"
```

### Task 5: Final verification and hygiene

**Files:**
- Modify: none
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
- branch only contains intended changes

**Step 2: Review against governance**

Verify manually that the work:
- stays in `UI Lab`
- does not introduce a new shared primitive
- does not broaden into `ActionBar`, `DocumentActions`, or production page refactors

**Step 3: Summarize manual responsive results**

Record brief notes for:
- desktop
- mobile portrait
- any edge case that should keep `Toolbar` in convergence

**Step 4: Commit**

```bash
git add -A
git commit -m "docs: finalize ui lab toolbar demo"
```

**Step 5: Prepare review**

Open a PR only after the verification outputs are clean and the scope remains strictly limited to the demo.
