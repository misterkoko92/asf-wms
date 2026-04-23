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
- `templates/scan/base.html`
- `wms/static/scan/modules/core.js`
- `wms/static/scan/modules/dashboard.js`
- `wms/static/scan/modules/shipments.js`
- `wms/static/scan/css/partials/`
- `api/v1/ui_views.py`
- `api/v1/views.py`

### What the flow covers

- stock update and stock availability
- stock recipient-needs cockpit under `/scan/recipient-needs/`, including destination /
  recipient / category / need-status / priority filters, linked shipper labels, stock-availability
  coverage, and per-product prioritization for recipient demand
- recipient-needs materialization limited to explicit product preferences and products covered by
  explicit category preferences; the page does not expand a full `unspecified` recipient x catalog
  cross-join
- recipient-needs priority driven by remaining need, current period deadline, and open-shipment
  delay against the runtime `tracking_alert_hours` SLA threshold, with hoverable operator help on
  each priority badge
- recipient-needs table exposes checkbox selection and `Préparer` actions that redirect into the
  existing shipment-create flow with prefilled destination / shipper / recipient / line quantities
  only when the selected rows share the same shipment grouping triplet
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
- stable legacy asset entrypoints where `scan.js`, `scan.css`, and `scan-bootstrap.css`
  remain the shared facades while `wms/static/scan/modules/` and
  `wms/static/scan/css/partials/` carry the first V3.3 modular slices
- receipt operator capture on `/scan/receive-pallet/`, `/scan/receive-listing/`, and
  `/scan/receive-association/`, including persisted `Receipt.conformity_status` and a mandatory
  observation when the operator marks the reception non-conform
- the `Contacts -> Validations` hub under `/scan/contacts/validations/`, with a dedicated
  `Validation expéditeurs` queue under `/scan/account-validations/` and
  `Validation destinataires` queue under `/scan/contacts/validations/recipients/`
- validator-group account review under `/scan/account-validations/` and
  `/scan/account-validations/<id>/`, including one-screen correction of the final business type,
  recipient data completion, and operator approval or rejection without going back through the
  Django admin changelist
- superuser recipient review under `/scan/contacts/validations/recipients/` and
  `/scan/contacts/validations/recipients/<id>/`, reusing the shared admin contact write path from
  a dedicated validation dossier instead of the overloaded contacts directory
- on that shared recipient write path, the single `ASF ID` field belongs to the organization and
  must never be propagated onto the referent person during save
- the dedicated listing flow under `/scan/receive-listing/` now starts with an intake gate:
  operators must choose the file type (`CSV`, `Excel`, `PDF`) and must link the import to an
  existing pallet receipt before any upload card appears
- the listing intake keeps a hard warning that reception linking is mandatory and exposes a
  shortcut back to `/scan/receive-pallet/` for operators who still need to create that reception
- once a listing session is in progress, reloading `/scan/receive-listing/` must restore the
  active step (`upload`, PDF analysis, mapping, assisted suggestions, review, or post-confirm
  incomplete-products recap) and scroll operators directly to the card they still need to process
- Excel/CSV still keep the existing mapping and review steps, while PDF now enters an explicit
  analysis stage before mapping so operators can inspect detected pages, extractable text/table
  coverage, extraction strategy, short text previews, and either the detected-page subset or the
  manual page range actually sent to mapping
- listing reception can create and receive incomplete products when only partial catalog metadata
  is known; the incomplete-products recap only appears after the final import confirmation and is
  scoped to the products created or reused by that last confirmed listing import
- after mapping, assisted suggestions now run as their own dedicated step before the review table:
  exact EAN can preselect an existing product automatically, global suggestion groups expose a
  compact preview of affected rows, operators can accept or refuse selected suggestions in batch,
  and applying a suggestion only fills still-empty fields while preserving manual row selection
- the listing review table now stays full width, only renders columns that contain at least one
  value in the current review state, and must keep the quick audit columns for product status
  (`Nouveau produit` / `Produit connu`), match type, and the fields auto-completed by assisted
  suggestions or matched-product fallbacks
- `/scan/stock-update/` is now the persistent operator cockpit for incomplete products across the
  whole warehouse: the classic `MAJ stock` form is collapsed by default while the incomplete
  products block opens by default, supports the same guarded batch edits, can be filtered by
  linked pallet receipt using the same reverse-chronological receipt selector contract as Listing,
  and surfaces the same assisted suggestion groups for brand, category, TVA, and default location
