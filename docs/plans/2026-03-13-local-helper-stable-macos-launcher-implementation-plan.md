# Local Helper Stable macOS Launcher Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Install the local macOS helper behind a stable user-level launcher so repeated Excel/PDF permission prompts are reduced across repo updates.

**Architecture:** The helper installer will create `~/Applications/ASF Planning Communication Helper.app` and a LaunchAgent that points to the bundle executable. The bundle executable will continue to run the existing repository helper server via the repo virtualenv.

**Tech Stack:** Python 3.11, Django helper installer code, macOS LaunchAgents, shell launcher scripts, `unittest`

---

### Task 1: Add failing tests for stable macOS launcher paths

**Files:**
- Modify: `tools/planning_comm_helper/tests/test_autostart.py`

**Step 1: Write the failing test**

Add tests asserting that macOS autostart paths include:

- `~/Applications/ASF Planning Communication Helper.app`
- `Contents/MacOS/ASF Planning Communication Helper`
- `Contents/Info.plist`

Add a plist test asserting the LaunchAgent references the stable app executable instead of `repo/.venv/bin/python`.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m unittest tools.planning_comm_helper.tests.test_autostart -v`

Expected: FAIL because `MacAutostartPaths` does not yet include the stable launcher fields and the plist still references the repo virtualenv Python path.

**Step 3: Write minimal implementation**

Extend the macOS autostart path model and plist rendering to support the stable app executable.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m unittest tools.planning_comm_helper.tests.test_autostart -v`

Expected: PASS

### Task 2: Add failing tests for app bundle installation output

**Files:**
- Modify: `tools/planning_comm_helper/tests/test_autostart.py`

**Step 1: Write the failing test**

Add a test that `install_macos_autostart()` writes:

- the LaunchAgent plist
- the app bundle `Info.plist`
- the bundle executable launcher script

Assert the launcher script executes the repo virtualenv helper server and the executable bit is set.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m unittest tools.planning_comm_helper.tests.test_autostart -v`

Expected: FAIL because the install flow currently writes only the LaunchAgent plist.

**Step 3: Write minimal implementation**

Create helpers that render and write the app bundle metadata and launcher script before bootstrapping the LaunchAgent.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m unittest tools.planning_comm_helper.tests.test_autostart -v`

Expected: PASS

### Task 3: Add helper installer regression coverage

**Files:**
- Create: `wms/tests/core/tests_helper_install.py`
- Modify: `wms/helper_install.py`

**Step 1: Write the failing test**

Add a test asserting the macOS installer payload exposes a user-facing command/script that still installs successfully while pointing to the stable helper app name in its post-install guidance.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_helper_install -v 2`

Expected: FAIL because the payload does not yet include the stable app guidance.

**Step 3: Write minimal implementation**

Add explicit macOS guidance fields to the installer payload and keep existing behavior for unsupported platforms and Windows.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_helper_install -v 2`

Expected: PASS

### Task 4: Verify the end-to-end contract remains intact

**Files:**
- Modify: `tools/planning_comm_helper/README.md`

**Step 1: Run targeted regression tests**

Run:

- `./.venv/bin/python -m unittest tools.planning_comm_helper.tests.test_autostart -v`
- `./.venv/bin/python manage.py test wms.tests.core.tests_helper_install -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments.ScanShipmentsViewsTests.test_scan_local_document_helper_installer_delegates_to_helper_install_response -v 2`

Expected: PASS

**Step 2: Update documentation**

Document that macOS installs a stable helper app bundle under `~/Applications`.

**Step 3: Run final verification**

Run:

- `./.venv/bin/python -m unittest tools.planning_comm_helper.tests.test_autostart -v`
- `./.venv/bin/python manage.py test wms.tests.core.tests_helper_install wms.tests.views.tests_views_scan_shipments -v 2`

Expected: PASS
