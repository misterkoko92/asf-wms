# Scan Assisted Product Suggestions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a conservative assisted-suggestion layer for listing imports and incomplete products, with strict auto-match on exact EAN, operator-validated global suggestions, and additional low-risk hardening for noisy import formats.

**Architecture:** Add a pure suggestion engine in a dedicated module, then reuse it from the listing review state and the shared incomplete-products cockpit. Keep analysis and application separate: exact-EAN auto-selection mutates only review state in `Listing`, while all other suggestions remain explicit operator actions and only fill empty fields.

**Tech Stack:** Django legacy scan views/templates/forms, existing listing handlers in `wms/pallet_listing_handlers.py`, shared incomplete-products helpers in `wms/incomplete_products.py`, Django TestCase/SimpleTestCase, legacy Bootstrap templates

---

### Task 1: Lock the parsing and non-product filtering contract with failing tests

**Files:**
- Modify: `wms/tests/imports/tests_import_utils.py`
- Modify: `wms/tests/pallet/tests_pallet_listing.py`
- Modify: `wms/tests/imports/tests_import_services_pallet.py`

**Step 1: Write the failing test**

Add normalization and filtering coverage:

```python
def test_parse_decimal_accepts_currency_percent_and_compact_formats(self):
    self.assertEqual(str(parse_decimal("3,75 EUR HT")), "3.75")
    self.assertEqual(str(parse_decimal("TVA 20%")), "20")

def test_parse_int_accepts_quantity_prefix_and_suffix(self):
    self.assertEqual(parse_int("x12"), 12)
    self.assertEqual(parse_int("12 pcs"), 12)

def test_apply_listing_mapping_skips_detected_summary_rows(self):
    rows = [["", "VALORISATION DU DON", "", "181", "1873,07 EUR"]]
    self.assertEqual(apply_listing_mapping(rows, {1: "name", 3: "quantity"}), [])
```

Add an import-service test proving summary rows do not raise import errors.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.imports.tests_import_utils wms.tests.pallet.tests_pallet_listing wms.tests.imports.tests_import_services_pallet -v 2`

Expected: FAIL because the parser still rejects some noisy values and summary rows are still treated as product rows.

**Step 3: Write minimal implementation**

No production code in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run the same targeted tests and confirm the failures are limited to missing parser/filter behavior.

**Step 5: Commit**

```bash
git add wms/tests/imports/tests_import_utils.py wms/tests/pallet/tests_pallet_listing.py wms/tests/imports/tests_import_services_pallet.py
git commit -m "test: lock listing parser hardening contract"
```

### Task 2: Implement low-risk format hardening and non-product row filtering

**Files:**
- Modify: `wms/import_utils.py`
- Modify: `wms/pallet_listing.py`
- Modify: `wms/import_services_pallet.py`
- Verify: `wms/pallet_listing_handlers.py`

**Step 1: Write the failing test**

Use the tests from Task 1.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.imports.tests_import_utils wms.tests.pallet.tests_pallet_listing wms.tests.imports.tests_import_services_pallet -v 2`

Expected: FAIL before implementation.

**Step 3: Write minimal implementation**

In `wms/import_utils.py`, extend text normalization:

```python
def _strip_numeric_noise(text):
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"(?i)(eur|euro|ht|ttc|tva|pcs|piece|pieces|unites?)", "", text)
```

In `wms/pallet_listing.py`, add row filtering:

```python
NON_PRODUCT_PATTERNS = ("TOTAL", "SOUS-TOTAL", "VALORISATION", "TRANSPORT", "PORT", "MANUTENTION")

def is_non_product_listing_row(row):
    ...
```

In `wms/import_services_pallet.py`, skip filtered rows with an informational skip instead of surfacing import errors.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.imports.tests_import_utils wms.tests.pallet.tests_pallet_listing wms.tests.imports.tests_import_services_pallet -v 2`

Expected: PASS with noisy numbers accepted and summary rows excluded.

**Step 5: Commit**

```bash
git add wms/import_utils.py wms/pallet_listing.py wms/import_services_pallet.py
git commit -m "feat: harden listing parsing and filter summary rows"
```

### Task 3: Add a pure assisted-suggestion engine with unit tests

**Files:**
- Create: `wms/incomplete_product_suggestions.py`
- Create: `wms/tests/stock/tests_incomplete_product_suggestions.py`
- Verify: `wms/models.py`
- Verify: `wms/import_services_products.py`

**Step 1: Write the failing test**

Add pure-engine tests:

```python
def test_build_listing_suggestions_auto_matches_unique_ean():
    result = analyze_listing_rows(rows=[...], products=[...])
    assert result.auto_matches["row-2"].product_id == product.id

