# Key Flows And Living Tests

This file identifies the repo’s most important cross-layer workflows and the tests that currently act as living references.

Use it when you need to answer:

- where does this workflow start?
- which runtime files define it?
- which tests prove the current contract?
- which docs must stay aligned?

This file is a flow map, not a full impact checklist.

For propagation details, use:

- `03-impact-map.md`
- the relevant `03x-impact-*.md`
- `04-shared-contracts.md`

---

## How To Use This File

Before changing a major workflow:

1. Identify the closest flow below.
2. Open the listed runtime entrypoints.
3. Read the critical contracts.
4. Run or inspect the living reference tests.
5. Check the relevant `03x-impact-*` file for propagation.
6. Update docs if the workflow contract changed.

Runtime code and passing tests remain the source of truth.

---

## Flow Index

| Flow | Read when touching | Main proof |
|------|--------------------|------------|
| Scan: Stock → Shipment → Tracking → Documents → Close | warehouse, stock, cartons, shipments, tracking, documents | `api/tests/tests_ui_e2e_workflows.py`, `wms/tests/core/tests_flow.py` |
| Portal: Recipient / Account / Order → Contact Sync → Shipment Eligibility | portal, recipients, account, orders, party sync | `wms/tests/portal/` |
| Orders: Public / Portal / Admin Side Effects | order submission, review, preparation links | order handler and public/portal order tests |
| Emailing And Notification Routing | emails, queues, signals, outbound events | `wms/tests/emailing/` |
| Planning: Seed → Solve → Publish → Communications → Cockpit | planning runs, versions, exports, artifacts | `wms/tests/planning/tests_smoke_planning_flow.py` |
| Shared UI Across Scan / Portal / Admin / Benevole | UI primitives, CSS, shell contracts | bootstrap UI tests |
| Structural Runtime Boundaries | `application`, `events`, `jobs`, `parties`, `artifacts` | structural contract tests and type checks |

---

## 1. Scan: Stock → Shipment → Tracking → Documents → Close

### When To Read

Read this flow when touching:

- stock update
- recipient needs
- dashboard / pilotage
- receipts
- listing import
- carton lifecycle
- preparateur workflow
- shipment creation/edit
- shipment tracking
- shipment closure
- shipment documents / labels
- scan UI assets

### Main Surfaces

- HTML/staff routes under `/scan/`
- UI API routes under `/api/v1/ui/`

### Main Entrypoints

- `wms/scan_urls.py`
- `api/v1/urls.py`
- `wms/views.py`

### Main Runtime Files

- `wms/views_scan_stock.py`
- `wms/application/scan/recipient_needs_queries.py`
- `wms/views_scan_shipments.py`
- `wms/views_scan_shipments_support.py`
- `wms/views_scan_preparation.py`
- `wms/views_scan_dashboard.py`
- `wms/views_scan_pilotage.py`
- `wms/scan_pilotage.py`
- `wms/scan_dashboard_destination_risk.py`
- `wms/views_scan_settings.py`
- `wms/scan_dashboard_sla.py`
- `wms/scan_shipment_handlers.py`
- `wms/shipment_tracking_access.py`
- `wms/recipient_product_preferences.py`
- `wms/shipment_tracking_handlers.py`
- `wms/views_shipment_tracking_access.py`
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

### Critical Contracts