- listing reception falls back to a warehouse-local reception buffer location
  `TEMP / RECEPTION / LISTING` when neither row-level nor product default location is available
- listing import quantities stay additive: confirmed rows create receipt lines and stock entries;
  they do not overwrite existing stock quantities already present for the matched product
- carton overview vs carton detail split under `/scan/cartons/` and `/scan/carton/<id>/edit/`;
  editable carton dossiers expose a guarded delete action that reuses the carton mutation handler
  and restores stock through unpacking before removing the carton
- preparateur-only login entry under `/scan/preparateur/`, including active bénévole selection,
  persistent single `Bonjour <prenom>` shell greeting, default recommendation of the most critical
  realizable order, grouped order choices, a `MAJ Stock` shortcut to `/scan/stock-update/`, and
  the `Voir les colis` shortcut to all non-shipped cartons
- preparateur order preparation plans use family-specific standard carton formats (`MM Standard` /
  `CN Standard`), allow a single-family forced carton count with warnings, and keep `Marquer prêt`
  tied to the selected order's shipment
- preparateur carton traceability that stores the selected bénévole on initial carton creation,
  preserves `Carton.prepared_by`, and appends `prepared` / `edited` activity rows for later audit
- preparateur pack success modal with a top-right close button plus footer print action:
  `Imprimer` for one carton and `Imprimer tout` when several packing lists are shown
- `/scan/pack/` keeps the product card on a stable three-row layout (search + scan, then
  selector/quantity/expiration, then optional forced carton count) and lets operators override the
  automatic carton count on free-pack flows with the same warning model as preparateur order
  preparation
- `/scan/cartons/` keeps checkbox-based bulk actions, now confirms any status jump that skips
  intermediate visible carton steps, requires an editable shipment selection when operators jump
  directly to `Étiqueté`, warns before bulk shipment assignment when selected cartons are
  pre-affectés to another destination, exposes a `Tout sélectionner` control, and shows a
  multiline `Produits` column (`Nom x quantité`) instead of the former
  emplacement/remplissage/contenu trio
- `/scan/admin/products/` exposes superuser deletion for kits and standalone active products,
  while blocking products that are used as kit components and falling back to archive guidance when
  protected stock/order/receipt/preference references prevent physical deletion
- `/scan/pack/` and `/scan/carton/<id>/edit/` now expose the same guarded escape hatch for unknown
  products: when an operator enters a product missing from the catalog, the UI proposes leaving the
  current packing flow and opening `/scan/import/`; accepting this redirect intentionally drops the
  in-progress carton draft instead of attempting a partial save
- the product card on `/scan/import/` now doubles as the manual catalog-completion entrypoint for
  pack flows: warehouse/rack/aisle/shelf/category/brand inputs keep free-text creation while
  autocompleting existing values, SKU auto-generates when left blank, and rack colors stay unique
  per warehouse while auto-filling and locking when the `(warehouse, rack)` pair is already known
- warehouse `run magasin` generation/review under `/scan/preparation-runs/`, including proposal scoring, checkbox review actions, and conversion of accepted proposals into real shipments/cartons
- warehouse `run magasin` flight acquisition first tries the planning API, then falls back to the latest imported exploitable flight batch; when that fallback batch is from a previous period, preparation capacity is computed from that batch period instead of crashing the operator flow
- shipment creation/edit, including document-first creation without cartons
- shipment refusal checks against recipient product preferences, with operator confirmation and override journaling
- warehouse conversion creates real shipments in `ShipmentStatus.PICKING`; they stay out of planning-vols until operators physically finish the cartons and move them to `PACKED`
- the final promotion from `PICKING` to `PACKED` is an explicit dossier action on `scan/shipment/<id>/edit/`; it is intentionally separate from preparation-run review and conversion
- shipment refusal checks against recipient product preferences, with operator confirmation and override journaling
- carton status progression
- grouped carton assignment and print/document entrypoints
- direct HTML print bundles for shipment `paper`, `standard_labels`, and `carton_lists_a4`
- shipment `paper` now prints, in order, `Bon d'expédition`, `Document douane`, then
  `Liste colisage générale` twice; those three shipment-paper surfaces now use `A4 portrait`
- shipment `standard_labels` now means one `A4 portrait` page per carton with four compact
  quadrants: donation certificate, shipment label, contact label, and carton packing list
