# Portal And Shipment-Party Contracts

Read this file when touching portal access, recipient sync, shipment-party graph, portal account requests, product preferences, or portal order creation.

---

## Shipment-Party And Portal Recipient Contract

### Primary runtime sources

- `wms/models_domain/portal.py`
- `wms/models_domain/shipment_parties.py`
- `wms/portal_access.py`
- `wms/portal_recipient_sync.py`
- `wms/views_portal_auth.py`
- `wms/portal_urls.py`
- `wms/shipment_party_registry.py`
- `wms/shipment_party_setup.py`
- `wms/shipment_party_rules.py`
- `wms/view_permissions.py`
- `wms/scan_admin_contacts_cockpit.py`
- `wms/parties/*`
- `wms/application/parties/use_cases.py`

### Current contract

- Portal recipient changes affect operational contacts.
- Operational contacts affect shipment selectors.
- Admin contact tools can repair or reshape the same graph.
- `PortalAccessGrant` grants one active scope per row: `ShipmentShipper` or `ShipmentRecipientOrganization`.
- `wms/portal_access.py` prefers explicit active grants and falls back to legacy `AssociationProfile` only when no explicit grant exists.
- One scope auto-activates; multiple scopes require `/portal/scope-select/`.
- `PortalOnboardingPreference` is scoped by user, role, and one active shipper / recipient organization / legacy association profile.
- Portal onboarding session state suppresses repeat display only inside the current session; unchecking the tutorial checkbox disables future automatic display for that scope only.
- `/portal/` branches by active scope: shipper cockpit or recipient home.
- Recipient maintenance lives at `/portal/`, `/portal/recipient/profile/`, `/portal/recipient/preferences/`, and mirrored UI API endpoints.
- `rebuild_recipient_party_graph --dry-run|--apply` repairs grants and stale projections.

### Maintenance rule

- Never treat portal recipient edits as pure presentation changes.
- Verify sync, authorizations, default contacts, and scan selectors.
- Keep access grants, fallback profile, scope select, portal guards, and recipient graph aligned.

---

## Account Request And Review Contracts

### Primary runtime sources

- `wms/account_request_handlers.py`
- `wms/admin_account_request_approval.py`
- `wms/views_scan_account_validations.py`
- `wms/forms_scan_account_validations.py`
- `wms/account_request_review_service.py`
- `wms/default_shipper_bindings.py`
- related templates and email templates

### Current contract

- Account requests support `shipper`, `recipient`, and `user`.
- Legacy `association` remains shipper-equivalent.
- Recipient requests carry exactly one destination.
- Recipient approval creates/reactivates organization contact, destination-scoped recipient organization, active recipient contact, and `PortalAccessGrant(recipient_admin)`.
- Default ASF shipper binding is resolved through shared helper.
- Public account review is scan-first; admin is fallback.
- `requested_account_type` preserves original request when operator changes final type.
- `review_snapshot` stores reviewed approval payload.

### Maintenance rule

- If account request fields, types, approval flow, emails, or provisioning change, update public form, scan review, approval path, portal access tests, and docs.

---

## Recipient Validation Contract

### Primary runtime sources

- `wms/views_scan_account_validations.py`
- `wms/admin_contacts_crud.py`
- `wms/admin_contacts_contact_service.py`
- recipient validation templates
- `templates/scan/includes/admin_contacts_contact_form.html`

### Current contract

- `/scan/contacts/validations/recipients/` is dedicated recipient validation queue.
- Access is limited to superusers.
- Detail page reuses shared admin contact form.
- Duplicate candidates stay scoped by shipment-party type first.
- Recipient candidates are destination-aware.
- `asf_id` is organization-owned and must not be copied onto referent person.
- Duplicate actions keep distinct semantics: merge, replace, duplicate.

### Maintenance rule

- If recipient validation changes, update validation hub, list/detail templates, shared form/service, scan nav/banner contract, and tests.

---

## Parties Boundary Contract

### Primary runtime sources