- Recipient-needs cockpit must stay limited to explicit product preferences and category-covered preferences; it must not expand a full recipient × catalog cross-join.
- Recipient-needs priority depends on remaining need, current period deadline, and open-shipment delay against `tracking_alert_hours`.
- Bulk `Préparer` from recipient-needs is only valid when selected rows share destination, shipper, and recipient grouping.
- Scan dashboard queues, SLA alerts, destination-risk rows, and health cards must remain operationally accurate.
- Listing import must keep pallet-receipt linking, resumable active step behavior, PDF analysis stage, assisted suggestions, additive quantities, and incomplete-product recap.
- `/scan/stock-update/` remains the persistent cockpit for incomplete products.
- Carton overview/detail split must preserve guarded delete, stock restoration through unpacking, and lock states.
- Preparateur workflow must preserve active volunteer session, order grouping, carton traceability, family-specific carton formats, and `Marquer prêt` behavior.
- Preparateur rangement starts from `/scan/preparateur/`, keeps a session batch capped at five distinct products, locks the batch to either `Entrée en stock` or `Déplacement de stock`, requires quantities, increments duplicate scans, routes every line to the product default location, blocks validation until missing default locations are corrected, writes stock only when the batch is validated, and stops unknown receipt-mode products before opening the preparateur product-creation modal.
- Unknown-product escape hatch from pack/carton edit intentionally drops in-progress carton draft when redirecting to `/scan/import/`.
- Warehouse preparation conversion creates shipments in `ShipmentStatus.PICKING`, not `PACKED`.
- Final promotion from `PICKING` to `PACKED` is explicit on shipment dossier and remains separate from preparation-run conversion.
- Planning must not see `PICKING` shipments as ready.
- Shipment document-first creation without cartons remains allowed.
- Prepared shipment creation can store `planned_carton_count` without attaching cartons; this planned count is document-only and must not make the shipment ready or create `Carton` rows.
- Prepared shipment batch creation is all-or-nothing and creates one independent document-first shipment per row.
- Shipment `paper` bundle order remains: `Bon d'expédition`, `Document douane`, `Liste colisage générale` twice.
- Shipment `standard_labels` means one A4 portrait page per carton with donation certificate, shipment label, contact label, and carton packing list.
- Shipment `preparatory_labels` means one A4 portrait page per planned/real slot with donation certificate, shipment label, and contact label only; it intentionally omits carton packing lists for virtual slots.
- `carton_lists` remains continuous-roll; `carton_lists_a4` remains direct printable A4.
- Public shipment QR tracking remains authenticated/restricted according to current access rules.
- Correspondent and recipient receipt scans require proof or explicit manual fallback.
- Workflow projection rebuild and reporting endpoints must stay aligned with runtime shipment truth.

### Living Reference Tests

