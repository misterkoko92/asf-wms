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
- `ui-number-input`
- `ui-comp-card`
- `ui-comp-panel`
- `ui-comp-actions`
- shared select contract (`form-select` + `ui-select--sm|md|lg|xl`)
- shared masthead history navigation include (`templates/includes/history_nav_buttons.html`)

Surfaces that already reuse these contracts:

- `templates/scan/`
- `templates/portal/`
- `templates/planning/`
- `templates/benevole/`
- custom admin templates
- `templates/scan/ui_lab.html`

Maintenance rule:

- if a primitive changes semantics, update the UI Lab and bootstrap regression tests
- if the shared select contract changes, keep `wms/view_utils.py`, Django form/widget sorting, and scan/portal/planning/benevole select templates aligned in the same work
- if the shared masthead history navigation changes, keep scan/portal/planning/benevole shells aligned in the same work
- if a pattern is still local, do not prematurely promote it into a shared primitive

Reference tests:

- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`
- `wms/tests/views/tests_views_planning.py`
- `wms/tests/views/tests_views_volunteer.py`
- `wms/tests/views/tests_views_imports.py`

### Scan Sidebar Navigation Contract

Primary runtime sources:

- `templates/scan/includes/scan_sidebar_navigation.html`
- `templates/scan/base.html`
- `wms/views_scan_*.py` via their `active` context key

Current contract:

- preparateur-only scan users keep a reduced sidebar with direct links to:
  - `Préparation`
  - `Runs magasin`
- the legacy scan sidebar remains group-based for non-preparateur staff: `Stocks`, `Réception`,
  `Préparation`, `Expéditions`, `Contacts`, `Gestion`
- the shared `Contacts` group currently exposes, in order:
  - `Répertoire` for superusers
  - `Rôles expédition` for superusers
  - `Validations` for users allowed by `user_can_review_account_requests()`
- the shared `Stocks` group currently exposes, in order:
  - `Vue Stock`
  - `Vue Besoins`
  - `Vue Kits`
  - `Vue Colis`
  - `Vue Commande`
  - `Vue Réception`
  - `MAJ stock`
- the shared `Préparation` group currently exposes, in order:
  - `Préparer des kits`
  - `Préparer des colis`
  - `Préparation expédition`
  - `Runs magasin`
- the shared `Réception` group currently exposes, in order:
  - `Réception palette`
  - `Listing`
  - `Réception association`
- the shared `Gestion` group is reduced to transversal operations such as planning and billing; it
  no longer hosts contact-management or validation entry points
- `/scan/receive-pallet/` is now the manual pallet-only screen and keeps a shortcut toward
  `/scan/receive-listing/`; file-upload contracts for listing imports must stay on the dedicated
  listing route
- the recipient-needs cockpit at `/scan/recipient-needs/` must set `active="recipient_needs"`
  so the shared `Stocks` group expands and highlights correctly
- warehouse-preparation screens under `/scan/preparation-runs/` must set `active="preparation_runs"` so the shared group expands and highlights correctly
- the warehouse-preparation settings screen at `/scan/preparation-runs/settings/` uses the same
  `active="preparation_runs"` highlight and preparateur permission scope as the list/create/detail flow
- the scan shell pending-recipient banner in `templates/scan/base.html` must link to
  `/scan/contacts/validations/recipients/` for superusers; recipient validation no longer lives on
  the contacts directory

Maintenance rule:

- if a scan sidebar entry is added, removed, renamed, or moved between groups, update the shared include, the relevant scan view `active` keys, the bootstrap regression tests, and this repo-reference section in the same work
- do not introduce page-local navigation copies for warehouse-preparation flows; the shared scan sidebar remains the operator entry point

Reference tests:

- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/views/tests_views_scan_preparation.py`

### Public Account Review Contract

Primary runtime sources:

- `wms/views_scan_account_validations.py`
- `wms/forms_scan_account_validations.py`
- `wms/admin_account_request_approval.py`
- `wms/account_request_review_service.py`
- `wms/models_domain/portal.py`
- `templates/scan/contact_validations_hub.html`
- `templates/scan/account_validation_list.html`
- `templates/scan/account_validation_detail.html`
- `templates/scan/includes/account_validation_request_summary.html`
- `templates/scan/includes/account_validation_review_form.html`
- `wms/admin.py`

Current contract:

- `/scan/contacts/validations/` is the operator entry point for contact-related validation work
- `/scan/account-validations/` is the dedicated `Validation expéditeurs` queue for pending
  `PublicAccountRequest` rows
- access is granted to superusers and staff in the configured validation group via
  `user_can_review_account_requests()` and `scan_account_validator_required`
- the detail page can approve a request with a final type different from the original signup type,
  especially `shipper -> recipient`
- `PublicAccountRequest.account_type` keeps the final operative type used for provisioning and
  access emails
- `PublicAccountRequest.requested_account_type` preserves the original requested type when the
  operator changes it during review
- `PublicAccountRequest.review_snapshot` stores the reviewed approval payload, including the final
  type and recipient-completion fields
- Django admin remains a minimal fallback: it exposes `destination` and a readonly link back to the
  scan review detail, but the operational correction workflow lives on the scan page

### Recipient Validation Contract

Primary runtime sources:

- `wms/views_scan_account_validations.py`
- `wms/admin_contacts_crud.py`
- `wms/admin_contacts_contact_service.py`
- `templates/scan/contact_validations_hub.html`
- `templates/scan/recipient_validation_list.html`
- `templates/scan/recipient_validation_detail.html`
- `templates/scan/includes/admin_contacts_contact_form.html`

Current contract:

- `/scan/contacts/validations/recipients/` is the dedicated `Validation destinataires` queue for
  pending `ShipmentRecipientOrganization` rows
- access is limited to superusers via `scan_staff_required` plus `_require_superuser()`
- `/scan/contacts/validations/recipients/<id>/` acts as a validation dossier and reuses the shared
  admin contact form instead of exposing recipient validation inline on the contacts directory
- recipient validation must keep using the same `ACTION_SAVE_CONTACT` submission path and runtime
  recipient shared-profile update semantics as scan/admin contact edits
- structure compliance fields, uploaded recipient documents, and allowed shipper context shown on
  the validation dossier must stay aligned with the shared recipient data model and write path

