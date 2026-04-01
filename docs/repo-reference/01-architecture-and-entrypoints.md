# Architecture And Entrypoints

This file is the shortest reliable way to rebuild a mental model of the repo before touching code.

## 1. Top-Level Routing Map

Start from `asf_wms/urls.py`.

Main surfaces:

- `/` -> home template
- `/admin/` -> Django admin
- `/scan/` -> legacy staff workflows via `wms.scan_urls`
- `/portal/` -> association portal via `wms.portal_urls`
- `/benevole/` -> volunteer area via `wms.volunteer_urls`
- `/planning/` -> planning cockpit via `wms.planning_urls`
- `/api/` -> API root via `api.urls`, then `api/v1/urls.py`

## 2. URL Modules To Open First

Use the URL module to find the real feature surface before searching broadly.

- `wms/scan_urls.py`: staff-facing scan, shipments, receipts, billing, imports, design, print, settings
- `wms/portal_urls.py`: portal auth, dashboard, orders, billing, recipients, account
- `wms/volunteer_urls.py`: volunteer auth, profile, constraints, availabilities
- `wms/planning_urls.py`: planning runs, versions, communications, artifacts
- `api/v1/urls.py`: REST endpoints, UI API endpoints, integration endpoints

## 3. Runtime Layering

The legacy Django stack is intentionally layered. Follow the flow in this order:

1. `urls.py`
2. `wms/views.py` re-export facade
3. `wms/views_scan_*`, `wms/views_portal_*`, `wms/views_public_*`, `wms/views_volunteer_*`, `wms/views_planning.py`
4. `*_handlers.py`, `*_helpers.py`, `*_state.py`, service modules, registry/sync modules
5. `wms/models.py` facade and `wms/models_domain/*`
6. templates and static assets
7. tests grouped by area

Practical rule:

- when routing or tests import `wms.views`, do not assume the logic is there
- `wms/views.py` is mostly a re-export layer
- V3 introduces `wms/application/` and `wms/policies/` as the preferred structural target
  for shared query composition and business rule classification, while legacy views and
  API endpoints remain the active delivery adapters during the migration

## 4. Main Runtime Clusters

### Scan / staff

- URL root: `wms/scan_urls.py`
- View facade exports: `wms/views.py`
- Main runtime modules: `wms/views_scan_stock.py`, `wms/views_scan_shipments.py`, `wms/views_scan_shipments_support.py`, `wms/views_scan_receipts.py`, `wms/views_scan_orders.py`, `wms/views_scan_admin.py`, `wms/views_scan_dashboard.py`, `wms/views_scan_billing.py`, `wms/views_scan_misc.py`
- Templates: `templates/scan/`
- Static assets: `wms/static/scan/`

### Portal / association

- URL root: `wms/portal_urls.py`
- Runtime modules: `wms/views_portal_auth.py`, `wms/views_portal_account.py`, `wms/views_portal_orders.py`, `wms/views_portal_billing.py`
- Templates: `templates/portal/`
- Static assets: `wms/static/portal/`

### Volunteer

- URL root: `wms/volunteer_urls.py`
- Runtime modules: `wms/views_volunteer_auth.py`, `wms/views_volunteer.py`, `wms/views_volunteer_account_request.py`
- Templates: `templates/benevole/`

### Planning

- URL root: `wms/planning_urls.py`
- Runtime modules: `wms/views_planning.py`, `wms/models_domain/planning.py`, `wms/planning/*`
- Templates: `templates/planning/`
- Primary cockpit surfaces: run list, run detail, version detail
- Current cockpit shell contract: planning pages reuse the scan shell and keep the operator hierarchy `header -> priorities -> section nav -> main planning by flight -> secondary details`

### API

