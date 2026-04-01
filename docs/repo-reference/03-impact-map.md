# Impact Map

This file is the day-to-day propagation checklist.

Use it when you add, modify, or remove a feature and need to answer:

- where else does the same rule probably exist?
- what docs should move with this change?
- which tests are the minimum proof that I did not miss a side effect?

## 1. Change On A Scan Page

Always check:

- `wms/scan_urls.py`
- `wms/views.py`
- the matching `wms/views_scan_*.py` module
- the matching shared query or use-case module under `wms/application/scan/` when the page is mirrored elsewhere
- the nearest `*_handlers.py` module
- the matching template in `templates/scan/`
- scan static assets in `wms/static/scan/` if behavior is JS/CSS driven
- scan view tests in `wms/tests/views/`

Ask yourself:

- does the same rule exist in the UI API under `api/v1/ui/`?
- if the HTML page and UI API mirror the same cockpit, should both adapters read the same `wms/application/*` payload instead of recomposing the data separately?
- if this is a carton-list change, does `scan_carton_edit` still carry the operational actions and lock states?
- does the same operation appear in print/document endpoints?
- if bulk carton actions or grouped documents change, do `scan_carton_picking`, `scan_cartons_picking`, `scan_carton_document`, and grouped bundle routes still match?
- does release smoke mention this user path?
- did the business sequence or wording in `docs/mvp_spec.md` change?

## 2. Change On A Portal Page

Always check:

- `wms/portal_urls.py`
- `wms/views.py`
- `wms/views_portal_*.py`
- `wms/portal_order_handlers.py` or `wms/portal_recipient_sync.py` when data moves downstream
- matching templates in `templates/portal/`
- portal tests in `wms/tests/portal/` and `wms/tests/views/tests_portal_bootstrap_ui.py`

Ask yourself:

- does the same feature exist in the portal UI API?
- does this field feed shipment-party eligibility or contact sync?
- does portal permission logic in `wms/view_permissions.py` need the same update?
- does a nominal post-deploy smoke step need to change?

## 3. Change To Shipment Creation / Edit / Tracking / Close

Always check:

- `wms/views_scan_shipments.py`
- `wms/views_scan_shipments_support.py`
- `wms/scan_shipment_handlers.py`
- `wms/shipment_tracking_handlers.py`
- `wms/carton_handlers.py`
- `wms/services.py`
- `api/v1/ui_views.py`
- `templates/scan/` shipment-related templates

Ask yourself:

- does draft behavior still match `EXP-TEMP-XX` expectations?
- do carton state transitions still agree with shipment state transitions?
- do tracking and close endpoints still expose the same availability rules?
- do `docs/mvp_spec.md`, `docs/operations.md`, and `docs/release_checklist.md` still describe reality?

Run or inspect first:

- `api/tests/tests_ui_e2e_workflows.py`
- `wms/tests/core/tests_flow.py`
- nearest scan shipment view tests

## 4. Change To Portal Recipient / Contact Sync / Shipment-Party Rules

Always check:

- `wms/portal_recipient_sync.py`
- `wms/models_domain/portal.py`
- `wms/models_domain/shipment_parties.py`
- `wms/shipment_party_registry.py`
- `wms/shipment_party_setup.py`
- `wms/shipment_party_rules.py`
- `wms/view_permissions.py`
- `wms/scan_admin_contacts_cockpit.py`
- `wms/admin_contacts_merge_service.py` when recipient organizations can be merged or deduplicated
- `wms/views_scan_admin.py` and `templates/scan/includes/admin_contacts_contact_form.html` when admin must review the same recipient data

Ask yourself:

- will scan shipment forms now show different shippers, recipients, or correspondents?
- does a portal change also require an admin contacts cockpit change?
- do structure compliance fields or uploaded recipient documents also need to appear on `scan/contacts`?
- do linked/default authorizations still stay unique and active?
- can admin merge flows preserve or deduplicate the same recipient compliance documents without losing them?
- are existing portal tests still the right contract, or did the business rule itself change?

Run or inspect first:

- `wms/tests/portal/tests_portal_recipient_sync.py`
- `wms/tests/portal/tests_portal_shipment_parties.py`
- `wms/tests/views/tests_views_scan_admin_shipment_parties.py`
- `wms/tests/views/tests_views_scan_admin.py`
- `wms/tests/scan/tests_admin_contacts_merge_service.py`

