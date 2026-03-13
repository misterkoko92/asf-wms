# Local Helper Versioning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add helper health/version/capability checks plus guided update-and-retry behavior before legacy PDF generation.

**Architecture:** Extend the existing local helper HTTP server with explicit version metadata and platform/capability reporting, then let Django legacy views publish version constraints while the browser bridge evaluates compatibility before calling `/v1/pdf/render`. Keep the current installer model and make updates guided rather than silent.

**Tech Stack:** Django legacy views/templates/static JS, `tools/planning_comm_helper`, `unittest`, semantic version comparison in Python and browser JS.

---

### Task 1: Lock the helper health contract before implementation

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/tests/test_server.py`
- Create: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/tests/test_versioning.py`

**Step 1: Write the failing helper health tests**

Add tests asserting `POST /health` returns:

```python
{
    "ok": True,
    "helper_version": "0.0.0",
    "platform": "Darwin",
    "capabilities": ["pdf_render", "excel_render", "pdf_merge"],
}
```

The exact default version string can be adjusted, but the test must require all four keys.

**Step 2: Write failing version metadata tests**

Add tests for a version metadata helper such as:

```python
version, capabilities = get_helper_runtime_metadata()
assert isinstance(version, str)
assert "pdf_render" in capabilities
```

**Step 3: Run the helper tests to confirm failure**

Run:

```bash
./.venv/bin/python -m unittest tools.planning_comm_helper.tests.test_server tools.planning_comm_helper.tests.test_versioning -v
```

Expected:
- failure because `/health` currently returns only `{"ok": true}`

**Step 4: Commit**

```bash
git add tools/planning_comm_helper/tests/test_server.py tools/planning_comm_helper/tests/test_versioning.py
git commit -m "test(helper): define helper health version contract"
```

### Task 2: Add explicit helper version and capability metadata

**Files:**
- Create: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/versioning.py`
- Modify: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/server.py`
- Modify: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/tests/test_server.py`
- Modify: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/tests/test_versioning.py`

**Step 1: Implement the version metadata module**

Create constants and a small accessor:

```python
HELPER_VERSION = "0.1.0"
HELPER_CAPABILITIES = ("pdf_render", "excel_render", "pdf_merge")

def get_helper_runtime_metadata():
    return {
        "helper_version": HELPER_VERSION,
        "platform": platform.system(),
        "capabilities": list(HELPER_CAPABILITIES),
    }
```

**Step 2: Wire `/health` to return the metadata**

Modify `server.py` so `POST /health` returns:

```python
{"ok": True, **get_helper_runtime_metadata()}
```

**Step 3: Run the tests**

Run:

```bash
./.venv/bin/python -m unittest tools.planning_comm_helper.tests.test_server tools.planning_comm_helper.tests.test_versioning -v
```

Expected:
- green tests for health payload and metadata

**Step 4: Commit**

```bash
git add tools/planning_comm_helper/versioning.py tools/planning_comm_helper/server.py tools/planning_comm_helper/tests/test_server.py tools/planning_comm_helper/tests/test_versioning.py
git commit -m "feat(helper): expose version and capability metadata"
```

### Task 3: Add Django-side helper compatibility policy

**Files:**
- Create: `/Users/EdouardGonnu/asf-wms/wms/helper_versioning.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/helper_install.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/core/tests_helper_install.py`
- Create: `/Users/EdouardGonnu/asf-wms/wms/tests/core/tests_helper_versioning.py`

**Step 1: Write the failing Django policy tests**

Add tests asserting a helper policy context builder returns:

```python
{
    "minimum_helper_version": "0.1.0",
    "latest_helper_version": "0.1.0",
}
```

**Step 2: Implement a shared policy helper**

Create a module containing constants and a reusable helper:

```python
MINIMUM_HELPER_VERSION = "0.1.0"
LATEST_HELPER_VERSION = "0.1.0"

def build_helper_version_policy():
    return {
        "minimum_helper_version": MINIMUM_HELPER_VERSION,
        "latest_helper_version": LATEST_HELPER_VERSION,
    }
```

**Step 3: Merge the policy into `build_helper_install_context(...)`**

Return the installer payload plus the version policy.

**Step 4: Run the tests**

Run:

```bash
./.venv/bin/python -m unittest wms.tests.core.tests_helper_install wms.tests.core.tests_helper_versioning -v
```

Expected:
- green tests for installer context + version policy fields

**Step 5: Commit**

```bash
git add wms/helper_versioning.py wms/helper_install.py wms/tests/core/tests_helper_install.py wms/tests/core/tests_helper_versioning.py
git commit -m "feat(helper): publish django helper version policy"
```

### Task 4: Add required capabilities to helper jobs

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/local_document_helper.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print_docs.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print_labels.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_docs.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_labels.py`

**Step 1: Write failing helper-job JSON tests**

Require helper job responses to include `required_capabilities`, for example:

```python
self.assertEqual(
    payload["required_capabilities"],
    ["pdf_render", "excel_render", "pdf_merge"],
)
```

for merged multi-document jobs, and omit `pdf_merge` for single-document jobs.

**Step 2: Implement capability selection in the helper-job builder**

Add a small helper:

```python
def _build_required_capabilities(*, merge: bool) -> list[str]:
    capabilities = ["pdf_render", "excel_render"]
    if merge:
        capabilities.append("pdf_merge")
    return capabilities