Maintenance rule:

- if recipient validation routes, labels, or write semantics change, update the validation hub,
  recipient list/detail templates, the admin contact shared form/service, the scan banner/nav
  contract, and the regression tests in the same work

Maintenance rule:

- if the public account review flow changes, keep the scan views/forms/templates, the shared
  approval path, the validator permission helper, the scan nav/banner contract, and the admin
  fallback link aligned in the same work
- if the approval payload or corrected-type semantics change, update the portal/party tests and
  repo-reference text in the same work

Reference tests:

- `wms/tests/views/tests_views_scan_account_validations.py`
- `wms/tests/views/tests_views_scan_contact_validations.py`
- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/portal/tests_portal_role_review_gate.py`
- `wms/tests/admin/tests_account_request_handlers.py`

### Scan Recipient Needs Priority Contract

Primary runtime sources:

- `wms/application/scan/recipient_needs_queries.py`
- `wms/views_scan_stock.py`
- `templates/scan/recipient_needs_view.html`
- `wms/recipient_product_preferences.py`
- `wms/runtime_settings.py`

Current contract:

- `/scan/recipient-needs/` lives in the scan `Stocks` family as a read-oriented synthesis view for
  recipient demand and expedition prioritization
- filters are `destination`, `recipient`, `category`, `need_status`, and `priority`
- one row represents one `(ShipmentRecipientOrganization, Product)` pair
- rows are materialized only from explicit product preferences and products covered by explicit
  category preferences; the view does not enumerate the full catalog for implicit `unspecified`
  preferences
- each row shows the linked shipper labels for that recipient organization, the target / delivered /
  pipeline / remaining quantities, stock availability for the current demand, the current period
  label, and the current deadline or shipment delay
- priority levels are `critical`, `high`, `normal`, `covered`, and `out_of_scope`
- operator-facing priority help must stay hoverable on the badge via Bootstrap tooltip markup and
  describe the threshold that triggered the level
- stock availability is rendered as `available / required` with operator-facing color thresholds:
  `<25%` danger, `25%..<75%` warning, `>=75%` ready
- the table supports per-row and bulk `Préparer` actions, but they must stay as a handoff into the
  existing shipment-create form rather than silently creating final cartons
- bulk prepare is only valid when all selected rows share the same destination, shipper contact,
  and recipient contact; otherwise the action must reject with an operator-visible error
- `critical` is driven by an expired period or an open shipment whose delay exceeds the runtime
  `tracking_alert_hours` SLA threshold
- default ordering is priority rank, then strongest delay, then nearest period deadline, then
  highest remaining need

Maintenance rule:

- if recipient-needs filters, priority rules, row materialization, or tooltip wording changes,
  keep the shared query helper, the scan view/template, the sidebar highlight contract, and the
  dedicated query/UI tests aligned in the same work
- if a future UI API or pilotage surface mirrors the same cockpit, promote the composition to the
  shared query helper rather than duplicating row/priority logic in each adapter

Reference tests:

- `wms/tests/core/tests_scan_recipient_needs_queries.py`
- `wms/tests/views/tests_views_scan_stock.py`
- `wms/tests/views/tests_scan_bootstrap_ui.py`

### Shared Select Contract

Primary runtime sources:

- `wms/view_utils.py`
- `wms/forms.py`
- `wms/static/scan/scan-bootstrap.css`
- `templates/scan/ui_lab.html`
- manual select templates under `templates/scan/`, `templates/portal/`, `templates/planning/`, `templates/benevole/`

Current contract:

- selects use native `<select>` controls with `form-select`
- fixed-width sizing uses `ui-select--sm`, `ui-select--md`, `ui-select--lg`, or `ui-select--xl`
- the right-side caret is provided by shared CSS with extra right padding so labels never overlap it
- select widths stay stable and do not resize based on the selected label
- default ordering is alphabetical by rendered label
- placeholder options such as `---------` stay at the top
- grouped choices keep their group structure while sorting the options inside each group
- explicit per-select exceptions are allowed when business order matters; `scan/pack`
  uses descending shipment references with labels formatted as `REFERENCE - IATA`
- warehouse-preparation create/config screens keep native selects and use `ui-select--lg` for the
  parameter-set picker and `ui-select--xl` for shipper/destination multi-select scopes

Maintenance rule:

- when changing select ordering or sizing, update both the backend choice builders and the rendered template/widget classes in the same work
- keep documented exceptions explicit and local; do not silently drift into mixed ordering rules

### Shared Number Input Contract

Primary runtime sources:

- `wms/static/scan/modules/core.js`
- `wms/static/scan/scan-bootstrap.css`
- `templates/scan/ui_lab.html`
- `templates/scan/base.html`
- `templates/portal/base.html`
- `templates/planning/base.html`
- `templates/benevole/base.html`
- standalone benevole auth templates that do not extend `benevole/base.html`

Current contract:

- eligible legacy `input[type="number"]` controls can be progressively enhanced into the shared `ui-number-input` wrapper
- the shared control renders compact decrement/increment buttons on the left side of the field
- the shared control geometry is driven by shared CSS variables for button size, spacing, inset, and reserved value offset
- the core runtime synchronizes the input left padding from the rendered control width and shared spacing tokens so values never overlap the buttons even when stylesheet cascade differs by browser
- tight contexts can opt into the compact shared sizing variant with `ui-number-input-compact`; the core runtime promotes that marker to the wrapper contract
- the runtime enhancement respects native `min`, `max`, `step`, `disabled`, and `readonly` semantics
- the enhancement dispatches native-feeling `input` and `change` events after button clicks so existing page logic keeps reacting to quantity changes
- page-level horizontal drift stays clipped in the shared legacy shell; any required horizontal movement must live inside an explicit local wrapper such as `scan-table-wrap table-responsive`
- page-local exceptions can opt out with `data-ui-number-input-optout="1"` or `ui-number-input-optout`

Maintenance rule:

- if the shared number-input behavior changes, keep the shared JS, shared CSS, base template script includes, UI Lab contract example, and runtime tests aligned in the same work
- do not reintroduce browser-specific spinner styling as the primary contract; the shared left-side controls are now the repository default for enhanced legacy number inputs

Reference tests:

- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`
- `wms/tests/views/tests_views_planning.py`
- `wms/tests/views/tests_views_volunteer.py`
- `wms/tests/core/tests_ui.py`

