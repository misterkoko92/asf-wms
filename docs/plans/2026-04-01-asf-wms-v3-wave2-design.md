# ASF WMS V3.2 Events And Jobs Design

## Goal

Deliver a structural V3.2 that makes orchestration explicit, shrinks `wms/signals.py` to bridging responsibilities, and gives operational runtime work a first-class home outside management-command wrappers.

## Why V3.2 Exists

V3.1 extracted shared queries and policies, but the production runtime is still hard to reason about because:

- domain side effects are still concentrated in `wms/signals.py`
- many operational concerns are executed through management commands that call module-level helpers directly
- queue processing, snapshot capture, escalation evaluation, artifact checks, and projection rebuilds do not share one runtime model
- durable dispatch already exists in places through `IntegrationEvent`, but it is not presented as an explicit outbox boundary

V3.2 should not add new end-user features. It should make the existing runtime safer to evolve.

## Current Runtime Hotspots

The main orchestration hotspots today are:

- `wms/signals.py`
- `wms/emailing.py`
- `wms/document_scan_queue.py`
- `wms/print_pack_sync.py`
- `wms/workflow_projection.py`
- `wms/ops_pilotage_snapshots.py`
- `wms/ops_escalations.py`
- `wms/management/commands/process_email_queue.py`
- `wms/management/commands/process_document_scan_queue.py`
- `wms/management/commands/process_print_artifact_queue.py`
- `wms/management/commands/rebuild_workflow_projections.py`
- `wms/management/commands/capture_ops_pilotage_snapshot.py`
- `wms/management/commands/evaluate_ops_escalations.py`
- `wms/management/commands/refresh_ops_pilotage.py`

## Scope

V3.2 covers:

- explicit event contracts
- signal-to-event bridging
- extracted event handlers
- a first `wms/jobs/` layer
- durable run visibility for operational jobs
- an explicit outbox boundary built on the primitives already present in the repo

V3.2 does not cover:

- React or Next migration
- translation work
- a new external queue broker
- a distributed event bus
- a rewrite of the planning or portal domains
- major new user-facing features

## Architectural Decisions

### 1. Events Stay In-Process First

V3.2 should introduce `wms/events/` as an explicit in-process layer before considering any remote bus.

The first event system should:

- define stable event names and payload shapes
- expose small publisher helpers
- keep handler registration explicit
- remain synchronous by default unless a handler is intentionally routed through the durable outbox boundary

This keeps the migration incremental and testable.

### 2. Django Signals Become Bridges

Signals should keep only what is truly signal-specific:

- model lifecycle registration
- minimal state capture needed before save
- mapping runtime objects to an explicit event
- dispatching the event to handlers

Heavy branching, notification rendering, sync logic, and projection orchestration should move out of `wms/signals.py`.

### 3. Jobs Become The Runtime API

Operational execution should move into `wms/jobs/`.

Target job modules:

- `wms/jobs/email_queue.py`
- `wms/jobs/document_scan.py`
- `wms/jobs/print_artifacts.py`
- `wms/jobs/workflow_projection.py`
- `wms/jobs/pilotage.py`
- `wms/jobs/runtime_checks.py`

Management commands should become CLI adapters around these modules.

### 4. Use Existing Durable Primitives Before Adding New Infrastructure

`IntegrationEvent` already behaves like a durable queue/outbox for some flows.

V3.2 should formalize that instead of introducing a second asynchronous persistence model too early.

The explicit outbox boundary should therefore:

- wrap `IntegrationEvent` creation and dispatch rules in one place
- normalize event metadata and replay semantics
- be used first for notifications and asynchronous processors already backed by `IntegrationEvent`

If V3.3 later needs a broader outbox model, that can build on this first normalized layer.

### 5. Add Run Visibility With A Dedicated Model

The repo currently exposes the outcome of queue commands through stdout and a few models, but there is no single runtime record of execution attempts.

V3.2 should add a dedicated persisted run model, for example in `wms/models_domain/integration.py`, to track:

- job key
- trigger source
- started and finished timestamps
- status
- result summary
- error summary
- attempt metadata or context payload

That model is intentionally operational, not domain-level.

## Event Taxonomy

The first explicit event catalog should cover the current real side effects:

### Shipment And Tracking Events

- shipment status changed
- shipment delivered notification target reached
- shipment tracking event created
- shipment party snapshot notification needed
- shipment correspondant notification needed

### Order And Portal Events

- order status changed
- association profile created
- association profile contact or user email synchronized

### Recipient And Shipper Sync Events

- shipment recipient organization changed
- destination changed
- default shipper bindings need sync
- destination correspondant recipient support needs refresh

### Projection And Pilotage Events

- shipment workflow projection refresh requested
- pilotage snapshot refresh requested
- pilotage escalation evaluation requested

### Planning Artifact Events

- planning workbook exported
- planning PDF exported
- print artifact sync requested

## Proposed Package Layout

### `wms/events/`

- `__init__.py`
- `types.py`
- `publishers.py`
- `dispatch.py`
- `outbox.py`
- `handlers_notifications.py`
- `handlers_projections.py`
- `handlers_sync.py`

Optional later split if needed:

- `handlers_planning.py`
- `handlers_pilotage.py`

### `wms/jobs/`

- `__init__.py`
- `email_queue.py`
- `document_scan.py`
- `print_artifacts.py`
- `workflow_projection.py`
- `pilotage.py`
- `runtime_checks.py`

## Migration Rules

### Keep Behavior Stable First

V3.2 should not change visible behavior while moving orchestration code.

The first slices should only:

- move logic
- formalize contracts
- preserve current side effects
- preserve current command outputs where practical

### Migrate By Concern, Not By File

The correct sequence is:

1. event contracts
2. notification handlers
3. projection and sync handlers
4. jobs
5. run visibility
6. explicit outbox boundary

This avoids reopening the same modules repeatedly without a target architecture.

### Keep One Exception Explicit

`user_logged_in` session policy in `wms/signals.py` can remain a direct runtime hook in V3.2 if it stays small.

It is not a durable domain event and should not force unnecessary abstraction.

## Success Criteria

V3.2 is structurally successful when:

- `wms/signals.py` is mostly registration and event bridging
- email, document scan, print artifact, pilotage, and workflow projection execution all have modules under `wms/jobs/`
- management commands are thin wrappers over those jobs
- operational job runs are traceable in one persisted model
- asynchronous dispatch through `IntegrationEvent` is wrapped behind an explicit outbox helper layer
- existing living tests still validate the same user-visible behavior

## Main Risks

- creating an event abstraction that is too generic and hides the real business concerns
- moving logic out of signals without preserving transaction timing semantics
- introducing a job layer that is just a second wrapper without reducing coupling
- adding a new outbox model even though `IntegrationEvent` already covers the first durable dispatch use cases

## Delivery Recommendation

Implement V3.2 in this order:

1. event catalog and scaffolding
2. notification handler extraction
3. projection and sync handler extraction
4. jobs layer
5. run visibility
6. explicit outbox normalization

Do not start with outbox persistence first. It will be easier to design once the signal bridge and job boundaries are explicit.
