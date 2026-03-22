# Legacy UI Wave 2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add one high-value shared alert primitive, document wrapper contracts in the UI Lab, and refactor `scan/pack` plus `scan/public_account_request` into clearer partial-based templates without regressing existing hooks.

**Architecture:** Keep `wms_ui` focused on closed leaf primitives and avoid forcing arbitrary wrapper tags into Django templates. Standardize wrappers through shared class contracts already present in Bootstrap bridge CSS, expose those contracts in `scan/ui-lab/`, then migrate two real scan surfaces with partial decomposition plus shared `ui_button`, `ui_switch`, and new `ui_alert` usage.

**Tech Stack:** Django templates, Django inclusion tags, Django TestCase, Bootstrap 5 bridge CSS, legacy scan JS hooks

---

### Task 1: Lock wave 2 UI contracts with failing tests

**Files:**
- Modify: `wms/tests/templatetags/tests_wms_ui.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Verify: `templates/scan/pack.html`
- Verify: `templates/scan/public_account_request.html`
- Verify: `templates/scan/ui_lab.html`

**Step 1: Write the failing test**

Add tests that prove the wave 2 target:
- `ui_alert` renders a shared alert contract with level classes, optional title/body, and passthrough attrs.
- `scan_ui_lab` renders examples for `ui-comp-alert`, `ui-comp-panel`, `ui-comp-toolbar`, and `ui-comp-actions`.
- `scan_pack` keeps shared action wrappers on the packing result links and shipping footer, renders the defaults toggle through the shared switch contract, and uses a shared alert contract for non-field errors / missing-default warnings.
- `scan_public_account_request` keeps shared tertiary back navigation, primary submit semantics, and a shared alert contract for validation errors.

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.templatetags.tests_wms_ui wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments -v 2`

Expected: FAIL because `ui_alert` does not exist yet and the target templates still use manual alert / switch / action markup.

**Step 3: Write minimal implementation**

No production implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.templatetags.tests_wms_ui wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments -v 2`

Expected: FAIL only on the newly added wave 2 assertions.

**Step 5: Commit**

```bash
git add wms/tests/templatetags/tests_wms_ui.py wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "test: lock legacy ui wave 2 contracts"
```

### Task 2: Add the shared alert primitive and extend the UI Lab catalog

**Files:**
- Modify: `wms/templatetags/wms_ui.py`
- Create: `templates/wms/components/alert.html`
- Modify: `templates/scan/ui_lab.html`
- Modify: `wms/views_scan_misc.py`
- Modify: `wms/static/scan/scan-bootstrap.css`
- Modify: `wms/static/scan/ui-lab.css`
- Modify: `wms/tests/templatetags/tests_wms_ui.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Use the red tests from Task 1 for:
- `ui_alert` rendering,
- `UI Lab` examples for panel / toolbar / action group / alert.

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.templatetags.tests_wms_ui wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL because the inclusion tag, component template, and catalog examples do not exist.

**Step 3: Write minimal implementation**

- add `ui_alert(...)` to `wms/templatetags/wms_ui.py`
- create `templates/wms/components/alert.html` with a simple closed contract for tone, title, body, and attrs
- extend `scan/ui-lab/` with:
  - one alert example,
  - one panel example,
  - one toolbar example,
  - one action group example
- add only the CSS needed to make `ui-comp-alert` visually coherent with the existing scan bridge
- keep wrapper examples as HTML/CSS contracts, not new generic wrapper tags

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.templatetags.tests_wms_ui wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS for the alert primitive and the catalog assertions, with any remaining failures limited to unmigrated page contracts.

**Step 5: Commit**

```bash
git add wms/templatetags/wms_ui.py templates/wms/components/alert.html templates/scan/ui_lab.html wms/views_scan_misc.py wms/static/scan/scan-bootstrap.css wms/static/scan/ui-lab.css wms/tests/templatetags/tests_wms_ui.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add legacy ui alert primitive and catalog coverage"
```

### Task 3: Refactor `scan/pack` onto shared primitives and partials

**Files:**
- Modify: `templates/scan/pack.html`
- Create: `templates/scan/includes/pack_result_lists.html`
- Create: `templates/scan/includes/pack_success_modal.html`
- Create: `templates/scan/includes/pack_shipping_section.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Verify: `wms/views_scan_shipments.py`
- Verify: `wms/static/scan/scan.js`

**Step 1: Write the failing test**

Add or tighten tests that assert:
- packing result links live inside a shared `ui-comp-actions` wrapper
- the defaults toggle uses the shared switch contract
- the warning / error blocks use the shared alert contract
- the shipping footer actions keep their existing CTA levels and names
- preparateur mode still renders the success modal and keeps reduced controls

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments -v 2`

