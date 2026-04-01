# ASF WMS V3.1 Application And Policies Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract shared application queries and policy modules for the highest-value operational surfaces without changing legacy routes or user-visible behavior.

**Architecture:** Create an additive `wms/application/` and `wms/policies/` layer, migrate `scan` and mirrored UI API reads first, then make views and endpoints thinner by delegating to those shared modules. Keep the existing HTML and JSON contracts stable while moving decision logic out of the hotspot modules.

**Tech Stack:** Django 5, legacy Django templates, UI API endpoints, pytest/manage.py tests, Ruff, mypy, pyright.

---

### Task 1: Create V3.1 package scaffolding and guardrail docs

**Files:**
- Create: `wms/application/__init__.py`
- Create: `wms/application/scan/__init__.py`
- Create: `wms/application/pilotage/__init__.py`
- Create: `wms/application/portal/__init__.py`
- Create: `wms/application/planning/__init__.py`
- Create: `wms/policies/__init__.py`
- Modify: `docs/repo-reference/01-architecture-and-entrypoints.md`
- Test: no new runtime test; use import smoke through existing test commands

**Step 1: Write the failing test**

Add a minimal import smoke test file:

```python
from wms.application import scan, pilotage, portal, planning
from wms import policies


def test_v31_packages_import():
    assert scan is not None
    assert pilotage is not None
    assert portal is not None
    assert planning is not None
    assert policies is not None
```

Suggested file: `wms/tests/core/tests_v3_application_imports.py`

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_v3_application_imports -v 2`

Expected: FAIL because the new packages do not exist yet.

**Step 3: Write minimal implementation**

- create the package directories and `__init__.py` files
- add a short paragraph in `docs/repo-reference/01-architecture-and-entrypoints.md` documenting the new structural target

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_v3_application_imports -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/application wms/policies wms/tests/core/tests_v3_application_imports.py docs/repo-reference/01-architecture-and-entrypoints.md
git commit -m "docs: scaffold v3 application and policies packages"
```

### Task 2: Extract scan dashboard query builder

**Files:**
- Create: `wms/application/scan/dashboard_queries.py`
- Modify: `wms/views_scan_dashboard.py`
- Modify: `api/v1/ui_views.py`
- Test: `wms/tests/views/tests_views_scan_dashboard.py`
- Test: `api/tests/tests_ui_endpoints.py`

**Step 1: Write the failing test**

Add a focused unit-style contract test for the new shared query builder:

```python
from wms.application.scan.dashboard_queries import build_scan_dashboard_payload


def test_build_scan_dashboard_payload_includes_action_queue(admin_user):
    payload = build_scan_dashboard_payload(user=admin_user)
    assert "pending_actions" in payload
```

Suggested file: `wms/tests/core/tests_scan_dashboard_queries.py`

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_scan_dashboard_queries -v 2`

Expected: FAIL because `dashboard_queries.py` or `build_scan_dashboard_payload` does not exist.

**Step 3: Write minimal implementation**

- create `wms/application/scan/dashboard_queries.py`
- move read-only dashboard composition helpers out of `wms/views_scan_dashboard.py`
- keep the return contract aligned with the existing HTML and UI API consumers
- call the shared query from both `wms/views_scan_dashboard.py` and `api/v1/ui_views.py`

**Step 4: Run test to verify it passes**

Run:

- `./.venv/bin/python manage.py test wms.tests.core.tests_scan_dashboard_queries -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard api.tests.tests_ui_endpoints -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/application/scan/dashboard_queries.py wms/views_scan_dashboard.py api/v1/ui_views.py wms/tests/core/tests_scan_dashboard_queries.py wms/tests/views/tests_views_scan_dashboard.py api/tests/tests_ui_endpoints.py
git commit -m "refactor: extract shared scan dashboard queries"
```

### Task 3: Extract pilotage query builder

**Files:**
- Create: `wms/application/pilotage/pilotage_queries.py`
- Modify: `wms/views_scan_pilotage.py`
- Modify: `api/v1/ui_views.py`
- Test: `wms/tests/views/tests_views_scan_pilotage.py`
- Test: `api/tests/tests_ui_endpoints.py`

**Step 1: Write the failing test**

Add a contract test:

```python
from wms.application.pilotage.pilotage_queries import build_ops_pilotage_payload


def test_build_ops_pilotage_payload_includes_summary_cards(admin_user):
    payload = build_ops_pilotage_payload(user=admin_user)
    assert "summary_cards" in payload
```

Suggested file: `wms/tests/core/tests_pilotage_queries.py`

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_pilotage_queries -v 2`

Expected: FAIL

**Step 3: Write minimal implementation**

- create `wms/application/pilotage/pilotage_queries.py`
- move read composition currently duplicated between pilotage HTML and UI API
- keep permissions and filtering in the adapters, not in the query itself, unless they are business-level constraints