def test_build_listing_suggestions_ignores_duplicate_ean_matches():
    result = analyze_listing_rows(rows=[...], products=[product_a, product_b])
    assert "row-2" not in result.auto_matches

def test_build_listing_suggestions_emits_brand_group_from_batch_prefix():
    result = analyze_listing_rows(rows=[...])
    assert result.group_suggestions[0]["field_name"] == "brand"
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.stock.tests_incomplete_product_suggestions -v 2`

Expected: FAIL because the suggestion module does not exist yet.

**Step 3: Write minimal implementation**

In `wms/incomplete_product_suggestions.py`, add pure helpers:

```python
def analyze_listing_rows(*, rows, products):
    return {
        "auto_matches": ...,
        "line_suggestions": ...,
        "group_suggestions": ...,
    }
```

Keep the first pass intentionally narrow:

- exact EAN auto-match
- repeated leading-brand prefix detection
- base-consensus suggestions for category, VAT, and location

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.stock.tests_incomplete_product_suggestions -v 2`

Expected: PASS with a pure, deterministic engine.

**Step 5: Commit**

```bash
git add wms/incomplete_product_suggestions.py wms/tests/stock/tests_incomplete_product_suggestions.py
git commit -m "feat: add incomplete product suggestion engine"
```

### Task 4: Wire exact-EAN auto-match and suggestion state into listing review

**Files:**
- Modify: `wms/pallet_listing.py`
- Modify: `wms/pallet_listing_handlers.py`
- Modify: `wms/receipt_listing_state.py`
- Modify: `wms/tests/pallet/tests_pallet_listing.py`
- Modify: `wms/tests/pallet/tests_pallet_listing_handlers.py`
- Modify: `wms/tests/receipt/tests_receipt_listing.py`

**Step 1: Write the failing test**

Add review-row tests:

```python
def test_build_listing_review_rows_marks_exact_ean_auto_match(self):
    row = review_rows[0]
    self.assertEqual(row["default_match"], "product:42")
    self.assertEqual(row["match_badge"], "Match auto EAN")
```

Add handler/state tests proving `listing_rows` now carries:

- `match_badge`
- `line_suggestions`
- `group_suggestions`

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.pallet.tests_pallet_listing wms.tests.pallet.tests_pallet_listing_handlers wms.tests.receipt.tests_receipt_listing -v 2`

Expected: FAIL because the current review rows do not expose suggestion metadata.

**Step 3: Write minimal implementation**

Update review row construction:

```python
review.append(
    {
        "index": row_index,
        "default_match": auto_match_value or default_match,
        "match_badge": "Match auto EAN" if auto_match else "",
        "line_suggestions": line_suggestions_by_row.get(row_key, []),
    }
)
```

Store `group_suggestions` on listing state/context without persisting them as standalone models.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.pallet.tests_pallet_listing wms.tests.pallet.tests_pallet_listing_handlers wms.tests.receipt.tests_receipt_listing -v 2`

Expected: PASS with exact-EAN preselection and suggestion metadata available to templates.

**Step 5: Commit**

```bash
git add wms/pallet_listing.py wms/pallet_listing_handlers.py wms/receipt_listing_state.py wms/tests/pallet/tests_pallet_listing.py wms/tests/pallet/tests_pallet_listing_handlers.py wms/tests/receipt/tests_receipt_listing.py
git commit -m "feat: add listing suggestion state"
```

### Task 5: Render the listing suggestion UI with global previews and line badges

**Files:**
- Modify: `templates/scan/receive_listing.html`
- Modify: `templates/scan/includes/receive_pallet_review_card.html`
- Create: `templates/scan/includes/receive_listing_suggestions_card.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_scan_receipts.py`

**Step 1: Write the failing test**

Add UI assertions:

