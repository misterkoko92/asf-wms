# ASF WMS V3.2 Events And Jobs Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace implicit orchestration with explicit event and job boundaries, while keeping the current legacy Django behavior stable and production-safe.

**Architecture:** Introduce `wms/events/` and `wms/jobs/` as additive layers. Reduce `wms/signals.py` to lifecycle bridging, move side-effect code into event handlers, wrap operational commands in job modules, and formalize durable dispatch on top of the existing `IntegrationEvent` model before considering broader runtime changes.

**Tech Stack:** Django 5, legacy Django views and templates, `IntegrationEvent` queue model, management commands, Ruff, mypy, pyright, `manage.py test`.

---

### Task 1: Create V3.2 runtime scaffolding and runtime map

**Files:**
- Create: `wms/events/__init__.py`
- Create: `wms/jobs/__init__.py`
- Create: `wms/tests/core/tests_v32_runtime_imports.py`
- Modify: `docs/plans/2026-04-01-asf-wms-v3-wave2-design.md`
- Modify: `docs/repo-reference/01-architecture-and-entrypoints.md`

**Step 1: Write the failing test**

Add a minimal import smoke test:

```python
from wms import events, jobs


def test_v32_runtime_packages_import():
    assert events is not None
    assert jobs is not None
```

Suggested file: `wms/tests/core/tests_v32_runtime_imports.py`

**Step 2: Run test to verify it fails**

Run:

`./.venv/bin/python manage.py test wms.tests.core.tests_v32_runtime_imports -v 2`

Expected: FAIL because the new packages do not exist yet.

**Step 3: Write minimal implementation**

- create `wms/events/` and `wms/jobs/`
- document in `docs/repo-reference/01-architecture-and-entrypoints.md` that V3.2 introduces explicit runtime layers below management commands and Django signals

**Step 4: Run test to verify it passes**

Run:

`./.venv/bin/python manage.py test wms.tests.core.tests_v32_runtime_imports -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/events wms/jobs wms/tests/core/tests_v32_runtime_imports.py docs/plans/2026-04-01-asf-wms-v3-wave2-design.md docs/repo-reference/01-architecture-and-entrypoints.md
git commit -m "docs: scaffold v3 wave2 runtime layers"
```

### Task 2: Introduce explicit event types and publishers

**Files:**
- Create: `wms/events/types.py`
- Create: `wms/events/publishers.py`
- Create: `wms/tests/core/tests_event_types.py`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Write the failing test**

Add focused contract tests for the first event primitives:

```python
from wms.events.publishers import build_shipment_status_changed_event
from wms.events.types import EVENT_SHIPMENT_STATUS_CHANGED


def test_build_shipment_status_changed_event_sets_type():
    event = build_shipment_status_changed_event(
        shipment_id=1,
        old_status="planned",
        new_status="shipped",
    )
    assert event.event_type == EVENT_SHIPMENT_STATUS_CHANGED
    assert event.scope_type == "shipment"
    assert event.scope_id == "1"
```

Suggested file: `wms/tests/core/tests_event_types.py`

**Step 2: Run test to verify it fails**

Run:

`./.venv/bin/python manage.py test wms.tests.core.tests_event_types -v 2`

Expected: FAIL because the event contract does not exist yet.

**Step 3: Write minimal implementation**

- add explicit event name constants in `wms/events/types.py`
- add a small immutable event object or equivalent typed payload
- create publisher helpers for at least:
  - shipment status changed
  - tracking event created
  - order status changed
  - workflow projection refresh requested
  - pilotage refresh requested
  - planning artifact exported
- keep the first contract deliberately small and explicit

**Step 4: Run test to verify it passes**

Run:

`./.venv/bin/python manage.py test wms.tests.core.tests_event_types -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/events/types.py wms/events/publishers.py wms/tests/core/tests_event_types.py docs/repo-reference/04-shared-contracts.md
git commit -m "refactor: add explicit v3 event contracts"
```

### Task 3: Extract notification orchestration from signals into event handlers

