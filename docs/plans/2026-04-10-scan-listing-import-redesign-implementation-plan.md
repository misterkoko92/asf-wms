# Scan Listing Import Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split listing import into its own `scan` page, preserve Excel/CSV behavior, make PDF the primary robust workflow, and support incomplete-product reception plus guided completion.

**Architecture:** Move listing state and UI out of `receive_pallet` into a dedicated `scan_receive_listing` flow while reusing the current mapping/review pipeline. Introduce a richer PDF analysis stage, persistent incomplete-product tracking on `Product`, a reception buffer-location fallback, and a completion cockpit with single-item and bulk field updates. Keep everything on legacy Django `scan` and update sidebar/repo-reference contracts in the same work.

**Tech Stack:** Django 4.2 views/templates/forms/models, Django migrations, Django TestCase/SimpleTestCase, legacy scan Bootstrap templates, `pdfplumber`, `pypdfium2`

---

### Task 1: Lock the new scan listing navigation and page-shell contracts with failing UI tests

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `templates/scan/includes/scan_sidebar_navigation.html`
- Verify: `templates/scan/receive_pallet.html`
- Verify: `templates/scan/receive_listing.html`

**Step 1: Write the failing test**

Add one sidebar assertion for the new listing entry:

```python
def test_scan_sidebar_exposes_listing_link_in_reception_group(self):
    response = self.client.get(reverse("scan:scan_dashboard"))
    nav_html = self._scan_sidebar_html(response)

    self.assertIn(reverse("scan:scan_receive_listing"), nav_html)
    self._assert_nav_labels_in_order(
        nav_html,
        [
            "Réception palette",
            "Listing",
            "Réception association",
        ],
    )
```

Extend the receiving structure test:

```python
def test_scan_receive_listing_page_uses_design_component_classes(self):
    response = self.client.get(reverse("scan:scan_receive_listing"))

    self.assertContains(response, 'id="scan-receive-listing-pdf-card"')
    self.assertContains(response, 'id="scan-receive-listing-excel-card"')
    self.assertContains(response, 'id="scan-receive-listing-csv-card"')
    self.assertContains(response, 'id="scan-receive-listing-incomplete-products-card"')
```

Also assert the shortcut remains on `receive_pallet`:

```python
self.assertContains(response, reverse("scan:scan_receive_listing"))
self.assertContains(response, "Listing")
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_sidebar_exposes_listing_link_in_reception_group wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_receive_listing_page_uses_design_component_classes -v 2`

Expected: FAIL because the route, sidebar entry, page shell, and shortcut do not exist yet.

**Step 3: Write minimal implementation**

No production implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run the targeted tests above and confirm the failures are only missing route/template markers.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "test: lock scan listing navigation contracts"
```

### Task 2: Add the dedicated `scan_receive_listing` route, view, and page shell

**Files:**
- Modify: `wms/scan_urls.py`
- Modify: `wms/views_scan_receipts.py`
- Modify: `wms/views.py`
- Modify: `templates/scan/includes/scan_sidebar_navigation.html`
- Modify: `templates/scan/receive_pallet.html`
- Create: `templates/scan/receive_listing.html`
- Create: `wms/tests/views/tests_views_scan_receipts.py`

**Step 1: Write the failing test**

Add view tests for the new route:

```python
def test_scan_receive_listing_returns_state_response_when_present(self):
    with mock.patch(
        "wms.views_scan_receipts.build_receive_listing_state",
        return_value={"response": HttpResponse("listing-response")},
    ):
        response = self.client.post(reverse("scan:scan_receive_listing"), {"action": "listing_upload"})
    self.assertEqual(response.content.decode(), "listing-response")
