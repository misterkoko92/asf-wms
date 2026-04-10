# Shared Number Input Sizing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the shared legacy number-input controls smaller and variable-driven so values never overlap the left-side `+ / -` buttons, especially in narrow table cells.

**Architecture:** Keep the number-input behavior centralized in `wms/static/scan/modules/core.js`, move the component geometry in `wms/static/scan/scan-bootstrap.css` to shared CSS variables, and update only the narrow legacy contexts that still need explicit compact sizing after the shared reduction. Keep the contract aligned across the UI Lab, repo-reference docs, and regression tests.

**Tech Stack:** Django templates, shared legacy JS/CSS assets, Django test runner, Playwright-backed UI tests already present in `wms/tests/core/tests_ui.py`.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:verification-before-completion`, `@repo-reference-governance`.

### Task 1: Add failing shared CSS contract tests for variable-driven sizing

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Review: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Write the failing tests**

Add assertions that prove:
- the shared number-input CSS defines reusable variables for control sizing and reserved value padding
- the default button width is smaller than the current contract
- the small or compact sizing branch also derives from variables rather than a second hard-coded padding formula
- recipient preference quantity cells still keep an explicit width contract compatible with the shared component

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  -v 2
```

Expected: failures because the CSS still uses hard-coded geometry.

### Task 2: Add failing runtime tests for enhancement sizing variants

**Files:**
- Modify: `wms/tests/core/tests_ui.py`
- Review: `templates/scan/ui_lab.html`

**Step 1: Write the failing tests**

Add tests that prove:
- the UI Lab demo still gets enhanced into the shared wrapper
- the shared wrapper exposes the expected classes or attributes for reduced-size controls
- dynamically added number inputs in existing scan flows still get enhanced with the same sizing semantics

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.core.tests_ui \
  -v 2
```

Expected: failures because the new shared sizing contract is not implemented yet.

### Task 3: Implement variable-driven number-input geometry in shared CSS

**Files:**
- Modify: `wms/static/scan/scan-bootstrap.css`

**Step 1: Write minimal implementation**

Refactor the shared number-input CSS to:
- introduce variables for button width, button height, button gap, start inset, and reserved input padding
- reduce the default button footprint
- derive input `padding-left` from the same variables that size the controls
- preserve `is-sm`
- add a compact modifier if needed for narrow contexts

Keep the selectors scoped to the existing shared `ui-number-input` contract.

**Step 2: Run the targeted tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  -v 2
```

Expected: the CSS contract tests pass.

**Step 3: Commit**

```bash
git add wms/static/scan/scan-bootstrap.css wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "fix: tighten shared number input sizing"
```

### Task 4: Update shared runtime enhancement only where sizing metadata is needed

**Files:**
- Modify: `wms/static/scan/modules/core.js`
- Review: `templates/portal/includes/order_create_unit_products_card.html`
- Review: `templates/portal/includes/order_create_ready_cartons_card.html`
- Review: `templates/portal/includes/order_create_ready_kits_card.html`

**Step 1: Write minimal implementation**

Update the shared enhancement logic only if needed to:
- propagate a compact wrapper modifier from existing field classes or local opt-in classes
- preserve existing `min`, `max`, `step`, `disabled`, `readonly`, `input`, and `change` behavior
- avoid introducing screen-specific branching into the core runtime

If the CSS-only refactor is sufficient, keep the JS change minimal and explicit.

**Step 2: Run the targeted tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.core.tests_ui \
  -v 2
```

Expected: the runtime enhancement tests pass with the new sizing contract.

**Step 3: Commit**

```bash
git add wms/static/scan/modules/core.js wms/tests/core/tests_ui.py
git commit -m "fix: keep shared number input enhancement aligned with compact sizing"
```

### Task 5: Apply compact sizing to the known narrow contexts

**Files:**
- Modify: `wms/static/scan/scan-bootstrap.css`
- Modify: `templates/portal/recipient_detail.html`
- Modify: `templates/portal/recipient_preferences.html`
- Modify: `templates/scan/admin_recipient_organization_detail.html`
- Review: `templates/scan/print_template_edit.html`
- Review: `templates/scan/includes/receive_pallet_review_card.html`
- Review: `templates/scan/includes/imports_products_card.html`

**Step 1: Write the failing assertions or coverage if needed**

If current tests do not cover the constrained quantity fields, add assertions in `wms/tests/views/tests_scan_bootstrap_ui.py` that prove the recipient preference quantity inputs opt into the compact shared sizing contract.

**Step 2: Write minimal implementation**

Apply the compact shared contract to the narrow contexts that need it most:
- recipient preference quantity inputs on portal shipper
- recipient preference quantity inputs on portal recipient
- recipient preference quantity inputs on scan/admin

Only widen or rebalance local widths if the smaller shared controls still do not leave enough reading space.

**Step 3: Run the targeted tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.core.tests_ui \
  -v 2
```

Expected: the shared and constrained-context UI tests pass together.

**Step 4: Commit**

```bash
git add \
  wms/static/scan/scan-bootstrap.css \
  templates/portal/recipient_detail.html \
  templates/portal/recipient_preferences.html \
  templates/scan/admin_recipient_organization_detail.html \
  wms/tests/views/tests_scan_bootstrap_ui.py \
  wms/tests/core/tests_ui.py
git commit -m "fix: keep narrow quantity fields readable with compact number controls"
```

### Task 6: Update the UI Lab and repo-reference contract

**Files:**
- Modify: `templates/scan/ui_lab.html`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Review: `docs/repo-reference/03-impact-map.md`

**Step 1: Update the docs and contract demo**

Document:
- the variable-backed shared sizing contract
- the smaller default button geometry
- the compact variant for constrained fields

Keep the UI Lab example aligned with the real shared markup and styling.

**Step 2: Run final verification**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.core.tests_ui \
  wms.tests.views.tests_portal_bootstrap_ui \
  -v 2
```

Expected: the number-input contract, UI Lab, and shared legacy surface coverage all pass.

**Step 3: Commit**

```bash
git add templates/scan/ui_lab.html docs/repo-reference/04-shared-contracts.md
git commit -m "docs: refresh shared number input contract"
```
