# ASF WMS V3.3 Domain And Runtime Simplification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Simplify the shipment-party graph, planning artifact runtime, legacy scan asset surface, and structural quality gates after `V3.1` and `V3.2`.

**Architecture:** Introduce explicit `wms/parties/` and `wms/artifacts/` boundaries below the `V3.1` application layer, route existing portal/admin/planning surfaces through those boundaries, then reduce legacy frontend coupling while expanding type and contract safety around the new layers.

**Tech Stack:** Django 5, legacy Django templates, `wms/application`, `wms/events`, `wms/jobs`, Excel-based planning exports, Ruff, mypy, pyright, `manage.py test`.

---

### Task 1: Freeze V3.3 runtime maps and invariants before code changes

**Files:**
- Create: `docs/plans/2026-04-02-v33-parties-runtime-map.md`
- Create: `docs/plans/2026-04-02-v33-artifacts-runtime-map.md`
- Modify: `docs/repo-reference/01-architecture-and-entrypoints.md`
- Modify: `docs/repo-reference/03-impact-map.md`
- Test: create `wms/tests/core/tests_v33_runtime_maps.py`

**Step 1: Write the failing test**

Create a guard test that asserts the repo-reference and runtime maps mention the new target boundaries:

```python
from pathlib import Path


def test_v33_runtime_maps_reference_parties_and_artifacts():
    base = Path(__file__).resolve().parents[3]
    parties_map = (base / "docs" / "plans" / "2026-04-02-v33-parties-runtime-map.md").read_text()
    artifacts_map = (base / "docs" / "plans" / "2026-04-02-v33-artifacts-runtime-map.md").read_text()
    assert "wms/parties/" in parties_map
    assert "wms/artifacts/" in artifacts_map
```

Suggested file: `wms/tests/core/tests_v33_runtime_maps.py`

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_v33_runtime_maps -v 2`

Expected: FAIL because the runtime map docs do not exist yet.

**Step 3: Write minimal implementation**

- document the current runtime entry points for:
  - portal recipient sync
  - shipment-party selectors and rules
  - admin merge flow
  - planning workbook / PDF / attachment / proof flow
- update `docs/repo-reference/01-architecture-and-entrypoints.md` and `docs/repo-reference/03-impact-map.md` to acknowledge the incoming `V3.3` boundaries

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_v33_runtime_maps -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add docs/plans/2026-04-02-v33-parties-runtime-map.md docs/plans/2026-04-02-v33-artifacts-runtime-map.md docs/repo-reference/01-architecture-and-entrypoints.md docs/repo-reference/03-impact-map.md wms/tests/core/tests_v33_runtime_maps.py
git commit -m "docs: map v3.3 parties and artifact runtime boundaries"
```

### Task 2: Create the `wms/parties/` boundary and shared selectors

**Files:**
- Create: `wms/parties/__init__.py`
- Create: `wms/parties/selectors.py`
- Create: `wms/parties/invariants.py`
- Create: `wms/application/parties/__init__.py`
- Modify: `wms/shipment_party_registry.py`
- Modify: `wms/shipment_party_rules.py`
- Test: create `wms/tests/core/tests_parties_selectors.py`
- Test: `wms/tests/portal/tests_portal_shipment_parties.py`

**Step 1: Write the failing test**

Add focused selector tests:

```python
from wms.parties.selectors import validated_recipient_organizations_for_destination


def test_validated_recipient_organizations_for_destination_filters_active_validated_rows(destination):
    rows = list(validated_recipient_organizations_for_destination(destination))
    assert rows == []
```

