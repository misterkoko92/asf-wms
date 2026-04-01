# V2 Prod Readiness Excel-First Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** harden ASF WMS V2 for production by making Excel the explicit planning PDF backend, adding readiness checks and safe mail behavior, and finalizing the ops/release loop.

**Architecture:** keep the strict workbook as the rendering source of truth and harden the existing planning PDF path instead of replacing it. Add a small helper boundary for Excel runtime readiness, propagate that signal through artifact health and planning UI, then add production-facing commands and release docs.

**Tech Stack:** Django 5.2 legacy templates, DRF, openpyxl, Microsoft Excel automation, management commands, local pilotage models, Django test suites under `wms/tests`, `api/tests`, and `tools/planning_comm_helper/tests`.

---

### Task 1: Add Excel Runtime Readiness Boundary

**Files:**
- Create: `tools/planning_comm_helper/excel_runtime.py`
- Modify: `tools/planning_comm_helper/excel_pdf.py`
- Modify: `tools/planning_comm_helper/planning_pdf.py`
- Test: `tools/planning_comm_helper/tests/test_excel_runtime.py`
- Test: `tools/planning_comm_helper/tests/test_planning_pdf.py`

**Step 1: Write the failing readiness tests**

Add focused tests in `tools/planning_comm_helper/tests/test_excel_runtime.py` covering:

```python
def test_excel_runtime_ready_on_macos_when_excel_app_is_visible(self):
    status = excel_runtime.get_excel_runtime_status()
    self.assertEqual(status["status"], "ready")
    self.assertEqual(status["backend"], "excel_desktop")
```

```python
def test_excel_runtime_returns_excel_not_installed_code(self):
    status = excel_runtime.get_excel_runtime_status()
    self.assertEqual(status["status"], "excel_not_installed")
```

Extend `tools/planning_comm_helper/tests/test_planning_pdf.py` with:

```python
def test_convert_workbook_to_pdf_surfaces_runtime_unavailable_error_code(self):
    with self.assertRaises(PlanningPdfConversionError) as error:
        convert_workbook_to_pdf(workbook.name)
    self.assertIn("excel_not_installed", str(error.exception))
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
./.venv/bin/python -m unittest \
  tools/planning_comm_helper/tests/test_excel_runtime.py \
  tools/planning_comm_helper/tests/test_planning_pdf.py
```

Expected:

- FAIL because the runtime boundary does not exist yet

**Step 3: Add the minimal readiness helper**

Implement `tools/planning_comm_helper/excel_runtime.py` with a stable helper such as:

```python
def get_excel_runtime_status() -> dict[str, str | bool]:
    return {
        "backend": "excel_desktop",
        "status": "ready",
        "available": True,
        "detail": "",
    }
```

Cover at least:

- macOS Excel detection
- Windows Excel automation availability
- unsupported platform result

**Step 4: Wire the helper into planning PDF conversion**

Update `excel_pdf.py` and `planning_pdf.py` so that:

- the runtime helper is consulted before conversion
- failures expose stable readiness codes
- the backend name remains `excel_desktop`

**Step 5: Run the tests to verify they pass**

Run:

```bash
./.venv/bin/python -m unittest \
  tools/planning_comm_helper/tests/test_excel_runtime.py \
  tools/planning_comm_helper/tests/test_planning_pdf.py
```

Expected:

- PASS with stable readiness status and failure messaging

**Step 6: Commit**

```bash
git add tools/planning_comm_helper/excel_runtime.py \
  tools/planning_comm_helper/excel_pdf.py \
  tools/planning_comm_helper/planning_pdf.py \
  tools/planning_comm_helper/tests/test_excel_runtime.py \
  tools/planning_comm_helper/tests/test_planning_pdf.py
git commit -m "feat: add excel runtime readiness checks"
```

### Task 2: Harden Planning PDF Artifacts And Mail Safety

**Files:**
- Modify: `wms/planning/artifact_health.py`
- Modify: `wms/planning/exports.py`
- Modify: `wms/planning/communication_actions.py`
- Modify: `wms/planning/version_dashboard.py`
- Modify: `templates/planning/_version_exports_block.html`
- Test: `wms/tests/planning/tests_outputs.py`
- Test: `wms/tests/planning/tests_communication_actions.py`
- Test: `wms/tests/views/tests_views_planning.py`

**Step 1: Write the failing tests**

Extend `wms/tests/planning/tests_outputs.py` with:

```python
def test_planning_export_records_runtime_failure_code_when_excel_is_unavailable(self):
    artifact = generate_planning_artifacts(version=self.version)
    self.assertEqual(artifact.output_type, "planning_pdf")
    self.assertEqual(artifact.payload["error_code"], "excel_not_installed")
```

Extend `wms/tests/planning/tests_communication_actions.py` with:

```python
def test_planning_mail_payload_is_blocked_when_no_ready_pdf_exists(self):
    payload = build_family_helper_action_payload(version=self.version, family="email_asf")
    self.assertTrue(payload["drafts"][0]["blocked"])
    self.assertEqual(payload["drafts"][0]["blocking_reason"], "planning_pdf_not_ready")
```

Extend `wms/tests/views/tests_views_planning.py` with:

```python
def test_version_detail_renders_pdf_runtime_status(self):
    response = self.client.get(reverse("planning:version_detail", args=[self.version.pk]))
    self.assertContains(response, "Runtime PDF")
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.planning.tests_outputs \
  wms.tests.planning.tests_communication_actions \
  wms.tests.views.tests_views_planning -v 2
```