## 5. Change To Email / Notification Logic

Always check:

- `wms/emailing.py`
- `wms/signals.py`
- `wms/account_request_handlers.py`
- `wms/admin_account_request_approval.py`
- `wms/public_order_handlers.py`
- `wms/order_notifications.py`
- `wms/models_domain/integration.py`
- `wms/management/commands/process_email_queue.py`
- `docs/email_flows_target_matrix_2026-02-20.md`
- `docs/operations.md`

Ask yourself:

- is the producer changing, or only the queue transport?
- are recipient groups, env vars, or retry semantics changing?
- do release or runtime checks now need different wording?
- does a signal side effect impact admin, public, portal, shipment, or volunteer flows too?

Run or inspect first:

- `wms/tests/emailing/`
- `wms/tests/admin/tests_account_request_handlers.py`
- any nearest producer tests in `wms/tests/public/`, `wms/tests/portal/`, or `wms/tests/views/`

## 6. Change To Print / Document / Label Behavior

Always check:

- `wms/shipment_document_handlers.py`
- `wms/billing_document_handlers.py`
- scan print views re-exported by `wms/views.py`
- `templates/print/`
- `templates/scan/print_template_*`
- `api/v1/ui_views.py` template or document endpoints
- admin actions if the same print entry point exists there

Ask yourself:

- is the same document reachable from scan, admin, and API?
- does the print-template editor still expose the current contract?
- do bundle/view/export routes all need the same adjustment?
- does this change distinguish between the continuous-roll `carton_lists` action page and the direct printable `carton_lists_a4` A4 surface?

Run or inspect first:

- print and shipment document tests under `wms/tests/print/`, `wms/tests/shipment/`, `wms/tests/admin/`
- `api/tests/tests_ui_e2e_workflows.py` if the workflow is user-visible end-to-end

## 7. Change To Shared UI Primitives Or Shared Classes

Always check:

- `wms/templatetags/wms_ui.py`
- `templates/wms/components/`
- `templates/scan/ui_lab.html`
- `wms/static/scan/scan-bootstrap.css`
- `wms/static/portal/portal-bootstrap.css`
- `wms/static/wms/admin-bootstrap.css`
- scan/portal/benevole templates using the same primitive

Ask yourself:

- is this a local page pattern or a shared contract?
- does the same primitive exist on `scan`, `portal`, `admin`, and `benevole`?
- does the UI Lab still document the current contract?
- do the governance docs still match the implementation?

Run or inspect first:

- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`

## 8. Change To API UI Payloads Or Endpoints

Always check:

- `api/v1/urls.py`
- `api/v1/ui_views.py`
- the mirrored shared query or use-case module under `wms/application/`
- any matching HTML surface under `wms/views_scan_*` or `wms/views_portal_*`
- `api/tests/`

Ask yourself:

- is the API mirroring an existing legacy page or becoming the de facto contract?
- do HTML and API still agree on validation, permissions, and sequencing?
- does the shared application payload need to change first so both adapters stay aligned?
- does the release smoke subset still name the right test?

Run or inspect first:

- `api/tests/tests_ui_e2e_workflows.py`
- nearest `api/tests/tests_ui_endpoints.py` or feature-specific API tests

## 9. Change To Planning Flow

Always check:

- `wms/planning_urls.py`
- `wms/views_planning.py`
- `wms/models_domain/planning.py`
- the matching module in `wms/planning/`
- planning commands under `wms/management/commands/`
- `docs/operations.md`
- `docs/release_checklist.md`

Ask yourself:

- does the seeded smoke flow still reach solve, publish, draft generation, export, and cockpit view?
- did artifact names or visibility change?
- should the post-deploy conditional smoke wording change?

Run or inspect first:

- `wms/tests/planning/tests_smoke_planning_flow.py`
- nearest planning output or communication tests

## 10. Questions To Ask Automatically During Maintenance

When adding a feature on page `YY`, ask:

- does the same rule exist in scan HTML, portal HTML, admin, volunteer, or UI API?
- does a shared handler, service, signal, or registry already define this behavior elsewhere?
- does a shared template-tag or shared CSS contract already exist for this UI?
- does the release smoke checklist mention this user journey?
- does `docs/mvp_spec.md` or a domain matrix now need an update?
- which living reference test is the quickest proof that the repo-wide contract is still true?
