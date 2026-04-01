# ASF WMS V2 Phase 2 Global Pilotage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** deliver the second local-only phase of ASF WMS V2 by adding persisted pilotage metrics, local escalations, a transverse daily ops cockpit, and a more robust planning PDF/mail control loop on top of the legacy Django surfaces already delivered in phase 1.

**Architecture:** keep the legacy Django stack as the visible surface and build phase 2 on derived data rather than new transactional workflows. Persist daily pilotage snapshots and local escalations in `wms/models_domain/integration.py`, reuse existing workflow and planning read models, then expose the resulting signal through a new staff cockpit under `scan` and mirrored API payloads. Treat PDF/mail planning hardening as an observable subsystem first: expose artifact health and escalation state before attempting a full backend replacement.

**Tech Stack:** Django 5.2 legacy templates, DRF, SQLite local dev, `wms/models_domain/*`, `wms/workflow_projection.py`, `wms/planning/*`, `api/v1/*`, management commands, runtime settings, local exhaustive seed, Django test suites under `wms/tests` and `api/tests`.

---

### Task 1: Capture Daily Pilotage Snapshots

**Files:**
- Modify: `wms/models_domain/integration.py`
- Create: `wms/migrations/0103_opspilotagesnapshot.py`
- Create: `wms/ops_pilotage_snapshots.py`
- Create: `wms/management/commands/capture_ops_pilotage_snapshot.py`
- Modify: `wms/workflow_projection.py`
- Modify: `wms/planning/stats.py`
- Test: `wms/tests/test_ops_pilotage_snapshots.py`
- Test: `wms/tests/management/tests_management_capture_ops_pilotage_snapshot.py`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Write the failing snapshot helper tests**

Add focused tests in `wms/tests/test_ops_pilotage_snapshots.py` covering:

```python
def test_build_ops_pilotage_snapshots_captures_global_destination_and_flight_metrics(self):
    rows = build_ops_pilotage_snapshots(snapshot_date=date(2026, 4, 1))
    metrics = {(row["scope_type"], row["metric_key"]) for row in rows}
    self.assertIn(("global", "sla_new_count"), metrics)
    self.assertIn(("destination", "critical_shipment_count"), metrics)
    self.assertIn(("flight", "capacity_overload_count"), metrics)
```

```python
def test_build_ops_pilotage_snapshots_captures_planning_pdf_and_queue_health(self):
    rows = build_ops_pilotage_snapshots(snapshot_date=date(2026, 4, 1))
    metrics = {(row["scope_type"], row["metric_key"]) for row in rows}
    self.assertIn(("planning_export", "planning_pdf_ok"), metrics)
    self.assertIn(("queue", "document_scan_failed_count"), metrics)
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.test_ops_pilotage_snapshots -v 2
```

Expected:

- FAIL because the snapshot helper and model do not exist yet

**Step 3: Add the snapshot model and helper**

Implement `OpsPilotageSnapshot` in `wms/models_domain/integration.py` with a uniqueness rule around:

```python
("snapshot_date", "scope_type", "scope_key", "metric_key")
```

Create `wms/ops_pilotage_snapshots.py` with a helper shaped like:

```python
def build_ops_pilotage_snapshots(*, snapshot_date):
    return [
        {
            "snapshot_date": snapshot_date,
            "scope_type": "global",
            "scope_key": "all",
            "metric_key": "sla_new_count",
            "metric_value": 3,
            "payload": {"source": "dashboard"},
        }
    ]
```

Reuse existing sources instead of re-deriving rules:

- `build_destination_workflow_projection_rows(...)`
- `build_destination_week_workflow_projection_rows(...)`
- planning capacity helpers in `wms/planning/stats.py`
- queue snapshots already used by `wms/views_scan_dashboard.py`

**Step 4: Add the management command**

Create `capture_ops_pilotage_snapshot` that:

- defaults to today in the local timezone
- rebuilds or upserts snapshots for one day
- prints the number of rows written

**Step 5: Add the command tests**

Create `wms/tests/management/tests_management_capture_ops_pilotage_snapshot.py` with a smoke test:

```python
def test_capture_ops_pilotage_snapshot_writes_rows(self):
    call_command("capture_ops_pilotage_snapshot", snapshot_date="2026-04-01")
    self.assertTrue(OpsPilotageSnapshot.objects.exists())
```

**Step 6: Run the tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.test_ops_pilotage_snapshots \
  wms.tests.management.tests_management_capture_ops_pilotage_snapshot -v 2
