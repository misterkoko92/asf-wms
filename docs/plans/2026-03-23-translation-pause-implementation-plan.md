# Translation Pause Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Hide the language switch across legacy Django surfaces and remove FR/EN translation work from default development, test, and verification scope.

**Architecture:** Centralize the visible freeze in the shared language-switch partials, then codify the pause in repository guardrails. Replace broad i18n rendering coverage with a minimal absence-of-switch contract and remove translation-specific regression tests from routine suites.

**Tech Stack:** Django templates, Django TestCase, repository policy docs

---

### Task 1: Add the failing contract for hidden language switch

**Files:**
- Modify: `wms/tests/views/tests_i18n_language_switch.py`

**Step 1: Write the failing test**

Replace the existing broad i18n suite with a smaller suite asserting that pages using the shared switch partials no longer render any `name="language"` controls.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch -v 2`
Expected: FAIL because the switch is still rendered.

**Step 3: Write minimal implementation**

Neutralize the shared language switch partials so they render nothing.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch -v 2`
Expected: PASS.

### Task 2: Codify the translation pause in repository guardrails

**Files:**
- Modify: `AGENTS.md`
- Create: `docs/policies/translation-paused.md`

**Step 1: Add pause policy text**

Document that FR/EN translation scope is excluded by default from analysis, implementation, tests, and verification unless the user explicitly asks to resume it.

**Step 2: Verify wording**

Check that the new policy matches the hidden-switch implementation and does not conflict with the existing Next pause policy.

### Task 3: Remove translation-heavy regression tests from routine suites

**Files:**
- Delete: `wms/tests/management/tests_management_audit_i18n_strings.py`
- Modify: `wms/tests/views/tests_views_imports.py`
- Modify: `wms/tests/views/tests_views_scan_misc.py`
- Modify: `wms/tests/views/tests_views_scan_orders.py`
- Modify: `wms/tests/views/tests_views_scan_admin.py`
- Modify: `wms/tests/views/tests_views_scan_stock.py`
- Modify: `wms/tests/views/tests_views_print_templates.py`
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/views/tests_views_scan_receipts.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/tests/admin/tests_admin_bootstrap_ui.py`

**Step 1: Remove tests whose primary purpose is FR/EN rendering parity**

Delete or simplify English-rendering assertions that are now outside the active scope.

**Step 2: Keep business coverage intact**

Retain non-i18n behavior tests for the same features.

**Step 3: Run focused suites**

Run:

- `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_imports wms.tests.views.tests_views_scan_misc wms.tests.views.tests_views_scan_orders wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_scan_stock wms.tests.views.tests_views_print_templates wms.tests.views.tests_views_portal wms.tests.views.tests_views_scan_receipts wms.tests.views.tests_views_scan_shipments wms.tests.admin.tests_admin_bootstrap_ui -v 2`

Expected: PASS.

### Task 4: Final verification

**Files:**
- Verify only

**Step 1: Run final targeted verification**

Run:

- `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch wms.tests.views.tests_views_imports wms.tests.views.tests_views_scan_misc wms.tests.views.tests_views_scan_orders wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_scan_stock wms.tests.views.tests_views_print_templates wms.tests.views.tests_views_portal wms.tests.views.tests_views_scan_receipts wms.tests.views.tests_views_scan_shipments wms.tests.admin.tests_admin_bootstrap_ui -v 2`

Expected: PASS.

**Step 2: Optional broader confidence check**

Run: `./.venv/bin/python manage.py test wms.tests -v 1`
Expected: PASS, or report any unrelated failures explicitly.