**Step 4: Run test to verify it passes**

Run:

- `./.venv/bin/python manage.py test wms.tests.core.tests_pilotage_queries -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_pilotage api.tests.tests_ui_endpoints -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/application/pilotage/pilotage_queries.py wms/views_scan_pilotage.py api/v1/ui_views.py wms/tests/core/tests_pilotage_queries.py wms/tests/views/tests_views_scan_pilotage.py api/tests/tests_ui_endpoints.py
git commit -m "refactor: extract shared ops pilotage queries"
```

### Task 4: Introduce operational policies modules

**Files:**
- Create: `wms/policies/sla.py`
- Create: `wms/policies/pilotage.py`
- Create: `wms/policies/planning.py`
- Create: `wms/policies/shipment_parties.py`
- Modify: `wms/runtime_settings.py`
- Modify: `wms/default_shipper_bindings.py`
- Modify: `wms/views_scan_dashboard.py`
- Modify: `wms/scan_dashboard_sla.py`
- Modify: `wms/planning/stats.py`
- Test: `wms/tests/core/tests_runtime_settings.py`
- Test: create `wms/tests/core/tests_policies.py`

**Step 1: Write the failing test**

Add policy-focused tests:

```python
from wms.policies.pilotage import classify_planning_load_state
from wms.policies.sla import classify_sla_delay


def test_classify_planning_load_state_marks_overload():
    assert classify_planning_load_state(101, tension_pct=80, critical_pct=95) == "overload"


def test_classify_sla_delay_marks_persistent_after_double_threshold():
    result = classify_sla_delay(delay_hours=145, threshold_hours=72)
    assert result == "persistent"
```

Suggested file: `wms/tests/core/tests_policies.py`

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_policies -v 2`

Expected: FAIL

**Step 3: Write minimal implementation**

- create the policy modules
- move raw rule decisions out of dashboard, SLA helper, planning stats, and default shipper bindings where practical
- keep `runtime_settings.py` as configuration resolution, not as business classification

**Step 4: Run test to verify it passes**

Run:

- `./.venv/bin/python manage.py test wms.tests.core.tests_policies wms.tests.core.tests_runtime_settings -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard wms.tests.planning.tests_version_dashboard -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/policies wms/runtime_settings.py wms/default_shipper_bindings.py wms/views_scan_dashboard.py wms/scan_dashboard_sla.py wms/planning/stats.py wms/tests/core/tests_policies.py wms/tests/core/tests_runtime_settings.py wms/tests/views/tests_views_scan_dashboard.py wms/tests/planning/tests_version_dashboard.py
git commit -m "refactor: centralize operational policies"
```

### Task 5: Thin down scan and UI API adapters

**Files:**
- Modify: `wms/views_scan_dashboard.py`
- Modify: `wms/views_scan_pilotage.py`
- Modify: `api/v1/ui_views.py`
- Modify: `docs/repo-reference/03-impact-map.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Test: `api/tests/tests_ui_endpoints.py`
- Test: `wms/tests/views/tests_views_scan_dashboard.py`
- Test: `wms/tests/views/tests_views_scan_pilotage.py`

**Step 1: Write the failing test**

Add a regression test that proves the adapters are still contract-compatible after extraction. Reuse current endpoint assertions rather than inventing a new business contract.

For example, add a test asserting both HTML and API still expose the same action queue count from the shared query data.

**Step 2: Run test to verify it fails**

Run the new targeted test only:

`./.venv/bin/python manage.py test <new_test_path> -v 2`

Expected: FAIL before the adapters are aligned.

**Step 3: Write minimal implementation**

- reduce view modules to request parsing, query invocation, and render/response shaping
- update repository reference docs to mention the new shared application boundary

**Step 4: Run test to verify it passes**

Run:

- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard wms.tests.views.tests_views_scan_pilotage api.tests.tests_ui_endpoints -v 2`
- `uv run ruff check wms/application wms/policies wms/views_scan_dashboard.py wms/views_scan_pilotage.py api/v1/ui_views.py`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/views_scan_dashboard.py wms/views_scan_pilotage.py api/v1/ui_views.py docs/repo-reference/03-impact-map.md docs/repo-reference/04-shared-contracts.md wms/tests/views/tests_views_scan_dashboard.py wms/tests/views/tests_views_scan_pilotage.py api/tests/tests_ui_endpoints.py
git commit -m "refactor: thin scan and ui api adapters around shared queries"
```

### Task 6: Extend the same pattern to portal and planning reads

**Files:**
- Create: `wms/application/portal/dashboard_queries.py`
- Create: `wms/application/planning/version_queries.py`
- Modify: `wms/views_portal_orders.py`
- Modify: `wms/views_planning.py`
- Modify: `wms/planning/version_dashboard.py`
- Modify: `api/v1/ui_views.py` if a mirrored payload exists
- Test: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Test: `wms/tests/views/tests_views_planning.py`
- Test: relevant `api/tests/`