Expected:

- FAIL because runtime status and blocked mail payloads are not exposed yet

**Step 3: Add minimal runtime-aware export behavior**

Update the planning export layer so that:

- runtime readiness is captured before PDF conversion
- failed `planning_pdf` health rows store stable payload keys:

```python
{
    "error_code": "excel_not_installed",
    "runtime_status": "excel_not_installed",
    "runtime_detail": "...",
}
```

- workbook success is preserved even when PDF fails

**Step 4: Add safe mail payload behavior**

Update `wms/planning/communication_actions.py` so planning families:

- use the latest ready PDF when present
- otherwise expose `blocked=True` and `blocking_reason="planning_pdf_not_ready"`

Do not change packing-list flows.

**Step 5: Surface runtime status in planning UI**

Update the planning exports block so it shows:

- `Runtime PDF`
- backend name
- readiness status label
- runtime detail if unavailable

Keep the artifact-health block and existing controls intact.

**Step 6: Run the tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.planning.tests_outputs \
  wms.tests.planning.tests_communication_actions \
  wms.tests.views.tests_views_planning -v 2
```

Expected:

- PASS with runtime-aware planning exports and safe mail payloads

**Step 7: Commit**

```bash
git add wms/planning/artifact_health.py \
  wms/planning/exports.py \
  wms/planning/communication_actions.py \
  wms/planning/version_dashboard.py \
  templates/planning/_version_exports_block.html \
  wms/tests/planning/tests_outputs.py \
  wms/tests/planning/tests_communication_actions.py \
  wms/tests/views/tests_views_planning.py
git commit -m "feat: harden planning pdf runtime and mail safety"
```

### Task 3: Add Production Ops Commands

**Files:**
- Create: `wms/management/commands/check_planning_pdf_runtime.py`
- Create: `wms/management/commands/refresh_ops_pilotage.py`
- Test: `wms/tests/management/tests_management_check_planning_pdf_runtime.py`
- Test: `wms/tests/management/tests_management_refresh_ops_pilotage.py`
- Modify: `docs/operations.md`

**Step 1: Write the failing command tests**

Add focused tests:

```python
def test_check_planning_pdf_runtime_returns_success_when_backend_is_ready(self):
    call_command("check_planning_pdf_runtime")
```

```python
def test_refresh_ops_pilotage_runs_snapshot_and_escalation_pipeline(self):
    call_command("refresh_ops_pilotage", snapshot_date="2026-04-01")
    self.assertTrue(OpsPilotageSnapshot.objects.exists())
    self.assertTrue(OpsEscalation.objects.exists() or OpsEscalation.objects.count() == 0)
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.management.tests_management_check_planning_pdf_runtime \
  wms.tests.management.tests_management_refresh_ops_pilotage -v 2
```

Expected:

- FAIL because the commands do not exist yet

**Step 3: Add the commands**

Implement:

- `check_planning_pdf_runtime`
  - prints backend, status, detail
  - exits non-zero when not ready
- `refresh_ops_pilotage`
  - runs `capture_ops_pilotage_snapshot`
  - runs `evaluate_ops_escalations`
  - prints written/open/resolved counts

**Step 4: Run the tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.management.tests_management_check_planning_pdf_runtime \
  wms.tests.management.tests_management_refresh_ops_pilotage -v 2
```

Expected:

- PASS with production-oriented command coverage

**Step 5: Commit**

```bash
git add wms/management/commands/check_planning_pdf_runtime.py \
  wms/management/commands/refresh_ops_pilotage.py \
  wms/tests/management/tests_management_check_planning_pdf_runtime.py \
  wms/tests/management/tests_management_refresh_ops_pilotage.py \
  docs/operations.md
git commit -m "feat: add planning pdf and pilotage prod commands"
```

### Task 4: Finalize Release Gate Docs And Validation Loop

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Modify: `docs/release_checklist.md`
- Modify: `docs/operations.md`

**Step 1: Add the doc deltas**

Document:

- Excel as the official V2 planning PDF backend
- runtime readiness contract and stable statuses
- `check_planning_pdf_runtime`
- `refresh_ops_pilotage`
- the required prod smoke around:
  - `/planning/versions/<id>/`
  - PDF runtime visibility
  - safe planning mail payload expectations

**Step 2: Run the final verification set**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.forms.tests_forms_scan_settings \
  wms.tests.core.tests_runtime_settings \
  wms.tests.planning.tests_outputs \
  wms.tests.planning.tests_communication_actions \
  wms.tests.planning.tests_version_dashboard \
  wms.tests.views.tests_views_planning \
  wms.tests.views.tests_views_scan_settings \
  wms.tests.views.tests_views_scan_dashboard \
  wms.tests.views.tests_views_scan_pilotage \
  wms.tests.management.tests_management_check_planning_pdf_runtime \
  wms.tests.management.tests_management_refresh_ops_pilotage \
  api.tests.tests_ui_endpoints -v 2

uv run ruff check \
  wms/planning \
  wms/views_planning.py \
  wms/views_scan_settings.py \
  wms/views_scan_dashboard.py \
  wms/scan_pilotage.py \
  wms/runtime_settings.py \
  tools/planning_comm_helper
```

Expected:

- PASS with V2 production hardening complete

**Step 3: Commit**

```bash
git add docs/repo-reference/02-key-flows-and-living-tests.md \
  docs/repo-reference/04-shared-contracts.md \
  docs/release_checklist.md \
  docs/operations.md
git commit -m "docs: finalize v2 prod readiness runbook"
```