```python
def test_scan_receive_listing_renders_suggestions_card_and_auto_ean_badge(self):
    response = self.client.get(reverse("scan:scan_receive_listing"))
    self.assertContains(response, 'id="scan-receive-listing-suggestions-card"')
    self.assertContains(response, "Match auto EAN")
    self.assertContains(response, "Voir les lignes")
```

Also assert the group preview table renders the proposed rows.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_receipts -v 2`

Expected: FAIL because there is no dedicated suggestion card yet.

**Step 3: Write minimal implementation**

Create a reusable suggestions include:

```django
{% include "scan/includes/receive_listing_suggestions_card.html" with suggestion_groups=listing_group_suggestions %}
```

In `receive_pallet_review_card.html`, add:

```django
{% if row.match_badge %}<span class="badge">{{ row.match_badge }}</span>{% endif %}
```

Render a compact preview table under each group suggestion with row-level checkboxes.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_receipts -v 2`

Expected: PASS with the global card and row badges.

**Step 5: Commit**

```bash
git add templates/scan/receive_listing.html templates/scan/includes/receive_pallet_review_card.html templates/scan/includes/receive_listing_suggestions_card.html wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_receipts.py
git commit -m "feat: render listing suggestion controls"
```

### Task 6: Add explicit listing actions to apply group suggestions to the current review state

**Files:**
- Modify: `wms/forms.py`
- Modify: `wms/pallet_listing_handlers.py`
- Modify: `wms/receipt_listing_state.py`
- Modify: `wms/tests/pallet/tests_pallet_listing_handlers.py`
- Modify: `wms/tests/views/tests_views_scan_receipts.py`

**Step 1: Write the failing test**

Add handler coverage:

```python
def test_listing_apply_suggestion_group_updates_only_selected_rows_and_empty_fields(self):
    response = self._post(
        action="listing_apply_suggestion_group",
        suggestion_id="brand:braun",
        selected_row_indexes=["2", "3"],
    )
    self.assertEqual(updated_rows[0]["brand"], "BRAUN")
    self.assertEqual(updated_rows[0]["name"], "THERMOMETRE")
```

Assert that an already filled field is not overwritten.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.pallet.tests_pallet_listing_handlers wms.tests.views.tests_views_scan_receipts -v 2`

Expected: FAIL because there is no action to apply suggestion groups.

**Step 3: Write minimal implementation**

Add a small form or POST parser:

```python
class ScanListingSuggestionApplyForm(forms.Form):
    suggestion_id = forms.CharField()
    selected_row_indexes = forms.MultipleChoiceField(required=False)
```

In the handler:

```python
if action == "listing_apply_suggestion_group":
    pending = request.session["pallet_listing_pending"]
    rows = rebuild_review_rows(...)
    apply_group_suggestion(rows=rows, ...)
```

Persist only the updated review-state values already used by the review form/session.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.pallet.tests_pallet_listing_handlers wms.tests.views.tests_views_scan_receipts -v 2`

Expected: PASS with explicit review-state mutation and no unintended overwrites.

**Step 5: Commit**

```bash
git add wms/forms.py wms/pallet_listing_handlers.py wms/receipt_listing_state.py wms/tests/pallet/tests_pallet_listing_handlers.py wms/tests/views/tests_views_scan_receipts.py
git commit -m "feat: apply listing suggestion groups"
```

### Task 7: Reuse the same suggestion engine in the persistent incomplete-products cockpit

**Files:**
- Modify: `wms/incomplete_products.py`
- Modify: `wms/views_scan_stock.py`
- Modify: `wms/views_scan_receipts.py`
- Modify: `templates/scan/includes/receive_listing_incomplete_products_card.html`
- Modify: `templates/scan/includes/receive_listing_incomplete_products_script.html`
- Modify: `wms/tests/views/tests_views_scan_stock.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add stock-update assertions:

```python
def test_scan_stock_update_renders_suggestions_for_filtered_incomplete_products(self):
    response = self.client.get(reverse("scan:scan_stock_update"), {"incomplete_receipt_id": receipt.id})
    self.assertContains(response, 'id="scan-stock-update-suggestions-card"')
    self.assertContains(response, "Appliquer aux lignes proposees")