- shipment `carton_lists` kept as a per-carton action page for continuous-roll printing
- carton bundle page exposes global print actions for continuous-roll and A4 four-up outputs
- tracking events
- public shipment QR tracking under `/scan/shipment/track/<tracking_token>/` is an
  authenticated gateway: unauthenticated scans must enter their existing ASF/volunteer identifier
  and then log in before any tracking event can be recorded
- lost-code recovery for shipment QR tracking uses role + email + escale and sends the existing
  ASF ID / role back by email without revealing whether an unknown email exists
- QR tracking login and lost-code recovery are throttled, and restricted grants are ignored after
  `expires_at`
- no-identifier QR tracking creation creates a restricted `pending` identity and the matching
  pending review object (`PublicAccountRequest` or `VolunteerAccountRequest`) without granting
  broad portal / volunteer access before review approval
- correspondent and recipient receipt scans require proof of a carton face IATA by photo, or a
  manual carton number when the operator checks that they cannot take a photo
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

### Docs that must stay aligned

- `docs/mvp_spec.md`
- `docs/release_checklist.md`
- `docs/operations.md`

### Propagation warning

If you change shipment sequencing, status rules, document-first creation behavior, closure rules, or document/label availability, do not stop at one page or one handler. Check:

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

### What the flow covers

- association authentication and account maintenance
- public account requests now distinguish `shipper`, `recipient`, and `user`, while legacy
  `association` rows remain accepted as shipper-equivalent during approval
- operator review of public account requests is now scan-first: validator-group staff enter via
  `/scan/contacts/validations/` and review pending shipper rows under `/scan/account-validations/`,
  while Django admin remains a bounded fallback
- recipient public account requests must choose exactly one delivery stop up front because
  recipient portal access is scoped to one `ShipmentRecipientOrganization (organization,
  destination)`
- ASF approval of a recipient public account request now provisions the validated runtime
  recipient organization, one minimal active recipient contact, one
  `PortalAccessGrant(recipient_admin)`, and the default ASF shipper binding in the same flow
- when an operator corrects a public request from `shipper` to `recipient`, the approval flow
  preserves the original requested type in `PublicAccountRequest.requested_account_type`, stores
  the reviewed payload in `PublicAccountRequest.review_snapshot`, and provisions the final runtime
  from the reviewed scan payload instead of the original signup type
- portal access resolution from explicit `PortalAccessGrant` rows with fallback to legacy `AssociationProfile`
- single-scope portal activation in session, with `/portal/scope-select/` as the explicit chooser when a user has multiple portal scopes
- when a shipper scope comes from an explicit grant and the user still has no legacy `AssociationProfile`,
  `association_required` can bridge that missing shipper profile from the granted `ShipmentShipper`
  organization so the shipper cockpit remains reachable after `/portal/scope-select/`
- `/portal/` now branches on the active scope: shipper scopes keep the order cockpit, recipient scopes land on a recipient home showing shared structure data, recipient contacts, structure documents, and explicit product preferences for exactly one `ShipmentRecipientOrganization`
- recipient scopes can now jump from the home summary at `/portal/` to `/portal/recipient/profile/` for direct maintenance of the active recipient structure identity, main contact, address, notes, and structure documents
- recipient scopes can now jump from the home summary at `/portal/` to `/portal/recipient/preferences/` for line-by-line product preference maintenance on that active `ShipmentRecipientOrganization`
- legacy shipper pages outside `/portal/` remain guarded by the active portal scope in `wms/view_permissions.py`
- portal shell navigation now adapts to the active scope, keeping shipper order/billing/recipient links unchanged while recipient scopes expose in-page anchors for identity, contacts, documents, and preferences
- shipper portal dashboard cockpit KPIs and per-order next-step guidance
- recipient list/detail/create/update
- recipient-scoped profile editing for structure, main contact, address, notes, and documents
- recipient product preference editing from both portal recipient detail and scan admin recipient cockpit
- canonical recipient shared-profile writes, document upserts, and product-preference upserts through `wms/application/parties/use_cases.py`
- shipper portal recipient create/update now write the canonical shipment-party graph first and only refresh `AssociationRecipient` as a compatibility projection
- scan/admin recipient shared-field edits from `scan/contacts` now also route through the same application use-case layer and refresh any matching legacy `AssociationRecipient` projections before portal shipper views re-read them
- the same `scan/admin/contacts` surface also persists non-shipment contact history categories through `ContactCapability` rows; `donor`, `transporter`, `partner`, and `other` stay in the legacy contact CRUD path and do not create shipment-party runtime rows by themselves
- `python manage.py rebuild_recipient_party_graph --dry-run|--apply` is the deterministic repair path when explicit shipper grants or legacy `AssociationRecipient` projections must be rebuilt from the canonical shipment-party runtime
- once a `PortalAccessGrant(recipient_admin)` exists for the synced `ShipmentRecipientOrganization`, shipper-side recipient maintenance becomes read-only on both `/portal/recipients/?edit=<id>` and `/portal/recipients/<id>/`
- synchronization from `AssociationRecipient` compatibility projections to operational contact structures
- shipper/recipient authorization chain
- order creation from portal
- downstream readiness for shipment creation
- destination-scoped recipient runtimes keyed by `(organization, destination)` even when the same synced structure is reused across multiple stopovers