**Files:**
- Create: `wms/events/handlers_notifications.py`
- Modify: `wms/signals.py`
- Modify: `wms/emailing.py`
- Test: `wms/tests/emailing/tests_signals_extra.py`
- Test: `wms/tests/emailing/tests_order_status_notifications.py`
- Test: `wms/tests/emailing/tests_shipment_party_notifications.py`
- Test: `wms/tests/emailing/tests_notifications_queue.py`

**Step 1: Write the failing test**

Add a focused regression test proving the signal module delegates to explicit handlers rather than containing the notification orchestration itself.

Recommended shape:

- patch the new handler entry point
- trigger the existing save path
- assert the handler was called once with the expected event contract

Suggested file: extend `wms/tests/emailing/tests_signals_extra.py`

**Step 2: Run test to verify it fails**

Run:

`./.venv/bin/python manage.py test wms.tests.emailing.tests_signals_extra -v 2`

Expected: FAIL before the signal bridge exists.

**Step 3: Write minimal implementation**

- move shipment notification rendering and dispatch orchestration out of `wms/signals.py`
- keep lifecycle capture in `wms/signals.py`, but convert it to:
  - detect change
  - build explicit event
  - dispatch to notification handlers
- keep transaction timing equivalent to current behavior
- do not change recipient resolution or queue semantics yet

**Step 4: Run test to verify it passes**

Run:

- `./.venv/bin/python manage.py test wms.tests.emailing.tests_signals_extra -v 2`
- `./.venv/bin/python manage.py test wms.tests.emailing.tests_order_status_notifications wms.tests.emailing.tests_shipment_party_notifications wms.tests.emailing.tests_notifications_queue -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/events/handlers_notifications.py wms/signals.py wms/emailing.py wms/tests/emailing/tests_signals_extra.py wms/tests/emailing/tests_order_status_notifications.py wms/tests/emailing/tests_shipment_party_notifications.py wms/tests/emailing/tests_notifications_queue.py
git commit -m "refactor: bridge notification signals through event handlers"
```

### Task 4: Extract projection and sync handlers from signals

**Files:**
- Create: `wms/events/handlers_projections.py`
- Create: `wms/events/handlers_sync.py`
- Modify: `wms/signals.py`
- Modify: `wms/workflow_projection.py`
- Modify: `wms/portal_recipient_sync.py`
- Modify: `wms/default_shipper_bindings.py`
- Test: `wms/tests/test_workflow_projection.py`
- Test: `wms/tests/emailing/tests_signals_extra.py`
- Test: `wms/tests/views/tests_views_scan_dashboard.py`

**Step 1: Write the failing test**

Add regression tests showing that:

- shipment save and tracking event save now dispatch through projection handlers
- recipient and destination synchronization paths dispatch through sync handlers

Recommended first target:

- patch a handler function in `wms.events.handlers_projections`
- save a shipment or tracking event used by the existing tests
- assert the handler was called

**Step 2: Run test to verify it fails**

Run:

`./.venv/bin/python manage.py test wms.tests.test_workflow_projection wms.tests.emailing.tests_signals_extra -v 2`

Expected: FAIL before extraction.

**Step 3: Write minimal implementation**

- move workflow projection refresh scheduling out of `wms/signals.py`
- move default shipper link synchronization and destination correspondant support refresh into explicit sync handlers
- keep `user_logged_in` session policy direct if it remains small
- do not change projection semantics or sync policy decisions in this task

**Step 4: Run test to verify it passes**

Run:

- `./.venv/bin/python manage.py test wms.tests.test_workflow_projection -v 2`
- `./.venv/bin/python manage.py test wms.tests.emailing.tests_signals_extra wms.tests.views.tests_views_scan_dashboard -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/events/handlers_projections.py wms/events/handlers_sync.py wms/signals.py wms/workflow_projection.py wms/portal_recipient_sync.py wms/default_shipper_bindings.py wms/tests/test_workflow_projection.py wms/tests/emailing/tests_signals_extra.py wms/tests/views/tests_views_scan_dashboard.py
git commit -m "refactor: move projection and sync side effects behind event handlers"
```

