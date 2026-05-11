# Runtime Events, Jobs, Pilotage, Operations, And Smoke Contracts

Read this file when touching policies, notifications, durable outbox, jobs, pilotage snapshots/escalations, runtime settings, release smoke, RGPD, security dependencies, or operational commands.

---

## Workflow Notification Contract

### Primary runtime sources

- `wms/signals.py`
- `wms/emailing.py`
- `wms/models_domain/integration.py`
- producer modules

### Current contract

- One business event may notify admin groups, association contacts, shipment parties, or volunteers.
- Portal shipper recipient creation that leaves a `ShipmentRecipientOrganization` pending
  validation notifies superusers plus `ACCOUNT_REQUEST_VALIDATION_GROUP_NAME` and links to
  the scan recipient validation detail.
- Portal order admin notifications link staff to `/scan/orders-view/` and the precise
  `/scan/orders/<id>/` dossier rather than portal or Django admin routes.
- Portal order drafts are recovery state only; autosave and clear-draft actions must not
  emit notifications or runtime integration events.
- Operational docs and env vars depend on same routing rules.

### Maintenance rule

- When notification routing changes, update producers, queue behavior, docs, and email target matrices.

---

## Extracted Policies Contract

### Primary runtime sources

- `wms/policies/sla.py`
- `wms/policies/pilotage.py`
- `wms/policies/planning.py`
- `wms/policies/shipment_parties.py`

### Current contract

- SLA, pilotage thresholds, planning load-state rules, and shipment-party labels are centralized.
- Shared thresholds, labels, or classifications belong here first.

### Maintenance rule

- Legacy adapters should consume policies rather than redefining shared rules.

---

## Runtime Event Contract

### Primary runtime sources

- `wms/events/types.py`
- `wms/events/publishers.py`

### Current contract

- `RuntimeEvent` has `event_type`, `scope_type`, `scope_id`, `payload`.
- Explicit event constants include shipment status, tracking event, order status, workflow projection refresh, pilotage refresh, and planning artifact export.

### Maintenance rule

- Define or update event contract before wiring signals/jobs.
- Do not let signals invent ad hoc payload dicts.

---

## Durable Outbox Contract

### Primary runtime sources

- `wms/events/outbox.py`
- `wms/emailing.py`
- `wms/document_scan_queue.py`

### Current contract

- `enqueue_integration_event(...)` is explicit helper for durable `IntegrationEvent` creation.
- Producers own payload construction.
- Outbox owns persisted row creation.

### Maintenance rule

- Move direct queue-backed `IntegrationEvent.objects.create(...)` producers behind outbox when extending durable behavior.
- Do not introduce a second persistence model during this phase.

---

## Operational Job Run Contract

### Primary runtime sources

- `wms/models_domain/integration.py`
- `wms/jobs/runtime_tracking.py`
- `wms/jobs/*`

### Current contract

- `OperationalJobRun` is persisted runtime trace for job wrappers.
- Stable statuses: `running`, `succeeded`, `failed`.
- Job wrappers, not commands, own run persistence.
- Scalar results normalize to `{"result": ...}`.
- Print-artifact job persists bounded `proof_sync_preview`.

### Maintenance rule

- If runtime wrapper is added, decide whether it should persist `OperationalJobRun`.
- Keep commands thin.
- If status vocabulary or summary normalization changes, update model helper, jobs, ops docs, and contract.

---

## Ops Pilotage Snapshot Contract

### Primary runtime sources

- `wms/models_domain/integration.py`
- `wms/ops_pilotage_snapshots.py`
- `wms/management/commands/capture_ops_pilotage_snapshot.py`

### Current contract

- `OpsPilotageSnapshot` is derived daily metric store.
- Unique on `(snapshot_date, scope_type, scope_key, metric_key)`.
- Supported scope types: `global`, `destination`, `flight`, `queue`, `planning_export`.
- Capture command: `python manage.py capture_ops_pilotage_snapshot`.

### Maintenance rule

- Keep table read-only historical signal layer.
- If vocabularies or metric keys change, update helper, command, tests, and contract.

---

## Ops Escalation Contract

### Primary runtime sources

- `wms/models_domain/integration.py`
- `wms/ops_escalations.py`
- `wms/management/commands/evaluate_ops_escalations.py`
- `wms/pilotage_runtime.py`
- `wms/views_scan_settings.py`

### Current contract

- `OpsEscalation` is persistent local anomaly layer.
- Supported categories include SLA, disputes, unclaimed blockages, planning capacity, missing planning PDF, queue backlog, and portal stalled.
- Supported statuses: `open`, `acknowledged`, `resolved`, `suppressed`.
- Evaluation command: `python manage.py evaluate_ops_escalations`.

### Maintenance rule

- If categories, statuses, presets, or thresholds change, update evaluator, settings preview, runtime helpers, command, and contract.

---

## Daily Ops Cockpit Contract

### Primary runtime sources

- `wms/application/pilotage/pilotage_queries.py`
- `wms/scan_pilotage.py`
- `wms/views_scan_pilotage.py`
- `templates/scan/pilotage.html`
- `api/v1/ui_views.py`

### Current contract

- `build_scan_pilotage_payload()` is shared adapter for HTML and UI API.
- Cockpit is read-only.
- Consumes snapshots, escalations, destination trends, and portal backlog.
- UI API exposes summary cards, priority rows, escalation rows, destination trends, planning exports, portal backlog, and threshold context.

### Maintenance rule

- If ordering, payload keys, routing, or planning export semantics change, update shared adapter, HTML, UI API, tests, and contract.

---

## Local Dashboard V2 API Contract

### Primary runtime sources

- `api/v1/ui_views.py`
- `wms/application/scan/dashboard_queries.py`

### Current contract

- Shared dashboard payload is composed in `wms/application/scan/dashboard_queries.py`.
- Workflow blockage categories include creation, order, tracking, closure, queue.
- Claim/release parity exists through UI API.
- SLA alert semantics use `tracking_alert_hours` and shared policies.

### Maintenance rule

- Keep dashboard views/API thin over shared query helper.
- If routing, categories, SLA priority, destination ranking, or vocabulary changes, update dashboard, settings, deep links, tests, and contract.

---

## Operations And Smoke Contract

### Primary docs

- `docs/operations.md`
- `docs/release_checklist.md`
- `docs/security-dependencies.md`
- `docs/policies/rgpd.md`

### Current contract

- Operations docs define post-change verification loops.
- Release checklist is last defense against smoke drift.
- Security dependencies and RGPD policies move with affected code.
- External error tracking checked with `python manage.py check_sentry_runtime --allow-missing`.
- After DSN change, verify one `--send-test` event outside repository.
- Post-migration integrity checked with `python manage.py check_referential_integrity`.
- Monthly maintenance may use `--report-only`.

### Maintenance rule

- If critical journey, queue behavior, deployment-sensitive asset, data integrity, personal data, monitoring, backup, restore, RPO/RTO, or incident response changes, update operations docs and release checklist.

---

## Final Rule

Runtime side effects, jobs, smoke checks, and operational docs must move together.