- `wms/parties/selectors.py`
- `wms/parties/invariants.py`
- `wms/parties/sync.py`
- `wms/parties/projections.py`
- `wms/parties/merge.py`
- `wms/application/parties/use_cases.py`
- compatibility adapters

### Current contract

- `wms/parties/selectors.py` owns validated/active selectors.
- `wms/parties/invariants.py` owns destination-scope checks.
- `wms/parties/sync.py` owns portal-recipient sync orchestration.
- `wms/parties/projections.py` owns legacy projection refresh.
- `wms/parties/merge.py` owns graph merge runtime.
- `ShipmentRecipientOrganization` is scoped by `(organization, destination)`.
- Organization-only runtime assumptions are invalid.
- Compatibility adapters stay thin.

### Maintenance rule

- If graph orchestration changes, update `wms/parties/*` or `wms/application/parties/use_cases.py` first.
- Use destination-aware helpers or explicit `(organization, destination)` filters.
- Do not reintroduce selector duplication.

---

## Recipient Product Preference Contract

### Primary runtime sources

- `wms/models_domain/shipment_parties.py`
- `wms/recipient_product_preferences.py`
- portal/account views
- scan/admin/shipment views
- `wms/static/scan/scan.js`

### Current contract

- Preferences attach to `ShipmentRecipientOrganization`.
- Persisted statuses: `requested`, `allowed`, `refused`.
- `unspecified` remains implicit.
- `requested` and `allowed` require quantity and period.
- `refused` forbids quantity and period.
- Overrides are append-only journaling.
- Category-level `requested`/`allowed` supported; category-level `refused` invalid.
- Portal product preference tables submit changed lines in one batch action; server validation is all-or-nothing and must preserve row input/errors on rejection.
- Scan shipment create/edit blocks only explicit `refused` products and records overrides.

### Maintenance rule

- If preference semantics change, update model validation, helper, portal/admin surfaces, scan metadata/JS, and tests.
- Keep `unspecified` implicit.
- Keep portal batch-save behavior aligned between recipient scope and shipper recipient-detail pages.

---

## Portal Dashboard And Mutation Contracts

### Primary runtime sources

- `wms/application/portal/dashboard_queries.py`
- `wms/application/portal/account_use_cases.py`
- `wms/application/portal/order_use_cases.py`
- `wms/application/portal/recipient_resolution.py`
- portal views
- `api/v1/ui_views.py`

### Current contract

- Portal dashboard and recipient home composition live in shared query helpers.
- UI API returns `mode="shipper"` or `mode="recipient"`.
- `Date d'expédition` stays empty until real `BOARDING_OK`.
- Portal account writes use `save_portal_account_profile(...)`.
- Order destination resolution uses shared helpers.
- `submit_portal_order(...)` is shared submission entrypoint.
- HTML and UI API adapters stay thin.

### Maintenance rule

- If dashboard, account, destination, recipient, or order semantics change, update shared helper first, then HTML/API adapters and tests.

---

## Portal Order-Create Workflow Contract

### Primary runtime sources

- `wms/views_portal_orders.py`
- `templates/portal/order_create.html`
- portal order-create includes

### Current contract

- `/portal/orders/new/` is progressive four-step flow:
  - choose route
  - choose parcel source
  - compose order
  - review and submit
- Fulfillment/review hidden until destination and recipient are selected.
- Server validation with valid route keeps later steps open.
- Shipper-inbound checkbox remains compatibility entrypoint.
- Pickup requests may snapshot optional opening weekdays on `OrderInboundDelivery` and reusable pickup address entries.
- Shipper-prepared parcels require ASF parcel-guideline certification; pickup requests also require declared pallet count.
- When shipper-prepared parcels are selected, stock ASF selection is opt-in and ignored server-side unless the stock-completion checkbox is checked.
- Review displays a read-only shipping type derived from inbound mode and stock-completion intent: Stock ASF, Dépôt, Dépôt + Stock ASF, Enlèvement, or Enlèvement + Stock ASF.
- Review card is only primary submit surface.

### Maintenance rule

- If route/inbound/ready-carton/unit-product semantics change, align views, includes, tests, and optional smoke tests.
