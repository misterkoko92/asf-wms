# Scan Catalog And Ops Adjustments Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Livrer le cockpit catalogue scan `produits + kits`, les ajustements ergonomiques demandés sur les flux stock / réception / colis / expédition / facturation, et les contrats UI globaux associés.

**Architecture:** Le lot reste sur le legacy Django. Les nouvelles capacités s'ajoutent via un dossier catalogue scan dédié, des vues / templates scan existants, et des contrats partagés déjà en place dans `wms/templatetags/wms_ui.py`, `wms/static/scan/modules/core.js`, `wms/static/scan/scan.js` et `wms/static/scan/scan-bootstrap.css`. Les changements de flux doivent rester rétrocompatibles avec les données existantes, notamment les anciens codes colis.

**Tech Stack:** Django, Django templates, ModelForms, JS vanilla partagé scan, CSS Bootstrap legacy, `manage.py test`

---

Reference design: `docs/plans/2026-04-24-scan-catalog-and-ops-adjustments-design.md`

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:verification-before-completion`.

### Task 1: Add The Scan Catalog Dossier Entry Points

**Files:**
- Modify: `wms/scan_urls.py`
- Modify: `wms/views_scan_admin.py`
- Modify: `templates/scan/admin_products.html`
- Modify: `templates/scan/stock.html`
- Create: `templates/scan/admin_product_detail.html`
- Create: `templates/scan/includes/admin_product_detail_header.html`
- Create: `templates/scan/includes/admin_product_detail_summary.html`
- Modify: `wms/tests/views/tests_views_scan_admin.py`
- Modify: `wms/tests/views/tests_views_scan_stock.py`

**Step 1: Write the failing tests**

Add view tests that assert:

- `/scan/admin/products/<id>/` exists for superusers
- `/scan/admin/products/` renders `Ouvrir` links to the new scan dossier instead of `admin:wms_product_change`
- `/scan/stock/` renders `Ouvrir` links to the new scan dossier
- non-superusers still cannot access the admin catalogue dossier

Example assertions:

```python
response = self.client.get(reverse("scan:scan_admin_product_detail", args=[self.kit.id]))
self.assertEqual(response.status_code, 200)
self.assertContains(response, reverse("scan:scan_admin_product_detail", args=[self.kit.id]))
```

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_admin.ScanAdminViewTests.test_scan_admin_products_links_to_scan_dossier \
  wms.tests.views.tests_views_scan_admin.ScanAdminViewTests.test_scan_admin_product_detail_renders_for_superuser \
  wms.tests.views.tests_views_scan_stock.ScanStockViewsTests.test_scan_stock_product_open_action_targets_scan_dossier \
  -v 2
```

Expected: FAIL because the route, template, and links do not exist yet.

**Step 3: Write the minimal implementation**

Implement:

- new route `scan_admin_product_detail`
- product dossier view in `wms/views_scan_admin.py`
- catalogue index links pointing to the scan dossier
- stock `Ouvrir` links pointing to the scan dossier
- initial dossier template with header + summary cards only

**Step 4: Run tests to verify they pass**

Run the same command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/scan_urls.py wms/views_scan_admin.py templates/scan/admin_products.html templates/scan/stock.html templates/scan/admin_product_detail.html templates/scan/includes/admin_product_detail_header.html templates/scan/includes/admin_product_detail_summary.html wms/tests/views/tests_views_scan_admin.py wms/tests/views/tests_views_scan_stock.py
git commit -m "feat: add scan product dossier entrypoints"
```

### Task 2: Add Product And Kit Editing To The Scan Catalog Dossier

**Files:**
- Create: `wms/forms_scan_admin_products.py`
- Modify: `wms/views_scan_admin.py`
- Modify: `templates/scan/admin_product_detail.html`
- Create: `templates/scan/includes/admin_product_detail_identity_panel.html`
- Create: `templates/scan/includes/admin_product_detail_logistics_panel.html`
- Create: `templates/scan/includes/admin_product_detail_pricing_panel.html`
- Create: `templates/scan/includes/admin_product_detail_qr_panel.html`
- Create: `templates/scan/includes/admin_product_detail_kit_panel.html`
- Create: `templates/scan/includes/admin_product_detail_danger_panel.html`
- Modify: `wms/tests/views/tests_views_scan_admin.py`

**Step 1: Write the failing tests**

Add tests that cover:

- updating product identity / logistics / pricing from the dossier
- kit composition add / remove / quantity edit from the dossier
- archive / reactivate actions
- delete guard visibility and error messages

Example behavior target:

```python
response = self.client.post(
    reverse("scan:scan_admin_product_detail", args=[self.kit.id]),
    {"action": "save_kit_components", "component_ids": [str(self.component.id)], "component_quantities": ["3"]},
    follow=True,
)
self.assertContains(response, "Composition du kit mise à jour.")
```

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin -v 2
```