```

Expected:

- PASS with persisted daily rows for global, destination, flight, queue, and planning export scopes

**Step 7: Update shared-contract docs**

Document in `docs/repo-reference/04-shared-contracts.md`:

- `OpsPilotageSnapshot` purpose
- stable `scope_type` vocabulary
- rebuild path `python manage.py capture_ops_pilotage_snapshot`

**Step 8: Commit**

```bash
git add wms/models_domain/integration.py \
  wms/migrations/0103_opspilotagesnapshot.py \
  wms/ops_pilotage_snapshots.py \
  wms/management/commands/capture_ops_pilotage_snapshot.py \
  wms/workflow_projection.py \
  wms/planning/stats.py \
  wms/tests/test_ops_pilotage_snapshots.py \
  wms/tests/management/tests_management_capture_ops_pilotage_snapshot.py \
  docs/repo-reference/04-shared-contracts.md
git commit -m "feat: add daily ops pilotage snapshots"
```

### Task 2: Add Persistent Local Escalations

**Files:**
- Modify: `wms/models_domain/integration.py`
- Create: `wms/migrations/0104_opsescalation.py`
- Create: `wms/ops_escalations.py`
- Create: `wms/management/commands/evaluate_ops_escalations.py`
- Modify: `wms/views_scan_settings.py`
- Modify: `templates/scan/settings.html`
- Test: `wms/tests/test_ops_escalations.py`
- Test: `wms/tests/views/tests_views_scan_settings.py`
- Modify: `docs/operations.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Write the failing escalation tests**

Add focused tests in `wms/tests/test_ops_escalations.py`:

```python
def test_evaluate_ops_escalations_opens_unassigned_dispute_and_sla_persistent_alerts(self):
    escalations = evaluate_ops_escalations(now=timezone.now())
    categories = {item["category"] for item in escalations}
    self.assertIn("dispute_unassigned", categories)
    self.assertIn("sla_persistent", categories)
```

```python
def test_evaluate_ops_escalations_detects_planning_pdf_missing(self):
    escalations = evaluate_ops_escalations(now=timezone.now())
    self.assertTrue(any(item["category"] == "planning_pdf_missing" for item in escalations))
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.test_ops_escalations -v 2
```

Expected:

- FAIL because the escalation engine does not exist yet

**Step 3: Add the escalation model and helper**

Implement `OpsEscalation` with:

- `escalation_key`
- `category`
- `scope_type`
- `scope_key`
- `severity`
- `owner`
- `status`
- `first_detected_at`
- `last_detected_at`
- `acknowledged_at`
- `resolved_at`
- `payload`

Create `wms/ops_escalations.py` with an evaluator shaped like:

```python
def evaluate_ops_escalations(*, now):
    return [
        {
            "category": "sla_persistent",
            "scope_type": "shipment",
            "scope_key": "EXP-001",
            "severity": "high",
            "owner": "qualite",
            "payload": {"delay_state": "persistent"},
        }
    ]
```

Use explicit local categories only:

- `sla_persistent`
- `dispute_unassigned`
- `workflow_blockage_unclaimed`
- `planning_capacity_overload`
- `planning_pdf_missing`
- `queue_backlog`
- `portal_stalled`

**Step 4: Add the evaluation command**

Create `evaluate_ops_escalations` that:

- computes current escalations
- upserts open ones
- resolves stale ones no longer present
- prints open/resolved counts

**Step 5: Add runtime calibration fields and preview**

Extend `scan/settings` with local thresholds:

- hours before `dispute_unassigned`
- hours before `workflow_blockage_unclaimed`
- queue backlog threshold
- optional multiplier for `planning_capacity_overload`

Expose preview counters in `templates/scan/settings.html`.

**Step 6: Add or extend tests for settings preview**

Add coverage in `wms/tests/views/tests_views_scan_settings.py` for:

```python
def test_scan_settings_preview_exposes_ops_escalation_counts(self):
    response = self.client.get(reverse("scan:scan_settings"))
    self.assertContains(response, "Escalades pilotage")
```

**Step 7: Run the tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.test_ops_escalations \
  wms.tests.views.tests_views_scan_settings -v 2
```

Expected:

- PASS with persistent local escalations and settings preview counters

**Step 8: Update docs**

Update:

- `docs/operations.md` with the evaluation command and local review loop
- `docs/repo-reference/04-shared-contracts.md` with escalation vocabulary and statuses

**Step 9: Commit**

```bash
git add wms/models_domain/integration.py \
  wms/migrations/0104_opsescalation.py \
  wms/ops_escalations.py \
  wms/management/commands/evaluate_ops_escalations.py \
  wms/views_scan_settings.py \
  templates/scan/settings.html \
  wms/tests/test_ops_escalations.py \
  wms/tests/views/tests_views_scan_settings.py \
  docs/operations.md \
  docs/repo-reference/04-shared-contracts.md
