# Architecture And Entrypoints

This file is the fastest reliable way to rebuild a mental model of the repo before touching code.

Use it to understand:

- where requests enter
- which runtime surface owns the feature
- where active business logic lives
- which layers are legacy adapters vs preferred targets
- which invariants must not be broken
- where to start safely for a given change

If unsure, runtime code and passing tests are the source of truth.

---

## TL;DR — 2 Minute Mental Model

ASF-WMS is currently a **Django monolith with progressive modular extraction**.

Production delivery still happens mainly through:

- Django URL modules
- legacy `views_*`
- templates
- forms
- management commands
- shared model facades

Newer extracted layers progressively centralize logic:

- `wms/application/`
- `wms/policies/`
- `wms/events/`
- `wms/jobs/`
- `wms/parties/`
- `wms/artifacts/`

Migration is partial. Do not assume legacy layers are retired.

---

## 1. Top-Level Routing Map

Start from:

`asf_wms/urls.py`

Main surfaces:

| Route | Purpose |
|------|---------|
| `/` | Home |
| `/admin/` | Django admin |
| `/scan/` | Internal warehouse / staff operations |
| `/portal/` | Partner portal |
| `/benevole/` | Volunteer area |
| `/planning/` | Planning cockpit |
| `/api/` | APIs |

---

## 2. Open These URL Modules First

Use URL modules before broad searching.

| Surface | Open First |
|--------|------------|
| Scan | `wms/scan_urls.py` |
| Portal | `wms/portal_urls.py` |
| Volunteer | `wms/volunteer_urls.py` |
| Planning | `wms/planning_urls.py` |
| API | `api/v1/urls.py` |

---

## 3. Runtime Layering

Follow request flow in this order:

1. `urls.py`
2. route target in `views_*`
3. handlers / helpers / services
4. models / domain modules
5. templates / static assets
6. tests

### Important Notes

- `wms/views.py` is largely a compatibility / re-export facade.
- Do not assume core logic lives there.
- Nearest tests often explain intended behavior faster than code archaeology.

---

## 4. Current Production Reality

Active delivery surface remains primarily:

- legacy Django views
- templates
- existing routes
- shared model layer

Prefer safe incremental improvements over structural rewrites.

---

## 5. Preferred Structural Targets

Use these directories when extracting or centralizing logic.

### `wms/application/`

Use-cases, shared query composition, mutations.

### `wms/policies/`

Business rules, classifications, thresholds, labels.

### `wms/events/`

Explicit side effects and domain events.

### `wms/jobs/`

Operational runtime jobs replacing hidden command sprawl.

### `wms/parties/`

Shipment-party graph, recipients, sync, reconciliation.

### `wms/artifacts/`

Planning documents, proofs, attachments, generated outputs.

---

## 6. Main Runtime Clusters

### Scan / Staff

Primary internal operational surface.

Open first:

- `wms/scan_urls.py`
- `wms/views_scan_stock.py`
- `wms/views_scan_shipments.py`
- `wms/views_scan_shipments_support.py`
- `wms/views_scan_receipts.py`
- `wms/views_scan_orders.py`
- `wms/views_scan_admin.py`
- `wms/views_scan_dashboard.py`
- `wms/views_scan_billing.py`
- `wms/views_scan_misc.py`
- `wms/views_scan_preparation.py`
- `templates/scan/`
- `wms/static/scan/`
- `wms/tests/views/`

Used for:

- stock
- shipments
- receipts
- preparation
- billing
- printing
- settings

#### Scan Asset Contract

Stable public entrypoints remain:

- `wms/static/scan/scan.js`
- `wms/static/scan/scan.css`
- `wms/static/scan/scan-bootstrap.css`

Modular slices may exist under:

- `wms/static/scan/modules/`
- `wms/static/scan/css/partials/`

Treat shared asset changes carefully.

### Portal / Partner Associations

Open first:

- `wms/portal_urls.py`
- `wms/views_portal_auth.py`
- `wms/views_portal_account.py`
- `wms/views_portal_orders.py`
- `wms/views_portal_billing.py`
- `wms/portal_recipient_sync.py`
- `templates/portal/`
- `wms/tests/portal/`

Shared extracted mutation/query sources may include:

- `wms/application/portal/account_use_cases.py`
- `wms/application/portal/order_use_cases.py`
- `wms/application/portal/recipient_resolution.py`
- `wms/application/portal/dashboard_queries.py`

### Volunteer

Open first:

- `wms/volunteer_urls.py`
- `wms/views_volunteer_auth.py`
- `wms/views_volunteer.py`
- `wms/views_volunteer_account_request.py`
- `templates/benevole/`

### Planning

Open first:

- `wms/planning_urls.py`
- `wms/views_planning.py`
- `wms/models_domain/planning.py`
- `wms/planning/*`
- `templates/planning/`
- `wms/tests/planning/`

Primary surfaces:

- run list
- run detail
- version detail

### API

Open first:

- `api/urls.py`
- `api/v1/urls.py`
- `api/v1/views.py`
- `api/v1/ui_views.py`
- serializers / routers
- `api/tests/`

---

## 7. Data And Domain Sources

Default import compatibility facade:

- `wms/models.py`

Extracted domain modules include:

- `catalog.py`
- `inventory.py`
- `shipment.py`
- `shipment_parties.py`
- `portal.py`
- `planning.py`
- `preparation.py`
- `billing.py`
- `integration.py`
- `references.py`
- `volunteer.py`

Check real repo structure before changing imports.

---

## 8. Critical Precision Notes

### Shipment Parties / Recipients

Primary sources:

- `wms/shipment_party_registry.py`
- `wms/shipment_party_setup.py`
- `wms/shipment_party_rules.py`
- `wms/portal_recipient_sync.py`

Newer target boundary:

- `wms/parties/`

Live extracted application entrypoint:

- `wms/application/parties/use_cases.py`

#### Important Invariant

`ShipmentRecipientOrganization` is scoped by:

`(organization, destination)`

not globally by organization.

Destination-aware lookups are the expected contract.

### Preparation / Warehouse Runs

Primary sources:

- `wms/models_domain/preparation.py`
- `wms/preparation/*`
- `wms/views_scan_preparation.py`

#### Important Invariant

Accepted proposals convert into real shipments through:

- `wms/preparation/conversion.py`

Conversion creates shipments in:

`ShipmentStatus.PICKING`

not:

`PACKED`

#### Planning Invariant

`wms/planning/sources.py` must continue excluding `PICKING`
until explicit dossier-ready confirmation promotes shipment to `PACKED`.

Breaking this risks planning pollution.

### Shared UI

Primary sources:

- `wms/templatetags/wms_ui.py`
- `templates/wms/components/`
- `templates/scan/ui_lab.html`

### Notifications / Side Effects

Primary sources:

- `wms/signals.py`
- `wms/services.py`

Preferred long-term boundaries:

- `wms/events/`
- `wms/jobs/`

---

## 9. High-Risk Functional Areas

Use extra caution when touching:

- shipment statuses
- stock movements
- carton lifecycle
- permissions
- recipient sync
- planning source selection
- document generation
- shared scan assets
- emails / notifications
- destructive admin actions

Prefer tests first.

---

## 10. Open These First By Change Type

### Scan flow

Open:

- `wms/scan_urls.py`
- relevant `wms/views_scan_*`
- nearest handlers
- `templates/scan/`
- `wms/tests/views/`

### Portal flow

Open:

- `wms/portal_urls.py`
- `wms/views_portal_*`
- `wms/portal_recipient_sync.py`
- `templates/portal/`
- `wms/tests/portal/`

### Shipment-party / contacts

Open:

- shipment party modules
- `wms/parties/*`
- `wms/shipment_party_*`
- related tests

### Preparation runs

Open:

- preparation modules
- `wms/preparation/*`
- preparation tests

### Planning artifacts

Open:

- `wms/planning/*`
- `wms/artifacts/*`
- planning tests

### Print / documents

Open:

- document handlers
- `templates/print/`
- print tests

### Shared UI

Open:

- template tags
- components
- shared CSS / JS

### Release / operations

Open:

- `docs/operations.md`
- `docs/release_checklist.md`

---

## 11. Tests As Runtime Maps

Nearest tests often explain intended behavior fastest.

Main clusters:

- `wms/tests/views/`
- `wms/tests/portal/`
- `wms/tests/shipment/`
- `wms/tests/emailing/`
- `wms/tests/planning/`
- `wms/tests/core/`
- `api/tests/`

---

## 12. Legacy vs Preferred Rule

If feature already works in legacy flow:

- preserve behavior first
- extract gradually
- do not rewrite whole surface

If new shared logic is needed:

- prefer `application/`
- prefer `policies/`
- prefer explicit boundaries

---

## 13. Final Rule

When lost:

1. Find route
2. Find view
3. Find tests
4. Find invariant
5. Make smallest safe change