### Task 5: Introduce `wms/jobs/` and thin management commands

**Files:**
- Create: `wms/jobs/email_queue.py`
- Create: `wms/jobs/document_scan.py`
- Create: `wms/jobs/print_artifacts.py`
- Create: `wms/jobs/workflow_projection.py`
- Create: `wms/jobs/pilotage.py`
- Create: `wms/jobs/runtime_checks.py`
- Modify: `wms/management/commands/process_email_queue.py`
- Modify: `wms/management/commands/process_document_scan_queue.py`
- Modify: `wms/management/commands/process_print_artifact_queue.py`
- Modify: `wms/management/commands/rebuild_workflow_projections.py`
- Modify: `wms/management/commands/capture_ops_pilotage_snapshot.py`
- Modify: `wms/management/commands/evaluate_ops_escalations.py`
- Modify: `wms/management/commands/refresh_ops_pilotage.py`
- Modify: `wms/management/commands/check_document_scan_runtime.py`
- Modify: `wms/management/commands/check_planning_pdf_runtime.py`
- Test: `wms/tests/management/tests_management_rebuild_workflow_projections.py`
- Test: `wms/tests/management/tests_management_capture_ops_pilotage_snapshot.py`
- Test: `wms/tests/management/tests_management_evaluate_ops_escalations.py`
- Test: `wms/tests/management/tests_management_refresh_ops_pilotage.py`
- Test: `wms/tests/management/tests_management_check_document_scan_runtime.py`
- Test: `wms/tests/management/tests_management_check_planning_pdf_runtime.py`
- Test: `wms/tests/emailing/tests_notifications_queue.py`
- Test: `wms/tests/security/tests_document_scan_queue.py`
- Test: `wms/tests/print/tests_print_pack_sync.py`

**Step 1: Write the failing test**

Add narrow tests proving that commands delegate to job modules instead of calling runtime helpers directly.

Recommended pattern:

- patch `wms.jobs.email_queue.run_email_queue_job`
- call the command
- assert the job wrapper was called once

Suggested files:

- extend `wms/tests/management/tests_management_refresh_ops_pilotage.py`
- add `wms/tests/core/tests_job_imports.py` if useful for smoke coverage

**Step 2: Run test to verify it fails**

Run:

`./.venv/bin/python manage.py test wms.tests.management.tests_management_refresh_ops_pilotage wms.tests.management.tests_management_rebuild_workflow_projections -v 2`

Expected: FAIL before command wrappers are switched.

**Step 3: Write minimal implementation**

- create job wrappers that own parameter normalization and execution
- let management commands become CLI-only adapters
- keep the existing return payloads stable so current management tests stay valid
- use the jobs layer for:
  - email queue processing
  - document scan processing
  - print artifact queue processing
  - workflow projection rebuild
  - pilotage snapshot capture
  - ops escalation evaluation
  - composite pilotage refresh
  - runtime checks where appropriate

**Step 4: Run test to verify it passes**

Run:

- `./.venv/bin/python manage.py test wms.tests.management.tests_management_rebuild_workflow_projections wms.tests.management.tests_management_capture_ops_pilotage_snapshot wms.tests.management.tests_management_evaluate_ops_escalations wms.tests.management.tests_management_refresh_ops_pilotage -v 2`
- `./.venv/bin/python manage.py test wms.tests.management.tests_management_check_document_scan_runtime wms.tests.management.tests_management_check_planning_pdf_runtime -v 2`
- `./.venv/bin/python manage.py test wms.tests.emailing.tests_notifications_queue wms.tests.security.tests_document_scan_queue wms.tests.print.tests_print_pack_sync -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/jobs wms/management/commands/process_email_queue.py wms/management/commands/process_document_scan_queue.py wms/management/commands/process_print_artifact_queue.py wms/management/commands/rebuild_workflow_projections.py wms/management/commands/capture_ops_pilotage_snapshot.py wms/management/commands/evaluate_ops_escalations.py wms/management/commands/refresh_ops_pilotage.py wms/management/commands/check_document_scan_runtime.py wms/management/commands/check_planning_pdf_runtime.py wms/tests/management wms/tests/emailing/tests_notifications_queue.py wms/tests/security/tests_document_scan_queue.py wms/tests/print/tests_print_pack_sync.py
git commit -m "refactor: add explicit jobs layer for operational runtime"
```

