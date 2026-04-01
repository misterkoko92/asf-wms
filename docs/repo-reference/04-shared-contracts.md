# Shared Contracts

This file lists the contracts most likely to be forgotten because they are reused across multiple surfaces.

## 1. View And Model Facade Contracts

### `wms/views.py`

Role:

- re-export layer for routing and many tests

Maintenance rule:

- if a scan/portal/public/volunteer view is moved or renamed, check `wms/views.py`
- do not assume the business logic lives there

### `wms/models.py`

Role:

- compatibility import facade above `wms/models_domain/*`

Maintenance rule:

- if a model-level contract changes, verify both the extracted domain module and any compatibility imports
- for normal runtime imports, prefer the facade unless the local task explicitly targets the extracted source module

## 2. Shared UI Contract

Primary runtime sources:

- `wms/templatetags/wms_ui.py`
- `templates/wms/components/`
- `templates/scan/ui_lab.html`
- `wms/static/scan/scan-bootstrap.css`
- `wms/static/portal/portal-bootstrap.css`
- `wms/static/wms/admin-bootstrap.css`

Primary governance docs:

- `docs/plans/2026-03-22-ui-library-governance-design.md`
- `docs/plans/2026-03-25-core-stable-usage-rules.md`

Stable primitives currently documented:

- `ui_button`
- `ui_field`
- `ui_file_input`
- `ui_alert`
- `ui_status_badge`
- `ui_switch`
- `ui-comp-card`
- `ui-comp-panel`
- `ui-comp-actions`

Surfaces that already reuse these contracts:

- `templates/scan/`
- `templates/portal/`
- `templates/benevole/`
- custom admin templates
- `templates/scan/ui_lab.html`

Maintenance rule:

- if a primitive changes semantics, update the UI Lab and bootstrap regression tests
- if a pattern is still local, do not prematurely promote it into a shared primitive

Reference tests:

- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`

### V3 Extracted Policies Contract

Primary runtime sources:

- `wms/policies/sla.py`
- `wms/policies/pilotage.py`
- `wms/policies/planning.py`
- `wms/policies/shipment_parties.py`

Current V3.1 contract:

- `wms/policies/sla.py` owns the shared SLA-delay freshness and alert classification reused by dashboard and API compositions
- `wms/policies/pilotage.py` owns planning-threshold normalization and is the single place that enforces `critical >= tension`
- `wms/policies/planning.py` owns planning flight `load_state` ordering, labels, and threshold-based classification
- `wms/policies/shipment_parties.py` owns the canonical default recipient shipper display name derived from shipment-party setup constants

Maintenance rule:

- if a business-rule threshold, label, or classification is shared across multiple screens or adapters, extract or update it here first instead of reintroducing it directly into views, helpers, or API adapters
- keep legacy adapters thin: `wms/scan_dashboard_sla.py`, `wms/planning/stats.py`, `wms/runtime_settings.py`, `wms/pilotage_runtime.py`, and `wms/default_shipper_bindings.py` should consume this layer rather than redefining the same rule locally

Reference tests:

- `wms/tests/core/tests_policies.py`
- `wms/tests/core/tests_runtime_settings.py`

### Local Dashboard V2 API Contract

Primary runtime sources:

- `api/v1/ui_views.py` via `GET /api/v1/ui/dashboard/`
- `wms/application/scan/dashboard_queries.py`

Phase 1 local contract:

- `wms/application/scan/dashboard_queries.py` is the shared composition layer for both the legacy dashboard HTML and `GET /api/v1/ui/dashboard/`
- shared dashboard payload keys now include `kpis` and `timeline` in addition to the existing card and row contracts
- `pending_actions[]` items expose `type`, `reference`, `label`, `priority`, `owner`, `url`, `age_hours`
- allowed `owner` values are `magasin`, `qualite`, `admin`, `portal`
- allowed `priority` values are `high`, `medium`, `low`
- `workflow_blockage_summary_cards[]` exposes `Blocages ouverts`, `Sans prise en charge`, `Pris en charge`
- `workflow_blockage_rows[]` exposes `blockage_key`, `category`, `category_label`, `label`, `reference`, `owner`, `priority`, `started_at`, `age_hours`, `url`, `is_claimed`, `claimed_by`, `claimed_at`, `claim_state`, `claim_state_label`
- workflow blockage categories are stable during local V2: `creation_expedition`, `commande`, `suivi`, `cloture`, `queue`
- `destination_risk_summary_cards[]` exposes `Destinations critiques`, `Destinations avec litiges`, `Plus ancien dossier ouvert`
- `destination_risk_rows[]` exposes `destination_id`, `destination_label`, `delayed_shipment_count`, `critical_shipment_count`, `open_dispute_count`, `top_blockage_category`, `oldest_open_segment_age_hours`, `url`, `cta_label`
- destination-risk rows open `scan/shipments_tracking` with the `destination` query parameter preserved end-to-end
- `document_scan_cards[]` mirrors the queue-card shape already used by `technical_cards[]`
- `sla_alert_summary_cards[]` exposes the short summary `Nouveaux retards`, `Retards persistants`, `Retards critiques`
- `sla_alert_rows[]` exposes `reference`, `label`, `segment`, `owner`, `severity`, `freshness`, `delay_hours`, `age_hours`, `url`
- the legacy dashboard surface and the UI API mirror the same open-SLA classification derived from `tracking_alert_hours`
- local claim/release parity also exists through `POST /api/v1/ui/dashboard/workflow-blockages/claims/` with `action=claim|release` and `blockage_key`
- the local runtime calibration loop also depends on `scan/settings` preset `incident_sla` and its preview counters for new/persistent/critical delays

Maintenance rule:

- if dashboard action routing, workflow blockage categorization, SLA prioritization, destination-risk ranking, or ownership vocabulary changes, update the legacy dashboard, `scan/settings` if relevant, the shipment-tracking deep link, the UI API tests, and the repo-reference in the same work
- `wms/views_scan_dashboard.py` and `api/v1/ui_views.py` should remain thin adapters over `wms/application/scan/dashboard_queries.py`; do not duplicate the full dashboard composition in both surfaces again during V3.1
- GET rendering in both adapters must rely only on the public shared payload; query-internal fields such as `shipments_scope`, `shipments_with_tracking`, `workflow_blockage_base_rows`, `status_map`, and raw snapshot objects stay private to the query layer or POST-only adapter needs
- shared SLA alert semantics should continue to resolve through `wms/policies/sla.py`, with `wms/scan_dashboard_sla.py` acting as the data adapter rather than the rule owner
- keep this contract intentionally short and stable during the local V2 phase; add new keys only when both HTML and API consumers need them

Reference tests:

- `api/tests/tests_ui_endpoints.py`
- `wms/tests/views/tests_views_scan_dashboard.py`
- `wms/tests/views/tests_views_scan_settings.py`

### Portal Dashboard Cockpit Contract

Primary runtime sources:

- `wms/application/portal/dashboard_queries.py`
- `wms/views_portal_orders.py`
- `wms/portal_dashboard_helpers.py`
- `templates/portal/dashboard.html`
- `api/v1/ui_views.py` via `GET /api/v1/ui/portal/dashboard/`

Current contract:

- `wms/application/portal/dashboard_queries.py` is the shared composition layer for the legacy portal dashboard and `GET /api/v1/ui/portal/dashboard/`
- `dashboard_kpis` exposes `orders_total`, `orders_pending_review`, `orders_changes_requested`, `orders_with_shipment`, `orders_shipments_in_progress`
- portal dashboard rows expose `next_step_label` and `next_step_tone` in both HTML context and UI API payloads
- the HTML table and the UI API must stay aligned on the meaning of "next step" for pending review, correction, preparation, and tracked shipment states

Maintenance rule:

- if the association-facing dossier guidance changes, update the helper logic, the portal template, and the portal UI API in the same work
- keep `wms/views_portal_orders.py` and `api/v1/ui_views.py` thin over `wms/application/portal/dashboard_queries.py`; do not let the two surfaces drift back to separate query composition during V3.1
- keep KPI naming stable while phase 1 stays local, so seed data and operator feedback can be compared across runs

Reference tests:

- `wms/tests/views/tests_portal_bootstrap_ui.py`
- `wms/tests/views/tests_views_portal.py`
- `api/tests/tests_ui_endpoints.py`

### Local Shipment Dispute Center Contract

Primary runtime sources:

- `wms/models_domain/shipment.py`
- `wms/shipment_tracking_handlers.py`
- `wms/views_scan_shipments.py`
- `wms/views_scan_shipments_support.py`
- `wms/shipment_view_helpers.py`
- `templates/scan/shipment_tracking.html`
- `templates/scan/shipments_tracking.html`

Current local contract:

- `Shipment` keeps the structured dispute state directly via `dispute_reason`, `dispute_owner`, `dispute_status`, `dispute_due_at`, `dispute_opened_at`, `dispute_resolved_at`, and `dispute_resolution_notes`
- `Shipment.is_disputed` remains the active lock signal for the tracking workflow
- opening a dispute now requires a valid reason and stores owner, active status, and optional due date
- resolving a dispute requires `dispute_resolution_notes` and keeps the last structured dispute visible on the detail screen
- `scan/shipment_tracking` is the edit surface for dispute intake, update, and resolution
- `scan/shipments_tracking` is the prioritization surface and must keep `dispute=open|overdue|unassigned` filters aligned with the row metadata

Maintenance rule:

- if dispute vocabularies or required fields change, update the handler validation, the tracking detail template, the list filters, and the dispute tests in the same work
- keep the local phase explicit: this is a shipment-level dispute contract, not yet a general case-management model

Reference tests:

- `wms/tests/views/tests_views_tracking_dispute.py`
- `wms/tests/views/tests_views_scan_shipments.py`

### Shipment Workflow Projection Contract

Primary runtime sources:

- `wms/models_domain/integration.py`
- `wms/workflow_projection.py`
- `wms/signals.py`
- `wms/management/commands/rebuild_workflow_projections.py`
- `api/v1/views.py` via `GET /api/v1/workflow-projections/shipments/`

Current local contract:

- `ShipmentWorkflowProjection` is a derived read model with one row per shipment dossier
- the projection is recomputed from `Shipment`, `ShipmentTrackingEvent`, structured dispute fields, and `closed_at`
- timeline markers are stable in this local phase: `shipment_created_at`, `planned_at`, `boarding_ok_at`, `received_correspondent_at`, `delivered_at`, `closed_at`
- current-state markers are stable in this local phase: `current_segment`, `segment_started_at`, `segment_age_hours`, `is_closed`
- lead-time fields are stable in this local phase: `lead_hours_planned_to_boarding`, `lead_hours_boarding_to_correspondent`, `lead_hours_correspondent_to_delivery`, `lead_hours_delivery_to_close`, `lead_hours_total_to_delivery`
- dispute fields are stable in this local phase: `has_open_dispute`, `dispute_reason`, `dispute_owner`, `dispute_opened_at`, `dispute_resolved_at`, `dispute_resolution_hours`
- delay fields are stable in this local phase: `delay_state`, `current_delay_hours`, `active_blockage_category`, `projected_at`
- supported current segments are `creation_expedition`, `planned_to_boarding`, `boarding_to_correspondent`, `correspondent_to_delivery`, `delivery_to_close`, `closed`
- supported delay states are `on_time`, `new`, `persistent`, `critical`
- supported API filters in this local phase are `destination_id`, `shipment_status`, `current_segment`, `delay_state`, `has_open_dispute`, `active_blockage_category`, `is_closed`, `projected_since`
- local refresh happens on shipment save and tracking-event creation, and the full rebuild path is `python manage.py rebuild_workflow_projections`

Maintenance rule:

- if shipment workflow timing, segment vocabulary, dispute projection, or delay classification changes, update the read-model helper, the API endpoint, the rebuild command, and the repo-reference in the same work
- keep this phase shipment-centric; do not mix order-only or queue-only blockers into this contract before the aggregate wave is explicitly opened

Reference tests:

- `wms/tests/test_workflow_projection.py`
- `wms/tests/management/tests_management_rebuild_workflow_projections.py`
- `api/tests/tests_views_extra.py`

### Ops Pilotage Snapshot Contract

Primary runtime sources:

- `wms/models_domain/integration.py`
- `wms/ops_pilotage_snapshots.py`
- `wms/management/commands/capture_ops_pilotage_snapshot.py`

Current local contract:

- `OpsPilotageSnapshot` is a derived daily metric store used for transverse pilotage only
- one row is unique on `(snapshot_date, scope_type, scope_key, metric_key)`
- supported `scope_type` values in this local phase are `global`, `destination`, `flight`, `queue`, `planning_export`
- `scope_key` stays explicit and stable per scope in this local phase:
  - `global` uses `all`
  - `destination` uses the destination id when available
  - `flight` uses `<planning_version_id>:<flight_snapshot_id>`
  - `queue` uses the producer source such as `wms.document_scan`
  - `planning_export` uses the planning version id
- metric capture remains rebuildable and local-first through `python manage.py capture_ops_pilotage_snapshot`
- snapshot rows must be derived from existing read models or artifacts, not from dashboard-only formatting

Maintenance rule:

- if pilotage scope vocabularies, daily metric keys, or capture semantics change, update the helper, the command, the local tests, and this repo-reference section in the same work
- keep the phase intentionally read-only: this table is a historical signal layer, not a workflow queue

Reference tests:

- `wms/tests/test_ops_pilotage_snapshots.py`
- `wms/tests/management/tests_management_capture_ops_pilotage_snapshot.py`

### Ops Escalation Contract

Primary runtime sources:

- `wms/models_domain/integration.py`
- `wms/ops_escalations.py`
- `wms/management/commands/evaluate_ops_escalations.py`
- `wms/pilotage_runtime.py`
- `wms/views_scan_settings.py`
- `templates/scan/settings.html`

Current local contract:

- `OpsEscalation` is the persistent local anomaly layer above workflow snapshots and current operational state
- supported categories in this local phase are `sla_persistent`, `dispute_unassigned`, `workflow_blockage_unclaimed`, `planning_capacity_overload`, `planning_pdf_missing`, `queue_backlog`, `portal_stalled`
- supported statuses in this local phase are `open`, `acknowledged`, `resolved`, `suppressed`
- `escalation_key` must stay stable and unique across evaluation runs
- the evaluation entry point is `python manage.py evaluate_ops_escalations`
- local calibration happens in `scan/settings` through:
  - `pilotage_dispute_unassigned_hours`
  - `pilotage_workflow_blockage_unclaimed_hours`
  - `pilotage_queue_backlog_threshold`
  - `pilotage_planning_tension_pct`
  - `pilotage_planning_critical_pct`
- preset vocabulary for this phase is `standard`, `incident_email_queue`, `incident_sla`, `pilotage_tendu`, plus implicit `Personnalise` when saved values no longer match a preset exactly
- the settings page always exposes a lightweight `Escalades pilotage` preview for the current thresholds
- the settings page and cockpit surfaces expose `Seuils actifs` with:
  - active preset label
  - visible threshold rows
  - projected impact counters for escalations and planning flight load states

Maintenance rule:

- if escalation categories, statuses, preset vocabulary, or threshold semantics change, update the evaluator, the settings preview, `wms/pilotage_runtime.py`, the command, and this repo-reference section in the same work
- keep this phase local and operator-facing: escalations are a pilotage layer, not customer-visible workflow statuses

Reference tests:

- `wms/tests/test_ops_escalations.py`
- `wms/tests/views/tests_views_scan_settings.py`

### Daily Ops Cockpit Contract

Primary runtime sources:

- `wms/application/pilotage/pilotage_queries.py`
- `wms/scan_pilotage.py`
- `wms/views_scan_pilotage.py`
- `templates/scan/pilotage.html`
- `api/v1/ui_views.py` via `GET /api/v1/ui/pilotage/`

Current local contract:

- `build_scan_pilotage_payload()` from `wms/application/pilotage/pilotage_queries.py` is the shared adapter for both the legacy HTML cockpit and the UI API mirror
- the cockpit is intentionally read-only in this local phase and consumes:
  - the latest `OpsPilotageSnapshot` capture for summary cards and planning export health
  - active `OpsEscalation` rows for `priority_rows[]` and `escalation_rows[]`
  - destination trend rows from the existing destination-risk aggregate
  - live portal backlog rows from pending or changes-requested orders without a shipment
- `GET /api/v1/ui/pilotage/` exposes at least `summary_cards`, `priority_rows`, `escalation_rows`, `destination_trend_rows`, `planning_export_rows`, `portal_backlog_rows`, `pilotage_threshold_context`
- `surface_links` keeps the stable cross-surface navigation targets toward `scan/dashboard`, `portal/dashboard`, and `planning/`
- planning export rows remain snapshot-driven in this phase; do not add cockpit-only recomputation of workbook or PDF state

Maintenance rule:

- if pilotage section ordering, payload keys, escalation-to-CTA routing, or planning-export health semantics change, update the shared adapter, the HTML cockpit, the UI API mirror, and this repo-reference section in the same work
- `wms/scan_pilotage.py` is only a compatibility wrapper during V3.1; new pilotage query composition belongs under `wms/application/pilotage/`
- keep this surface orchestration-only: it should link operators back to the underlying working screens instead of introducing a second workflow engine

Reference tests:

- `wms/tests/views/tests_views_scan_pilotage.py`
- `api/tests/tests_ui_endpoints.py`

### Destination Workflow Aggregate Contract

Primary runtime sources:

- `wms/workflow_projection.py`
- `wms/scan_dashboard_destination_risk.py`
- `wms/views_scan_dashboard.py`
- `templates/scan/dashboard.html`
- `api/v1/ui_views.py` via `GET /api/v1/ui/dashboard/`
- `api/v1/views.py` via `GET /api/v1/workflow-projections/destinations/`
- `api/v1/urls.py`

Current local contract:

- one row represents one destination aggregated from `ShipmentWorkflowProjection`
- supported fields in this local phase are `destination_id`, `destination_label`, `shipment_count`, `open_shipment_count`, `closed_shipment_count`, `open_dispute_count`, `delayed_shipment_count`, `critical_shipment_count`, `creation_blockage_count`, `tracking_blockage_count`, `closure_blockage_count`, `avg_total_to_delivery_hours`, `avg_delivery_to_close_hours`, `oldest_open_segment_age_hours`, `top_delay_state`, `top_blockage_category`, `projected_at_max`
- filters are applied on shipment projection rows before destination grouping
- supported filters in this local phase mirror the shipment projection read model where relevant: `delay_state`, `has_open_dispute`, `current_segment`, `active_blockage_category`, `is_closed`, `projected_since`, `destination_id`
- default ordering is operational and stable in this local phase: critical count desc, open dispute count desc, oldest open segment age desc, destination label asc
- `top_delay_state` and `top_blockage_category` are computed on open rows first and break count ties by severity
- the legacy dashboard and `GET /api/v1/ui/dashboard/` consume the same aggregate through the `Destinations à risque` block
- dashboard consumer rows are intentionally limited to the top 5 destinations and keep a CTA toward `scan/shipments_tracking?destination=<id>`
- dashboard consumer rows are enriched from the destination-week aggregate with `current_week_label`, `current_week_score`, `previous_week_label`, `previous_week_score`, `trend_delta`, `trend_direction`, `trend_label`
- the compact weekly score used in the dashboard and UI API mirror is explicit in this local phase: `delayed_shipment_count + open_dispute_count + critical_shipment_count`
- week labels follow the destination-week aggregate notation `YYYY-Www`, and missing current/previous buckets fall back to score `0`

Maintenance rule:

- if destination-level pilotage fields, ranking rules, or dashboard row formatting change, update the aggregation helper, the dashboard adapter, both API surfaces, and the repo-reference in the same work
- keep the aggregate read-only in this local phase; do not add independent dashboard-side computation that drifts from `ShipmentWorkflowProjection`

Reference tests:

- `api/tests/tests_views_extra.py`
- `api/tests/tests_ui_endpoints.py`
- `wms/tests/views/tests_views_scan_dashboard.py`

### Destination Week Workflow Aggregate Contract

Primary runtime sources:

- `wms/workflow_projection.py`
- `api/v1/views.py` via `GET /api/v1/workflow-projections/destination-weeks/`
- `api/v1/urls.py`

Current local contract:

- one row represents one `(destination, ISO week)` bucket aggregated from `ShipmentWorkflowProjection`
- the bucket anchor is `planned_at`
- rows with empty `planned_at` are excluded in this local phase
- supported fields in this local phase are `bucket_key`, `iso_year`, `iso_week`, `bucket_label`, `bucket_start`, `bucket_end`, `destination_id`, `destination_label`, `shipment_count`, `open_shipment_count`, `open_dispute_count`, `delayed_shipment_count`, `critical_shipment_count`, `oldest_open_segment_age_hours`, `top_blockage_category`, `projected_at_max`
- filters are applied on shipment projection rows before `(destination, ISO week)` grouping
- supported filters in this local phase are `destination_id`, `shipment_status`, `current_segment`, `delay_state`, `has_open_dispute`, `active_blockage_category`, `is_closed`, `projected_since`, `iso_year`, `iso_week`
- default ordering is operational and stable in this local phase: most recent ISO week first, then critical count desc, open dispute count desc, oldest open segment age desc, destination label asc
- `top_blockage_category` is computed on open rows first and breaks count ties by severity

Maintenance rule:

- if the period anchor, row shape, or bucket sorting changes, update the aggregation helper, the API endpoint, the API tests, and the repo-reference in the same work
- keep this period aggregate read-only in the local phase; do not introduce a second persisted projection until usage pressure is real

Reference tests:

- `api/tests/tests_views_extra.py`
- `wms/tests/test_workflow_projection.py`

## 3. Shipment-Party And Portal Recipient Contract

This is the most important cross-surface business contract in the repo.

Primary runtime sources:

- `wms/models_domain/portal.py`
- `wms/models_domain/shipment_parties.py`
- `wms/portal_recipient_sync.py`
- `wms/shipment_party_registry.py`
- `wms/shipment_party_setup.py`
- `wms/shipment_party_rules.py`
- `wms/view_permissions.py`
- `wms/scan_admin_contacts_cockpit.py`

Why it is shared:

- portal recipient changes affect operational contacts
- operational contacts affect shipment create/edit selectors
- admin contact tools can repair or reshape the same graph
- permissions and default bindings rely on the same data chain
- recipient structure compliance fields (`legal_form`, `beneficiary_count`) and uploaded structure documents now travel with the same graph

Maintenance rule:

- never treat portal recipient edits as pure presentation changes
- verify whether the change impacts synchronization, authorizations, default contacts, or scan selectors
- if recipient compliance fields or documents change, update portal creation/edit, synced `Contact`, `scan/contacts`, and admin merge/deduplication behavior together

Reference tests:

- `wms/tests/portal/tests_portal_recipient_sync.py`
- `wms/tests/portal/tests_portal_shipment_parties.py`
- `wms/tests/views/tests_views_scan_admin_shipment_parties.py`
- `wms/tests/views/tests_views_portal.py`
- `wms/tests/views/tests_views_scan_admin.py`
- `wms/tests/scan/tests_admin_contacts_merge_service.py`
- `api/tests/tests_ui_e2e_workflows.py`

## 4. Workflow Notification Contract

Primary runtime sources:

- `wms/signals.py`
- `wms/emailing.py`
- `wms/models_domain/integration.py`
- producer modules such as `wms/public_order_handlers.py`, `wms/order_notifications.py`, `wms/account_request_handlers.py`

Why it is shared:

- one business event may notify admin groups, association contacts, shipment parties, or volunteers
- operational docs and env vars depend on the same routing rules

Maintenance rule:

- when notification routing changes, update code, queue/runbook docs, and targeted matrices together

Reference docs and tests:

- `docs/email_flows_target_matrix_2026-02-20.md`
- `wms/tests/emailing/`
- `wms/tests/admin/tests_account_request_handlers.py`

Historical drift to watch:

- older docs still mention `wms.tests.emailing.tests_email_flows_e2e`
- verify the current `wms/tests/emailing/` tree before copying an old reference forward

### Planning Flight Capacity Cockpit Contract

Primary runtime sources:

- `wms/application/planning/version_detail_queries.py`
- `wms/planning/stats.py`
- `wms/planning/version_dashboard.py`
- `wms/planning/artifact_health.py`
- `templates/planning/_version_stats_block.html`
- `templates/planning/_version_planning_block.html`
- `templates/planning/version_detail.html`

Current local contract:

- `wms/application/planning/version_detail_queries.py` is the V3.1 shared GET composition layer for `planning/version_detail`
- `build_version_stats(version)` now keeps `flight_load_breakdown[]` as the flight-capacity source of truth for the planning cockpit
- one `flight_load_breakdown[]` row represents one `PlanningFlightSnapshot` from the run, even when no shipment is assigned yet
- stable row fields in this local phase are `flight_snapshot_id`, `flight_number`, `departure_date`, `departure_time`, `destination_iata`, `capacity_units`, `assignment_count`, `carton_total`, `equivalent_total`, `remaining_units`, `utilization_pct`, `load_state`, `load_state_label`
- load-state thresholds are explicit and stable in this local phase: `ok` when `< 80%`, `tension` when `>= 80% and < 95%`, `critical` when `>= 95% and <= 100%`, `overload` when `> 100%`
- missing capacity stays visible through `load_state=unknown`, `load_state_label=A renseigner`, and `remaining_units/utilization_pct = None`
- `build_version_dashboard(version)` exposes `capacity_summary` with `tension_count`, `critical_count`, `overload_count`, `remaining_capacity_total`
- `build_version_dashboard(version)` also exposes `flight_capacity_rows[]` for template consumption, with formatted labels layered on top of the stats rows
- `templates/planning/_version_stats_block.html` owns the four capacity summary cards
- `templates/planning/_version_planning_block.html` owns the compact `Charge vols` table and must keep it before the detailed assignment groups
- `wms/planning/exports.py` owns the strict planning export contract and now vendors the workbook template from `data/planning_templates/Planning-maquette.xlsx`
- stable planning artifact types in this local phase are `planning_workbook` and `planning_pdf`
- `PlanningCommunicationArtifact` is the health/event layer for workbook and PDF generation attempts; it keeps `output_type`, `status`, `backend`, `file_name`, `generated_at`, `error_message`, `payload`
- failed `planning_pdf` health payloads now keep stable local keys `error_code`, `runtime_status`, and `runtime_detail` when the backend is unavailable or the PDF export fails after runtime checks
- `templates/planning/_version_exports_block.html` owns the regenerate/download affordances plus the last-known workbook/PDF health summary
- `build_version_dashboard(version)` now exposes `exports.artifact_health` for `planning_workbook` and `planning_pdf`
- `build_version_dashboard(version)` also exposes `exports.pdf_runtime` with `backend`, `status`, `status_label`, `available`, `detail`
- stable local artifact-health statuses in this phase are `ready`, `failed`, and implicit UI fallback `missing`
- internal planning email helper payloads now use `planning_pdf` and resolve through `planning:version_communication_pdf`
- internal planning email helper payloads prefer the latest `planning_pdf` health row in `ready` status when available
- when no ready `planning_pdf` exists, internal planning email helper payloads stay honest through `blocked=True` and `blocking_reason=planning_pdf_not_ready`
- the production ops commands tied to this contract are `check_planning_pdf_runtime` and `refresh_ops_pilotage`

Maintenance rule:

- if flight-capacity thresholds, row fields, cockpit ordering, planning export artifacts, or artifact-health semantics change, update the stats/export helpers, the dashboard adapter, the planning templates, the repo-reference, and the planning tests in the same work
- keep `wms/views_planning.py` thin for the GET cockpit path: `dashboard` and `priority_cards` should continue to come from `wms/application/planning/version_detail_queries.py` instead of being recomposed in the view
- keep shared load-state ordering and threshold semantics in `wms/policies/planning.py` and `wms/policies/pilotage.py`; `wms/planning/stats.py` should remain the aggregator, not the rule-definition layer
- keep this lot read-only during the local phase; do not smuggle mutation or validation rules into the capacity cockpit

Reference tests:

- `wms/tests/planning/tests_version_dashboard.py`
- `wms/tests/views/tests_views_planning.py`

## 5. Living Cross-Domain Test Contracts

These tests are not just checks. They are compact maps of the intended repo wiring.

Primary examples:

- `api/tests/tests_ui_e2e_workflows.py`
- `wms/tests/core/tests_flow.py`
- `wms/tests/planning/tests_smoke_planning_flow.py`

Use them when:

- the change spans several layers
- you need a quick reminder of the nominal order of operations
- you suspect a hidden propagation from one surface into another

Maintenance rule:

- if a referenced test is renamed, split, or deleted, update this repository reference and any operational docs that cite it

## 6. Operations And Smoke Contract

Primary docs:

- `docs/operations.md`
- `docs/release_checklist.md`

Why they are shared contracts:

- they define the repository's expected post-change verification loops
- they are the last line of defense against "feature changed, smoke forgotten"

Maintenance rule:

- if a critical user journey, queue behavior, or deployment-sensitive asset changes, check whether operations or release smoke wording must change too