```

Add the render-path test:

```python
def test_scan_receive_listing_renders_context_when_no_state_response(self):
    with mock.patch(
        "wms.views_scan_receipts.build_receive_listing_state",
        return_value={"response": None, "state_key": "value"},
    ):
        with mock.patch(
            "wms.views_scan_receipts.build_receive_listing_context",
            return_value={"context_key": "listing"},
        ):
            with mock.patch("wms.views_scan_receipts.render", side_effect=self._render_stub):
                response = self.client.get(reverse("scan:scan_receive_listing"))
    self.assertEqual(response.content.decode(), "scan/receive_listing.html")
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_receipts.ScanReceiptsViewsTests.test_scan_receive_listing_returns_state_response_when_present wms.tests.views.tests_views_scan_receipts.ScanReceiptsViewsTests.test_scan_receive_listing_renders_context_when_no_state_response -v 2`

Expected: FAIL because `scan_receive_listing` and its builders do not exist yet.

**Step 3: Write minimal implementation**

Add the route:

```python
path("receive-listing/", views.scan_receive_listing, name="scan_receive_listing")
```

Add the view in `wms/views_scan_receipts.py`:

```python
@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_receive_listing(request):
    action = request.POST.get("action", "")
    state = build_receive_listing_state(request, action=action)
    if state["response"]:
        return state["response"]
    return render(request, "scan/receive_listing.html", build_receive_listing_context(state))
```

Keep `receive_pallet.html` focused on manual reception and add a visible tertiary link to `scan_receive_listing`.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_receipts.ScanReceiptsViewsTests.test_scan_receive_listing_returns_state_response_when_present wms.tests.views.tests_views_scan_receipts.ScanReceiptsViewsTests.test_scan_receive_listing_renders_context_when_no_state_response wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_receive_listing_page_uses_design_component_classes -v 2`

Expected: PASS for the new route/view/template shell markers.

**Step 5: Commit**

```bash
git add wms/scan_urls.py wms/views_scan_receipts.py wms/views.py templates/scan/includes/scan_sidebar_navigation.html templates/scan/receive_pallet.html templates/scan/receive_listing.html wms/tests/views/tests_views_scan_receipts.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add dedicated scan listing route"
```

### Task 3: Re-home the current Excel/CSV listing state and redirects onto the new page

**Files:**
- Create: `wms/receipt_listing_state.py`
- Modify: `wms/receipt_pallet_state.py`
- Modify: `wms/pallet_listing_handlers.py`
- Modify: `wms/tests/receipt/tests_receipt_pallet.py`
- Create: `wms/tests/receipt/tests_receipt_listing.py`
- Modify: `wms/tests/pallet/tests_pallet_listing_handlers.py`

**Step 1: Write the failing test**

Create dedicated listing state tests:

```python
def test_build_receive_listing_context_uses_listing_active_key(self):
    context = build_receive_listing_context(state)
    self.assertEqual(context["active"], "receive_listing")
```

Update redirect expectations in handler tests:

```python
self.assertEqual(response.url, reverse("scan:scan_receive_listing"))
```

Keep `receive_pallet` tests asserting it no longer owns listing context:

```python
self.assertNotIn("listing_form", context)
self.assertEqual(context["active"], "receive_pallet")
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.receipt.tests_receipt_pallet wms.tests.pallet.tests_pallet_listing_handlers -v 2`

Expected: FAIL because listing state is still embedded in `receipt_pallet_state` and redirects still point to `scan_receive_pallet`.

**Step 3: Write minimal implementation**

Move the listing builder into a dedicated module:

```python
def build_receive_listing_state(request, *, action):
    listing_form = ScanReceiptPalletForm(
        request.POST if action == "listing_upload" else None,
        prefix="listing",
    )
    ...
```

Update handler redirects:

```python
return redirect("scan:scan_receive_listing")
```

