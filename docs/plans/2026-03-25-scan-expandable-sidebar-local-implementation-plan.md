# Scan Expandable Sidebar Local Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current scan primary rail with a local expandable sidebar experiment on the navigation branch.

**Architecture:** Keep the utility masthead in the header, move the scan product sections into a sidebar workspace shell, and reuse Bootstrap `collapse` plus `offcanvas` for expandable desktop groups and mobile navigation. Keep permissions, active state routing, and legacy Django page structure intact.

**Tech Stack:** Django templates, Bootstrap 5.3, legacy scan CSS, Django tests

---

### Task 1: Lock the new scan shell contract in tests

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add assertions for:
- `scan-sidebar-nav`
- `scan-sidebar-group-*`
- `scan-sidebar-offcanvas`
- absence of the old horizontal primary dropdown contract

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_nav_renders_expandable_sidebar_shell -v 2`

Expected: FAIL because the sidebar shell does not exist yet.

**Step 3: Write minimal implementation**

No production implementation in this task.

**Step 4: Run test to verify it still fails for the right reason**

Run the same command and confirm the failure is about missing sidebar markup.

**Step 5: Commit**

Do not commit in this task.

### Task 2: Replace the scan primary nav with the expandable sidebar shell

**Files:**
- Modify: `templates/scan/base.html`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Implement the sidebar shell**

Update the template to:
- keep the utility masthead
- add a workspace wrapper
- add a desktop sidebar nav
- add a mobile offcanvas nav
- render the same scan sections as expandable groups or single links

**Step 2: Run the targeted test**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_nav_renders_expandable_sidebar_shell -v 2`

Expected: PASS

**Step 3: Run the navigation subset**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -k scan_nav -v 2`

Expected: PASS or clear contract failures for old expectations.

**Step 4: Refine active/open states minimally**

Mark active parents when a child is active and expand the active group by default.

**Step 5: Commit**

Commit only after CSS and final tests are green.

### Task 3: Style the sidebar and mobile offcanvas

**Files:**
- Modify: `wms/static/scan/scan-bootstrap.css`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Add the workspace and sidebar styles**

Implement:
- masthead + workspace spacing
- sidebar surface
- parent and child link styles
- active states
- offcanvas styles

**Step 2: Run the targeted shell tests**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc wms.tests.views.tests_scan_bootstrap_ui -v 1`

Expected: PASS

**Step 3: Verify formatting hygiene**

Run: `git diff --check`

Expected: no output

**Step 4: Commit**

Do not commit yet if admin view tests still need adjustment.

### Task 4: Align remaining scan admin navigation expectations

**Files:**
- Modify: `wms/tests/views/tests_views_scan_admin.py`
- Test: `wms/tests/views/tests_views_scan_admin.py`

**Step 1: Write or adapt failing tests**

Make the admin navigation assertions verify the new shell contract:
- management links live in the sidebar group
- settings live in admin utility

**Step 2: Run targeted tests**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin -v 1`

Expected: PASS

**Step 3: Run combined verification**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_scan_misc wms.tests.views.tests_scan_bootstrap_ui -v 1`

Expected: PASS

**Step 4: Commit**

```bash
git add templates/scan/base.html wms/static/scan/scan-bootstrap.css wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_admin.py docs/plans/2026-03-25-scan-expandable-sidebar-local-design.md docs/plans/2026-03-25-scan-expandable-sidebar-local-implementation-plan.md
git commit -m "feat: add local scan expandable sidebar experiment"
```

### Task 5: Prepare local review handoff

**Files:**
- Modify: none unless required by review outcome

**Step 1: Run final verification**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_scan_misc wms.tests.views.tests_scan_bootstrap_ui -v 1`

Expected: PASS

**Step 2: Confirm git hygiene**

Run:
- `git diff --check`
- `git status --short --branch`

Expected:
- no diff check output
- clean branch

**Step 3: Keep local server available**

Run local review on `/scan/` and `/scan/ui-lab/` if needed.

**Step 4: Commit**

No extra commit if Task 4 already produced the final clean state.