Suggested file: `wms/tests/core/tests_parties_selectors.py`

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_parties_selectors -v 2`

Expected: FAIL because `wms.parties.selectors` does not exist yet.

**Step 3: Write minimal implementation**

- create `wms/parties/selectors.py` as the new home for validated/active/eligible selector logic
- move or wrap the duplicated filters currently spread across `shipment_party_registry.py` and `shipment_party_rules.py`
- create `wms/parties/invariants.py` for graph-level assertions that can be reused later by sync and merge use cases
- leave old modules in place as adapters for now

**Step 4: Run test to verify it passes**

Run:

- `./.venv/bin/python manage.py test wms.tests.core.tests_parties_selectors -v 2`
- `./.venv/bin/python manage.py test wms.tests.portal.tests_portal_shipment_parties -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/parties wms/application/parties/__init__.py wms/shipment_party_registry.py wms/shipment_party_rules.py wms/tests/core/tests_parties_selectors.py wms/tests/portal/tests_portal_shipment_parties.py
git commit -m "refactor: introduce shared v3 parties selectors"
```

### Task 3: Route portal recipient sync through `wms/parties/sync.py`

**Files:**
- Create: `wms/parties/sync.py`
- Create: `wms/application/parties/use_cases.py`
- Modify: `wms/portal_recipient_sync.py`
- Modify: `wms/views_portal_account.py`
- Modify: `wms/views_portal_orders.py`
- Test: `wms/tests/portal/tests_portal_recipient_sync.py`
- Test: `wms/tests/views/tests_views_portal.py`

**Step 1: Write the failing test**

Add a use-case contract test:

```python
from wms.application.parties.use_cases import sync_portal_recipient


def test_sync_portal_recipient_returns_structure_and_recipient_scope(recipient):
    result = sync_portal_recipient(recipient=recipient)
    assert "synced_contact_id" in result
    assert "recipient_organization_id" in result
```

Suggested file: `wms/tests/core/tests_parties_use_cases.py`

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_parties_use_cases -v 2`

Expected: FAIL because the use case does not exist.

**Step 3: Write minimal implementation**

- move portal sync orchestration from `wms/portal_recipient_sync.py` into `wms/parties/sync.py`
- create `wms/application/parties/use_cases.py` as the application-facing entry point for portal sync
- keep `wms/portal_recipient_sync.py` as a compatibility adapter during migration
- update portal views to call the use case, not low-level orchestration helpers directly

**Step 4: Run test to verify it passes**

Run:

- `./.venv/bin/python manage.py test wms.tests.core.tests_parties_use_cases -v 2`
- `./.venv/bin/python manage.py test wms.tests.portal.tests_portal_recipient_sync -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/parties/sync.py wms/application/parties/use_cases.py wms/portal_recipient_sync.py wms/views_portal_account.py wms/views_portal_orders.py wms/tests/core/tests_parties_use_cases.py wms/tests/portal/tests_portal_recipient_sync.py wms/tests/views/tests_views_portal.py
git commit -m "refactor: route portal recipient sync through v3 parties use cases"
```

### Task 4: Route admin merge and cockpit mutations through `wms/parties/merge.py`

**Files:**
- Create: `wms/parties/merge.py`
- Modify: `wms/admin_contacts_merge_service.py`
- Modify: `wms/scan_admin_contacts_cockpit.py`
- Modify: `wms/views_scan_admin.py`
- Test: `wms/tests/scan/tests_admin_contacts_merge_service.py`
- Test: `wms/tests/views/tests_views_scan_admin.py`
- Test: `wms/tests/views/tests_views_scan_admin_shipment_parties.py`

**Step 1: Write the failing test**

Add a merge use-case test that proves graph reconciliation goes through the new boundary:

```python
from wms.parties.merge import merge_recipient_organizations


def test_merge_recipient_organizations_returns_target_scope(source_recipient_org, target_recipient_org):
    result = merge_recipient_organizations(source=source_recipient_org, target=target_recipient_org)
    assert result.target_recipient_organization_id == target_recipient_org.id
```