Trim `build_receive_pallet_context()` so it only serves manual pallet creation.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.receipt.tests_receipt_pallet wms.tests.receipt.tests_receipt_listing wms.tests.pallet.tests_pallet_listing_handlers -v 2`

Expected: PASS with dedicated listing state ownership and updated redirects.

**Step 5: Commit**

```bash
git add wms/receipt_listing_state.py wms/receipt_pallet_state.py wms/pallet_listing_handlers.py wms/tests/receipt/tests_receipt_pallet.py wms/tests/receipt/tests_receipt_listing.py wms/tests/pallet/tests_pallet_listing_handlers.py
git commit -m "refactor: separate listing flow from pallet reception"
```

### Task 4: Add PDF analysis diagnostics and extraction-state coverage before mapping

**Files:**
- Modify: `wms/import_utils.py`
- Modify: `wms/pallet_listing.py`
- Modify: `wms/pallet_listing_handlers.py`
- Modify: `wms/tests/imports/tests_import_utils.py`
- Modify: `wms/tests/pallet/tests_pallet_listing_handlers.py`

**Step 1: Write the failing test**

Add a PDF analysis helper test:

```python
def test_analyze_pdf_listing_reports_page_diagnostics(self):
    fake_page = SimpleNamespace(
        extract_table=lambda: [["Nom", "Qte"], ["Mask", "3"]],
        extract_text=lambda: "Nom  Qte\nMask  3",
    )
    fake_pdf_module = SimpleNamespace(open=lambda *_args, **_kwargs: _FakePdf([fake_page]))
    with mock.patch("wms.import_utils.pdfplumber", fake_pdf_module):
        analysis = import_utils.analyze_pdf_listing(b"%PDF-1")
    self.assertEqual(analysis["total_pages"], 1)
    self.assertEqual(analysis["mode"], "text")
```

Add handler coverage for the new intermediate stage:

```python
self.assertEqual(state["listing_stage"], "analysis")
self.assertEqual(state["listing_pdf_analysis"]["total_pages"], 5)
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.imports.tests_import_utils.ImportUtilsTests.test_analyze_pdf_listing_reports_page_diagnostics wms.tests.pallet.tests_pallet_listing_handlers.PalletListingHandlersTests.test_handle_listing_upload_pdf_enters_analysis_stage -v 2`

Expected: FAIL because the analysis helper, state, and stage do not exist yet.

**Step 3: Write minimal implementation**

Add a helper such as:

```python
def analyze_pdf_listing(data):
    return {
        "total_pages": total_pages,
        "mode": "text",
        "pages": page_diagnostics,
        "extractable_pages": [1, 2],
    }
```

Persist it in pending session data and set:

```python
state["listing_stage"] = "analysis"
state["listing_pdf_analysis"] = analysis
```

Keep extraction code reusable so the final table load still calls the same low-level helpers.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.imports.tests_import_utils wms.tests.pallet.tests_pallet_listing_handlers -v 2`

Expected: PASS for the PDF analysis diagnostics and new handler stage.

**Step 5: Commit**

```bash
git add wms/import_utils.py wms/pallet_listing.py wms/pallet_listing_handlers.py wms/tests/imports/tests_import_utils.py wms/tests/pallet/tests_pallet_listing_handlers.py
git commit -m "feat: add pdf analysis stage for listing imports"
```

### Task 5: Render the dedicated PDF analysis UI and preserve Excel/CSV cards