- URL roots: `api/urls.py`, `api/v1/urls.py`
- UI API layer: `api/v1/ui_views.py`
- Integration/business API layer: `api/v1/views.py`, serializers and routers
- Current V3.1 extracted query sources:
  - `wms/application/scan/dashboard_queries.py` is the shared composition source for the legacy scan dashboard and `GET /api/v1/ui/dashboard/`
  - `wms/application/pilotage/pilotage_queries.py` is the shared composition source for the legacy pilotage cockpit and `GET /api/v1/ui/pilotage/`
- Current V3.1 extracted policy sources:
  - `wms/policies/sla.py` owns shared SLA freshness and severity classification
  - `wms/policies/pilotage.py` owns planning-threshold normalization reused by runtime settings and pilotage previews
  - `wms/policies/planning.py` owns planning flight load-state ordering, labels, and classification
  - `wms/policies/shipment_parties.py` owns shared shipment-party naming helpers such as the default recipient shipper label

### Shared contracts

- View facade: `wms/views.py`
- Model facade: `wms/models.py`
- Shared UI template tags: `wms/templatetags/wms_ui.py`
- Shared component templates: `templates/wms/components/`
- Shared UI visual catalog: `templates/scan/ui_lab.html`

## 5. Data And Domain Sources

Prefer the facade for imports unless a local change explicitly belongs in the extracted domain module.

- import compatibility facade: `wms/models.py`
- extracted domain modules: `wms/models_domain/catalog.py`, `inventory.py`, `shipment.py`, `shipment_parties.py`, `portal.py`, `planning.py`, `billing.py`, `integration.py`, `references.py`, `volunteer.py`

Important cross-cutting domain modules:

- portal recipient sync: `wms/portal_recipient_sync.py`
- shipment-party registry and rules: `wms/shipment_party_registry.py`, `wms/shipment_party_setup.py`, `wms/shipment_party_rules.py`
- workflow notifications and side effects: `wms/signals.py`
- core orchestration services: `wms/services.py`

## 6. Tests As Runtime Maps

The fastest way to understand intended behavior is often the nearest test package.

Main test clusters:

- `wms/tests/views/`: page behavior and many UI regressions
- `wms/tests/portal/`: portal sync, permissions, shipment-party behavior
- `wms/tests/shipment/`: shipment-party and shipment-specific rules
- `wms/tests/emailing/`: queue, routing, signal-driven notifications
- `wms/tests/planning/`: planning domain and smoke flow
- `wms/tests/core/`: cross-domain contracts and sanity flows
- `api/tests/`: API contracts and UI API end-to-end flows

## 7. Docs That Define Current Expected Behavior

Open these before changing business rules:

- `docs/mvp_spec.md`: current implemented functional scope
- `docs/audit_2026-02-19.md`: transversal architecture and risk audit
- `docs/operations.md`: runbook and operational rules
- `docs/release_checklist.md`: smoke and release propagation
- `docs/email_flows_target_matrix_2026-02-20.md`: email routing matrix
- `docs/plans/2026-03-22-ui-library-governance-design.md`: shared UI governance
- `docs/plans/2026-03-25-core-stable-usage-rules.md`: stable cross-screen UI contracts

## 8. Open These First By Change Type

If the ticket touches:

- scan flow: `wms/scan_urls.py`, `wms/views_scan_*`, nearest `*_handlers.py`, `templates/scan/`, `wms/tests/views/`
- portal flow: `wms/portal_urls.py`, `wms/views_portal_*`, `wms/portal_recipient_sync.py`, `templates/portal/`, `wms/tests/portal/`
- shipment-party/contact rules: `wms/models_domain/shipment_parties.py`, `wms/models_domain/portal.py`, `wms/shipment_party_*`, `wms/portal_recipient_sync.py`
- print/documents: `wms/shipment_document_handlers.py`, `wms/billing_document_handlers.py`, `templates/print/`, scan print views, print tests
- shared UI: `wms/templatetags/wms_ui.py`, `templates/wms/components/`, `templates/scan/ui_lab.html`, bridge CSS files, bootstrap UI tests
- release/operations: `docs/operations.md`, `docs/release_checklist.md`