```

Add a listing-side assertion that the last-import incomplete-products card can also render suggestion groups.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_stock wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL because the shared incomplete-products card has no suggestion context.

**Step 3: Write minimal implementation**

Extend the shared context builder:

```python
return {
    ...,
    "incomplete_product_suggestions": analyze_incomplete_products(products),
}
```

Render a shared suggestions section above the table and keep it compatible with both `Listing` and `MAJ Stock`.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_stock wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS with identical suggestion UX across both surfaces.

**Step 5: Commit**

```bash
git add wms/incomplete_products.py wms/views_scan_stock.py wms/views_scan_receipts.py templates/scan/includes/receive_listing_incomplete_products_card.html templates/scan/includes/receive_listing_incomplete_products_script.html wms/tests/views/tests_views_scan_stock.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add incomplete product suggestions to stock cockpit"
```

### Task 8: Add persistent suggestion-application actions for incomplete products and update docs

**Files:**
- Modify: `wms/forms.py`
- Modify: `wms/incomplete_products.py`
- Modify: `wms/views_scan_stock.py`
- Modify: `wms/views_scan_receipts.py`
- Modify: `wms/tests/views/tests_views_scan_stock.py`
- Modify: `wms/tests/views/tests_views_scan_receipts.py`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Write the failing test**

Add POST coverage:

```python
def test_scan_stock_update_apply_suggestion_group_updates_only_empty_fields(self):
    response = self.client.post(reverse("scan:scan_stock_update"), data={...})
    product.refresh_from_db()
    self.assertEqual(product.brand, "BRAUN")
```

Add a docs assertion only if the repo uses explicit docs checks; otherwise use a manual verification note.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_stock wms.tests.views.tests_views_scan_receipts -v 2`

Expected: FAIL because no suggestion-application POST action exists for the incomplete-products cockpit.

**Step 3: Write minimal implementation**

Add explicit POST handling:

```python
if action == "apply_incomplete_product_suggestion_group":
    updated_count = apply_incomplete_product_suggestion_group(...)
```

Update repo-reference docs to mention:

- exact-EAN auto-match in listing review
- shared `Suggestions detectees` contract
- operator-only application for non-EAN suggestions

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_stock wms.tests.views.tests_views_scan_receipts -v 2`

Expected: PASS with durable stock-update application and docs aligned.

**Step 5: Commit**

```bash
git add wms/forms.py wms/incomplete_products.py wms/views_scan_stock.py wms/views_scan_receipts.py wms/tests/views/tests_views_scan_stock.py wms/tests/views/tests_views_scan_receipts.py docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md
git commit -m "feat: apply assisted suggestions to incomplete products"
```

### Task 9: Run the full targeted regression suite and clean up

**Files:**
- Verify: `wms/import_utils.py`
- Verify: `wms/incomplete_product_suggestions.py`
- Verify: `wms/pallet_listing.py`
- Verify: `wms/pallet_listing_handlers.py`
- Verify: `wms/incomplete_products.py`
- Verify: `templates/scan/receive_listing.html`
- Verify: `templates/scan/includes/receive_listing_incomplete_products_card.html`

**Step 1: Write the failing test**

No new tests in this task.

**Step 2: Run test to verify the integrated suite**

Run: `./.venv/bin/python manage.py test wms.tests.imports.tests_import_utils wms.tests.imports.tests_import_services_pallet wms.tests.stock.tests_incomplete_product_suggestions wms.tests.pallet.tests_pallet_listing wms.tests.pallet.tests_pallet_listing_handlers wms.tests.receipt.tests_receipt_listing wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_receipts wms.tests.views.tests_views_scan_stock -v 1`

Expected: PASS with no new regressions.

**Step 3: Write minimal implementation**

No production code in this task. Only trim dead branches or duplicate helpers discovered while running the integrated suite.

**Step 4: Run test to verify it still passes**

Re-run the same targeted suite and confirm stable green output.

**Step 5: Commit**

```bash
git add wms/import_utils.py wms/incomplete_product_suggestions.py wms/pallet_listing.py wms/pallet_listing_handlers.py wms/incomplete_products.py templates/scan/receive_listing.html templates/scan/includes/receive_listing_incomplete_products_card.html docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md
git commit -m "test: verify assisted product suggestion flow"
```