Expected: FAIL because `pack.html` still uses manual blocks and has not been decomposed into the target partials.

**Step 3: Write minimal implementation**

- load `wms_ui` in `templates/scan/pack.html`
- replace manual buttons with `ui_button` where the markup is closed and stable
- replace the defaults checkbox block with `ui_switch`
- replace manual warning / error boxes with `ui_alert`
- add shared `ui-comp-actions` wrappers for packing result links and footer actions
- split the template into the three target partials while preserving:
  - `id` values
  - `name` values
  - `data-*` attrs
  - preparateur/staff branching
  - document helper hooks

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add templates/scan/pack.html templates/scan/includes/pack_result_lists.html templates/scan/includes/pack_success_modal.html templates/scan/includes/pack_shipping_section.html wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "refactor: decompose scan pack onto shared ui contracts"
```

### Task 4: Refactor `scan/public_account_request` onto shared primitives and partials

**Files:**
- Modify: `templates/scan/public_account_request.html`
- Create: `templates/scan/includes/public_account_request_intro.html`
- Create: `templates/scan/includes/public_account_request_association_fields.html`
- Create: `templates/scan/includes/public_account_request_user_fields.html`
- Create: `templates/scan/includes/public_account_request_documents.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `wms/account_request_handlers.py`
- Verify: `wms/views_public_account.py`

**Step 1: Write the failing test**

Add or tighten tests that assert:
- the intro/back action still uses the shared tertiary button contract
- the submit CTA stays primary
- validation errors render with the shared alert contract
- the page still exposes the same field IDs and section markers used by the inline JS

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_public_account -v 2`

Expected: FAIL because the template is still monolithic and uses manual alert markup.

**Step 3: Write minimal implementation**

- load `wms_ui` in `templates/scan/public_account_request.html`
- replace the intro/back action and submit CTA with `ui_button`
- replace the error block with `ui_alert`
- split the page into the target partials for intro, association fields, user fields, and document uploads
- keep all existing form field IDs, names, and `data-address-*` / `data-account-section` hooks unchanged

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_public_account -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add templates/scan/public_account_request.html templates/scan/includes/public_account_request_intro.html templates/scan/includes/public_account_request_association_fields.html templates/scan/includes/public_account_request_user_fields.html templates/scan/includes/public_account_request_documents.html wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_public_account.py
git commit -m "refactor: split public account request onto shared ui pieces"
```

### Task 5: Final focused verification

**Files:**
- Verify: `wms/tests/templatetags/tests_wms_ui.py`
- Verify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `wms/tests/views/tests_views_scan_shipments.py`
- Verify: `wms/tests/views/tests_views_public_account.py`

**Step 1: Write the failing test**

No new tests in this task. Use the full wave 2 regression set from the previous tasks.

**Step 2: Run test to verify the final branch state**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.templatetags.tests_wms_ui wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments wms.tests.views.tests_views_public_account -v 2`

Expected: PASS.

**Step 3: Review deferred scope**

Record explicitly in the task notes or final summary that the following remain out of scope for this wave:
- `templates/scan/admin_contacts.html`
- `templates/scan/imports.html`
- `templates/scan/shipment_create.html`

**Step 4: Re-run the same command to confirm a clean verification pass**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.templatetags.tests_wms_ui wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments wms.tests.views.tests_views_public_account -v 2`

Expected: PASS again, confirming no accidental regressions after final cleanup.

**Step 5: Commit**

```bash
git add wms/tests/templatetags/tests_wms_ui.py wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_views_public_account.py templates/scan/pack.html templates/scan/public_account_request.html templates/scan/includes/pack_result_lists.html templates/scan/includes/pack_success_modal.html templates/scan/includes/pack_shipping_section.html templates/scan/includes/public_account_request_intro.html templates/scan/includes/public_account_request_association_fields.html templates/scan/includes/public_account_request_user_fields.html templates/scan/includes/public_account_request_documents.html templates/scan/ui_lab.html templates/wms/components/alert.html wms/templatetags/wms_ui.py wms/static/scan/scan-bootstrap.css wms/static/scan/ui-lab.css
git commit -m "refactor: deliver legacy ui wave 2 shared contracts"
```
