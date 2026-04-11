# Scan Listing Simplification And Stock Incomplete Cockpit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Simplify `/scan/receive-listing/` into a strict receipt-linked import flow and move the global incomplete-product cockpit to `/scan/stock-update/` with receipt filtering.

**Architecture:** Remove inline receipt-draft creation from listing, require an existing pallet receipt before any file import UI appears, keep PDF/Excel/CSV pipelines behind that intake gate, and extract incomplete-product querying/update helpers into a shared module reused by listing post-import and stock-update. Listing should only show incomplete products after a confirmed import, while stock update becomes the persistent global backlog cockpit.

**Tech Stack:** Django views/forms/templates, legacy scan Bootstrap templates, Django test suite

---

### Task 1: Lock the new listing intake contract with failing tests

**Files:**
- Modify: `wms/tests/receipt/tests_receipt_listing.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_scan_receipts.py`

**Step 1: Write the failing test**

Add tests that assert:

- the listing intake form requires both file type and receipt
- the inline receipt-draft card is no longer rendered
- the `Créer une réception` shortcut is present on listing
- the incomplete-products block is absent on initial listing load
- the incomplete-products block appears only after `listing_confirm` and only when the session carries the last import incomplete-product ids

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.receipt.tests_receipt_listing wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_receipts -v 2`

Expected: FAIL because listing still supports draft receipt creation and still renders the incomplete-products block too early.

**Step 3: Write minimal implementation**

Update listing state/context/tests contract only after the failures are confirmed.

**Step 4: Run test to verify it passes**

Run the same command.

Expected: PASS for the new listing contract.

**Step 5: Commit**

```bash
git add wms/tests/receipt/tests_receipt_listing.py wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_receipts.py
git commit -m "test: lock simplified listing intake contract"
```

### Task 2: Extract shared incomplete-product helpers

**Files:**
- Create: `wms/incomplete_products.py`
- Modify: `wms/views_scan_receipts.py`
- Modify: `wms/views_scan_stock.py`
- Modify: `wms/forms.py`
- Test: `wms/tests/forms/test_forms_scan_receipts.py`
- Test: `wms/tests/views/tests_views_scan_receipts.py`
- Test: `wms/tests/views/tests_views_scan_stock.py`

**Step 1: Write the failing test**

Add tests for shared helper behavior:

- default queryset returns incomplete products
- filtering by receipt id keeps only products linked through `ProductLot.source_receipt`
- batch updates still validate against the filtered queryset
- shared receipt-filter choices use the same receipt label format as listing

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.forms.test_forms_scan_receipts wms.tests.views.tests_views_scan_receipts wms.tests.views.tests_views_scan_stock -v 2`

Expected: FAIL because no shared helper module exists and stock update has no incomplete-product context yet.

**Step 3: Write minimal implementation**

Create a shared helper module that owns:

- base incomplete-products queryset
- optional receipt-linked filtering
- bulk update application
- receipt filter queryset/label builder
- shared context builder for templates

Keep the edit route unchanged for now.

**Step 4: Run test to verify it passes**

Run the same command.

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/incomplete_products.py wms/views_scan_receipts.py wms/views_scan_stock.py wms/forms.py wms/tests/forms/test_forms_scan_receipts.py wms/tests/views/tests_views_scan_receipts.py wms/tests/views/tests_views_scan_stock.py
git commit -m "refactor: share incomplete product helpers"
```

### Task 3: Simplify listing state and remove receipt-draft flow

**Files:**
- Modify: `wms/receipt_listing_state.py`
- Modify: `wms/pallet_listing_handlers.py`
- Modify: `wms/forms.py`
- Delete or stop using: `templates/scan/includes/receive_listing_receipt_draft_card.html`
- Test: `wms/tests/receipt/tests_receipt_listing.py`
- Test: `wms/tests/pallet/tests_pallet_listing_handlers.py`

**Step 1: Write the failing test**

Add tests for:

- `ScanListingEntryForm` rejecting missing receipt
- `listing_configure` storing a required `receipt_id`
- `listing_confirm` always reusing the selected receipt
- no draft-receipt fallback remaining in the listing handler path

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.receipt.tests_receipt_listing wms.tests.pallet.tests_pallet_listing_handlers -v 2`

Expected: FAIL because receipt is still optional in the form/state and the old draft logic still exists.

**Step 3: Write minimal implementation**

Remove receipt-draft flow from listing state and handlers. Keep only:

- selected file type
- selected existing receipt id

Persist only what is needed for the import pipeline.

**Step 4: Run test to verify it passes**

Run the same command.

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/receipt_listing_state.py wms/pallet_listing_handlers.py wms/forms.py templates/scan/includes/receive_listing_receipt_draft_card.html wms/tests/receipt/tests_receipt_listing.py wms/tests/pallet/tests_pallet_listing_handlers.py
git commit -m "feat: require existing receipt for listing imports"
```

### Task 4: Rebuild listing templates around the simpler intake flow

**Files:**
- Modify: `templates/scan/receive_listing.html`
- Modify: `templates/scan/includes/receive_listing_intake_card.html`
- Modify: `templates/scan/includes/receive_pallet_listing_upload_card.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add or update UI tests so they assert:

- initial listing page shows only the intake card
- receipt warning copy is visible
- `Créer une réception` button links to `/scan/receive-pallet/`
- only the selected file-type card appears after configuration
- incomplete-product card is absent before final confirm

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL because listing still renders more than the intake card and still exposes incomplete products too early.

**Step 3: Write minimal implementation**

Adjust templates and context conditions so listing behaves as a gated import surface.

**Step 4: Run test to verify it passes**

Run the same command.

Expected: PASS.

**Step 5: Commit**

```bash
git add templates/scan/receive_listing.html templates/scan/includes/receive_listing_intake_card.html templates/scan/includes/receive_pallet_listing_upload_card.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: simplify listing page flow"
```

### Task 5: Add post-import incomplete-product recap for listing only

**Files:**
- Modify: `wms/import_services_pallet.py`
- Modify: `wms/pallet_listing_handlers.py`
- Modify: `wms/views_scan_receipts.py`
- Modify: `templates/scan/receive_listing.html`
- Modify: `templates/scan/includes/receive_listing_incomplete_products_card.html`
- Test: `wms/tests/imports/tests_import_services_pallet.py`
- Test: `wms/tests/pallet/tests_pallet_listing_handlers.py`
- Test: `wms/tests/views/tests_views_scan_receipts.py`

**Step 1: Write the failing test**

Add tests asserting:

- listing confirm stores the ids of incomplete products created or touched by the import
- after redirect, listing shows only those incomplete products
- the post-import recap is absent when no incomplete products were produced

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.imports.tests_import_services_pallet wms.tests.pallet.tests_pallet_listing_handlers wms.tests.views.tests_views_scan_receipts -v 2`

Expected: FAIL because import services do not currently return or persist the incomplete-product subset for the confirmed import.

**Step 3: Write minimal implementation**

Return the incomplete-product ids from import services, persist them in session on confirm, and render the recap only after a confirmed import.

**Step 4: Run test to verify it passes**

Run the same command.

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/import_services_pallet.py wms/pallet_listing_handlers.py wms/views_scan_receipts.py templates/scan/receive_listing.html templates/scan/includes/receive_listing_incomplete_products_card.html wms/tests/imports/tests_import_services_pallet.py wms/tests/pallet/tests_pallet_listing_handlers.py wms/tests/views/tests_views_scan_receipts.py
git commit -m "feat: show listing incomplete recap after confirm"
```

### Task 6: Add incomplete-product cockpit to stock update

**Files:**
- Modify: `wms/views_scan_stock.py`
- Modify: `templates/scan/stock_update.html`
- Test: `wms/tests/views/tests_views_scan_stock.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add tests asserting:

- stock update renders a collapsed `MAJ Stock` card closed by default
- stock update renders an open `Produits incomplets` collapse by default
- the receipt filter select is visible with default `Toutes les réceptions`
- batch and individual incomplete-product actions are available from stock update

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_stock wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL because stock update currently renders only the stock form card.

**Step 3: Write minimal implementation**

Reuse the shared incomplete-product helper context in stock update and wrap both cards in collapses with the required defaults.

**Step 4: Run test to verify it passes**

Run the same command.

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_scan_stock.py templates/scan/stock_update.html wms/tests/views/tests_views_scan_stock.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add incomplete product cockpit to stock update"
```

### Task 7: Update docs and run the relevant full suite

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Verify: `docs/plans/2026-04-11-scan-listing-simplification-and-stock-incomplete-design.md`
- Verify: `docs/plans/2026-04-11-scan-listing-simplification-and-stock-incomplete-implementation-plan.md`

**Step 1: Write the failing test**

No new runtime test here. This is a docs/verification task.

**Step 2: Run verification**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.receipt.tests_receipt_listing \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_views_scan_receipts \
  wms.tests.views.tests_views_scan_stock \
  wms.tests.pallet.tests_pallet_listing_handlers \
  wms.tests.imports.tests_import_services_pallet \
  wms.tests.forms.test_forms_scan_receipts \
  -v 1
```

Expected: PASS.

**Step 3: Update docs**

Document:

- listing now requires an existing receipt before import
- incomplete-product global cockpit now lives under stock update
- listing only shows a post-confirm import-linked incomplete recap
- stock-update incomplete filter can scope by linked receipt

**Step 4: Commit**

```bash
git add docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md docs/plans/2026-04-11-scan-listing-simplification-and-stock-incomplete-design.md docs/plans/2026-04-11-scan-listing-simplification-and-stock-incomplete-implementation-plan.md
git commit -m "docs: align listing and stock update contracts"
```