**Files:**
- Modify: `templates/scan/receive_listing.html`
- Create: `templates/scan/includes/receive_listing_pdf_card.html`
- Create: `templates/scan/includes/receive_listing_excel_card.html`
- Create: `templates/scan/includes/receive_listing_csv_card.html`
- Create: `templates/scan/includes/receive_listing_mapping_card.html`
- Create: `templates/scan/includes/receive_listing_review_card.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Extend UI assertions:

```python
self.assertContains(response, 'id="scan-receive-listing-analysis-card"')
self.assertContains(response, 'name="listing_pdf_pages_mode"')
self.assertContains(response, 'id="listing_pdf_page_start"')
self.assertContains(response, 'id="listing_pdf_page_end"')
self.assertContains(response, "Pages detectees")
```

Keep Excel/CSV shells visible:

```python
self.assertContains(response, 'id="scan-receive-listing-excel-card"')
self.assertContains(response, 'id="scan-receive-listing-csv-card"')
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_receive_listing_page_uses_design_component_classes -v 2`

Expected: FAIL because the analysis card and split import cards are not rendered yet.

**Step 3: Write minimal implementation**

Keep `receive_listing.html` as the shell:

```django
{% include "scan/includes/receive_listing_pdf_card.html" %}
{% include "scan/includes/receive_listing_excel_card.html" %}
{% include "scan/includes/receive_listing_csv_card.html" %}
{% if listing_stage == "analysis" %}
  {% include "scan/includes/receive_listing_analysis_card.html" %}
{% endif %}
```

Render page diagnostics and page-selection controls only for the PDF path. Keep existing mapping/review hooks and field names unchanged wherever possible.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_receive_listing_page_uses_design_component_classes -v 2`

Expected: PASS for the listing page structure assertions.

**Step 5: Commit**

```bash
git add templates/scan/receive_listing.html templates/scan/includes/receive_listing_pdf_card.html templates/scan/includes/receive_listing_excel_card.html templates/scan/includes/receive_listing_csv_card.html templates/scan/includes/receive_listing_mapping_card.html templates/scan/includes/receive_listing_review_card.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: render scan listing import cards"
```

### Task 6: Add persistent incomplete-product tracking and a reception buffer location

**Files:**
- Modify: `wms/models_domain/catalog.py`
- Create: `wms/migrations/<next>_product_is_incomplete.py`
- Modify: `wms/import_services_locations.py`
- Modify: `wms/import_services_products.py`
- Modify: `wms/tests/imports/tests_import_services_pallet.py`
- Create: `wms/tests/imports/tests_import_services_locations_extra.py`

**Step 1: Write the failing test**

Add a product creation expectation:

```python
self.assertTrue(product.is_incomplete)
```

Add a buffer-location expectation:

```python
self.assertEqual(location.zone, "TEMP")
self.assertEqual(location.aisle, "RECEPTION")
self.assertEqual(location.shelf, "LISTING")
```

Add a migration sanity check by asserting the new field defaults to `False` for normal products in model tests if such tests already exist locally.

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.imports.tests_import_services_pallet wms.tests.imports.tests_import_services_locations_extra -v 2`

Expected: FAIL because `Product` has no `is_incomplete` flag and listing import still hard-fails when no location is available.

**Step 3: Write minimal implementation**

Add the model field:

```python
is_incomplete = models.BooleanField(default=False)
```

Add a helper in `wms/import_services_locations.py`:

```python
def get_or_create_listing_buffer_location(default_warehouse):
    return get_or_create_location(default_warehouse.name, "TEMP", "RECEPTION", "LISTING")
```

Use it as the final fallback when no explicit or default location exists.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py makemigrations wms`

Expected: Create one migration adding `Product.is_incomplete`.

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.imports.tests_import_services_pallet wms.tests.imports.tests_import_services_locations_extra -v 2`

Expected: PASS with the buffer-location fallback and new incomplete-product field available.

**Step 5: Commit**

```bash
git add wms/models_domain/catalog.py wms/migrations wms/import_services_locations.py wms/import_services_products.py wms/tests/imports/tests_import_services_pallet.py wms/tests/imports/tests_import_services_locations_extra.py
git commit -m "feat: track incomplete products and listing buffer location"
```

### Task 7: Extend matching and pallet import to create incomplete products instead of blocking

**Files:**
- Modify: `wms/pallet_listing.py`
- Modify: `wms/import_services_pallet.py`
- Modify: `wms/import_services_products.py`
- Modify: `wms/scan_product_helpers.py`
- Modify: `wms/tests/imports/tests_import_services_pallet.py`
- Modify: `wms/tests/pallet/tests_pallet_listing_handlers.py`

**Step 1: Write the failing test**

Add a matching-order test:

```python
def test_build_listing_review_rows_prefers_ean_barcode_before_name_brand(self):
    review_rows = build_listing_review_rows(rows, mapping)
    self.assertEqual(review_rows[0]["match_type"], "ean")
