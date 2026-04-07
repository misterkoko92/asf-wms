# Shared Number Input Controls Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a shared legacy Django number-input control with left-side decrement/increment buttons and safe text spacing across scan, portal, planning, and benevole surfaces.

**Architecture:** Keep native number inputs as the underlying form control, then progressively enhance them from the shared legacy core script. Shared Bootstrap-layer CSS defines the wrapper, controls, and input spacing, while the shared UI Lab documents the contract and provides a stable runtime demo for tests.

**Tech Stack:** Django templates, shared legacy JS (`wms/static/scan/modules/core.js`), shared CSS (`wms/static/scan/scan-bootstrap.css`), Django TestCase, Playwright UI test.

---

### Task 1: Lock The Shared Template Contract

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Modify: `templates/scan/ui_lab.html`
- Modify: `templates/portal/base.html`
- Modify: `templates/planning/base.html`
- Modify: `templates/benevole/base.html`

**Step 1: Write the failing tests**

- Add a scan bootstrap UI test asserting the UI Lab exposes a shared number-input contract block and demo field IDs.
- Add a portal bootstrap UI test asserting the portal base loads `scan/modules/core.js`.

**Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_portal_bootstrap_ui -v 2`

Expected: FAIL because the UI Lab block and shared script include do not exist yet.

**Step 3: Write minimal implementation**

- Add the UI Lab demo markup.
- Load `scan/modules/core.js` from portal, planning, and benevole base templates.

**Step 4: Run tests to verify they pass**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_portal_bootstrap_ui -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_portal_bootstrap_ui.py templates/scan/ui_lab.html templates/portal/base.html templates/planning/base.html templates/benevole/base.html
git commit -m "test: lock shared number input template contract"
```

### Task 2: Add Shared Styling For Left-Side Controls

**Files:**
- Modify: `wms/static/scan/scan-bootstrap.css`
- Modify: `templates/scan/ui_lab.html`

**Step 1: Write the failing test**

- Extend the UI Lab contract test to assert the presence of stable class names for the shared number-input wrapper and button group.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL because the classes are not rendered yet.

**Step 3: Write minimal implementation**

- Add shared wrapper/button markup to the UI Lab demo.
- Add CSS for wrapper layout, button stack, left padding, focus/disabled states, and native spinner suppression when enhanced.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/static/scan/scan-bootstrap.css templates/scan/ui_lab.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add shared number input styles"
```

### Task 3: Add Core Runtime Enhancement

**Files:**
- Modify: `wms/static/scan/modules/core.js`
- Test: `wms/tests/core/tests_ui.py`
- Verify Against: `templates/portal/includes/order_create_unit_products_card.html`

**Step 1: Write the failing test**

- Add a Playwright UI test on the UI Lab page that waits for the shared number-input demo, then asserts:
  - the demo input is wrapped by the shared control container
  - left-side decrement/increment buttons exist
  - clicking a button updates the value

**Step 2: Run test to verify it fails**

Run: `RUN_UI_TESTS=1 ./.venv/bin/python manage.py test wms.tests.core.tests_ui.ScanUiTests.test_scan_ui_lab_enhances_shared_number_input -v 2`

Expected: FAIL because the runtime enhancement does not exist yet.

**Step 3: Write minimal implementation**

- In `core.js`, scan for eligible `input[type="number"]`.
- Wrap them once, inject controls, and handle clicks with `min`/`max`/`step`.
- Dispatch `input` and `change` events after programmatic updates.
- Skip `disabled`, `readonly`, and explicit opt-out inputs.

**Step 4: Run test to verify it passes**

Run: `RUN_UI_TESTS=1 ./.venv/bin/python manage.py test wms.tests.core.tests_ui.ScanUiTests.test_scan_ui_lab_enhances_shared_number_input -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/static/scan/modules/core.js wms/tests/core/tests_ui.py
git commit -m "feat: enhance shared number inputs in core"
```

### Task 4: Update Shared Contract Docs And Final Verification

**Files:**
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Modify: `docs/repo-reference/03-impact-map.md` (only if the shared UI checklist needs explicit number-input mention)

**Step 1: Write the failing test**

- No automated failing doc test; use runtime code and UI tests as the source of truth.

**Step 2: Run verification before doc update**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_portal_bootstrap_ui -v 2`

Expected: PASS.

**Step 3: Write minimal implementation**

- Document the new shared number-input contract in repo-reference shared UI docs.

**Step 4: Run final verification**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_portal_bootstrap_ui -v 2`

Run: `RUN_UI_TESTS=1 ./.venv/bin/python manage.py test wms.tests.core.tests_ui.ScanUiTests.test_scan_ui_lab_enhances_shared_number_input -v 2`

Expected: PASS where Playwright is available; if unavailable, record that explicitly.

**Step 5: Commit**

```bash
git add docs/repo-reference/04-shared-contracts.md docs/repo-reference/03-impact-map.md
git commit -m "docs: record shared number input contract"
```