### Receipt Conformity Contract

Primary runtime sources:

- `wms/models_domain/inventory.py`
- `wms/forms.py`
- `wms/receipt_pallet_handlers.py`
- `wms/receipt_handlers.py`
- `templates/scan/includes/receive_pallet_create_card.html`
- `templates/scan/includes/receive_association_create_card.html`

Current contract:

- `Receipt` persists `conformity_status` and keeps `unknown` for legacy rows that predate this capture
- `/scan/receive-pallet/` stores the operator observation in `Receipt.notes`
- `/scan/receive-listing/` owns the file-import contract for listing reception and now starts with
  a dedicated intake card:
  operators must choose the file type first (`CSV`, `Excel`, `PDF`, sorted A-Z) and must
  link the import to an existing pallet receipt through a reverse-chronological select
  labelled as `date - palette count - donor - carrier`
- the intake card keeps an explicit warning that reception linking is mandatory and exposes a
  `Créer une réception` shortcut back to `/scan/receive-pallet/`; the listing route no longer owns
  an inline receipt-draft form
- the listing route must resume on the active step after reload: upload card after intake
  validation, PDF analysis after PDF upload, mapping after extraction, assisted suggestions after
  mapping when proposals exist, review after suggestion handling, and the incomplete-products recap
  after final confirmation when incomplete products were created
- Excel/CSV still enter direct mapping/review, while PDF first persists an analysis payload
  (`total_pages`, page diagnostics, extraction strategy, preview text, and recommended
  `all`/`detected`/manual page selection) before the operator triggers mapping
- the assisted suggestion contract now lives in its own dedicated step before the review table:
  exact EAN may preselect an existing product, `Match auto EAN` badges flag those rows, grouped
  suggestions expose a row preview plus explicit field/confidence metadata, and the step only
  exposes batch `Accepter les propositions sélectionnées` / `Refuser les propositions sélectionnées`
  actions; refused suggestions are only hidden from the current listing session and remain
  available later in `/scan/stock-update/`, while accepted suggestions only fill fields still left
  empty in the current review state
- the review table itself must remain full width, keep the operator audit columns for product
  status, detected match type, and auto-completed fields, and only render product/location columns
  that contain at least one value in the current review state
- listing-created products may persist with `Product.is_incomplete=True`; the same route renders
  the post-confirm recap for the last confirmed import so operators can open one product at a time
  or apply guarded bulk updates to non-identifier fields across multiple incomplete products
- `/scan/stock-update/` reuses the same incomplete-products cockpit contract as the durable
  warehouse-wide remediation surface, with the stock form collapsed by default, the incomplete
  products block open by default, an optional receipt filter using the same pallet receipt label
  contract as Listing, and a persistent suggestions card that can apply brand/category/TVA/default
  location proposals across the currently filtered incomplete products
- listing reception uses a warehouse-local buffer location `TEMP / RECEPTION / LISTING` when a
  listing row and the matched product both lack a usable default location
- listing import quantities are additive: each confirmed row creates a receipt line and stock
  movement instead of replacing existing stock quantities on the matched product
- `/scan/receive-association/` reuses `pickup_charge_comment` as the operator observation field
- when the operator marks a reception non-conform, the observation field becomes mandatory in both forms
- `/scan/receive-association/` may optionally attach the reception to an order inbound delivery; in
  that case the handler must also create one real `Carton` per declared carton with
  `source_kind=shipper_received` and `source_receipt=<receipt>`

Maintenance rule:

- if receipt conformity capture changes, keep the model field, form validation, handler persistence, and scan templates aligned in the same work
- preserve the historical `unknown` state unless a dedicated migration explicitly backfills it for statistics

### Warehouse Preparation Create Contract

Primary runtime sources:

- `wms/forms_preparation.py`
- `wms/views_scan_preparation.py`
- `templates/scan/preparation_run_create.html`
- `templates/scan/preparation_parameter_set_config.html`

Current contract:

- flight-window fields on `/scan/preparation-runs/create/` use native date inputs via `type="date"`
- default operational targets on `/scan/preparation-runs/create/` are `200` colis équivalents, `15` expéditions, taille cible `10`, minimum `8`, maximum `22`
- the default flight window starts on the Monday of `S+1` when the run is launched on Monday/Tuesday/Wednesday, and on the Monday of `S+2` when launched on Thursday/Friday/Saturday/Sunday; the end date defaults to the following Sunday
- shipper and destination scopes expose a `Tout sélectionner` toggle and default to all active options selected on first load
- the parameter set defaults to the last run used by the current operator, then falls back to the latest known/current parameter set
- the create screen keeps a direct operator path to parameter-set configuration without leaving the warehouse-preparation flow
- the parameter-set picker on `/scan/preparation-runs/settings/` reloads automatically on selection change and does not rely on a separate `Ouvrir` submit button
- warehouse-preparation destination rules stay in their own `PreparationDestinationRule` table; they are not the same rows as planning-vols `PlanningDestinationRule`, but blank magasin fields are prefilled from the current planning parameter set when a matching active destination rule exists
- the settings screen explains destination-capacity units through hoverable `title` help on the column headers; weekly/flight capacities are `colis équivalents`, while shipment count is `dossiers d'expédition`
- destination allowed weekdays are edited through a native multi-select widget rather than a free-text token field, and the "all days when empty" rule is documented in the shared column-header tooltip instead of repeated inline help on each row
- the fairness-weight column must expose a hover explanation with a concrete example (`1,20` favors an escale vs `1,00`; `0,80` deprioritizes it)
- if flight acquisition fails and no fallback batch can be used, the create screen must stay on the form, render a non-field error, and avoid leaving a draft run orphaned in the database

Reference tests:

- `wms/tests/views/tests_views_scan_preparation.py`
- `wms/tests/views/tests_scan_bootstrap_ui.py`

### Public Account Request Portal Contract

Primary runtime sources:

- `wms/account_request_handlers.py`
- `wms/admin_account_request_approval.py`
- `wms/models_domain/portal.py`
- `wms/default_shipper_bindings.py`
- `templates/scan/public_account_request.html`
- `templates/emails/account_request_approved.txt`
- `templates/emails/account_request_admin_notification.txt`

