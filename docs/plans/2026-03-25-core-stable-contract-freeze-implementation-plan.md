# Core Stable Contract Freeze Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Freeze the usage rules for the current `Core stable` legacy UI contracts through one short rules document and a light `UI Lab` clarification pass.

**Architecture:** Keep the change narrow and governance-oriented. Add one usage-rules document under `docs/plans/`, then clarify `Core stable` usage in `templates/scan/ui_lab.html` with minimal supporting test updates so the stable base becomes easier to consume without expanding the component surface.

**Tech Stack:** Django templates, legacy Bootstrap UI, `UI Lab`, Django view tests, Markdown docs

---

### Task 1: Write the stable-usage rules document

**Files:**
- Create: `docs/plans/2026-03-25-core-stable-contract-freeze-design.md`
- Modify: `docs/plans/2026-03-25-legacy-ui-adoption-note.md` only if a cross-link is genuinely needed

**Step 1: Draft the rules document**

Write a short document that freezes rules for:
- `ui_button`
- `ui_field`
- `ui_alert`
- `ui_status_badge`
- `ui_switch`
- `ui-comp-card`
- `ui-comp-panel`
- `ui-comp-actions`

Use a repeatable structure for each:
- role
- when to use
- when not to use
- allowed variants
- expected composition
- anti-patterns
- responsive/accessibility notes

**Step 2: Keep the scope tight**

Do not add new stable primitives. Do not write about convergence patterns except to say they remain out of scope.

**Step 3: Review for adoption alignment**

Confirm the document is consistent with:
- `docs/plans/2026-03-22-ui-library-governance-design.md`
- `docs/plans/2026-03-25-legacy-ui-adoption-note.md`

**Step 4: Hygiene check**

Run:

```bash
git diff --check
```

Expected:
- no whitespace or file-format issues

**Step 5: Commit**

```bash
git add docs/plans/2026-03-25-core-stable-contract-freeze-design.md
git commit -m "docs: define core stable usage rules"
```

### Task 2: Add a light Core stable guidance block to UI Lab

**Files:**
- Modify: `templates/scan/ui_lab.html`
- Optional Modify: `wms/static/scan/ui-lab.css`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add a focused test for the new stable-guidance block with assertions such as:

```python
self.assertContains(response, 'id="ui-lab-core-stable-rules"')
self.assertContains(response, "Core stable usage rules")
self.assertContains(response, "ui_button")
self.assertContains(response, "ui-comp-actions")
```

Keep the test narrow. It should verify that the stable guidance is visible, not restate the whole document.

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.<new_test_name> -v 2
```

Expected:
- failure because the guidance block is not rendered yet

**Step 3: Add the minimal UI Lab markup**

Add one light guidance block near the `Core stable` area in `templates/scan/ui_lab.html`.

Include:
- a short title,
- a short explanatory sentence,
- a concise reminder about reuse rules or stable responsibilities.

Do not create a large new gallery or duplicate all stable examples.

**Step 4: Add CSS only if needed**

If the guidance block needs a tiny layout or spacing adjustment, keep it local in:

```css
wms/static/scan/ui-lab.css
```

Do not create a new shared production rule for this.

**Step 5: Re-run the targeted test**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.<new_test_name> -v 2
```

Expected:
- the new stable-guidance test passes

**Step 6: Commit**

```bash
git add templates/scan/ui_lab.html wms/static/scan/ui-lab.css wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: clarify core stable usage in ui lab"
```

### Task 3: Run the full targeted verification set

**Files:**
- Modify: none
- Test: `wms/tests/views/tests_views_scan_misc.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Run the stable-target verification**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc wms.tests.views.tests_scan_bootstrap_ui -v 1
git diff --check
git status --short --branch
```

Expected:
- tests pass
- no diff hygiene issues
- only the intended doc and `UI Lab` clarification changes are present

**Step 2: Review the result against scope**

Verify manually that:
- the work stayed inside docs and `UI Lab`,
- no new convergence demo was introduced,
- no stable primitive API changed,
- no production screen was touched.

**Step 3: Commit**

```bash
git add -A
git commit -m "docs: finalize core stable contract freeze"
```

**Step 4: Prepare integration**

Only after the verification is clean:
- decide whether to push directly or open a short PR,
- but do not extend the scope into convergence patterns.