**Step 1: Write the failing test**

Add one focused query contract test per surface:

- portal dashboard query returns KPI and next-step keys
- planning version query returns capacity summary and flight capacity rows

Suggested files:

- `wms/tests/core/tests_portal_dashboard_queries.py`
- `wms/tests/core/tests_planning_version_queries.py`

**Step 2: Run test to verify it fails**

Run:

- `./.venv/bin/python manage.py test wms.tests.core.tests_portal_dashboard_queries -v 2`
- `./.venv/bin/python manage.py test wms.tests.core.tests_planning_version_queries -v 2`

Expected: FAIL

**Step 3: Write minimal implementation**

- extract portal and planning read composition into the new application packages
- keep current route, template, and artifact behavior unchanged

**Step 4: Run test to verify it passes**

Run:

- `./.venv/bin/python manage.py test wms.tests.core.tests_portal_dashboard_queries wms.tests.core.tests_planning_version_queries -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_planning -v 2`
- run any closest API tests if a mirrored payload was updated

Expected: PASS

**Step 5: Commit**

```bash
git add wms/application/portal/dashboard_queries.py wms/application/planning/version_queries.py wms/views_portal_orders.py wms/views_planning.py wms/planning/version_dashboard.py wms/tests/core/tests_portal_dashboard_queries.py wms/tests/core/tests_planning_version_queries.py wms/tests/views/tests_portal_bootstrap_ui.py wms/tests/views/tests_views_planning.py api/tests
git commit -m "refactor: extend shared application queries to portal and planning"
```

### Task 7: Broaden static checks to the new V3.1 boundary

**Files:**
- Modify: `mypy.ini`
- Modify: `pyrightconfig.json`
- Test: `make typecheck`
- Test: `make typecheck-pyright`

**Step 1: Write the failing test**

There is no unit test here. The failing proof is the type gate itself.

**Step 2: Run test to verify it fails**

Run:

- `make typecheck`
- `make typecheck-pyright`

Expected: one or both gates may fail once the new modules are included.

**Step 3: Write minimal implementation**

- extend the type-check include lists to the new application and policy modules
- fix only issues inside the V3.1 scope

**Step 4: Run test to verify it passes**

Run:

- `make typecheck`
- `make typecheck-pyright`

Expected: PASS

**Step 5: Commit**

```bash
git add mypy.ini pyrightconfig.json wms/application wms/policies
git commit -m "chore: extend type gates to v3 application boundaries"
```

### Task 8: Close V3.1 with repo-reference updates and full verification

**Files:**
- Modify: `docs/repo-reference/01-architecture-and-entrypoints.md`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/03-impact-map.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Test: targeted scan, portal, planning, and API suites

**Step 1: Write the failing test**

There is no new code test here. The failing proof is missing documentation alignment discovered during review.

**Step 2: Run test to verify the verification set before docs alignment**

Run:

- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard wms.tests.views.tests_views_scan_pilotage wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_planning api.tests.tests_ui_endpoints -v 2`

Expected: PASS before final docs, establishing the runtime baseline.

**Step 3: Write minimal implementation**

- update the repo reference to reflect the new application and policy boundary
- document the new preferred entry points for future tickets

**Step 4: Run test to verify it passes**

Run:

- the same Django test command as above
- `uv run ruff check wms/application wms/policies`

Expected: PASS

**Step 5: Commit**

```bash
git add docs/repo-reference wms/application wms/policies
git commit -m "docs: align repo reference with v3.1 architecture"
```

## Verification Bundle

Run this bundle before claiming `V3.1` complete:

```bash
./.venv/bin/python manage.py test \
  wms.tests.core.tests_v3_application_imports \
  wms.tests.core.tests_scan_dashboard_queries \
  wms.tests.core.tests_pilotage_queries \
  wms.tests.core.tests_policies \
  wms.tests.core.tests_portal_dashboard_queries \
  wms.tests.core.tests_planning_version_queries \
  wms.tests.views.tests_views_scan_dashboard \
  wms.tests.views.tests_views_scan_pilotage \
  wms.tests.views.tests_portal_bootstrap_ui \
  wms.tests.views.tests_views_planning \
  api.tests.tests_ui_endpoints \
  -v 2

make typecheck
make typecheck-pyright
uv run ruff check wms/application wms/policies api/v1/ui_views.py wms/views_scan_dashboard.py wms/views_scan_pilotage.py wms/views_portal_orders.py wms/views_planning.py
```

Expected:

- targeted Django suites pass
- type gates pass for the expanded V3.1 perimeter
- Ruff passes on touched modules