Suggested file: `wms/tests/core/tests_parties_merge.py`

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_parties_merge -v 2`

Expected: FAIL

**Step 3: Write minimal implementation**

- extract merge behavior from `admin_contacts_merge_service.py` and `scan_admin_contacts_cockpit.py`
- keep form validation and user messages in the adapters
- move graph mutation semantics into `wms/parties/merge.py`

**Step 4: Run test to verify it passes**

Run:

- `./.venv/bin/python manage.py test wms.tests.core.tests_parties_merge -v 2`
- `./.venv/bin/python manage.py test wms.tests.scan.tests_admin_contacts_merge_service -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_scan_admin_shipment_parties -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/parties/merge.py wms/admin_contacts_merge_service.py wms/scan_admin_contacts_cockpit.py wms/views_scan_admin.py wms/tests/core/tests_parties_merge.py wms/tests/scan/tests_admin_contacts_merge_service.py wms/tests/views/tests_views_scan_admin.py wms/tests/views/tests_views_scan_admin_shipment_parties.py
git commit -m "refactor: centralize admin parties merge orchestration"
```

### Task 5: Simplify recipient organization scope to `(organization, destination)`

**Files:**
- Modify: `wms/models_domain/shipment_parties.py`
- Create: `wms/migrations/<new_migration>.py`
- Modify: `wms/portal_recipient_sync.py`
- Modify: `wms/admin_contacts_merge_service.py`
- Modify: `wms/views_portal_account.py`
- Modify: `wms/views_portal_orders.py`
- Modify: `wms/local_exhaustive_seed.py`
- Test: `wms/tests/portal/tests_portal_recipient_sync.py`
- Test: `wms/tests/portal/tests_portal_shipment_parties.py`
- Test: `wms/tests/views/tests_views_portal.py`
- Test: create `wms/tests/core/tests_parties_destination_scope.py`

**Step 1: Write the failing test**

Add a new scope test:

```python
def test_same_structure_can_exist_as_recipient_on_two_destinations(structure, destination_a, destination_b):
    ShipmentRecipientOrganization.objects.create(organization=structure, destination=destination_a)
    ShipmentRecipientOrganization.objects.create(organization=structure, destination=destination_b)
```

Suggested file: `wms/tests/core/tests_parties_destination_scope.py`

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_parties_destination_scope -v 2`

Expected: FAIL because the current unique constraint still blocks a second destination-scoped row.

**Step 3: Write minimal implementation**

- change the recipient organization uniqueness model to be destination-scoped
- update sync, merge, and portal callers that still assume “one organization means one recipient scope”
- keep existing business behavior stable for current nominal cases while removing the global uniqueness workaround

**Step 4: Run test to verify it passes**

Run:

- `./.venv/bin/python manage.py test wms.tests.core.tests_parties_destination_scope -v 2`
- `./.venv/bin/python manage.py test wms.tests.portal.tests_portal_recipient_sync wms.tests.portal.tests_portal_shipment_parties -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal -v 2`
- `./.venv/bin/python manage.py makemigrations --check --dry-run`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/models_domain/shipment_parties.py wms/migrations wms/portal_recipient_sync.py wms/admin_contacts_merge_service.py wms/views_portal_account.py wms/views_portal_orders.py wms/local_exhaustive_seed.py wms/tests/core/tests_parties_destination_scope.py wms/tests/portal/tests_portal_recipient_sync.py wms/tests/portal/tests_portal_shipment_parties.py wms/tests/views/tests_views_portal.py
git commit -m "refactor: scope shipment recipient organizations by destination"
```

### Task 6: Introduce artifact lifecycle services for planning exports

**Files:**
- Create: `wms/artifacts/__init__.py`
- Create: `wms/artifacts/planning.py`
- Create: `wms/artifacts/attachments.py`
- Create: `wms/artifacts/proofs.py`
- Create: `wms/application/planning_artifacts/__init__.py`
- Create: `wms/application/planning_artifacts/use_cases.py`
- Modify: `wms/planning/exports.py`
- Modify: `wms/planning/communication_actions.py`
- Modify: `wms/planning/artifact_health.py`
- Test: create `wms/tests/planning/tests_artifact_services.py`
- Test: `wms/tests/planning/tests_outputs.py`
- Test: `wms/tests/planning/tests_communication_actions.py`

**Step 1: Write the failing test**

Add a lifecycle test:

```python
from wms.artifacts.planning import build_planning_artifacts


