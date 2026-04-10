# Recipient Preferences Filters Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add stock-style filter/sort controls to recipient product-preference pages and fix beneficiary-count number inputs so values no longer render under the +/- buttons.

**Architecture:** Extract a shared recipient-preference catalogue helper that applies query, category subtree filtering, and product-level sorting before templates render rows. Reuse the existing multi-level category UI pattern from scan stock, preserve filter state through row save/delete actions, and fix the shared number-input left padding in the shared scan bootstrap CSS so portal and scan forms stay aligned.

**Tech Stack:** Django views/templates, shared legacy Bootstrap CSS/JS, Django tests.

---

### Task 1: Add failing tests for recipient-preference filtering and sorting

**Files:**
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/views/tests_views_scan_admin.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Write the failing tests**

- Add portal recipient-scope tests proving:
  - `q` filters products by name on `portal_recipient_preferences`
  - `category` filters a selected subtree
  - `sort` supports `name`, `brand`, and `units_per_carton_estimate`
  - redirects after save/delete preserve active GET filters
- Add scan admin recipient-detail tests proving the same filter/sort behavior.
- Add bootstrap/UI tests proving the new filter controls render on the three line-by-line preference pages.

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_portal \
  wms.tests.views.tests_views_scan_admin \
  wms.tests.views.tests_portal_bootstrap_ui \
  -v 2
```

Expected: failures showing missing filter/sort context or missing rendered controls.

### Task 2: Add failing tests for the beneficiary-count number-input layout contract

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

- Assert the shared `.ui-number-input` CSS uses enough left padding for the two left-side controls so the number text starts to the right of the buttons.

**Step 2: Run the targeted test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_shared_number_input_keeps_value_clear_of_left_controls \
  -v 2
```

Expected: failure on the old padding value.

### Task 3: Implement the shared recipient-preference filter/sort helper

**Files:**
- Create: `wms/recipient_preference_view_helpers.py`
- Modify: `wms/views_portal_account.py`
- Modify: `wms/views_scan_admin.py`

**Step 1: Write minimal implementation**

- Build a shared helper that:
  - reads `q`, `category`, and `sort`
  - reuses category subtree logic from stock
  - filters/sorts active products before calling `list_effective_recipient_product_preferences`
  - returns the same category metadata needed by the stock-style multi-level selects
- Feed the helper output into:
  - `portal_recipient_preferences`
  - `portal_recipient_detail`
  - `scan_admin_recipient_organization_detail`
- Preserve GET filters in row forms and redirect URLs after save/delete.

**Step 2: Run the focused tests**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_portal \
  wms.tests.views.tests_views_scan_admin \
  -v 2
```

Expected: filter/sort tests pass.

### Task 4: Render the stock-style controls on the three preference pages

**Files:**
- Modify: `templates/portal/recipient_preferences.html`
- Modify: `templates/portal/recipient_detail.html`
- Modify: `templates/scan/admin_recipient_organization_detail.html`

**Step 1: Write minimal implementation**

- Add the existing stock-style block with:
  - name search
  - multi-level category filter
  - sort select
- Keep selectors A-Z and reuse the same client-side category-level script pattern.
- Carry filter values into per-row save/delete forms.

**Step 2: Run the UI tests**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_portal_bootstrap_ui \
  wms.tests.views.tests_scan_bootstrap_ui \
  -v 2
```

Expected: rendered contract tests pass.

### Task 5: Fix the shared number-input left padding

**Files:**
- Modify: `wms/static/scan/scan-bootstrap.css`

**Step 1: Write minimal implementation**

- Increase the left padding for `.ui-number-input` and `.ui-number-input.is-sm` so entered values begin to the right of the two left-side controls.
- Keep the shared number-input contract unchanged otherwise.

**Step 2: Run the targeted UI tests**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_portal_bootstrap_ui \
  -v 2
```

Expected: CSS contract tests pass.

### Task 6: Final verification and repo-reference check

**Files:**
- Review: `docs/repo-reference/03-impact-map.md`
- Review: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Run final verification**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.stock.tests_stock_view_helpers \
  wms.tests.views.tests_views_portal \
  wms.tests.views.tests_views_scan_admin \
  wms.tests.views.tests_portal_bootstrap_ui \
  wms.tests.views.tests_scan_bootstrap_ui \
  -v 2
```

Expected: all targeted tests pass.

**Step 2: Re-check shared-contract impact**

- Confirm the shared number-input contract is still accurately described.
- Confirm no repo-reference docs need updating beyond the code/test changes.