### Task 6: Add persisted job-run visibility

**Files:**
- Modify: `wms/models_domain/integration.py`
- Create: migration for the new job-run model
- Create: `wms/jobs/runtime_tracking.py`
- Modify: `wms/jobs/email_queue.py`
- Modify: `wms/jobs/document_scan.py`
- Modify: `wms/jobs/print_artifacts.py`
- Modify: `wms/jobs/workflow_projection.py`
- Modify: `wms/jobs/pilotage.py`
- Create: `wms/tests/test_job_runs.py`
- Modify: `wms/tests/management/tests_management_refresh_ops_pilotage.py`
- Modify: `docs/operations.md`
- Modify: `docs/release_checklist.md`

**Step 1: Write the failing test**

Add tests proving that running a job persists one runtime row with a stable summary.

Example:

```python
from wms.jobs.email_queue import run_email_queue_job
from wms.models import OperationalJobRun


def test_run_email_queue_job_persists_job_run(db):
    run_email_queue_job(limit=1)
    assert OperationalJobRun.objects.filter(job_key="email_queue").exists()
```

Suggested file: `wms/tests/test_job_runs.py`

**Step 2: Run test to verify it fails**

Run:

`./.venv/bin/python manage.py test wms.tests.test_job_runs -v 2`

Expected: FAIL because the model and instrumentation do not exist yet.

**Step 3: Write minimal implementation**

- add a dedicated persisted job-run model
- record started and finished timestamps, status, trigger source, and a compact JSON summary
- instrument job wrappers, not management commands directly
- keep job tracking generic enough for all current operational jobs, but do not over-generalize into a scheduler framework

**Step 4: Run test to verify it passes**

Run:

- `./.venv/bin/python manage.py test wms.tests.test_job_runs -v 2`
- `./.venv/bin/python manage.py test wms.tests.management.tests_management_refresh_ops_pilotage -v 2`
- `./.venv/bin/python manage.py makemigrations --check --dry-run`

Expected: PASS and no missing migrations.

**Step 5: Commit**

```bash
git add wms/models_domain/integration.py wms/migrations wms/jobs/runtime_tracking.py wms/jobs/email_queue.py wms/jobs/document_scan.py wms/jobs/print_artifacts.py wms/jobs/workflow_projection.py wms/jobs/pilotage.py wms/tests/test_job_runs.py wms/tests/management/tests_management_refresh_ops_pilotage.py docs/operations.md docs/release_checklist.md
git commit -m "feat: add job run visibility for v3 runtime"
```

### Task 7: Normalize the durable outbox boundary on top of `IntegrationEvent`

**Files:**
- Create: `wms/events/outbox.py`
- Modify: `wms/emailing.py`
- Modify: `wms/document_scan_queue.py`
- Modify: `wms/print_pack_sync.py`
- Modify: `wms/events/handlers_notifications.py`
- Modify: `wms/jobs/email_queue.py`
- Modify: `wms/jobs/document_scan.py`
- Modify: `wms/jobs/print_artifacts.py`
- Test: `wms/tests/emailing/tests_notifications_queue.py`
- Test: `wms/tests/security/tests_document_scan_queue.py`
- Test: `wms/tests/print/tests_print_pack_sync.py`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Write the failing test**

Add regression tests proving queue-backed dispatch now uses one explicit outbox helper rather than each subsystem writing `IntegrationEvent` rows independently.

Recommended pattern:

- patch `wms.events.outbox.enqueue_integration_event`
- trigger the current email or document scan enqueue path
- assert the outbox helper was used

