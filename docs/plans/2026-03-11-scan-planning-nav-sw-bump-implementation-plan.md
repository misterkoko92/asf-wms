# Scan Planning Nav And Service Worker Bump Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `Planning` shortcut to the legacy scan navbar and force scan clients to refresh onto the latest deployed assets.

**Architecture:** Modify the shared scan base template for navigation and service worker registration, bump the served worker cache version in the scan misc view, and cover the behavior with narrow legacy Django view tests.

**Tech Stack:** Django templates, Django view tests, legacy scan service worker script

---

### Task 1: Add the nav regression test

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add a test on a scan page such as `scan_dashboard` or `scan_stock` asserting:
- the response contains `Planning`
- the response contains `reverse("planning:run_list")`

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_nav_includes_planning_link -v 2
```

Expected: fail because the link is not rendered yet.

**Step 3: Write minimal implementation**

Modify `templates/scan/base.html` to add a top-level nav item linking to `planning:run_list`.

**Step 4: Run test to verify it passes**

Run the same command and confirm `OK`.

**Step 5: Commit**

```bash
git add templates/scan/base.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat(scan): add planning nav link"
```

### Task 2: Add the service worker bump regression test

**Files:**
- Modify: `wms/tests/views/tests_views_scan_misc.py`
- Modify: `wms/views_scan_misc.py`
- Modify: `templates/scan/base.html`

**Step 1: Write the failing test**

Extend the existing service worker test to assert:
- headers stay unchanged
- the worker body contains the new bumped cache name

Optionally add a template render assertion that the registration URL contains the version query string.

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc.ScanMiscViewsTests.test_scan_service_worker_returns_expected_headers_and_body -v 2
```

Expected: fail until the bump is applied.

**Step 3: Write minimal implementation**

Change:
- `SERVICE_WORKER_JS` cache name in `wms/views_scan_misc.py`
- worker registration URL in `templates/scan/base.html` to append a version query param

Keep:
- `Cache-Control: no-cache`
- `Service-Worker-Allowed: /scan/`

**Step 4: Run test to verify it passes**

Run the same command and confirm `OK`.

**Step 5: Commit**

```bash
git add templates/scan/base.html wms/views_scan_misc.py wms/tests/views/tests_views_scan_misc.py
git commit -m "fix(scan): bump service worker version"
```

### Task 3: Run focused legacy verification

**Files:**
- No code changes expected

**Step 1: Run focused test suite**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_misc -v 1
```

Expected: all tests pass.

**Step 2: Run lint on touched Python files**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/ruff check wms/views_scan_misc.py wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_misc.py
```

Expected: `All checks passed!`

**Step 3: Commit if needed**

If hooks or formatting changed files:

```bash
git add -A
git commit -m "test(scan): cover planning nav and sw bump"
```
