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
- `wms/scan_shipment_handlers.py`
- `wms/shipment_tracking_handlers.py`
- `wms/shipment_document_handlers.py`
- `wms/carton_handlers.py`
- `wms/services.py`
- `templates/scan/`
- `templates/print/`
- `wms/static/scan/`
- `api/v1/ui_views.py`

### What the flow covers

- stock update and stock availability
- carton overview vs carton detail split under `/scan/cartons/` and `/scan/carton/<id>/edit/`
- shipment creation or draft/edit
- carton status progression
- grouped carton print/document entrypoints
- tracking events
- document upload and print/document endpoints
- label generation
- closure of a completed shipment

### Living reference tests

- `api/tests/tests_ui_e2e_workflows.py::UiApiE2EWorkflowsTests::test_e2e_scan_workflow_stock_to_close_with_docs_labels_templates`
- `wms/tests/core/tests_flow.py::FlowTests::test_import_to_order_prepare_flow`
- `wms/tests/views/tests_views_scan_shipments.py`
- `wms/tests/views/tests_views_scan_stock.py`
- `wms/tests/views/tests_views_scan_dashboard.py`
- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/shipment/tests_shipment_document_handlers.py`

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

## 5. Planning: Seed -> Solve -> Publish -> Communications -> Cockpit

### Main entry points

- `wms/planning_urls.py`
- planning management commands

### Main runtime files

- `wms/views_planning.py`
- `wms/models_domain/planning.py`
- `wms/planning/*`
- `wms/management/commands/seed_planning_demo_data.py`
- `wms/management/commands/planning_recipe_export.py`

### Living reference tests

- `wms/tests/planning/tests_smoke_planning_flow.py`
- `wms/tests/planning/tests_outputs.py`
- `wms/tests/planning/tests_communication_actions.py`
- `wms/tests/planning/tests_run_preparation.py`

### Docs that must stay aligned

- `docs/operations.md`
- `docs/release_checklist.md`
- planning-specific design and implementation notes under `docs/plans/`

### Propagation warning

If planning run lifecycle, publication, artifact export, or communication draft behavior changes, update both:

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