```

Add an import-path test for incomplete product creation:

```python
with mock.patch("wms.import_services_pallet.import_product_row", return_value=(product, True, [])):
    created, skipped, errors, receipt = apply_pallet_listing_import(...)
self.assertEqual(errors, [])
self.assertTrue(product.is_incomplete)
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.imports.tests_import_services_pallet wms.tests.pallet.tests_pallet_listing_handlers -v 2`

Expected: FAIL because matching still centers on `name + brand` and new products are not marked incomplete by the pallet listing path.

**Step 3: Write minimal implementation**

Update match resolution order in `wms/pallet_listing.py` and `wms/scan_product_helpers.py`:

```python
matches = find_product_matches(
    sku=sku_or_barcode,
    name=name,
    brand=brand,
    ean=ean,
    barcode=barcode,
)
```

Mark minimal products created from listing rows:

```python
new_row["is_incomplete"] = True
```

Keep line-level statuses so the review UI can expose `match exact`, `match a confirmer`, `nouveau produit incomplet`, and `emplacement manquant`.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.imports.tests_import_services_pallet wms.tests.pallet.tests_pallet_listing_handlers -v 2`

Expected: PASS for the new matching priority and incomplete-product creation path.

**Step 5: Commit**

```bash
git add wms/pallet_listing.py wms/import_services_pallet.py wms/import_services_products.py wms/scan_product_helpers.py wms/tests/imports/tests_import_services_pallet.py wms/tests/pallet/tests_pallet_listing_handlers.py
git commit -m "feat: accept incomplete products in listing imports"
```

### Task 8: Add the incomplete-product cockpit and single-product completion screen

**Files:**
- Modify: `wms/views_scan_receipts.py`
- Modify: `wms/forms.py`
- Modify: `wms/scan_urls.py`
- Create: `templates/scan/receive_listing_product_edit.html`
- Modify: `templates/scan/includes/receive_listing_incomplete_products_card.html`
- Modify: `wms/tests/views/tests_views_scan_receipts.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add the cockpit render test:

```python
def test_scan_receive_listing_renders_incomplete_product_rows(self):
    product = Product.objects.create(name="Mask", is_incomplete=True)
    response = self.client.get(reverse("scan:scan_receive_listing"))
    self.assertContains(response, "Mask")
    self.assertContains(response, "Ouvrir")
```

Add the single-edit screen test:

```python
def test_scan_receive_listing_product_edit_updates_product_and_clears_incomplete(self):
    product = Product.objects.create(name="Mask", is_incomplete=True, warehouse=...)
    response = self.client.post(
        reverse("scan:scan_receive_listing_product_edit", args=[product.id]),
        {"name": "Mask", "brand": "ASF", "action": "save"},
    )
    product.refresh_from_db()
    self.assertFalse(product.is_incomplete)
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_receipts -v 2`

Expected: FAIL because the cockpit data, edit route, and form do not exist yet.

**Step 3: Write minimal implementation**

Add list/query composition inside `scan_receive_listing` context:

```python
incomplete_products = Product.objects.filter(is_incomplete=True).select_related("category", "default_location")
```

Add a simple edit form and view:

```python
@scan_staff_required
def scan_receive_listing_product_edit(request, product_id):
    ...
```

Render the table with per-row checkbox + `Ouvrir` action.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_receipts wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_receive_listing_page_uses_design_component_classes -v 2`

Expected: PASS for cockpit rendering and the single-product completion route.

**Step 5: Commit**