Expected: FAIL on the new dossier mutation tests.

**Step 3: Write the minimal implementation**

Implement:

- form classes for product fields and kit composition
- POST actions in `wms/views_scan_admin.py`
- dossier cards for identity, logistics, pricing, QR / labels, kit composition, archive / delete
- scan-native success / error messages

**Step 4: Run tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin -v 2
```

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/forms_scan_admin_products.py wms/views_scan_admin.py templates/scan/admin_product_detail.html templates/scan/includes/admin_product_detail_identity_panel.html templates/scan/includes/admin_product_detail_logistics_panel.html templates/scan/includes/admin_product_detail_pricing_panel.html templates/scan/includes/admin_product_detail_qr_panel.html templates/scan/includes/admin_product_detail_kit_panel.html templates/scan/includes/admin_product_detail_danger_panel.html wms/tests/views/tests_views_scan_admin.py
git commit -m "feat: make scan product dossier fully manageable"
```

### Task 3: Normalize Required Markers And Shared Date Buttons

**Files:**
- Modify: `wms/templatetags/wms_ui.py`
- Modify: `templates/wms/components/field.html`
- Modify: `wms/static/scan/modules/core.js`
- Modify: `wms/static/scan/scan-bootstrap.css`
- Modify: `wms/tests/templatetags/tests_wms_ui.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing tests**

Add tests that assert:

- `ui_field` can render a red required marker for required fields
- the shared date input enhancer uses an icon-only trigger, not the visible `Calendrier` text
- the icon-only trigger keeps an explicit `aria-label`

Example template test:

```python
rendered = self._render("{% ui_field field_id='id_name' label='Nom' field_html=field_html required=True %}")
self.assertIn('ui-field-required-marker', rendered)
```

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.templatetags.tests_wms_ui \
  wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_shared_date_input_exposes_reusable_calendar_contract \
  -v 2
```

Expected: FAIL because the shared field / date contracts do not yet match.

**Step 3: Write the minimal implementation**

Implement:

- `ui_field(..., required=True)` support and the matching red marker in the shared component
- icon-only calendar button in the shared date enhancer
- CSS tweaks for the new button sizing and icon spacing

**Step 4: Run tests to verify they pass**

Run the same command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/templatetags/wms_ui.py templates/wms/components/field.html wms/static/scan/modules/core.js wms/static/scan/scan-bootstrap.css wms/tests/templatetags/tests_wms_ui.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: unify required markers and date icon buttons"
```

### Task 4: Add A Persistent Pending-Actions Masthead Indicator

**Files:**
- Modify: `wms/context_processors.py`
- Modify: `templates/scan/base.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing tests**

Add tests that assert:

- the scan masthead shows a persistent actions indicator when unresolved actions exist
- the indicator still appears even when the existing recipient-validation bell is not the only pending source
- the indicator links to the intended queue or dashboard anchor

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_masthead_shows_pending_actions_indicator \
  -v 2
```

Expected: FAIL because no persistent aggregate indicator exists.

**Step 3: Write the minimal implementation**

Implement:

- aggregate pending-action counts in `wms/context_processors.py`
- masthead indicator rendering in `templates/scan/base.html`
- clear copy such as `Actions en attente`

Keep the logic simple and query-backed; do not implement a read/unread notification state machine.

**Step 4: Run tests to verify they pass**

Run the same command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/context_processors.py templates/scan/base.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: show persistent pending actions in scan masthead"
```

### Task 5: Add The FAQ Change Log And Repo Rule

**Files:**
- Modify: `wms/views_scan_misc.py`
- Modify: `templates/scan/faq.html`
- Create: `docs/changelog/scan_faq_entries.json`
- Modify: `AGENTS.md`
- Modify: `wms/tests/views/tests_views_scan_misc.py`

**Step 1: Write the failing tests**

Add tests that assert:

- `/scan/faq/` renders a `Change Log` section
- the view exposes structured changelog entries
- the initial entry format includes date, PR number, and short summary

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc -v 2
```

Expected: FAIL because no changelog source or FAQ section exists.

**Step 3: Write the minimal implementation**

Implement:

- a small JSON changelog source under `docs/changelog/`
- FAQ context loading in `wms/views_scan_misc.py`
- `Change Log` rendering in `templates/scan/faq.html`
- a repo rule in `AGENTS.md` requiring a changelog entry per PR for this surface

Seed the first entry for this implementation PR only; do not backfill older work.

**Step 4: Run tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc -v 2
```

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_scan_misc.py templates/scan/faq.html docs/changelog/scan_faq_entries.json AGENTS.md wms/tests/views/tests_views_scan_misc.py
git commit -m "feat: add faq changelog feed"
```

### Task 6: Update Stock And Receipt Screens

**Files:**
- Modify: `wms/views_scan_stock.py`
- Modify: `templates/scan/stock.html`
- Modify: `templates/scan/stock_update.html`
- Modify: `wms/forms.py`
- Modify: `wms/views_scan_receipts.py`
- Modify: `templates/scan/includes/receive_pallet_create_card.html`
- Modify: `templates/scan/includes/receive_association_create_card.html`
- Modify: `templates/scan/billing_settings.html`
- Modify: `wms/forms_billing.py`
- Modify: `wms/views_scan_billing.py`
- Modify: `wms/tests/views/tests_views_scan_stock.py`
- Modify: `wms/tests/views/tests_views.py`
- Modify: `wms/tests/forms/tests_forms.py`
- Modify: `wms/tests/receipt/test_receipt_association_billing_fields.py`
- Modify: `wms/tests/views/test_views_scan_billing.py`

**Step 1: Write the failing tests**

Add tests that assert:

- `include_zero` defaults to enabled on `/scan/stock/`
- the `MAJ stock` collapse is open by default
- `Non conforme` sits above `Observation` on pallet and association receipts
- association receipt form preloads pickup cost / currency from the configured default service when the checkbox is enabled
- manual override still works when the checkbox is off

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_stock \
  wms.tests.views.tests_views \
  wms.tests.forms.tests_forms \
  wms.tests.receipt.test_receipt_association_billing_fields \
  wms.tests.views.test_views_scan_billing \
  -v 2
```

Expected: FAIL on the new default-state and pickup-default tests.

**Step 3: Write the minimal implementation**

Implement:

- stock include-zero default in `wms/views_scan_stock.py`
- open stock-update main collapse by default
- reorder the pallet / association receipt controls in templates
- add `use_default_pickup_service` form field and initial values
- resolve the default pickup service from billing settings / service catalog

Do not create billing document lines automatically from receipts in this task.

**Step 4: Run tests to verify they pass**

Run the same command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_scan_stock.py templates/scan/stock.html templates/scan/stock_update.html wms/forms.py wms/views_scan_receipts.py templates/scan/includes/receive_pallet_create_card.html templates/scan/includes/receive_association_create_card.html templates/scan/billing_settings.html wms/forms_billing.py wms/views_scan_billing.py wms/tests/views/tests_views_scan_stock.py wms/tests/views/tests_views.py wms/tests/forms/tests_forms.py wms/tests/receipt/test_receipt_association_billing_fields.py wms/tests/views/test_views_scan_billing.py
git commit -m "feat: adjust stock and receipt operational defaults"
```

### Task 7: Add Product Removal In Pack And Carton Edit

**Files:**
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/pack_handlers.py`
- Modify: `templates/scan/pack.html`
- Modify: `wms/static/scan/scan.js`
- Modify: `wms/tests/orders/tests_pack_handlers.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing tests**

Add tests that assert:

- the pack draft UI exposes a remove-line control
- removing a draft line reduces `line_count` and keeps the remaining lines intact
- removing a persisted carton line restores stock and updates carton contents

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.orders.tests_pack_handlers \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_scan_bootstrap_ui \
  -v 2
```

Expected: FAIL because only add-line behavior exists today.

**Step 3: Write the minimal implementation**

Implement:

- remove-line buttons in the JS-generated pack lines
- server-side handling for reduced line sets
- carton edit mutation for removing persisted packed content and restoring stock

Respect existing dossier lock rules when the carton or shipment is no longer editable.

**Step 4: Run tests to verify they pass**

Run the same command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_scan_shipments.py wms/pack_handlers.py templates/scan/pack.html wms/static/scan/scan.js wms/tests/orders/tests_pack_handlers.py wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: allow removing products from pack flows"
```

### Task 8: Generate New Carton Codes Without Zero Padding

**Files:**
- Modify: `wms/domain/stock.py`
- Modify: `wms/tests/domain/tests_domain_stock_extra.py`

**Step 1: Write the failing tests**

Add tests that assert:

- new generated codes use `MM-1`, `MM-2`, `CN-1`
- existing padded codes remain untouched by `ensure_carton_code`
- legacy padded values and new compact values both remain accepted

Example:

```python
self.assertEqual(generate_carton_code(type_code="MM"), "MM-1")
```

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.domain.tests_domain_stock_extra -v 2
```

Expected: FAIL because generation still pads to 5 digits.

**Step 3: Write the minimal implementation**

Implement:

- compact formatter for new linear carton codes
- backward-compatible parsing / preservation for existing values

Do not migrate existing codes.

**Step 4: Run tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.domain.tests_domain_stock_extra -v 2
```

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/domain/stock.py wms/tests/domain/tests_domain_stock_extra.py
git commit -m "feat: generate future carton codes without zero padding"
```

### Task 9: Rework Shipment Carton Selection Grouping And Forced Count

**Files:**
- Modify: `wms/scan_carton_helpers.py`
- Modify: `wms/shipment_form_helpers.py`
- Modify: `wms/views_scan_shipments.py`
- Modify: `templates/scan/includes/shipment_create_details_panel.html`
- Modify: `wms/static/scan/scan.js`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing tests**

Add tests that assert:

- `cartons_json` exposes enough metadata to group by compatibility + preassignment
- the shipment create/edit template renders 4 grouped buckets
- group 3 highlights the other destination IATA
- shipment create/edit exposes `forced_carton_count`
- the same warning model as pack is shown when forcing the count

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_scan_bootstrap_ui \
  -v 2
```

Expected: FAIL because grouping and forced-count behavior are missing.

**Step 3: Write the minimal implementation**

Implement:

- grouping metadata in carton selection payloads
- grouped UI rendering in shipment details
- forced carton count field and POST handling mirroring pack behavior
- explicit confirmations for preassignment conflicts and incompatible choices

**Step 4: Run tests to verify they pass**

Run the same command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/scan_carton_helpers.py wms/shipment_form_helpers.py wms/views_scan_shipments.py templates/scan/includes/shipment_create_details_panel.html wms/static/scan/scan.js wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: group shipment carton choices and support forced counts"
```

### Task 10: Differentiate Shipment Dossier Actions Visually

**Files:**
- Modify: `templates/scan/includes/shipment_dossier_header.html`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing tests**

Add tests that assert:

- dossier primary actions no longer all share the same button variant
- `Modifier` remains primary
- `Confirmer prêt` keeps a success variant
- `Clore le dossier` keeps state-specific classes

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_scan_bootstrap_ui \
  -v 2
```

Expected: FAIL because the action hierarchy is still visually flat.

**Step 3: Write the minimal implementation**

Implement:

- clearer button variants in the shipment dossier header
- no workflow change; visuals only

**Step 4: Run tests to verify they pass**

Run the same command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add templates/scan/includes/shipment_dossier_header.html wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: clarify shipment dossier action hierarchy"
```

### Task 11: Show Billing Exchange Rates With 2 Default Decimals While Keeping Manual Precision

**Files:**
- Modify: `wms/views_scan_billing.py`
- Modify: `wms/tests/views/test_views_scan_billing.py`

**Step 1: Write the failing tests**

Add tests that assert:

- an auto-resolved rate such as `1.000000` renders as `1.00`
- a manual POST value such as `655.957000` is preserved and saved with full precision

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.test_views_scan_billing -v 2
```

Expected: FAIL because the initial display still uses the full fixed-point string.

**Step 3: Write the minimal implementation**

Implement:

- `.2f` display formatting only for auto-filled initial values
- preserve the raw user POST value when the field is manually supplied

**Step 4: Run tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.test_views_scan_billing -v 2
```

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_scan_billing.py wms/tests/views/test_views_scan_billing.py
git commit -m "feat: simplify default billing exchange rate display"
```

### Task 12: Run Targeted Verification And Close The Loop

**Files:**
- Modify if needed after failures from verification
- Re-check: `docs/plans/2026-04-24-scan-catalog-and-ops-adjustments-design.md`
- Re-check: `docs/repo-reference/03-impact-map.md`
- Re-check: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Run the targeted verification suite**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_admin \
  wms.tests.views.tests_views_scan_stock \
  wms.tests.views.tests_views_scan_misc \
  wms.tests.views.tests_views \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.orders.tests_pack_handlers \
  wms.tests.forms.tests_forms \
  wms.tests.templatetags.tests_wms_ui \
  wms.tests.receipt.test_receipt_association_billing_fields \
  wms.tests.domain.tests_domain_stock_extra \
  wms.tests.views.test_views_scan_billing \
  -v 2
```

Expected: PASS.

**Step 2: Fix any adjacent regressions**

If any test fails, make the smallest correction in the touched module before re-running the suite.

**Step 3: Re-check propagation**

Verify:

- the new catalogue dossier fully replaces the stock/admin `Ouvrir` path
- shared required markers and date buttons still behave on scan / portal / bénévole surfaces touched by shared contracts
- no repo-reference update is required beyond the changelog / repo rule additions made in this work

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: deliver scan catalog and ops adjustments"
```