def test_build_planning_artifacts_returns_workbook_and_pdf_metadata(version):
    result = build_planning_artifacts(version)
    assert "workbook" in result
    assert "pdf" in result
```

Suggested file: `wms/tests/planning/tests_artifact_services.py`

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.planning.tests_artifact_services -v 2`

Expected: FAIL

**Step 3: Write minimal implementation**

- move planning artifact orchestration out of `wms/planning/exports.py`
- keep workbook generation, PDF conversion, readiness recording, and attachment selection in separate modules
- let `wms/planning/exports.py` and `communication_actions.py` become adapters around those services

**Step 4: Run test to verify it passes**

Run:

- `./.venv/bin/python manage.py test wms.tests.planning.tests_artifact_services -v 2`
- `./.venv/bin/python manage.py test wms.tests.planning.tests_outputs wms.tests.planning.tests_communication_actions -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/artifacts wms/application/planning_artifacts wms/planning/exports.py wms/planning/communication_actions.py wms/planning/artifact_health.py wms/tests/planning/tests_artifact_services.py wms/tests/planning/tests_outputs.py wms/tests/planning/tests_communication_actions.py
git commit -m "refactor: introduce planning artifact lifecycle services"
```

### Task 7: Route proof and sync behavior through explicit artifact runtime helpers

**Files:**
- Modify: `wms/print_pack_sync.py`
- Modify: `wms/jobs/print_artifacts.py`
- Modify: `wms/jobs/runtime_tracking.py`
- Modify: `docs/operations.md`
- Modify: `docs/release_checklist.md`
- Test: `wms/tests/print/tests_print_pack_sync.py`
- Test: `wms/tests/test_job_runs.py`

**Step 1: Write the failing test**

Add a focused regression test asserting the sync path uses the new proof helper payload rather than inlined path logic.

Suggested file: extend `wms/tests/print/tests_print_pack_sync.py`

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.print.tests_print_pack_sync -v 2`

Expected: FAIL after adding the assertion but before refactoring the runtime path.

**Step 3: Write minimal implementation**

- move proof-path and sync orchestration into `wms/artifacts/proofs.py`
- keep `wms/print_pack_sync.py` as an adapter over the shared runtime helper
- surface meaningful job-run summaries for artifact sync failures and retries

**Step 4: Run test to verify it passes**

Run:

- `./.venv/bin/python manage.py test wms.tests.print.tests_print_pack_sync -v 2`
- `./.venv/bin/python manage.py test wms.tests.test_job_runs -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/print_pack_sync.py wms/jobs/print_artifacts.py wms/jobs/runtime_tracking.py docs/operations.md docs/release_checklist.md wms/tests/print/tests_print_pack_sync.py wms/tests/test_job_runs.py
git commit -m "refactor: align artifact proof sync with v3 runtime helpers"
```

### Task 8: Modularize legacy scan assets without adding a build step

**Files:**
- Create: `wms/static/scan/modules/core.js`
- Create: `wms/static/scan/modules/dashboard.js`
- Create: `wms/static/scan/modules/shipments.js`
- Create: `wms/static/scan/css/partials/foundation.css`
- Create: `wms/static/scan/css/partials/ops.css`
- Create: `wms/static/scan/css/partials/auth-public.css`
- Modify: `wms/static/scan/scan.js`
- Modify: `wms/static/scan/scan.css`
- Modify: `wms/static/scan/scan-bootstrap.css`
- Modify: `templates/scan/base.html`
- Modify: `templates/portal/base.html`
- Modify: `templates/planning/base.html`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Test: `wms/tests/views/tests_views_imports.py`

**Step 1: Write the failing test**

Add bootstrap tests that assert the shared entrypoint stays present while a first modular file is also loaded on the scan base template.

**Step 2: Run test to verify it fails**

Run:

- `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL once the test asserts the new module contract.