### Living reference tests

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

### Docs that must stay aligned

- `docs/mvp_spec.md`
- `docs/audit_2026-02-19.md`
- `docs/release_checklist.md`

### Propagation warning

If you change recipient fields, validation, shipment-party eligibility, default shipper binding, or portal permissions, check both:

- the portal HTML views and templates
- the portal UI API endpoints

Also inspect the shipment-party registry and sync layers. A portal-only change is often not portal-only in practice.
Default ASF shipper resolution now prefers the canonical `Contact.asf_id` when available and only
falls back to the legacy display-name anchor for transitional data.
When a recipient structure can now exist on multiple destinations, avoid organization-only runtime lookups and assertions.
Recipient management routes now include both the lightweight list at `/portal/recipients/` and
the recipient cockpit detail at `/portal/recipients/<id>/`, while recipient scopes also use
`/portal/recipient/preferences/` as the dedicated product-preference maintenance page. Permission
guards and portal-side navigation should treat all three as part of the same maintenance surface.
The same maintenance surface now has UI API mirrors at `/api/v1/ui/portal/dashboard/`,
`/api/v1/ui/portal/recipients/`, and `/api/v1/ui/portal/recipients/<id>/`; scope-aware
recipient changes must stay aligned across HTML and UI API.

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

Current local-phase contract additions:

- a portal shipper order may now contain ASF-stock lines, a declared shipper inbound delivery, or
  both
- portal order submission and ASF review no longer require supporting documents up front; document
  completeness now blocks later shipment readiness when the shipment actually depends on them
- one order may now link multiple shipment dossiers through `OrderShipmentLink`; the scan
  `create_shipment` action always opens a new dossier while `order.shipment` remains a compatibility
  pointer for older surfaces
- `scan/receive-association/` can attach a receipt to the order inbound delivery and materialize the
  declared shipper cartons as real `Carton` rows with `source_kind=shipper_received`
- the legacy scan order flow is now split across three dedicated surfaces:
  - `/scan/orders-view/` as the queue with one `Ouvrir` action per row
  - `/scan/orders/<id>/` as the operator dossier for review, visible contacts/destination, and
    workflow actions
  - `/scan/orders/` as the create / select / line-maintenance screen
- `Réception association` and `Dossier expédition` remain the downstream operational surfaces:
  the order dossier links to the inbound receipt screen, `Réception association` can create a linked
  shipment directly once the order is approved, the order dossier can also trigger the combined
  "create cartons and shipment" preparation path, and `Dossier expédition` shows the linked order
  plus remaining shipper cartons still available for assignment

## 4. Emailing And Notification Routing

### Main runtime files

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
- `wms/events/outbox.py` when `IntegrationEvent` enqueue semantics change
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

Document scan queue follows the same V3.2 durable-dispatch rule:

- enqueue paths should use `wms/events/outbox.py` rather than creating `IntegrationEvent` rows ad hoc
- reference tests live in `wms/tests/security/tests_document_scan_queue.py` and `wms/tests/management/tests_management_check_document_scan_runtime.py`

## 5. Planning: Seed -> Solve -> Publish -> Communications -> Cockpit

### Main entry points

- `wms/planning_urls.py`
- planning management commands

### Main runtime files

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

### Living reference tests

- `wms/tests/planning/tests_smoke_planning_flow.py`
- `wms/tests/planning/tests_artifact_services.py`
- `wms/tests/planning/tests_outputs.py`
- `wms/tests/planning/tests_communication_actions.py`
- `wms/tests/planning/tests_run_preparation.py`
- `wms/tests/planning/tests_version_dashboard.py`
- `wms/tests/print/tests_print_pack_sync.py`
- `wms/tests/test_job_runs.py`
- `wms/tests/views/tests_views_planning.py`