git commit -m "feat: add persistent local ops escalations"
```

### Task 3: Build The Daily Ops Cockpit

**Files:**
- Modify: `wms/scan_urls.py`
- Modify: `wms/views.py`
- Create: `wms/views_scan_pilotage.py`
- Create: `templates/scan/pilotage.html`
- Modify: `api/v1/urls.py`
- Modify: `api/v1/ui_views.py`
- Test: `wms/tests/views/tests_views_scan_pilotage.py`
- Test: `api/tests/tests_ui_endpoints.py`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Write the failing HTML cockpit tests**

Create `wms/tests/views/tests_views_scan_pilotage.py` with:

```python
def test_scan_pilotage_renders_transverse_sections(self):
    response = self.client.get(reverse("scan:scan_pilotage"))
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "Priorites du jour")
    self.assertContains(response, "Escalades persistantes")
    self.assertContains(response, "Exports planning")
```

```python
def test_scan_pilotage_links_back_to_scan_portal_and_planning_surfaces(self):
    response = self.client.get(reverse("scan:scan_pilotage"))
    self.assertContains(response, reverse("scan:scan_dashboard"))
    self.assertContains(response, reverse("portal:portal_dashboard"))
    self.assertContains(response, reverse("planning:planning_versions"))
```

**Step 2: Write the failing UI API tests**

Extend `api/tests/tests_ui_endpoints.py` with:

```python
def test_ui_pilotage_exposes_summary_escalations_and_export_health(self):
    response = self.staff_client.get("/api/v1/ui/pilotage/")
    self.assertEqual(response.status_code, 200)
    payload = response.json()
    self.assertIn("summary_cards", payload)
    self.assertIn("escalation_rows", payload)
    self.assertIn("planning_export_rows", payload)
```

**Step 3: Run the tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_pilotage \
  api.tests.tests_ui_endpoints -v 2
```

Expected:

- FAIL because the route, template, and UI API do not exist yet

**Step 4: Add the cockpit view and template**

Create `wms/views_scan_pilotage.py` with a view that composes:

- daily summary cards from `OpsPilotageSnapshot`
- active escalations from `OpsEscalation`
- destination trend summaries from existing destination aggregates
- planning export health
- portal backlog summary

Wire the route in `wms/scan_urls.py` and re-export in `wms/views.py`.

Add a template section skeleton like:

```django
<section id="scan-pilotage-priorities">
  <h2>Priorites du jour</h2>
</section>
<section id="scan-pilotage-escalations">
  <h2>Escalades persistantes</h2>
</section>
<section id="scan-pilotage-planning-exports">
  <h2>Exports planning</h2>
</section>
```

**Step 5: Add the UI API mirror**

Extend `api/v1/ui_views.py` with `GET /api/v1/ui/pilotage/` returning:

- `summary_cards`
- `priority_rows`
- `escalation_rows`
- `destination_trend_rows`
- `planning_export_rows`
- `portal_backlog_rows`

Keep field names explicit and short.

**Step 6: Run the tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_pilotage \
  api.tests.tests_ui_endpoints -v 2
```

Expected:

- PASS with HTML and API parity on the new daily ops cockpit

**Step 7: Update repo-reference docs**

Update:

- `docs/repo-reference/02-key-flows-and-living-tests.md` with the new cockpit as a reference pilotage surface
- `docs/repo-reference/04-shared-contracts.md` with the `/api/v1/ui/pilotage/` payload contract

**Step 8: Commit**

```bash
git add wms/scan_urls.py \
  wms/views.py \
  wms/views_scan_pilotage.py \
  templates/scan/pilotage.html \
  api/v1/urls.py \
  api/v1/ui_views.py \
  wms/tests/views/tests_views_scan_pilotage.py \
  api/tests/tests_ui_endpoints.py \
  docs/repo-reference/02-key-flows-and-living-tests.md \
  docs/repo-reference/04-shared-contracts.md
git commit -m "feat: add transverse daily ops cockpit"
```

### Task 4: Harden Planning PDF And Mail Artifact Health

**Files:**
- Modify: `wms/models_domain/integration.py`
- Create: `wms/migrations/0105_planningcommunicationartifact.py`
- Create: `wms/planning/artifact_health.py`
- Modify: `wms/planning/exports.py`
- Modify: `wms/planning/communication_actions.py`
- Modify: `wms/views_planning.py`
- Modify: `templates/planning/_version_exports_block.html`
- Modify: `tools/planning_comm_helper/excel_pdf.py`
- Test: `wms/tests/planning/tests_outputs.py`
- Test: `wms/tests/planning/tests_communication_actions.py`
- Test: `tools/planning_comm_helper/tests/test_planning_pdf.py`
- Modify: `docs/operations.md`

**Step 1: Write the failing artifact-health tests**

Extend `wms/tests/planning/tests_outputs.py` with:

```python
def test_planning_export_records_pdf_artifact_health(self):
    artifact = generate_planning_artifacts(version=self.version)
    self.assertEqual(artifact.output_type, "planning_pdf")
    self.assertIn(artifact.status, {"ready", "failed"})