```

**Step 3: Attach the field to helper job JSON**

Update the helper job payload emitted by Django views.

**Step 4: Run the view tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs wms.tests.views.tests_views_print_labels -v 2
```

Expected:
- helper job JSON includes the correct required capabilities

**Step 5: Commit**

```bash
git add wms/local_document_helper.py wms/views_print_docs.py wms/views_print_labels.py wms/tests/views/tests_views_print_docs.py wms/tests/views/tests_views_print_labels.py
git commit -m "feat(print): declare helper capabilities per render job"
```

### Task 5: Add browser-side helper health and compatibility evaluation

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/static/wms/local_document_helper.js`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/static/wms/planning_communications_helper.js`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/scan/shipments_ready.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/scan/cartons_ready.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/admin/wms/shipment/change_form.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/planning/_version_communications_block.html`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/core/tests_ui.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/admin/tests_admin_extra.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_planning.py`

**Step 1: Write the failing UI assertions**

Require helper-aware surfaces to expose:
- `minimum_helper_version`
- `latest_helper_version`

as `data-*` attributes on the helper root element.

**Step 2: Add the health probe to JS**

Implement browser helpers such as:

```javascript
async function fetchHelperHealth(root) {
  return postJson(`http://${root.dataset.localDocumentHelperOrigin}/health`, {})
}
```

and

```javascript
function evaluateHelperStatus({ health, minimumVersion, latestVersion, requiredCapabilities }) {
  // return missing / outdated_blocking / outdated_recommended / unsupported_blocking / ready
}
```

**Step 3: Use the compatibility status before render**

Before `POST /v1/pdf/render`:
- probe `/health`
- compare version and capabilities
- block only on missing / outdated_blocking / unsupported_blocking
- allow render on `outdated_recommended` with warning

**Step 4: Run the targeted tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.core.tests_ui wms.tests.admin.tests_admin_extra wms.tests.views.tests_views_planning -v 2
```

Expected:
- helper hooks include the new version policy data

**Step 5: Commit**

```bash
git add wms/static/wms/local_document_helper.js wms/static/wms/planning_communications_helper.js templates/scan/shipments_ready.html templates/scan/cartons_ready.html templates/admin/wms/shipment/change_form.html templates/planning/_version_communications_block.html wms/tests/core/tests_ui.py wms/tests/admin/tests_admin_extra.py wms/tests/views/tests_views_planning.py
git commit -m "feat(helper): enforce version compatibility in browser bridge"
```

### Task 6: Add guided update-and-retry behavior

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/static/wms/local_document_helper.js`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/static/wms/planning_communications_helper.js`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/wms/_local_document_helper_install_panel.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/planning/_version_communications_block.html`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_planning.py`

**Step 1: Write failing behavior tests**

Document the target flow:
- incompatible helper shows update messaging
- clicking retry reprobes `/health`
- if now compatible, the pending action is replayed automatically

**Step 2: Implement pending action replay**

Store the pending action as a closure, then on retry:

```javascript
async function retryPendingAction(root) {
  const action = root._localDocumentHelperRetryAction
  if (!action) return
  await action()
}
```

Change the stored action so it:
- reprobes health
- only resumes render when status is now `ready` or `outdated_recommended`

**Step 3: Update user-facing text**

Make the install panel speak about both installation and update.

**Step 4: Run the targeted tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_planning -v 2
```

Expected:
- helper update messaging and retry flow are covered

**Step 5: Commit**

```bash
git add wms/static/wms/local_document_helper.js wms/static/wms/planning_communications_helper.js templates/wms/_local_document_helper_install_panel.html templates/planning/_version_communications_block.html wms/tests/views/tests_views_planning.py
git commit -m "feat(helper): add guided update and retry flow"
```

### Task 7: Run end-to-end verification on the helper-related test subsets

**Files:**
- No code changes required unless failures appear

**Step 1: Run helper unit tests**

```bash
./.venv/bin/python -m unittest tools.planning_comm_helper.tests.test_server tools.planning_comm_helper.tests.test_versioning tools.planning_comm_helper.tests.test_pdf_render tools.planning_comm_helper.tests.test_planning_pdf tools.planning_comm_helper.tests.test_autostart -v
```

Expected:
- all helper tests pass

**Step 2: Run Django helper-related tests**

```bash
./.venv/bin/python manage.py test wms.tests.core.tests_helper_install wms.tests.core.tests_helper_versioning wms.tests.views.tests_views_print_docs wms.tests.views.tests_views_print_labels wms.tests.views.tests_views_planning wms.tests.core.tests_ui wms.tests.admin.tests_admin_extra -v 2
```

Expected:
- all Django helper compatibility tests pass

**Step 3: Run `git diff --check`**

```bash
git diff --check
```

Expected:
- no whitespace or conflict-marker issues

**Step 4: Commit final cleanup if needed**

```bash
git add -A
git commit -m "test(helper): verify helper versioning rollout"
```

Only commit here if Task 7 required follow-up fixes.