```bash
git add wms/views_scan_receipts.py wms/forms.py wms/scan_urls.py templates/scan/receive_listing_product_edit.html templates/scan/includes/receive_listing_incomplete_products_card.html wms/tests/views/tests_views_scan_receipts.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add incomplete product completion cockpit"
```

### Task 9: Add bulk field updates for incomplete products with identifier safeguards

**Files:**
- Modify: `wms/forms.py`
- Modify: `wms/views_scan_receipts.py`
- Modify: `templates/scan/includes/receive_listing_incomplete_products_card.html`
- Modify: `wms/tests/views/tests_views_scan_receipts.py`

**Step 1: Write the failing test**

Add one safe shared-field bulk action test:

```python
def test_scan_receive_listing_bulk_sets_category_for_selected_products(self):
    ...
    self.assertEqual(product_1.category, category)
    self.assertEqual(product_2.category, category)
```

Add one identifier-guard test:

```python
def test_scan_receive_listing_bulk_rejects_duplicate_ean_assignment(self):
    response = self.client.post(
        reverse("scan:scan_receive_listing"),
        {
            "action": "bulk_update_incomplete_products",
            "selected_product_ids": [str(product_1.id), str(product_2.id)],
            "field_name": "ean",
            "field_value": "1234567890123",
        },
    )
    self.assertContains(response, "EAN")
    self.assertContains(response, "ne peut pas etre applique en masse")
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_receipts -v 2`

Expected: FAIL because bulk update actions and identifier safeguards do not exist yet.

**Step 3: Write minimal implementation**

Add a bulk action form that normalizes:

```python
SAFE_SHARED_FIELDS = {"category", "brand", "default_location", "storage_conditions", ...}
IDENTIFIER_FIELDS = {"name", "sku", "ean", "barcode"}
```

Handle the post action in `scan_receive_listing`:

```python
if field_name in IDENTIFIER_FIELDS and len(selected_products) > 1:
    form.add_error("field_name", "Ce champ ne peut pas etre applique en masse.")
```

Apply shared-field updates only after validation passes.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_receipts -v 2`

Expected: PASS for bulk shared-field updates and identifier safeguards.

**Step 5: Commit**

```bash
git add wms/forms.py wms/views_scan_receipts.py templates/scan/includes/receive_listing_incomplete_products_card.html wms/tests/views/tests_views_scan_receipts.py
git commit -m "feat: add bulk completion actions for incomplete products"
```

### Task 10: Update repo-reference docs and run the focused verification matrix

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Verify: `docs/plans/2026-04-10-scan-listing-import-redesign-design.md`
- Verify: `docs/plans/2026-04-10-scan-listing-import-redesign-implementation-plan.md`

**Step 1: Write the failing test**

No automated failing test for docs, but create a manual verification checklist in the commit message and in the plan execution notes.

**Step 2: Run focused verification before doc edits**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_views_scan_receipts \
  wms.tests.receipt.tests_receipt_pallet \
  wms.tests.receipt.tests_receipt_listing \
  wms.tests.pallet.tests_pallet_listing_handlers \
  wms.tests.imports.tests_import_utils \
  wms.tests.imports.tests_import_services_pallet \
  wms.tests.imports.tests_import_services_locations_extra -v 2
```

Expected: PASS before closing the ticket.

**Step 3: Write minimal implementation**

Update repo-reference docs to reflect:
- the new `Reception > Listing` sidebar contract
- the dedicated listing route in scan receiving flows
- the fact that listing import now supports incomplete products and a completion cockpit

**Step 4: Re-run verification after doc updates**

Re-run the focused suite above and confirm no doc-driven rename or route drift was introduced.

**Step 5: Commit**

```bash
git add docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md docs/plans/2026-04-10-scan-listing-import-redesign-design.md docs/plans/2026-04-10-scan-listing-import-redesign-implementation-plan.md
git commit -m "docs: record scan listing import redesign"
```