### Docs that must stay aligned

- `docs/operations.md`
- `docs/release_checklist.md`
- planning-specific design and implementation notes under `docs/plans/`

### Current cockpit contract

- `templates/planning/run_list.html` is the action-oriented entry page with an attention block before history
- `templates/planning/run_detail.html` exposes a single primary CTA and a short operator list of versions
- `templates/planning/version_detail.html` is the operator cockpit and should stay ordered as `header -> priorities -> section nav -> planning capacity -> planning by flight -> secondary details`
- `prepare_run_inputs(...)` must resolve flight batches from `flight_mode` through `wms/planning/flight_sources.py`; `api` mode records a blocking `flight_import_failed` issue when the provider import fails, while `hybrid` snapshots every retained Excel/API flight and keeps the existing Excel batch as the run anchor when present
- when planning shipments or active destination rules expose IATA targets, Air France imports must query the provider per destination code instead of using a single broad request, then deduplicate overlapping multi-stop rows before persisting the API batch
- planning flight API config resolves from Django settings first, then `PLANNING_FLIGHT_API_*` env vars, with compatibility aliases for `AF_API_KEY`, `AF_TIME_ORIGIN_TYPE`, `AF_MAX_CALLS_PER_DAY`, and `AF_MIN_DELAY_SECONDS` to reuse the scheduler Air France setup and its QPS pacing
- the stats panel now includes the local flight-capacity summary cards `Vols en tension`, `Vols critiques`, `Vols en surcharge`, `Capacité restante totale`
- the main planning block now starts with a compact `Charge vols` table ordered by load urgency before the detailed assignment groups
- the exports block now regenerates a strict planning workbook plus a derived planning PDF from the vendored `Planning-maquette.xlsx`
- the planning PDF is the primary operator artifact; the workbook remains available for calibration and download
- the exports block also exposes the latest workbook/PDF artifact health with backend, last attempt, and the last PDF error when present
- the exports block exposes a distinct `Runtime PDF` state for the current host, separate from the last artifact attempt
- internal planning communication drafts now expose `planning_pdf` attachments instead of the workbook
- internal planning communication drafts are explicitly `blocked` with `blocking_reason=planning_pdf_not_ready` when no ready PDF artifact exists yet
- the V3.3 artifact slice keeps `wms/planning/exports.py` and `wms/planning/communication_actions.py` as compatibility adapters over `wms/artifacts/*` and `wms/application/planning_artifacts/use_cases.py`
- print artifact sync now builds its proof payload through `wms/artifacts/proofs.py`, and the persisted `OperationalJobRun` summary for `print_artifact_queue` now carries a bounded `proof_sync_preview`
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

## 7. Structural Runtime Boundaries: Application / Events / Jobs / Parties / Artifacts

### Main runtime files

- `wms/application/`
- `wms/events/`
- `wms/jobs/`
- `wms/parties/`
- `wms/artifacts/`
- `mypy.ini`
- `pyrightconfig.json`
- `Makefile`

### Living reference tests

- `wms/tests/core/tests_v33_contracts.py`
- `wms/tests/core/tests_event_types.py`
- `wms/tests/core/tests_parties_use_cases.py`
- `wms/tests/core/tests_parties_merge.py`
- `wms/tests/core/tests_parties_destination_scope.py`
- `wms/tests/planning/tests_artifact_services.py`
- `wms/tests/print/tests_print_pack_sync.py`
- `wms/tests/test_job_runs.py`

### Structural proof commands

- `make typecheck-structural`
- `make ruff-structural`
- `./.venv/bin/python manage.py test wms.tests.core.tests_v33_contracts -v 2`

### Current quality-gate split

- `mypy.ini` now carries the broader structural proof over `wms/application`, `wms/events`, `wms/jobs`, `wms/parties`, and `wms/artifacts`
- `pyrightconfig.json` intentionally locks only the public `__init__` facades for those boundaries, avoiding a false signal from unstubbed Django ORM internals while still guarding the exported import surface

### Propagation warning

If a new V3 boundary is introduced or a package root facade changes, update the package `__init__` export surface, the structural proof suite, and the typecheck scope together. Do not grow new runtime layers that are invisible to `mypy`, `pyright`, or the contract tests.