Current contract:

- public account requests support `shipper`, `recipient`, and `user`; legacy `association`
  rows stay valid as shipper-equivalent data
- `/portal/request-account/` exposes `Expediteur` and `Destinataire` choices in the HTML form;
  the legacy backend `user` request type remains accepted for compatibility even though it is not
  shown on that page
- recipient requests must carry exactly one `Destination`; shipper requests do not
- approved recipient requests do not create a legacy `AssociationProfile`
- approved recipient requests must create or reactivate:
  - the organization contact
  - the destination-scoped `ShipmentRecipientOrganization`
  - one active `ShipmentRecipientContact`
  - one active `PortalAccessGrant(recipient_admin)`
- recipient approval must also ensure the default ASF shipper binding through the shared
  default-shipper helper path rather than duplicating link logic inside approval code
- the shared default-shipper helper now prefers the canonical ASF organization `Contact.asf_id`
  before falling back to the historical `AVIATION SANS FRONTIERES` display-name match
- if the default ASF shipper cannot be resolved, recipient approval must fail explicitly instead
  of validating a partially usable account

Maintenance rule:

- if public account request fields or account types change, keep the public form, approval flow,
  approval emails, and portal-access provisioning aligned in the same work
- if recipient portal provisioning changes, verify both the approval flow and the portal-login
  scope-resolution behavior, because first-login and password-recovery flows depend on the same
  access graph

Reference tests:

- `wms/tests/admin/tests_account_request_handlers.py`
- `wms/tests/portal/tests_portal_role_review_gate.py`
- `wms/tests/portal/tests_portal_access_grants.py`
- `wms/tests/views/tests_views_portal.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`

### Portal Recipient Product Preference Contract

Primary runtime sources:

- `wms/views_portal_account.py`
- `api/v1/ui_views.py`
- `templates/portal/recipients.html`
- `wms/models_domain/shipment_parties.py`
- `wms/recipient_product_preferences.py`

Current contract:

- the portal recipient edit flow at `/portal/recipients/?edit=<id>` exposes a dedicated
  `Préférences produits du destinataire` section backed by the synced
  `ShipmentRecipientOrganization` row for the same `(organization, destination)` scope
- recipient-scoped portal users keep the summary table on `/portal/` and use
  `/portal/recipient/profile/` for direct maintenance of the active
  `ShipmentRecipientOrganization` shared profile fields, main recipient contact, and structure
  documents
- recipient-scoped portal users keep the summary table on `/portal/` and use
  `/portal/recipient/preferences/` for line-by-line maintenance of the active
  `ShipmentRecipientOrganization` product preferences
- `GET /api/v1/ui/portal/recipients/` and `PATCH /api/v1/ui/portal/recipients/<id>/`
  reuse the same shared runtime recipient scope instead of mutating `AssociationRecipient`
  directly; a `recipient_admin` scope addresses the runtime `ShipmentRecipientOrganization.id`
- portal users can create, edit, and delete recipient product preferences with native
  Bootstrap form controls on the same page as recipient editing; the shipper form is anchored
  with `#recipient-product-preferences`, while the recipient-scoped page exposes the same row
  save semantics plus a dedicated `Supprimer` action for explicit preferences
- portal status labels use operator-facing wording `Demandé`, `Autorisé`, and `Refusé` even
  though the model `TextChoices` labels remain shorter internally
- category-level preferences are allowed for `requested` and `allowed`; category-level
  `refused` remains invalid and must surface a form error instead of being silently accepted
- the portal form keeps separate `product` and `category` scopes and hides quantity/period
  inputs when status is `refused`
- the source of portal-created preferences must be persisted as `RecipientProductPreferenceSource.PORTAL`

Maintenance rule:

- if recipient preference semantics change, keep the portal edit UI, shipment-party validation
  rules, and any preparation-run consumers aligned in the same work
- if recipient-scoped profile maintenance changes, keep `/portal/recipient/profile/`, the
  recipient dashboard summary, runtime shipment-party contacts, and refreshed
  `AssociationRecipient` compatibility projections aligned in the same work
- do not fork a second portal-specific preference model or scope; the portal stays on the shared
  shipment-party preference records

Reference tests:

- `wms/tests/views/tests_views_portal.py`
- `api/tests/tests_ui_endpoints.py`
- `api/tests/tests_ui_e2e_workflows.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`
- `wms/tests/portal/tests_portal_shipment_parties.py`

### V3.3 Legacy Scan Asset Facade Contract

Primary runtime sources:

- `templates/scan/base.html`
- `templates/portal/base.html`
- `templates/planning/base.html`
- `wms/static/scan/scan.js`
- `wms/static/scan/scan.css`
- `wms/static/scan/scan-bootstrap.css`
- `wms/static/scan/modules/`
- `wms/static/scan/css/partials/`

Current V3.3 contract:

- `scan.js`, `scan.css`, and `scan-bootstrap.css` remain the stable shared filenames consumed by scan, portal, planning, and public/auth surfaces
- `templates/scan/base.html` keeps `scan.js` plus `scan/modules/core.js` as the shared scan script facade
- page-local scan scripts now extend the shell through the `extra_scripts` block instead of growing `templates/scan/base.html` directly
- `templates/portal/base.html` and `templates/planning/base.html` keep consuming the stable shared scan CSS entrypoints and expose the same extension block for future page-local scripts
- the first V3.3 script slices now live in `wms/static/scan/modules/core.js`, `dashboard.js`, and `shipments.js`
- the first V3.3 style slices now live in `wms/static/scan/css/partials/foundation.css`, `ops.css`, and `auth-public.css`
- when extracting more JS/CSS, prefer moving code behind these module/partial facades instead of changing the shared entrypoint filenames or inlining more asset tags into templates

Maintenance rule:

- keep `scan.js`, `scan.css`, and `scan-bootstrap.css` present unless the consuming templates and bootstrap regression tests move together
- if a new page-local script is needed on scan, load it through `templates/scan/base.html`'s `extra_scripts` block instead of broadening the shared shell for every page
- if portal or planning still depend on a shared scan stylesheet selector, do not move or rename that selector without checking their templates and bootstrap tests
- when extracting styles, keep the stable entrypoint files as facades and move only clearly scoped concerns into `wms/static/scan/css/partials/`