```

Extend `wms/tests/planning/tests_communication_actions.py` with:

```python
def test_planning_mail_prefers_latest_ready_pdf_artifact(self):
    action = build_planning_communication_action(version=self.version)
    self.assertEqual(action.primary_attachment_type, "planning_pdf")
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.planning.tests_outputs \
  wms.tests.planning.tests_communication_actions -v 2
```

Expected:

- FAIL because planning artifact health is not persisted yet

**Step 3: Add the planning artifact model and helper**

Create a lightweight `PlanningCommunicationArtifact` model storing:

- `planning_version`
- `output_type`
- `status`
- `backend`
- `file_name`
- `generated_at`
- `error_message`
- `payload`

Add `wms/planning/artifact_health.py` with helper functions like:

```python
def record_planning_artifact_result(*, version, output_type, status, backend, file_name="", error_message=""):
    ...
```

**Step 4: Wire exports and communication actions**

Update `wms/planning/exports.py` and `wms/planning/communication_actions.py` so that:

- workbook and PDF generation both record artifact status
- latest ready PDF is preferred for communication
- failures produce a stable `planning_pdf_missing` escalation payload

Keep `tools/planning_comm_helper/excel_pdf.py` behind a small adapter boundary rather than calling it directly from the view layer.

**Step 5: Expose artifact health in the planning UI**

Update `wms/views_planning.py` and `_version_exports_block.html` to show:

- last PDF generation status
- backend name
- last successful generation
- operator hint when PDF is unavailable

**Step 6: Run the tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.planning.tests_outputs \
  wms.tests.planning.tests_communication_actions \
  wms.tests.views.tests_views_planning -v 2
./.venv/bin/python -m unittest tools/planning_comm_helper/tests/test_planning_pdf.py
```

Expected:

- PASS with PDF-first communication logic and visible artifact health

**Step 7: Update operations docs**

Document in `docs/operations.md`:

- how to inspect planning artifact health
- how to interpret PDF/backend failures locally
- how this now feeds pilotage escalations

**Step 8: Commit**

```bash
git add wms/models_domain/integration.py \
  wms/migrations/0105_planningcommunicationartifact.py \
  wms/planning/artifact_health.py \
  wms/planning/exports.py \
  wms/planning/communication_actions.py \
  wms/views_planning.py \
  templates/planning/_version_exports_block.html \
  tools/planning_comm_helper/excel_pdf.py \
  wms/tests/planning/tests_outputs.py \
  wms/tests/planning/tests_communication_actions.py \
  wms/tests/views/tests_views_planning.py \
  tools/planning_comm_helper/tests/test_planning_pdf.py \
  docs/operations.md
git commit -m "feat: add planning artifact health and pdf-first comms"
```

### Task 5: Add Pilotage Runtime Rules And Presets

**Files:**
- Modify: `wms/views_scan_settings.py`
- Modify: `templates/scan/settings.html`
- Modify: `wms/views_scan_dashboard.py`
- Modify: `wms/views_scan_pilotage.py`
- Test: `wms/tests/views/tests_views_scan_settings.py`
- Test: `wms/tests/views/tests_views_scan_dashboard.py`
- Test: `wms/tests/views/tests_views_scan_pilotage.py`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Modify: `docs/release_checklist.md`

**Step 1: Write the failing settings and cockpit tests**

Add or extend tests:

```python
def test_scan_settings_exposes_pilotage_presets(self):
    response = self.client.get(reverse("scan:scan_settings"))
    self.assertContains(response, "Pilotage tendu")
```

```python
def test_scan_pilotage_uses_runtime_thresholds_for_summary(self):
    response = self.client.get(reverse("scan:scan_pilotage"))
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "Seuils actifs")
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_settings \
  wms.tests.views.tests_views_scan_dashboard \
  wms.tests.views.tests_views_scan_pilotage -v 2
```

Expected:

- FAIL because pilotage presets and active-threshold summaries do not exist yet

**Step 3: Add runtime settings and presets**

Extend the local settings UI with:

- `pilotage_dispute_unassigned_hours`
- `pilotage_workflow_blockage_unclaimed_hours`
- `pilotage_queue_backlog_threshold`
- `pilotage_planning_tension_pct`
- `pilotage_planning_critical_pct`

Add a preset such as:

```python
{
    "slug": "pilotage_tendu",
    "label": "Pilotage tendu",
    "tracking_alert_hours": 24,
    "pilotage_dispute_unassigned_hours": 8,
    "pilotage_queue_backlog_threshold": 3,
}
```

**Step 4: Surface active thresholds in the cockpit**

Update `wms/views_scan_dashboard.py` and `wms/views_scan_pilotage.py` so the operator can see:

- the active preset name
- the main thresholds currently applied
- the projected impact counts if available

**Step 5: Run the tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_settings \
  wms.tests.views.tests_views_scan_dashboard \
  wms.tests.views.tests_views_scan_pilotage -v 2
```

Expected:

- PASS with visible pilotage presets and active threshold context

**Step 6: Update docs**

Update:

- `docs/repo-reference/04-shared-contracts.md` for runtime pilotage vocabulary
- `docs/release_checklist.md` for local smoke expectations around pilotage thresholds and cockpit visibility

**Step 7: Commit**

```bash
git add wms/views_scan_settings.py \
  templates/scan/settings.html \
  wms/views_scan_dashboard.py \
  wms/views_scan_pilotage.py \
  wms/tests/views/tests_views_scan_settings.py \
  wms/tests/views/tests_views_scan_dashboard.py \
  wms/tests/views/tests_views_scan_pilotage.py \
  docs/repo-reference/04-shared-contracts.md \
  docs/release_checklist.md
git commit -m "feat: add pilotage runtime presets and thresholds"
```

### Task 6: Run The Local Phase 2 Validation Loop

**Files:**
- Modify: `docs/operations.md`
- Modify: `docs/release_checklist.md`
- Optional: `wms/tests/management/tests_management_seed_local_exhaustive_data.py`

**Step 1: Rebuild local derived data**

Run:

```bash
./.venv/bin/python manage.py migrate
./.venv/bin/python manage.py rebuild_workflow_projections
./.venv/bin/python manage.py capture_ops_pilotage_snapshot
./.venv/bin/python manage.py evaluate_ops_escalations
```

Expected:

- migrations apply cleanly
- workflow projections rebuild
- pilotage snapshots are written
- escalations are evaluated and printed

**Step 2: Run the local regression suite**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.test_workflow_projection \
  wms.tests.test_ops_pilotage_snapshots \
  wms.tests.test_ops_escalations \
  wms.tests.management.tests_management_rebuild_workflow_projections \
  wms.tests.management.tests_management_capture_ops_pilotage_snapshot \
  wms.tests.views.tests_views_scan_dashboard \
  wms.tests.views.tests_views_scan_settings \
  wms.tests.views.tests_views_scan_pilotage \
  wms.tests.views.tests_portal_bootstrap_ui \
  wms.tests.views.tests_views_planning \
  wms.tests.planning.tests_outputs \
  wms.tests.planning.tests_communication_actions \
  api.tests.tests_ui_endpoints \
  api.tests.tests_views_extra -v 2
uv run ruff check \
  wms/models_domain/integration.py \
  wms/ops_pilotage_snapshots.py \
  wms/ops_escalations.py \
  wms/workflow_projection.py \
  wms/views_scan_settings.py \
  wms/views_scan_dashboard.py \
  wms/views_scan_pilotage.py \
  wms/views_planning.py \
  wms/planning/exports.py \
  wms/planning/communication_actions.py \
  api/v1/ui_views.py \
  api/v1/views.py
```

Expected:

- PASS on the phase 2 regression slice
- Ruff clean on touched modules

**Step 3: Run the manual local smoke**

Check:

- `/scan/dashboard/`
- `/scan/settings/`
- `/scan/pilotage/`
- `/portal/`
- `/planning/versions/1/`
- `/api/v1/ui/dashboard/`
- `/api/v1/ui/pilotage/`
- `/api/v1/workflow-projections/shipments/`
- `/api/v1/workflow-projections/destinations/`
- `/api/v1/workflow-projections/destination-weeks/`

Expected:

- the daily ops cockpit is navigable
- escalations are visible and drill down correctly
- planning export health is readable
- destination trends and planning capacity remain intact

**Step 4: Update operations and release docs**

Record:

- the local phase 2 operator loop
- rebuild/capture/evaluate commands
- smoke pages and credentials used for local review

**Step 5: Commit**

```bash
git add docs/operations.md docs/release_checklist.md
git commit -m "docs: add local phase 2 pilotage validation loop"
```
