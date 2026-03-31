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

### Local Dashboard V2 API Contract

Primary runtime source:

- `api/v1/ui_views.py` via `GET /api/v1/ui/dashboard/`

Phase 1 local contract:

- `pending_actions[]` items expose `type`, `reference`, `label`, `priority`, `owner`, `url`, `age_hours`
- allowed `owner` values are `magasin`, `qualite`, `admin`, `portal`
- allowed `priority` values are `high`, `medium`, `low`
- `document_scan_cards[]` mirrors the queue-card shape already used by `technical_cards[]`
- `sla_alert_summary_cards[]` exposes the short summary `Nouveaux retards`, `Retards persistants`, `Retards critiques`
- `sla_alert_rows[]` exposes `reference`, `label`, `segment`, `owner`, `severity`, `freshness`, `delay_hours`, `age_hours`, `url`
- the legacy dashboard surface and the UI API mirror the same open-SLA classification derived from `tracking_alert_hours`
- the local runtime calibration loop also depends on `scan/settings` preset `incident_sla` and its preview counters for new/persistent/critical delays

Maintenance rule:

- if dashboard action routing, SLA prioritization, or ownership vocabulary changes, update the legacy dashboard, `scan/settings`, the UI API tests, and the repo-reference in the same work
- keep this contract intentionally short and stable during the local V2 phase; add new keys only when both HTML and API consumers need them

Reference tests:

- `api/tests/tests_ui_endpoints.py`
- `wms/tests/views/tests_views_scan_dashboard.py`
- `wms/tests/views/tests_views_scan_settings.py`

### Portal Dashboard Cockpit Contract

Primary runtime sources:

- `wms/views_portal_orders.py`
- `wms/portal_dashboard_helpers.py`
- `templates/portal/dashboard.html`
- `api/v1/ui_views.py` via `GET /api/v1/ui/portal/dashboard/`

Current contract:

- `dashboard_kpis` exposes `orders_total`, `orders_pending_review`, `orders_changes_requested`, `orders_with_shipment`, `orders_shipments_in_progress`
- portal dashboard rows expose `next_step_label` and `next_step_tone` in both HTML context and UI API payloads
- the HTML table and the UI API must stay aligned on the meaning of "next step" for pending review, correction, preparation, and tracked shipment states

Maintenance rule:

- if the association-facing dossier guidance changes, update the helper logic, the portal template, and the portal UI API in the same work
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

Maintenance rule:

- never treat portal recipient edits as pure presentation changes
- verify whether the change impacts synchronization, authorizations, default contacts, or scan selectors

Reference tests:

- `wms/tests/portal/tests_portal_recipient_sync.py`
- `wms/tests/portal/tests_portal_shipment_parties.py`
- `wms/tests/views/tests_views_scan_admin_shipment_parties.py`
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
