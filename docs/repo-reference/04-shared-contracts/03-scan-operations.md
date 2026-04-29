# Scan Operations Contracts

Read this file when touching scan lists, sidebar navigation, preparateur flows, receipts, pack/import flows, product/carton deletion, or scan operational UI.

---

## Scan Cockpit List Contract

### Primary runtime sources

- `wms/templatetags/wms_dates.py`
- `wms/scan_list_urls.py`
- `templates/scan/includes/scan_list_pagination.html`
- `wms/receipt_list_queries.py`
- `wms/order_list_queries.py`
- `wms/views_scan_shipments_support.py`
- `templates/scan/receipts_view.html`
- `templates/scan/orders_view.html`
- `templates/scan/shipments_tracking.html`

### Current contract

- Dense scan cockpit lists use server-side filtering, sorting, and pagination.
- Shared query parameters are `q`, `sort`, and `page`.
- Domain filters may extend with `type`, `planned_week`, `closed`, `dispute`, or `destination`.
- Filtering and sorting apply before pagination.
- Matching rows must appear even if they lived outside the former page window.
- Shared pagination include is `templates/scan/includes/scan_list_pagination.html`.
- Dense dates use named helpers: `scan_date_short`, `scan_datetime_short`, `scan_date_weekday_short`.
- Row exposes explicit primary cockpit action.
- Count badge reflects filtered dataset, not current page only.
- Migrated lists no longer rely on local client-side `data-table-tools="1"` behavior.

### Maintenance rule

- If a scan cockpit list changes, keep query builder, presenter, template, pagination include, date helpers, regression tests, and this section aligned.

---

## Scan Sidebar Navigation Contract

### Primary runtime sources

- `templates/scan/includes/scan_sidebar_navigation.html`
- `templates/scan/base.html`
- `wms/scan_permissions.py`
- `wms/views_scan_*.py` via `active` context key
- `wms/faq_changelog.py`

### Current contract

- Preparateur-only users use reduced navigation and responsive masthead.
- `/scan/` redirects preparateurs to `/scan/preparateur/`.
- `/scan/preparateur/` stores selected volunteer in `preparateur_active_volunteer_id`.
- Shared non-preparateur sidebar remains grouped into `Stocks`, `Réception`, `Préparation`, `Expéditions`, `Contacts`, `Gestion`.
- `Contacts` group contains `Répertoire`, `Rôles expédition`, `Validations`.
- `Stocks` group contains stock, needs, kits, cartons, orders, receipts, stock update.
- `Préparation` group contains kits, packs, shipment preparation, runs magasin.
- `/scan/faq/` includes Change Log backed by `wms/faq_changelog.py`.
- Each user-visible PR must add one Change Log entry.

### Maintenance rule

- If sidebar entry changes, update shared include, relevant `active` keys, bootstrap tests, and this section.
- If a new scan action queue is added, update context processor, masthead dropdown, and scan bootstrap tests.
- If a PR changes user-visible scan workflow, append FAQ Change Log entry.

---

## Scan Preparateur Pack Contract

### Primary runtime sources

- `wms/preparateur_session.py`
- `wms/preparateur_orders.py`
- `wms/views_scan_preparateur.py`
- `wms/views_scan_orders.py`
- `wms/views_scan_shipments.py`
- `wms/forms.py`
- `wms/pack_handlers.py`
- `templates/scan/pack.html`
- `templates/scan/includes/pack_shipping_section.html`
- `templates/scan/includes/pack_unknown_product_modal.html`
- `wms/static/scan/scan.js`

### Current contract

- Flow starts on `/scan/preparateur/` by selecting active volunteer.
- Active volunteer session key: `preparateur_active_volunteer_id`.
- Selected order session key: `preparateur_selected_order_id`.
- Picking plan session key: `preparateur_order_plan`.
- Rangement batch session key: `preparateur_rangement_batch`.
- Planned carton becomes real only when `Marquer prêt` is clicked.
- `/scan/pack/` preserves linked shipment reference through hidden shipment field when active.
- Product card layout stays three-row.
- Free-pack supports forced carton count with warnings.
- Camera-facing choice maps rear/front to `environment`/`user`.
- Barcode flows reuse selected camera mode.
- OCR is currently disabled and must fail closed unless future work self-hosts OCR assets and updates CSP, cache, and regression tests.
- Unknown product opens modal; SKU auto-generates; preparateur-created products are incomplete and notify reviewers.
- `/scan/preparateur/rangement/` caps each batch at five distinct products and stores the mode in `preparateur_rangement_mode`.
- Rangement mode is chosen before scanning and remains locked for the batch: `Entrée en stock` creates receipt stock on validation; `Déplacement de stock` moves available stock toward the product default location using FEFO source selection and supports partial quantities.
- Rangement scans are draft lines until `Valider le batch`; duplicate scans merge by increasing quantity, every line requires a quantity, and validation is blocked when a product has no default location.
- Products missing a default location are corrected through the rangement page by setting only `Product.default_location`; unknown products reuse the preparateur product-creation modal in receipt mode and are added to the draft batch before stock is written.

### Maintenance rule

- If preparateur pack or rangement flow changes, keep session helper, order selection, workbench/rangement template, unknown-product JS/modal behavior, pack/rangement handlers, notifications, tests, and this section aligned.

---

## Receipt Conformity And Listing Contract

### Primary runtime sources

- `wms/models_domain/inventory.py`
- `wms/forms.py`
- `wms/receipt_pallet_handlers.py`
- `wms/receipt_handlers.py`
- receipt templates

### Current contract

- `Receipt` persists `conformity_status`; legacy rows keep `unknown`.
- Non-conform reception requires observation.
- `/scan/receive-listing/` owns listing imports.
- Listing starts with intake gate: file type + existing pallet receipt.
- Listing route resumes active step after reload.
- PDF listing has analysis stage before mapping.
- Assisted suggestions run as dedicated step before review.
- Listing-created products may stay incomplete.
- `/scan/stock-update/` is durable incomplete-products cockpit.
- Listing quantities are additive.
- `/scan/receive-association/` can attach reception to order inbound delivery and create `Carton(source_kind=shipper_received)` rows.

### Maintenance rule

- If receipt/listing behavior changes, keep model fields, validation, handlers, templates, and tests aligned.

---

## Product And Carton Deletion Contract

### Primary runtime sources

- `wms/views_scan_shipments.py`
- `wms/carton_handlers.py`
- `wms/views_scan_admin.py`
- `templates/scan/pack.html`
- `templates/scan/admin_products.html`

### Current contract

- Editable carton dossier exposes `Supprimer le colis`.
- Carton deletion routes through `handle_carton_status_update(action=delete_carton)`.
- Deletion unpacks stocked content, restores stock, resyncs shipment ready state, then removes carton.
- Locked cartons stay non-deletable.
- `/scan/admin/products/` is superuser Scan UI for deletion.
- Kit components are blocked before deletion.
- Protected products/kits are archived instead of force-deleted.

### Maintenance rule

- If product, kit, carton, stock, or preference deletion semantics change, update handlers, templates, tests, and this section.