Reference tests:

- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`
- `wms/tests/views/tests_views_imports.py`

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

### V3.2 Event Contract

Primary runtime sources:

- `wms/events/types.py`
- `wms/events/publishers.py`

Current V3.2 contract:

- `RuntimeEvent` is the base immutable runtime event shape used by the signal bridge and future job/runtime handlers
- the event shape is intentionally short during the first V3.2 slice: `event_type`, `scope_type`, `scope_id`, `payload`
- the first explicit event constants are:
  - `shipment.status_changed`
  - `shipment_tracking.event_created`
  - `order.status_changed`
  - `workflow_projection.refresh_requested`
  - `pilotage.refresh_requested`
  - `planning.artifact_exported`
- publisher helpers own the initial payload normalization and stringification of scope identifiers

Maintenance rule:

- if a new cross-surface runtime side effect is introduced during V3.2, define or update the event contract here before wiring handlers in `wms/signals.py` or `wms/jobs/*`
- do not let signals invent ad-hoc payload dicts once the explicit event contract exists

Reference tests:

- `wms/tests/core/tests_event_types.py`

### V3.2 Durable Outbox Contract

Primary runtime sources:

- `wms/events/outbox.py`
- `wms/emailing.py`
- `wms/document_scan_queue.py`

Current V3.2 contract:

- `enqueue_integration_event(...)` is the explicit helper for durable `IntegrationEvent` creation in the first V3.2 outbox slice
- this slice currently normalizes queue-backed email and document-scan producers without changing their source, target, event_type, payload, or initial status semantics
- producers still own payload construction, while `wms/events/outbox.py` owns persisted row creation

Maintenance rule:

- if a queue-backed producer currently writes `IntegrationEvent.objects.create(...)` directly, decide whether it should move behind `wms/events/outbox.py` before adding more enqueue logic
- do not broaden this helper into a second persistence model during V3.2; the contract is still a normalized boundary over `IntegrationEvent`

Reference tests:

- `wms/tests/emailing/tests_notifications_queue.py`
- `wms/tests/security/tests_document_scan_queue.py`

### V3.2 Operational Job Run Contract

Primary runtime sources:

- `wms/models_domain/integration.py`
- `wms/jobs/runtime_tracking.py`
- `wms/jobs/email_queue.py`
- `wms/jobs/document_scan.py`
- `wms/jobs/print_artifacts.py`
- `wms/jobs/workflow_projection.py`
- `wms/jobs/pilotage.py`

Current V3.2 contract:

- `OperationalJobRun` is the persisted runtime trace for operational job wrappers under `wms/jobs/`
- stable fields in this first slice are `job_key`, `trigger_source`, `status`, `started_at`, `finished_at`, `context_payload`, `result_summary`, `error_summary`
- current stable statuses are `running`, `succeeded`, `failed`
- job wrappers, not management commands, own run persistence
- scalar job results are normalized to `result_summary={"result": ...}`
- structured job results remain JSON summaries, with `date` and datetime-like values normalized through the runtime tracking helper
- job wrappers may now provide a `result_summary_factory` when the persisted summary should stay smaller or more action-oriented than the raw runtime result
- the print-artifact job persists a bounded `proof_sync_preview` rather than the full raw sync payload list when proof-level details are present

Maintenance rule:

- if a runtime wrapper is added under `wms/jobs/`, decide in the same work whether it should persist an `OperationalJobRun`
- keep command modules thin; do not duplicate run persistence inside management commands once the job wrapper exists
- if run status vocabulary or summary normalization changes, update the model helper, affected jobs, ops docs, and this section together

Reference tests:

- `wms/tests/test_job_runs.py`

### V3.3 Parties Boundary Contract

Primary runtime sources:

- `wms/parties/selectors.py`
- `wms/parties/invariants.py`
- `wms/parties/sync.py`
- `wms/parties/projections.py`
- `wms/parties/merge.py`
- `wms/application/parties/use_cases.py`
- `wms/portal_recipient_sync.py`
- `wms/admin_contacts_merge_service.py`
- `wms/scan_admin_contacts_cockpit.py`

Current V3.3 contract:

- `wms/parties/selectors.py` is now the shared home for validated and active shipment-party selectors previously duplicated across registry and rules modules
- `wms/parties/invariants.py` owns graph-level destination-scope checks that future sync and merge flows can reuse
- `wms/parties/sync.py` now owns the portal-recipient sync orchestration and shipment-party contact resolution runtime
- `wms/parties/projections.py` now owns legacy `AssociationRecipient` refresh logic when compatibility projections must follow canonical shipment-party writes
- `wms/parties/merge.py` now owns the contact-graph and recipient-organization merge runtime used by scan admin and shipment-party cockpit adapters
- `ShipmentRecipientOrganization` is now uniquely scoped by `(organization, destination)`; organization-only runtime assumptions are no longer a valid shared contract
- portal recipient destination changes now keep the same synced structure contact when possible and create or reuse a destination-scoped recipient runtime row instead of forcing a second synced organization contact
- portal recipient sync and shared-profile writes may carry a transient `structure_asf_id`; when
  present, runtime reuse must prefer that canonical contact identifier before exact-name structure
  fallback
- `wms/application/parties/use_cases.py` is the application-facing entrypoint for portal-recipient sync, shared recipient-profile writes, document upserts, recipient-product preference upserts, and recipient-contact resolution
- shipper portal recipient create/update flows in `wms/views_portal_account.py` must route shared-profile writes through `wms/application/parties/use_cases.py`; direct `AssociationRecipient` mutation is no longer the shared contract
- scan/admin recipient shared-field edits in `wms/admin_contacts_contact_service.py` must also route shared runtime writes through `wms/application/parties/use_cases.py::update_runtime_recipient_shared_profile(...)` instead of rebuilding shipment-party mutations inline
- when an active `PortalAccessGrant` with role `recipient_admin` exists for the synced `ShipmentRecipientOrganization`, shipper portal recipient shared fields and product-preference edits become read-only and the HTML portal must surface that lock explicitly
- `wms/portal_recipient_sync.py` remains a compatibility adapter and should not grow new orchestration logic again
- `wms/admin_contacts_merge_service.py` remains a compatibility adapter and should not grow graph mutation logic again
- `wms/scan_admin_contacts_cockpit.py` keeps forms and user-facing validation/messages, but delegates merge mutations to `wms/parties/merge.py`
- scan/admin editing of an existing recipient/correspondent contact is an explicit overwrite of the current shared fields; merge-style “fill only missing fields” remains reserved for explicit duplicate-resolution actions

Maintenance rule:

- if a portal recipient sync change affects graph orchestration, destination reuse, or recipient-contact resolution, update `wms/parties/sync.py` or `wms/application/parties/use_cases.py` first, then keep compatibility wrappers thin
- if a canonical shipment-party write still needs a legacy `AssociationRecipient`, route the compatibility refresh through `wms/parties/projections.py` instead of rebuilding portal projection logic in views or wrappers
- if a scan/admin recipient edit must stay visible in shipper portal and recipient portal, keep the write in `wms/application/parties/use_cases.py` and let `wms/parties/projections.py` refresh compatibility rows instead of patching portal reads
- if an admin contact merge or shipment-party cockpit merge changes graph mutation semantics, update `wms/parties/merge.py` first, then keep scan/admin wrappers thin
- if a caller resolves or mutates `ShipmentRecipientOrganization`, prefer destination-aware helpers or explicit `(organization, destination)` filters over organization-only lookups
- do not reintroduce validated/active selector duplication back into `wms/shipment_party_registry.py` or `wms/shipment_party_rules.py`

Reference tests:

- `wms/tests/core/tests_parties_selectors.py`
- `wms/tests/core/tests_parties_use_cases.py`
- `wms/tests/core/tests_parties_merge.py`
- `wms/tests/core/tests_parties_destination_scope.py`
- `wms/tests/core/tests_parties_use_cases.py`
- `wms/tests/scan/tests_admin_contacts_contact_service.py`
- `wms/tests/portal/tests_portal_recipient_sync.py`
- `wms/tests/portal/tests_portal_shipment_parties.py`
- `wms/tests/views/tests_views_scan_admin.py`

### Recipient Product Preference Contract

Primary runtime sources:

- `wms/models_domain/shipment_parties.py`
- `wms/recipient_product_preferences.py`
- `wms/views_portal_account.py`
- `wms/views_scan_admin.py`
- `wms/views_scan_shipments.py`
- `wms/scan_shipment_handlers.py`
- `wms/shipment_helpers.py`
- `wms/static/scan/scan.js`

Current contract:

- canonical product preferences attach to `ShipmentRecipientOrganization`, not to `AssociationRecipient`
  and not directly to `contacts.Contact`
- the only persisted statuses are `requested`, `allowed`, and `refused`; `unspecified` remains
  implicit when no row exists for `(recipient_organization, product)`
- `requested` and `allowed` require `quantity_target` plus `period_unit`; `refused` forbids both
- `ShipmentPreferenceOverride` is append-only journaling for one-off shipment/carton overrides and
  must not mutate the canonical preference row
- coverage metrics use the current local calendar week/month window, `ShipmentWorkflowProjection.delivered_at`
  as delivery evidence, and open assigned shipments as pipeline quantity
- portal recipient detail, recipient-scoped portal preference maintenance, and scan/admin recipient
  detail render the same canonical preference rows plus the same coverage summary semantics
- those three line-by-line tables also expose the same computed `Qté par colis (estimation)` metadata,
  derived from the default carton format and the shared weight/volume carton-capacity rule
- when product and carton metadata are insufficient, the line-by-line tables must render `--` for that
  estimate instead of inventing a fallback
- if the synced recipient now has an active recipient portal grant, shipper-side portal preference controls become read-only on both the list edit surface and the recipient detail surface while scan/admin keeps the canonical maintenance path
- scan shipment create/edit exposes per-carton compatibility metadata keyed by recipient runtime,
  blocks only explicit `refused` products, and records override rows when staff continues

Maintenance rule:

- if preference semantics, quantities, or status vocabulary change, update the model validation,
  shared helper module, portal/admin detail surfaces, and scan shipment metadata/JS together
- keep `unspecified` implicit; do not introduce stored "allowed by default" rows without updating
  the shared helper and every consumer
- if coverage math changes, keep the period/window rules, delivery evidence source, and scan
  compatibility bucket logic aligned in the same work
- if the line-by-line preference table columns change, keep portal shipper, portal recipient, and
  scan/admin column order plus estimate semantics aligned in the same work

Reference tests:

- `wms/tests/core/tests_recipient_product_preferences.py`
- `wms/tests/core/tests_recipient_product_preference_coverage.py`
- `wms/tests/views/tests_views_portal.py`
- `wms/tests/views/tests_views_scan_admin_shipment_parties.py`
- `wms/tests/scan/tests_scan_shipment_handlers.py`
- `wms/tests/views/tests_views.py`
- `wms/tests/views/tests_views_scan_shipments.py`

### V3.3 Artifacts Boundary Contract

Primary runtime sources:

- `wms/artifacts/planning.py`
- `wms/artifacts/attachments.py`
- `wms/artifacts/proofs.py`
- `wms/application/planning_artifacts/use_cases.py`
- `wms/planning/exports.py`
- `wms/planning/communication_actions.py`
- `wms/print_pack_sync.py`
- `wms/jobs/print_artifacts.py`

Current V3.3 contract:

- `wms/artifacts/planning.py` is now the shared home for planning workbook/PDF export orchestration, persisted artifact health helpers, and artifact metadata summaries
- `wms/planning/exports.py` remains a compatibility adapter and should not grow new export orchestration logic again
- `wms/artifacts/attachments.py` now owns planning attachment resolution and PDF readiness/blocking semantics for communication helpers
- `wms/application/planning_artifacts/use_cases.py` is now the application-facing entrypoint for helper payload composition that depends on planning artifact state
- `wms/planning/communication_actions.py` remains a compatibility adapter and should not grow attachment-selection logic again
- `wms/artifacts/proofs.py` now owns proof-path payloads for print artifact sync, including the canonical file name, relative directory, and OneDrive path
- `wms/print_pack_sync.py` keeps transport and queue retry behavior, but should delegate proof-path construction to `wms/artifacts/proofs.py`
- `process_print_artifact_queue(...)` now returns the legacy counters plus a `proof_sync` list, and `wms/jobs/print_artifacts.py` persists a bounded `proof_sync_preview` inside `OperationalJobRun.result_summary`

Maintenance rule:

- if planning workbook/PDF lifecycle, artifact health persistence, or communication attachment eligibility changes, update `wms/artifacts/planning.py` and `wms/artifacts/attachments.py` first, then keep planning adapters thin
- if print artifact sync path construction changes, update `wms/artifacts/proofs.py` first, then keep `wms/print_pack_sync.py` focused on transport/retry behavior
- if print artifact job summaries change, update `wms/jobs/print_artifacts.py`, `wms/jobs/runtime_tracking.py`, ops docs, and this section together

Reference tests:

- `wms/tests/planning/tests_artifact_services.py`
- `wms/tests/planning/tests_outputs.py`
- `wms/tests/planning/tests_communication_actions.py`

### Warehouse Preparation And Recipient Preference Contract

Primary runtime sources:

- `wms/models_domain/preparation.py`
- `wms/models_domain/shipment_parties.py`
- `wms/recipient_product_preferences.py`
- `wms/preparation/needs.py`
- `wms/preparation/reservations.py`
- `wms/preparation/candidates.py`
- `wms/preparation/scoring.py`
- `wms/preparation/conversion.py`

Current contract:

- `planning vols` and warehouse `run magasin` remain separate domains; proposal, snapshot, reservation, and scoring state for warehouse preparation must not be folded back into `wms/models_domain/planning.py`
- canonical recipient product preferences live on `RecipientProductPreference`, scoped by `ShipmentRecipientOrganization`
- effective recipient preference resolution order is `product -> most specific category -> unspecified`
- category-level `requested` and `allowed` are supported; category-level `refused` is intentionally invalid in this phase
- kit products resolve as the kit product itself for preference/scoring purposes; component preferences do not implicitly apply to the kit
- `PreparationRunNeedSnapshot` freezes recurring need data at run time; run-local overrides mutate only the snapshot row, not the recurring need source
- preparation reservation helpers own lot-level `quantity_reserved` mutations for run proposals, and urgent manual reclaim must mark the impacted proposal `needs_recalc` with an audit log entry
- conversion of accepted proposals is explicit: accepted or partial proposal rows convert into real `Shipment` / `Carton` objects only when staff triggers the conversion action, not during proposal review itself
- conversion creates shipments in `ShipmentStatus.PICKING`; warehouse review acceptance must not silently promote them to `PACKED`, because planning-vols only consumes physically confirmed `PACKED` / `PLANNED` shipments later
- the later promotion from `ShipmentStatus.PICKING` to `PACKED` is a separate explicit shipment-dossier action; proposal conversion alone must never make a shipment planning-eligible
- accepted deposit cartons are reattached to the converted shipment, while accepted ASF-stock cartons are materialized from the FEFO preparation reservations without double-consuming stock
- fairness history counts only converted ASF-stock or mixed shipments in `PACKED` or `PLANNED`; deposited-only history must not bias fairness

Maintenance rule:

- if recipient preference semantics change, update `wms/models_domain/shipment_parties.py`, `wms/recipient_product_preferences.py`, and the nearest prep/core tests together
- if warehouse run state changes, keep `wms/models_domain/preparation.py` and `wms/preparation/*` aligned instead of scattering preparation logic into planning or shipment views
- if fairness, reservation, or need-snapshot semantics change, update this section in the same work so the warehouse-preparation contract stays explicit

Reference tests:

- `wms/tests/core/tests_recipient_product_preferences.py`
- `wms/tests/preparation/tests_models.py`
- `wms/tests/preparation/tests_needs.py`
- `wms/tests/preparation/tests_reservations.py`
- `wms/tests/preparation/tests_candidates.py`
- `wms/tests/preparation/tests_scoring.py`
- `wms/tests/preparation/tests_conversion.py`
- `wms/tests/views/tests_views_scan_preparation.py`
- `wms/tests/print/tests_print_pack_sync.py`
- `wms/tests/test_job_runs.py`

### Shipment Ready Confirmation Contract

Primary runtime sources:

- `wms/shipment_status.py`
- `wms/views_scan_shipments.py`
- `wms/views_scan_shipments_support.py`
- `templates/scan/includes/shipment_dossier_header.html`
- `wms/planning/sources.py`

Current contract:

- the explicit helper pair is `shipment_can_be_confirmed_ready(shipment)` and `confirm_shipment_ready(shipment, user)`
- this action is for dossier-level confirmation after physical preparation, especially for shipments created by warehouse proposal conversion
- confirmation is only valid while the shipment remains editable and every carton is already in `ASSIGNED` or `LABELED`
- when a shipment is linked to an order, clean order-level attestations are part of the readiness
  gate: donation is always required, and humanitarian attestation is required unless the linked
  shipper / association contact is marked exempt
- when a shipment contains any `Carton` with `source_kind=shipper_received`, readiness also requires
  a linked and conform inbound association receipt plus clean order-level `packing_list_global` and
  `packing_list_by_carton` documents
- order linkage for readiness checks must resolve through `OrderShipmentLink`; `order.shipment`
  remains only a compatibility pointer for older single-shipment surfaces
- confirmation relabels remaining `ASSIGNED` cartons to `LABELED`, then sets the shipment to `ShipmentStatus.PACKED` and stamps `ready_at`
- the dossier action is explicit in `scan/shipment/<id>/edit/`; it must not be folded into generic shipment edit POST handling or preparation-run review actions
- planning-vols eligibility stays restricted to `ShipmentStatus.PACKED` and `ShipmentStatus.PLANNED`; `ShipmentStatus.PICKING` stays excluded even if its `ready_at` window would otherwise match

Maintenance rule:

- if shipment-ready confirmation semantics change, update the helper, dossier view, dossier header actions, planning source filter, and the related tests in the same work
- keep this contract shipment-level and operator-triggered; do not silently reintroduce automatic planning eligibility from warehouse conversion or unrelated carton updates

Reference tests:

- `wms/tests/shipment/tests_shipment_status.py`
- `wms/tests/views/tests_views_scan_shipments.py`
- `wms/tests/planning/tests_sources.py`

### V3.3 Structural Facade Contract

Primary runtime sources:

- `wms/application/__init__.py`
- `wms/application/parties/__init__.py`
- `wms/application/planning_artifacts/__init__.py`
- `wms/events/__init__.py`
- `wms/jobs/__init__.py`
- `wms/parties/__init__.py`
- `wms/artifacts/__init__.py`
- `mypy.ini`
- `pyrightconfig.json`
- `Makefile`

Current V3.3 contract:

- the package-root `__init__` modules above are now the stable public import facades for the structural layers introduced across V3.1 to V3.3
- `mypy.ini` is the broad structural type gate and covers the internal modules under `wms/application`, `wms/events`, `wms/jobs`, `wms/parties`, and `wms/artifacts`
- `pyrightconfig.json` is intentionally narrower and validates the package-root public facades rather than the full Django ORM-heavy internals
- `make typecheck-structural` is the repeatable proof command for the combined mypy + pyright structural gate
- `make ruff-structural` is the repeatable lint proof command for those same structural packages
- `wms/tests/core/tests_v33_contracts.py` is the runtime contract guard proving those facades expose the expected V3 entry points

Maintenance rule:

- if a structural package adds, removes, or renames a public entry point, update the relevant package `__init__`, the contract test, and the structural typecheck config in the same work
- do not point `pyrightconfig.json` at ORM-heavy internal modules unless the repo also adopts the stubs and typing discipline needed to keep that signal green
- do not reintroduce hidden cross-package imports when the boundary can be expressed through the package-root facade

Reference tests:

- `wms/tests/core/tests_v33_contracts.py`

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

- `wms/application/portal/dashboard_queries.py` owns both the shipper dashboard composition and the recipient-scope home composition for `/portal/`
- `build_portal_dashboard_payload(profile=...)` remains the shared shipper composition layer for the legacy portal dashboard and `GET /api/v1/ui/portal/dashboard/`
- `build_recipient_scope_home_payload(recipient_organization=...)` feeds both the legacy recipient home rendered on `/portal/` and the recipient-scope branch of `GET /api/v1/ui/portal/dashboard/` when the active scope is `recipient_admin`
- the recipient home at `/portal/` remains the lightweight summary surface, while
  `/portal/recipient/profile/` is the maintenance surface for the same active recipient scope
- the portal UI API dashboard is now scope-aware and returns `mode="shipper"` or `mode="recipient"` so consumers can branch without re-deriving portal access rules
- `dashboard_kpis` exposes `orders_total`, `orders_pending_review`, `orders_changes_requested`, `orders_with_shipment`, `orders_shipments_in_progress`
- portal dashboard rows expose `next_step_label` and `next_step_tone` in both HTML context and UI API payloads
- the HTML table and the UI API must stay aligned on the meaning of "next step" for pending review, correction, preparation, and tracked shipment states

Maintenance rule:

- if the shipper-facing dossier guidance changes, update the helper logic, the shipper portal template, and the portal UI API in the same work
- if the recipient home fields, section anchors, or shell navigation change, update `wms/views_portal_orders.py`, `templates/portal/base.html`, `templates/portal/recipient_scope_home.html`, and the portal bootstrap/view tests in the same work
- keep `wms/views_portal_orders.py` and `api/v1/ui_views.py` thin over `wms/application/portal/dashboard_queries.py`; do not let shipper composition drift back into duplicated query logic during V3.1
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
- `wms/portal_access.py`
- `wms/portal_recipient_sync.py`
- `wms/views_portal_auth.py`
- `wms/portal_urls.py`
- `wms/shipment_party_registry.py`
- `wms/shipment_party_setup.py`
- `wms/shipment_party_rules.py`
- `wms/view_permissions.py`
- `wms/scan_admin_contacts_cockpit.py`

Why it is shared:

- portal recipient changes affect operational contacts
- operational contacts affect shipment create/edit selectors
- admin contact tools can repair or reshape the same graph
- portal authentication and session scope selection now depend on the same shipper/recipient graph
- permissions and default bindings rely on the same data chain
- recipient structure compliance fields (`legal_form`, `beneficiary_count`) and uploaded structure documents now travel with the same graph

Current auth scope contract:

- `PortalAccessGrant` grants exactly one active scope per row: either a `ShipmentShipper` or a
  `ShipmentRecipientOrganization`
- `wms/portal_access.py` prefers explicit active grants and falls back to legacy
  `AssociationProfile` scope resolution only when no explicit grant exists
- portal login, password-set, and access-recovery eligibility accept either explicit grants or the
  legacy profile fallback
- when a portal user has exactly one scope, login auto-activates it in session; when a user has
  multiple scopes, the session stays unbound until `/portal/scope-select/` resolves the active
  scope
- `/portal/faq/` is the shared documentation entry point for both active portal scopes and is
  reachable from the utility area of `templates/portal/base.html`
- `/portal/` is now the first role-aware page: shipper scopes keep the order cockpit while
  recipient scopes render a recipient home on the same shell
- the remaining legacy pages guarded by `association_required` remain shipper-only, while the
  recipient-specific maintenance contract now lives on the role-aware `/portal/` home,
  `/portal/recipient/profile/`, `/portal/recipient/preferences/`, and the mirrored UI API
  endpoints under `/api/v1/ui/portal/*`
- when a shipper scope comes from an explicit `PortalAccessGrant` and no legacy
  `AssociationProfile` exists yet for that user, `association_required` can create the missing
  bridge profile for the granted shipper organization on first access; an existing profile pointing
  at a different organization still fails closed
- `python manage.py rebuild_recipient_party_graph --dry-run|--apply` is the compatibility repair
  path for explicit shipper grants and stale `AssociationRecipient` projections when canonical
  shipment-party runtime rows were merged or reshaped outside the portal adapters

Maintenance rule:

- never treat portal recipient edits as pure presentation changes
- verify whether the change impacts synchronization, authorizations, default contacts, or scan selectors
- keep `PortalAccessGrant`, legacy `AssociationProfile` fallback, `/portal/scope-select/`,
  `portal_scope_required`, and `association_required` aligned in the same work while the portal is
  still mid-transition
- if recipient compliance fields or documents change, update portal creation/edit, synced `Contact`, `scan/contacts`, and admin merge/deduplication behavior together

Reference tests:

- `wms/tests/portal/tests_portal_access_grants.py`
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
