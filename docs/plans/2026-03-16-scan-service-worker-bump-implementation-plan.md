# Scan Service Worker Bump Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bump the legacy scan service worker version so deployed scan pages stop requiring hard refreshes to pick up new assets.

**Architecture:** Keep the existing legacy scan invalidation model, but align the service worker version constant in the response body with the explicit registration query string in the shared scan base template. Lock the behavior with narrow Django view tests only.

**Tech Stack:** Django templates, Django view tests, legacy scan service worker script

---

### Task 1: Add the failing service worker bump assertions

**Files:**
- Modify: `wms/tests/views/tests_views_scan_misc.py`
- Reference: `wms/views_scan_misc.py`
- Reference: `templates/scan/base.html`

**Step 1: Write the failing test**

Update the existing scan misc tests so they expect the next service worker version in both places:
- the worker body contains `wms-scan-v51`
- the scan base template contains `service-worker.js?v=51`

Keep all header assertions unchanged.

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_misc.ScanMiscViewsTests.test_scan_service_worker_returns_expected_headers_and_body \
  wms.tests.views.tests_views_scan_misc.ScanMiscViewsTests.test_scan_base_registers_versioned_service_worker_url \
  -v 2
```

Expected: FAIL because the code still serves/registers version `50`.

**Step 3: Write minimal implementation**

Do not implement yet in this task.

**Step 4: Commit**

No commit in the red phase.

### Task 2: Implement the minimal scan worker bump

**Files:**
- Modify: `wms/views_scan_misc.py`
- Modify: `templates/scan/base.html`
- Test: `wms/tests/views/tests_views_scan_misc.py`

**Step 1: Write minimal implementation**

Change only:
- `SCAN_SERVICE_WORKER_VERSION` from `50` to `51` in `wms/views_scan_misc.py`
- the `navigator.serviceWorker.register(...)` query string from `?v=50` to `?v=51` in `templates/scan/base.html`

Do not change headers, scope, asset list, or worker strategy.

**Step 2: Run the targeted test to verify it passes**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_misc.ScanMiscViewsTests.test_scan_service_worker_returns_expected_headers_and_body \
  wms.tests.views.tests_views_scan_misc.ScanMiscViewsTests.test_scan_base_registers_versioned_service_worker_url \
  -v 2
```

Expected: both tests PASS.

**Step 3: Run the focused module to catch local regressions**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc -v 2
```

Expected:
- the two service-worker tests pass
- the known unrelated FAQ English failure may still reproduce

**Step 4: Commit**

```bash
git add templates/scan/base.html wms/views_scan_misc.py wms/tests/views/tests_views_scan_misc.py
git commit -m "fix(scan): bump service worker version"
```

### Task 3: Verify branch hygiene and deployment handoff

**Files:**
- No new code expected

**Step 1: Run formatting/lint checks on touched Python test and view files**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/ruff check \
  wms/views_scan_misc.py \
  wms/tests/views/tests_views_scan_misc.py
```

Expected: `All checks passed!`

**Step 2: Run git diff sanity check**

Run:

```bash
git diff --check
git status --short
```

Expected:
- no whitespace or patch formatting issues
- only the intended scan worker bump files changed

**Step 3: Record PythonAnywhere handoff**

Deployment follow-up after merge:

```bash
cd /home/messmed/asf-wms
git pull
source /home/messmed/.virtualenvs/asf-wms/bin/activate
source /home/messmed/.asf-wms.env
python manage.py check
```

Then reload the Web app in PythonAnywhere. No migrations or data backfills are required for this bump.
