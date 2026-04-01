# Key Flows And Living Tests

This file lists the repo's most important cross-layer flows and the tests that currently act as living references.

Use it when you need to answer:

- where does this workflow really start?
- which files define it?
- what is the quickest test or doc proof that the contract still holds?

## 1. Scan: Stock -> Shipment -> Tracking -> Documents -> Close

### Main surfaces

- HTML/staff routes under `/scan/`
- UI API routes under `/api/v1/ui/`

### Main entry points

- `wms/scan_urls.py`
- `api/v1/urls.py`
- `wms/views.py`

### Main runtime files

- `wms/views_scan_stock.py`
- `wms/views_scan_shipments.py`
- `wms/views_scan_shipments_support.py`
- `wms/views_scan_dashboard.py`
- `wms/views_scan_pilotage.py`
- `wms/scan_pilotage.py`
- `wms/scan_dashboard_destination_risk.py`
- `wms/views_scan_settings.py`
- `wms/scan_dashboard_sla.py`
- `wms/scan_shipment_handlers.py`
- `wms/shipment_tracking_handlers.py`
- `wms/shipment_document_handlers.py`
- `wms/workflow_projection.py`
- `wms/management/commands/rebuild_workflow_projections.py`
- `wms/carton_handlers.py`
- `wms/services.py`
- `templates/scan/`
- `templates/print/`
- `wms/static/scan/`
- `api/v1/ui_views.py`
- `api/v1/views.py`

### What the flow covers

- stock update and stock availability
- scan dashboard action queue for low stock, disputes, and pending reviews
- scan dashboard workflow blockage queue split by `creation_expedition`, `commande`, `suivi`, `cloture`, `queue`
- scan dashboard local claim/release flow for workflow blockages
- scan dashboard SLA alert queue for new, persistent, and critical tracking delays
- scan dashboard destination-risk block driven by destination workflow aggregates
- scan dashboard destination-risk rows enriched with current ISO week vs previous ISO week trend
- scan dashboard health cards for both email and document-scan queues
- daily ops cockpit under `/scan/pilotage/` as the transverse read surface for snapshots, escalations, destination trends, portal backlog, and planning exports
- UI API mirror under `/api/v1/ui/pilotage/`
- scan settings preset-based calibration, including local `incident_sla` preview
- carton overview vs carton detail split under `/scan/cartons/` and `/scan/carton/<id>/edit/`
- shipment creation or draft/edit
- carton status progression
- grouped carton print/document entrypoints
- direct HTML print bundles for shipment `paper`, `standard_labels`, and `carton_lists_a4`
- shipment `carton_lists` kept as a per-carton action page for continuous-roll printing
- tracking events
- structured shipment dispute intake, assignment, due date, and resolution
- shipment tracking list filters for open, overdue, and unassigned disputes
- shipment tracking deep links filtered by `destination`
- shipment workflow projection rebuild and reporting endpoint under `/api/v1/workflow-projections/shipments/`
- destination workflow aggregates under `/api/v1/workflow-projections/destinations/`
- destination workflow aggregates by ISO week of `planned_at` under `/api/v1/workflow-projections/destination-weeks/`
- document upload and print/document endpoints
- label generation
- closure of a completed shipment

### Living reference tests