**Step 2: Run test to verify it fails**

Run:

`./.venv/bin/python manage.py test wms.tests.emailing.tests_notifications_queue wms.tests.security.tests_document_scan_queue -v 2`

Expected: FAIL before the helper layer exists.

**Step 3: Write minimal implementation**

- centralize durable dispatch helpers in `wms/events/outbox.py`
- wrap `IntegrationEvent` creation there
- keep current queue semantics and statuses stable
- route email, document scan, and print artifact durable dispatch through the helper
- do not yet broaden the outbox to unrelated synchronous flows

**Step 4: Run test to verify it passes**

Run:

- `./.venv/bin/python manage.py test wms.tests.emailing.tests_notifications_queue wms.tests.security.tests_document_scan_queue wms.tests.print.tests_print_pack_sync -v 2`
- `./.venv/bin/python manage.py test wms.tests.management.tests_management_check_document_scan_runtime wms.tests.management.tests_management_check_planning_pdf_runtime -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/events/outbox.py wms/emailing.py wms/document_scan_queue.py wms/print_pack_sync.py wms/events/handlers_notifications.py wms/jobs/email_queue.py wms/jobs/document_scan.py wms/jobs/print_artifacts.py wms/tests/emailing/tests_notifications_queue.py wms/tests/security/tests_document_scan_queue.py wms/tests/print/tests_print_pack_sync.py docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md
git commit -m "refactor: normalize durable dispatch through v3 outbox helpers"
```

### Task 8: Consolidate repo-reference and run the V3.2 release slice

**Files:**
- Modify: `docs/repo-reference/01-architecture-and-entrypoints.md`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/03-impact-map.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Modify: `docs/operations.md`
- Modify: `docs/release_checklist.md`

**Step 1: Re-read propagation and contracts**

Re-check:

- `docs/repo-reference/03-impact-map.md`
- `docs/repo-reference/04-shared-contracts.md`

Document:

- new runtime layer entry points
- signal bridge rules
- job boundaries
- outbox ownership
- reference tests for queues, commands, and event bridges

**Step 2: Run the consolidated verification slice**

Run:

```bash
make typecheck
./.venv/bin/python manage.py test \
  wms.tests.core.tests_v32_runtime_imports \
  wms.tests.core.tests_event_types \
  wms.tests.emailing.tests_signals_extra \
  wms.tests.emailing.tests_order_status_notifications \
  wms.tests.emailing.tests_shipment_party_notifications \
  wms.tests.emailing.tests_notifications_queue \
  wms.tests.security.tests_document_scan_queue \
  wms.tests.print.tests_print_pack_sync \
  wms.tests.test_workflow_projection \
  wms.tests.test_ops_pilotage_snapshots \
  wms.tests.test_ops_escalations \
  wms.tests.test_job_runs \
  wms.tests.management.tests_management_rebuild_workflow_projections \
  wms.tests.management.tests_management_capture_ops_pilotage_snapshot \
  wms.tests.management.tests_management_evaluate_ops_escalations \
  wms.tests.management.tests_management_refresh_ops_pilotage \
  wms.tests.management.tests_management_check_document_scan_runtime \
  wms.tests.management.tests_management_check_planning_pdf_runtime -v 2
```

Expected: PASS

**Step 3: Commit**

```bash
git add docs/repo-reference/01-architecture-and-entrypoints.md docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/03-impact-map.md docs/repo-reference/04-shared-contracts.md docs/operations.md docs/release_checklist.md
git commit -m "docs: finalize v3 wave2 runtime reference"
```

## Notes For Execution

- Preserve current transaction semantics when moving signal logic.
- Prefer additive extraction first, deletion second.
- Do not introduce a distributed event bus or external worker stack in this wave.
- Keep `user_logged_in` session policy local unless it grows materially.
- If the outbox helper reveals that `IntegrationEvent` is insufficient for one flow, record the gap but do not fork into a second persistence model mid-wave without a targeted design note.