- `api/tests/tests_ui_e2e_workflows.py::UiApiE2EWorkflowsTests::test_e2e_scan_workflow_stock_to_close_with_docs_labels_templates`
- `wms/tests/core/tests_flow.py::FlowTests::test_import_to_order_prepare_flow`
- `wms/tests/views/tests_views_scan_shipments.py`
- `wms/tests/views/tests_views_scan_preparateur.py`
- `wms/tests/shipment/tests_carton_volunteer_activity.py`
- `wms/tests/orders/tests_pack_handlers.py`
- `wms/tests/domain/tests_domain_orders_extra.py`
- `wms/tests/views/tests_views_shipment_tracking_access.py`
- `wms/tests/shipment/tests_shipment_tracking_access.py`
- `wms/tests/forms/tests_forms_shipment_tracking.py`
- `wms/tests/emailing/tests_shipment_tracking_access.py`
- `wms/tests/views/tests_views_scan_preparation.py`
- `wms/tests/views/tests_views_tracking_dispute.py`
- `wms/tests/views/tests_views_scan_stock.py`
- `wms/tests/core/tests_scan_recipient_needs_queries.py`
- `wms/tests/views/tests_views_scan_dashboard.py`
- `wms/tests/views/tests_views_scan_pilotage.py`
- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/views/tests_views_scan_account_validations.py`
- `wms/tests/views/tests_views_scan_receipts.py`
- `wms/tests/receipt/tests_receipt_listing.py`
- `wms/tests/pallet/tests_pallet_listing.py`
- `wms/tests/pallet/tests_pallet_listing_handlers.py`
- `wms/tests/imports/tests_import_utils.py`
- `wms/tests/imports/tests_import_services_pallet.py`
- `wms/tests/imports/tests_import_services_locations_extra.py`
- `wms/tests/views/tests_views_imports.py`
- `wms/tests/shipment/tests_shipment_status.py`
- `wms/tests/shipment/tests_shipment_document_handlers.py`
- `wms/tests/test_workflow_projection.py`
- `wms/tests/management/tests_management_rebuild_workflow_projections.py`
- `wms/tests/preparation/tests_conversion.py`
- `wms/tests/planning/tests_sources.py`
- `api/tests/tests_views_extra.py`

### Docs That Must Stay Aligned

- `docs/mvp_spec.md`
- `docs/release_checklist.md`
- `docs/operations.md`
- `docs/repo-reference/03a-impact-scan.md`
- `docs/repo-reference/03c-impact-shipments.md`
- `docs/repo-reference/03e-impact-print-documents.md`
- `docs/repo-reference/04-shared-contracts.md`

### Propagation Warning

If shipment sequencing, status rules, document-first creation, closure behavior, or document/label availability changes, do not stop at one page or handler.

Check:

- `/scan/` routes
- UI API endpoints
- print/document handlers
- release smoke text
- functional specs
- impact maps for scan, shipments, print, planning, and email/events

---

## 2. Portal: Recipient / Account / Order → Contact Sync → Shipment Eligibility

### When To Read

Read this flow when touching:

- portal auth
- account maintenance
- portal scope selection
- recipient portal access
- shipper portal access
- recipient create/update
- recipient product preferences
- public account review
- portal order creation
- portal UI API endpoints
- contact sync
- shipment-party eligibility

### Main Surfaces

- HTML portal routes under `/portal/`
- UI API routes under `/api/v1/ui/portal/`

### Main Entrypoints

- `wms/portal_urls.py`
- `api/v1/urls.py`
- `wms/views.py`

### Main Runtime Files

- `wms/views_portal_auth.py`
- `wms/portal_access.py`
- `wms/views_portal_account.py`
- `wms/views_portal_orders.py`
- `wms/views_portal_billing.py`
- `wms/application/portal/dashboard_queries.py`
- `wms/application/parties/use_cases.py`
- `wms/portal_order_handlers.py`
- `wms/portal_recipient_sync.py`
- `wms/parties/projections.py`
- `wms/parties/selectors.py`
- `wms/parties/sync.py`
- `wms/view_permissions.py`
- `wms/shipment_party_registry.py`
- `wms/shipment_party_setup.py`
- `wms/shipment_party_rules.py`
- `wms/models_domain/portal.py`
- `wms/models_domain/shipment_parties.py`
- `templates/portal/`
- `api/v1/ui_views.py`

### Critical Contracts

- Public account requests distinguish `shipper`, `recipient`, and `user`; legacy `association` remains shipper-equivalent during approval.
- Public account request review is scan-first via `/scan/contacts/validations/` and `/scan/account-validations/`; Django admin is fallback only.
- Recipient public account requests choose exactly one delivery stop because recipient portal access is scoped to one `ShipmentRecipientOrganization`.
- Recipient approval provisions the recipient organization, minimal active recipient contact, `PortalAccessGrant(recipient_admin)`, and default ASF shipper binding together.
- If operator corrects `shipper` to `recipient`, `requested_account_type` preserves original type and `review_snapshot` stores reviewed payload.
- Portal access resolves explicit `PortalAccessGrant` first, then legacy `AssociationProfile` fallback.
- `/portal/` branches by active scope: shipper cockpit or recipient home.
- Recipient scopes use `/portal/recipient/profile/` and `/portal/recipient/preferences/`.
- Legacy shipper pages remain guarded by active portal scope.
- Portal shell navigation adapts by active scope.
- Shipper recipient create/update writes canonical shipment-party graph first and refreshes `AssociationRecipient` only as compatibility projection.
- Scan/admin recipient shared-field edits route through the same application use-case layer.
- Non-shipment contact history categories stay in legacy contact CRUD and do not create shipment-party runtime rows by themselves.
- `rebuild_recipient_party_graph --dry-run|--apply` is the deterministic repair path for explicit shipper grants or legacy projection rebuilds.
- Once `PortalAccessGrant(recipient_admin)` exists, shipper-side recipient maintenance becomes read-only.
- Destination-scoped recipient runtimes are keyed by `(organization, destination)`.
- Default ASF shipper resolution prefers canonical `Contact.asf_id`, then legacy display-name anchor.
- Portal HTML and UI API mirrors must remain aligned.

### Living Reference Tests

- `api/tests/tests_ui_e2e_workflows.py::UiApiE2EWorkflowsTests::test_e2e_portal_workflow_recipients_account_and_order`
- `wms/tests/portal/tests_portal_recipient_sync.py`
- `wms/tests/portal/tests_portal_shipment_parties.py`
- `wms/tests/portal/tests_portal_access_grants.py`
- `wms/tests/admin/tests_account_request_handlers.py`
- `wms/tests/portal/tests_portal_role_review_gate.py`
- `wms/tests/core/tests_parties_destination_scope.py`
- `wms/tests/core/tests_parties_use_cases.py`
- `wms/tests/portal/tests_portal_order_handlers.py`
- `wms/tests/portal/tests_portal_permissions.py`
- `wms/tests/scan/tests_admin_contacts_contact_service.py`
- `wms/tests/management/tests_management_rebuild_recipient_party_graph.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`
- `wms/tests/views/tests_views_portal.py`
- `wms/tests/views/tests_views_scan_admin.py`
- `wms/tests/views/tests_views_scan_admin_shipment_parties.py`
- `api/tests/tests_ui_endpoints.py`

### Docs That Must Stay Aligned

- `docs/mvp_spec.md`
- `docs/audit_2026-02-19.md`
- `docs/release_checklist.md`
- `docs/repo-reference/03b-impact-portal.md`
- `docs/repo-reference/03d-impact-parties.md`
- `docs/repo-reference/04-shared-contracts.md`

### Propagation Warning

If recipient fields, validation, shipment-party eligibility, default shipper binding, portal scope, or portal permissions change, inspect:

- portal HTML views and templates
- portal UI API endpoints
- shipment-party registry and sync layers
- scan/admin contact surfaces
- destination-scoped recipient lookups

A portal-only change is often not portal-only.

---

## 3. Orders: Public / Portal / Admin Side Effects

### When To Read

Read this flow when touching:

- public order routes
- portal order routes
- order review
- order status transitions
- order-to-shipment linking
- order notifications
- order preparation
- association reception linked to orders

### Main Entrypoints

- public order routes in `wms/scan_urls.py`
- portal order routes in `wms/portal_urls.py`
- related signal-driven side effects

### Main Runtime Files

- `wms/public_order_handlers.py`
- `wms/views_public_order.py`
- `wms/views_portal_orders.py`
- `wms/portal_order_handlers.py`
- `wms/order_notifications.py`
- `wms/signals.py`

### Critical Contracts

- Portal shipper order may contain ASF-stock lines, declared shipper inbound delivery, or both.
- Portal order submission and ASF review do not require supporting documents up front.
- Document completeness blocks later shipment readiness when the shipment depends on those documents.
- One order may link multiple shipment dossiers through `OrderShipmentLink`.
- `order.shipment` remains a compatibility pointer for older surfaces.
- `scan/receive-association/` can attach a receipt to order inbound delivery and materialize declared shipper cartons.
- Legacy scan order flow is split:
  - `/scan/orders-view/` = queue
  - `/scan/orders/<id>/` = operator dossier
  - `/scan/orders/` = create/select/line maintenance
- `Réception association` and `Dossier expédition` remain downstream operational surfaces.

### Living Reference Tests

- `wms/tests/public/tests_public_order_handlers.py`
- `wms/tests/views/tests_views_public_order.py`
- `wms/tests/portal/tests_portal_order_handlers.py`
- `api/tests/tests_ui_e2e_workflows.py`

### Docs That Must Stay Aligned

- `docs/mvp_spec.md`
- `docs/operations.md`
- `docs/release_checklist.md`
- `docs/repo-reference/03b-impact-portal.md`
- `docs/repo-reference/03c-impact-shipments.md`
- `docs/repo-reference/03h-impact-email-events.md`

### Propagation Warning

If order creation or status transitions change, inspect:

- admin notification logic
- portal confirmation flows
- signal-driven side effects
- shipment preparation assumptions
- order-to-shipment compatibility surfaces

---

## 4. Emailing And Notification Routing

### When To Read

Read this flow when touching:

- outbound emails
- account approval emails
- order notifications
- shipment-party notifications
- volunteer email flows
- event queue
- signal-triggered side effects
- runtime notification settings
- email processing commands

### Main Runtime Files

- `wms/emailing.py`
- `wms/events/outbox.py`
- `wms/models_domain/integration.py`
- `wms/management/commands/process_email_queue.py`
- `wms/runtime_settings.py`
- `wms/views_scan_settings.py`
- `wms/account_request_handlers.py`
- `wms/admin_account_request_approval.py`
- `wms/public_order_handlers.py`
- `wms/order_notifications.py`
- `wms/signals.py`

### Critical Contracts

- Durable enqueue paths should use `wms/events/outbox.py`.
- Do not reintroduce ad hoc `IntegrationEvent` creation for durable dispatch.
- Notification changes must update producer code, queue behavior, docs, and matrices together.
- Runtime calibration loop may affect dashboard, pilotage, settings, and API mirrors.
- Document scan queue follows the same V3.2 durable-dispatch rule.
- Historical docs may reference old test paths; verify the current `wms/tests/emailing/` tree.

### Living Reference Tests

- `wms/tests/admin/tests_account_request_handlers.py`
- `wms/tests/emailing/tests_order_status_notifications.py`
- `wms/tests/emailing/tests_notifications_queue.py`
- `wms/tests/emailing/tests_signals_extra.py`
- `wms/tests/emailing/tests_shipment_party_notifications.py`
- `wms/tests/emailing/tests_volunteer_email_flows.py`
- `wms/tests/security/tests_document_scan_queue.py`
- `wms/tests/management/tests_management_check_document_scan_runtime.py`

### Primary Reference Doc

- `docs/email_flows_target_matrix_2026-02-20.md`

### Docs That Must Stay Aligned

- `docs/operations.md`
- `docs/release_checklist.md`
- `docs/email_flows_target_matrix_2026-02-20.md`
- `docs/repo-reference/03h-impact-email-events.md`

### Propagation Warning

If recipients, status-triggered notifications, delivery mode, or queue behavior change, update together:

- producer code
- `wms/events/outbox.py`
- queue/runtime docs
- targeted matrices
- operations/release docs

---

## 5. Planning: Seed → Solve → Publish → Communications → Cockpit

### When To Read

Read this flow when touching:

- planning runs
- versions
- solver/allocation
- publication
- planning communication drafts
- workbook/PDF exports
- planning artifacts
- flight-capacity readouts
- planning cockpit UI
- planning commands

### Main Entrypoints

- `wms/planning_urls.py`
- planning management commands

### Main Runtime Files

- `wms/views_planning.py`
- `wms/models_domain/planning.py`
- `wms/planning/*`
- `wms/artifacts/planning.py`
- `wms/artifacts/attachments.py`
- `wms/artifacts/proofs.py`
- `wms/application/planning_artifacts/use_cases.py`
- `wms/planning/stats.py`
- `wms/planning/version_dashboard.py`
- `wms/application/planning/version_detail_queries.py`
- `wms/management/commands/seed_planning_demo_data.py`
- `wms/management/commands/planning_recipe_export.py`
- `templates/planning/_version_stats_block.html`
- `templates/planning/_version_planning_block.html`

### Critical Contracts

- `version_detail.html` cockpit order stays: `header -> priorities -> section nav -> planning capacity -> planning by flight -> secondary details`.
- `prepare_run_inputs(...)` resolves flight batches through `wms/planning/flight_sources.py`.
- `api` mode records blocking `flight_import_failed` issue when provider import fails.
- `hybrid` snapshots retained Excel/API flights and preserves existing Excel anchor when present.
- Air France imports query provider per destination IATA when possible and deduplicate overlapping rows.
- Planning API config resolves from settings first, then env vars, with compatibility aliases.
- Stats panel includes local flight-capacity summary cards.
- Exports regenerate strict planning workbook plus derived planning PDF from vendored `Planning-maquette.xlsx`.
- Planning PDF is primary operator artifact; workbook remains available for calibration/download.
- Internal planning communication drafts expose `planning_pdf` attachments.
- Drafts are `blocked` with `planning_pdf_not_ready` when no ready PDF artifact exists.
- `wms/planning/exports.py` and `wms/planning/communication_actions.py` remain compatibility adapters over `wms/artifacts/*`.
- Production-facing ops entry points include:
  - `python manage.py check_planning_pdf_runtime`
  - `python manage.py refresh_ops_pilotage`
- Flight-capacity indicators are read-only in this phase and must not silently change assignment/publication rules.

### Living Reference Tests

- `wms/tests/planning/tests_smoke_planning_flow.py`
- `wms/tests/planning/tests_artifact_services.py`
- `wms/tests/planning/tests_outputs.py`
- `wms/tests/planning/tests_communication_actions.py`
- `wms/tests/planning/tests_run_preparation.py`
- `wms/tests/planning/tests_version_dashboard.py`
- `wms/tests/print/tests_print_pack_sync.py`
- `wms/tests/test_job_runs.py`
- `wms/tests/views/tests_views_planning.py`

### Docs That Must Stay Aligned

- `docs/operations.md`
- `docs/release_checklist.md`
- planning-specific notes under `docs/plans/`
- `docs/repo-reference/03f-impact-planning.md`
- `docs/repo-reference/03e-impact-print-documents.md`

### Propagation Warning

If planning run lifecycle, publication, artifacts, communication drafts, exports, or flight-capacity readouts change, update:

- planning cockpit/runtime docs
- smoke/reference tests
- print/artifact sync tests
- operations docs

---

## 6. Shared UI Across Scan / Portal / Admin / Benevole

### When To Read

Read this flow when touching:

- UI primitives
- shared template tags
- shared CSS utilities
- component templates
- shared shell behavior
- visual catalog
- cross-surface UI consistency

### Main Runtime Files

- `wms/templatetags/wms_ui.py`
- `templates/wms/components/`
- `templates/scan/ui_lab.html`
- `wms/static/scan/scan-bootstrap.css`
- `wms/static/portal/portal-bootstrap.css`
- `wms/static/wms/admin-bootstrap.css`

### Critical Contracts

- Shared primitives must stay consistent across scan, portal, benevole, admin, planning, and print where reused.
- If a shared primitive changes semantics, UI Lab and bootstrap regression tests must move with it.
- Do not promote local patterns into shared primitives prematurely.

### Living Reference Tests

- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`

### Primary Docs

- `docs/plans/2026-03-22-ui-library-governance-design.md`
- `docs/plans/2026-03-25-core-stable-usage-rules.md`
- `docs/repo-reference/03g-impact-shared-ui-api.md`
- `docs/repo-reference/04-shared-contracts.md`

### Propagation Warning

If a UI primitive or shared class changes, search beyond the current page.

Potential consumers:

- `templates/scan/`
- `templates/portal/`
- `templates/benevole/`
- `templates/admin/wms/`
- `templates/print/`
- `templates/planning/`

---

## 7. Structural Runtime Boundaries: Application / Events / Jobs / Parties / Artifacts

### When To Read

Read this flow when touching:

- `wms/application/`
- `wms/events/`
- `wms/jobs/`
- `wms/parties/`
- `wms/artifacts/`
- public package facades
- structural type gates
- extracted runtime boundaries
- Makefile structural commands

### Main Runtime Files

- `wms/application/`
- `wms/events/`
- `wms/jobs/`
- `wms/parties/`
- `wms/artifacts/`
- `mypy.ini`
- `pyrightconfig.json`
- `Makefile`

### Critical Contracts

- `mypy.ini` carries broader structural proof over extracted layers.
- `pyrightconfig.json` intentionally locks public `__init__` facades, not the full unstubbed Django ORM internals.
- Public package roots are stable import surfaces.
- New runtime layers must be visible to type checks and contract tests.
- Compatibility adapters can remain while extracted layers become preferred homes for shared logic.

### Living Reference Tests

- `wms/tests/core/tests_v33_contracts.py`
- `wms/tests/core/tests_event_types.py`
- `wms/tests/core/tests_parties_use_cases.py`
- `wms/tests/core/tests_parties_merge.py`
- `wms/tests/core/tests_parties_destination_scope.py`
- `wms/tests/planning/tests_artifact_services.py`
- `wms/tests/print/tests_print_pack_sync.py`
- `wms/tests/test_job_runs.py`

### Structural Proof Commands

- `make typecheck-structural`
- `make ruff-structural`
- `./.venv/bin/python manage.py test wms.tests.core.tests_v33_contracts -v 2`

### Docs That Must Stay Aligned

- `docs/repo-reference/01-architecture-and-entrypoints.md`
- `docs/repo-reference/03g-impact-shared-ui-api.md`
- `docs/repo-reference/04-shared-contracts.md`

### Propagation Warning

If a new boundary is introduced or a package-root facade changes, update together:

- package `__init__` exports
- structural proof suite
- typecheck scope
- contract tests
- architecture docs

Do not grow new runtime layers invisible to `mypy`, `pyright`, or contract tests.

---

## Final Rule

This file answers:

> “Which flows matter, and which tests prove them?”

For blast radius and propagation details, use the relevant `03x-impact-*.md` file.