- `api/tests/tests_ui_e2e_workflows.py::UiApiE2EWorkflowsTests::test_e2e_scan_workflow_stock_to_close_with_docs_labels_templates`
- `wms/tests/core/tests_flow.py::FlowTests::test_import_to_order_prepare_flow`
- `wms/tests/views/tests_views_scan_shipments.py`
- `wms/tests/views/tests_views_tracking_dispute.py`
- `wms/tests/views/tests_views_scan_stock.py`
- `wms/tests/views/tests_views_scan_dashboard.py`
- `wms/tests/views/tests_views_scan_pilotage.py`
- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/shipment/tests_shipment_document_handlers.py`
- `wms/tests/test_workflow_projection.py`
- `wms/tests/management/tests_management_rebuild_workflow_projections.py`
- `api/tests/tests_views_extra.py`

### Docs that must stay aligned

- `docs/mvp_spec.md`
- `docs/release_checklist.md`
- `docs/operations.md`

### Propagation warning

If you change shipment sequencing, status rules, draft behavior, closure rules, or document/label availability, do not stop at one page or one handler. Check:

- `/scan/` routes
- UI API endpoints
- print/document handlers
- release smoke text
- the functional spec

## 2. Portal: Recipient / Account / Order -> Contact Sync -> Shipment Eligibility

### Main surfaces

- HTML portal routes under `/portal/`
- UI API routes under `/api/v1/ui/portal/`

### Main entry points

- `wms/portal_urls.py`
- `api/v1/urls.py`
- `wms/views.py`

### Main runtime files

- `wms/views_portal_auth.py`
- `wms/views_portal_account.py`
- `wms/views_portal_orders.py`
- `wms/views_portal_billing.py`
- `wms/portal_order_handlers.py`
- `wms/portal_recipient_sync.py`
- `wms/view_permissions.py`
- `wms/shipment_party_registry.py`
- `wms/shipment_party_setup.py`
- `wms/shipment_party_rules.py`
- `wms/models_domain/portal.py`
- `wms/models_domain/shipment_parties.py`
- `templates/portal/`
- `api/v1/ui_views.py`

### What the flow covers

- association authentication and account maintenance
- portal dashboard cockpit KPIs and per-order next-step guidance
- recipient creation/update
- synchronization from `AssociationRecipient` to operational contact structures
- shipper/recipient authorization chain
- order creation from portal
- downstream readiness for shipment creation

### Living reference tests

- `api/tests/tests_ui_e2e_workflows.py::UiApiE2EWorkflowsTests::test_e2e_portal_workflow_recipients_account_and_order`
- `wms/tests/portal/tests_portal_recipient_sync.py`
- `wms/tests/portal/tests_portal_shipment_parties.py`
- `wms/tests/portal/tests_portal_order_handlers.py`
- `wms/tests/portal/tests_portal_permissions.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`
- `wms/tests/views/tests_views_portal.py`
- `api/tests/tests_ui_endpoints.py`

### Docs that must stay aligned

- `docs/mvp_spec.md`
- `docs/audit_2026-02-19.md`
- `docs/release_checklist.md`

### Propagation warning

If you change recipient fields, validation, shipment-party eligibility, default shipper binding, or portal permissions, check both:

- the portal HTML views and templates
- the portal UI API endpoints

Also inspect the shipment-party registry and sync layers. A portal-only change is often not portal-only in practice.

## 3. Orders: Public / Portal / Admin Side Effects

### Main entry points

- public order routes in `wms/scan_urls.py`
- portal order routes in `wms/portal_urls.py`
- related signal-driven side effects

### Main runtime files

- `wms/public_order_handlers.py`
- `wms/views_public_order.py`
- `wms/views_portal_orders.py`
- `wms/portal_order_handlers.py`
- `wms/order_notifications.py`
- `wms/signals.py`

### Living reference tests

- `wms/tests/public/tests_public_order_handlers.py`
- `wms/tests/views/tests_views_public_order.py`
- `wms/tests/portal/tests_portal_order_handlers.py`
- `api/tests/tests_ui_e2e_workflows.py`

### Propagation warning

If order creation or status transitions change, inspect:

- admin notification logic
- portal confirmation flows
- signal-driven side effects
- any linked shipment preparation assumptions

## 4. Emailing And Notification Routing

### Main runtime files

- `wms/emailing.py`
- `wms/models_domain/integration.py`
- `wms/management/commands/process_email_queue.py`
- `wms/runtime_settings.py`
- `wms/views_scan_settings.py`
- `wms/account_request_handlers.py`
- `wms/admin_account_request_approval.py`
- `wms/public_order_handlers.py`
- `wms/order_notifications.py`
- `wms/signals.py`

### Living reference tests

- `wms/tests/admin/tests_account_request_handlers.py`
- `wms/tests/emailing/tests_order_status_notifications.py`
- `wms/tests/emailing/tests_notifications_queue.py`
- `wms/tests/emailing/tests_signals_extra.py`
- `wms/tests/emailing/tests_shipment_party_notifications.py`
- `wms/tests/emailing/tests_volunteer_email_flows.py`

### Primary reference doc

- `docs/email_flows_target_matrix_2026-02-20.md`

### Propagation warning

If you change recipients, status-triggered notifications, delivery mode, or queue behavior, update all of these together:

- producer code
- queue/runtime docs
- targeted matrices
- operations/release docs if the operational behavior changed

Historical note:

- older docs still reference `wms.tests.emailing.tests_email_flows_e2e`
- do not trust that historical path blindly
- verify the real `wms/tests/emailing/` tree before updating smoke documentation

Also check whether the dashboard/runtime calibration loop changed:

- `/scan/dashboard/`
- `/scan/pilotage/`
- `/scan/settings/`
- `api/v1/ui/dashboard/`
- `api/v1/ui/pilotage/`
- `docs/operations.md`

## 5. Planning: Seed -> Solve -> Publish -> Communications -> Cockpit

### Main entry points

- `wms/planning_urls.py`
- planning management commands

### Main runtime files

- `wms/views_planning.py`
- `wms/models_domain/planning.py`
- `wms/planning/*`
- `wms/planning/stats.py`
- `wms/planning/version_dashboard.py`
- `wms/management/commands/seed_planning_demo_data.py`
- `wms/management/commands/planning_recipe_export.py`
- `templates/planning/_version_stats_block.html`
- `templates/planning/_version_planning_block.html`

### Living reference tests

- `wms/tests/planning/tests_smoke_planning_flow.py`
- `wms/tests/planning/tests_outputs.py`
- `wms/tests/planning/tests_communication_actions.py`
- `wms/tests/planning/tests_run_preparation.py`
- `wms/tests/planning/tests_version_dashboard.py`
- `wms/tests/views/tests_views_planning.py`

### Docs that must stay aligned

- `docs/operations.md`
- `docs/release_checklist.md`
- planning-specific design and implementation notes under `docs/plans/`

### Current cockpit contract

- `templates/planning/run_list.html` is the action-oriented entry page with an attention block before history
- `templates/planning/run_detail.html` exposes a single primary CTA and a short operator list of versions
- `templates/planning/version_detail.html` is the operator cockpit and should stay ordered as `header -> priorities -> section nav -> planning capacity -> planning by flight -> secondary details`
- the stats panel now includes the local flight-capacity summary cards `Vols en tension`, `Vols critiques`, `Vols en surcharge`, `Capacité restante totale`
- the main planning block now starts with a compact `Charge vols` table ordered by load urgency before the detailed assignment groups
- the exports block now regenerates a strict planning workbook plus a derived planning PDF from the vendored `Planning-maquette.xlsx`
- the planning PDF is the primary operator artifact; the workbook remains available for calibration and download
- the exports block also exposes the latest workbook/PDF artifact health with backend, last attempt, and the last PDF error when present
- the exports block exposes a distinct `Runtime PDF` state for the current host, separate from the last artifact attempt
- internal planning communication drafts now expose `planning_pdf` attachments instead of the workbook
- internal planning communication drafts are explicitly `blocked` with `blocking_reason=planning_pdf_not_ready` when no ready PDF artifact exists yet
- the production-facing ops entry points for this flow are `python manage.py check_planning_pdf_runtime` and `python manage.py refresh_ops_pilotage`
- flight-capacity indicators are read-only in this local phase and must not silently change assignment or publication rules

### Propagation warning

If planning run lifecycle, publication, artifact export, communication draft behavior, or flight-capacity readout changes, update both:

- the planning cockpit/runtime docs
- the smoke/reference tests

## 6. Shared UI Across Scan / Portal / Admin / Benevole

### Main runtime files

- `wms/templatetags/wms_ui.py`
- `templates/wms/components/`
- `templates/scan/ui_lab.html`
- `wms/static/scan/scan-bootstrap.css`
- `wms/static/portal/portal-bootstrap.css`
- `wms/static/wms/admin-bootstrap.css`

### Living reference tests

- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`

### Primary docs

- `docs/plans/2026-03-22-ui-library-governance-design.md`
- `docs/plans/2026-03-25-core-stable-usage-rules.md`

### Propagation warning

If a UI primitive or shared class changes, search beyond the current page. The same contract may be reused in:

- `templates/scan/`
- `templates/portal/`
- `templates/benevole/`
- `templates/admin/wms/`
- `templates/print/`