**Step 3: Write minimal implementation**

- keep `scan.js`, `scan.css`, and `scan-bootstrap.css` as stable entrypoint filenames
- thin those files down and move first concerns into modular partials
- load additional JS modules only from templates that need them
- preserve portal/planning/public consumers of the shared CSS entrypoints

**Step 4: Run test to verify it passes**

Run:

- `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_imports -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/static/scan/modules wms/static/scan/css/partials wms/static/scan/scan.js wms/static/scan/scan.css wms/static/scan/scan-bootstrap.css templates/scan/base.html templates/portal/base.html templates/planning/base.html wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_portal_bootstrap_ui.py wms/tests/views/tests_views_imports.py
git commit -m "refactor: modularize legacy scan static entrypoints"
```

### Task 9: Expand quality gates to the structural hotspots

**Files:**
- Modify: `mypy.ini`
- Modify: `pyrightconfig.json`
- Modify: `Makefile`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Test: create `wms/tests/core/tests_v33_contracts.py`
- Test: existing structural slices from `application`, `events`, `jobs`, `parties`, and `artifacts`

**Step 1: Write the failing test**

Add a simple contract suite that imports the V3 structural layers and asserts the presence of the main entry points.

Suggested file: `wms/tests/core/tests_v33_contracts.py`

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_v33_contracts -v 2`

Expected: FAIL before the entry points or import surface are finalized.

**Step 3: Write minimal implementation**

- expand mypy and pyright includes to the new structural packages
- keep the scope explicit rather than flipping the whole repo at once
- document the new structural proof suite in `docs/repo-reference/02-key-flows-and-living-tests.md`

**Step 4: Run test to verify it passes**

Run:

- `./.venv/bin/python manage.py test wms.tests.core.tests_v33_contracts -v 2`
- `make typecheck`
- `uv run ruff check wms/application wms/events wms/jobs wms/parties wms/artifacts`

Expected: PASS

**Step 5: Commit**

```bash
git add mypy.ini pyrightconfig.json Makefile docs/repo-reference/02-key-flows-and-living-tests.md wms/tests/core/tests_v33_contracts.py
git commit -m "chore: expand structural quality gates for v3 wave3"
```

### Task 10: Finalize V3.3 repo-reference and rollout docs

**Files:**
- Modify: `docs/repo-reference/01-architecture-and-entrypoints.md`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/03-impact-map.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Modify: `docs/operations.md`
- Modify: `docs/release_checklist.md`

**Step 1: Write the failing test**

No new runtime test. Use a doc completion checklist in the PR and verify the impacted reference files are updated.

**Step 2: Run test to verify it fails**

Not applicable. Use manual checklist review against the impacted surfaces.

**Step 3: Write minimal implementation**

- update repo-reference to reflect the final `V3.3` boundaries
- align operations and release docs with the new artifact runtime and party graph rules
- remove stale references that still describe the pre-`V3.3` orchestration as canonical

**Step 4: Run test to verify it passes**

Run the final structural verification bundle:

- `make typecheck`
- `uv run ruff check wms/application wms/events wms/jobs wms/parties wms/artifacts`
- the targeted test suites from Tasks 2 through 9

Expected: PASS

**Step 5: Commit**

```bash
git add docs/repo-reference/01-architecture-and-entrypoints.md docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/03-impact-map.md docs/repo-reference/04-shared-contracts.md docs/operations.md docs/release_checklist.md
git commit -m "docs: finalize v3 wave3 runtime reference"
```
