# Pack Unknown Product And Import Product Card Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add pack-page confirmation and direct navigation for unknown products, and upgrade the legacy Django import product card so it can create fuller products with guided selectors and warehouse-local rack color validation.

**Architecture:** Keep the legacy Django `scan` routes and shared pack/import templates, lock the new behavior with focused tests first, then implement the pack overlay in `scan.js` and `pack.html`, enrich the import datasets and selectors, add server-side rack-color validation scoped per warehouse, and expose the missing product fields already supported by the current model and import services.

**Tech Stack:** Django views/templates/forms/handlers, legacy scan JavaScript/CSS, Django test suite via `./.venv/bin/python manage.py test`

---

### Task 1: Lock Pack Unknown-Product Contracts With Failing Tests

**Files:**
- Modify: `wms/tests/orders/tests_pack_handlers.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing tests**

Add coverage for:

- `handle_pack_post()` still returning `Produit introuvable.` for an unknown product code
- `/scan/pack/` rendering:
  - the direct `Creer un nouveau produit` link
  - the unknown-product overlay
  - the import URL contract
- `/scan/carton/<id>/edit/` rendering the same pack creation affordances when the carton is editable

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.orders.tests_pack_handlers \
  wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected:
- FAIL because the pack page does not yet render the new overlay or creation button contracts

**Step 3: Write minimal implementation**

Only add the template context and HTML needed to satisfy the new rendering expectations while keeping the backend validation unchanged.

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 2: Add The Pack Overlay And Direct Create Button

**Files:**
- Modify: `templates/scan/pack.html`
- Modify: `wms/views_scan_shipments.py`
- Modify if needed: `wms/static/scan/scan.css`

**Step 1: Write the failing test**

Extend the pack view coverage to assert:

- the page exposes the import URL as page data
- the overlay carries the accepted text contract
- the `Creer un nouveau produit` button is present both on create and edit variants

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected:
- FAIL because the pack page still lacks the new UI contract

**Step 3: Write minimal implementation**

In `pack.html`:

- add a direct link button to `scan:scan_import`
- add the unknown-product overlay using the existing `scan-choice-overlay` primitive
- expose the import URL on `#pack-page`

In `views_scan_shipments.py`:

- ensure both `scan_pack` and `scan_carton_edit` pass the import URL through the shared render context if needed

In `scan.css`:

- only add scoped styling if the existing overlay primitive is insufficient

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 3: Add Front-End Unknown-Product Detection In Pack

**Files:**
- Modify: `wms/static/scan/scan.js`
- Test manually via page behavior after unit/view coverage stays green

**Step 1: Write the failing test or lock observable contract**

If there is existing JS integration coverage that can realistically assert the contract, extend it.
If not, lock the server-rendered contract first, then implement the JS with a tight manual verification note and keep the backend error as fallback.

**Step 2: Run test to verify baseline**

Run the same focused pack tests from Task 1 before touching JS so the server contract is stable.

Expected:
- PASS on the current server-side contract, with JS behavior still missing

**Step 3: Write minimal implementation**

Inside `setupPackLines()`:

- detect non-empty product values that do not match `findProduct(...)`
- open the overlay and remember the active product field
- on `Accepter`, redirect to the import URL
- on `Refuser`, clear the active field, re-focus it, close the overlay, and refresh line metrics
- wire the new direct create button to the same import destination
- avoid opening the overlay for empty values or known products

**Step 4: Verify behavior**

Manual verification in browser:

1. Open `/scan/pack/`
2. Type an unknown product and blur/change the field
3. Confirm the overlay appears
4. Click `Refuser` and confirm the field is emptied and focused
5. Re-enter an unknown product and click `Accepter`
6. Confirm redirect to `/scan/import/`
7. Repeat on `/scan/carton/<id>/edit/` for an editable carton

### Task 4: Lock Import Product Card Coverage With Failing Tests

**Files:**
- Modify: `wms/tests/scan/tests_scan_import_handlers.py`
- Modify: `wms/tests/views/tests_views_imports.py`
- Modify if needed: `wms/tests/imports/tests_import_services_products_extra.py`
- Modify if needed: `wms/tests/imports/tests_import_services_locations_extra.py`

**Step 1: Write the failing tests**

Add coverage for:

- the import page rendering the new product fields
- dedicated selector datasets for brands and richer location metadata
- known rack color being surfaced for an existing `(warehouse, zone)`
- rack color reuse being rejected within the same warehouse
- blank SKU still resulting in an auto-generated SKU on create

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.scan.tests_scan_import_handlers \
  wms.tests.views.tests_views_imports \
  wms.tests.imports.tests_import_services_products_extra \
  wms.tests.imports.tests_import_services_locations_extra -v 2
```

Expected:
- FAIL because the page, datasets, and rack-color uniqueness logic do not yet match the new contract

**Step 3: Write minimal implementation**

Only add the smallest backend/template changes needed to satisfy the failing assertions.

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 5: Enrich Import Selector Datasets

**Files:**
- Modify: `wms/scan_import_handlers.py`

**Step 1: Write the failing test**

Add assertions that `_build_import_selector_data()` includes:

- alphabetically sorted brand suggestions
- rack-aware location records sufficient for dependent UI behavior
- existing rack color values keyed by warehouse and rack

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.scan.tests_scan_import_handlers -v 2
```

Expected:
- FAIL because brands are not yet exposed as a dedicated dataset and location data is too coarse

**Step 3: Write minimal implementation**

Update selector builders to expose:

- a `brands` dataset from distinct non-empty `Product.brand` values
- any additional location/rack payload needed by the import UI
- stable alphabetical ordering

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 6: Upgrade The Import Product Card Template

**Files:**
- Modify: `templates/scan/includes/imports_products_card.html`
- Modify if needed: `templates/scan/import.html`

**Step 1: Write the failing test**

Add view assertions for the new fields and helper text:

- `weight_g`
- `length_cm`
- `width_cm`
- `height_cm`
- `volume_cm3`
- `storage_conditions`
- `perishable`
- `quarantine_default`
- SKU helper text about auto-generation

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_imports -v 2
```

Expected:
- FAIL because the current card does not render the richer product form

**Step 3: Write minimal implementation**

Extend the single-product card without disturbing the file-import section:

- add the missing fields in a compact layout
- keep the current naming contract aligned with `import_services_products.py`
- add helper text for blank SKU auto-generation

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 7: Rework Import Selector Behavior In JavaScript

**Files:**
- Modify: `wms/static/scan/import_selectors.js`

**Step 1: Lock the observable contract**

If there is existing JS coverage, extend it. Otherwise keep the contract anchored through rendered HTML/data tests and perform manual verification with a browser session.

**Step 2: Verify baseline**

Run the focused import tests from Tasks 4-6 first.

Expected:
- PASS on server contracts before JS behavior changes

**Step 3: Write minimal implementation**

Refactor only the import-product selectors needed for the new UX:

- separate product autocomplete from brand suggestions
- keep free text allowed for category, brand, warehouse, rack, aisle, shelf
- sort suggestions A-Z
- auto-fill `rack_color` when a known `(warehouse, zone)` pair is selected or typed
- keep `rack_color` editable only when the rack is new

**Step 4: Manual verification**

In `/scan/import/`:

1. confirm category suggestions are alphabetical and still accept free text
2. confirm brand suggestions no longer backfill the whole product
3. confirm selecting a known rack auto-fills the rack color
4. confirm a new rack leaves the color editable

### Task 8: Add Warehouse-Scoped Rack Color Validation

**Files:**
- Modify: `wms/import_services_products.py`
- Modify if needed: `wms/import_services_locations.py`
- Modify if needed: `wms/models_domain/inventory.py`
- Modify tests in import service suites

**Step 1: Write the failing test**

Add coverage showing:

- reusing the same color for two different racks in the same warehouse is rejected
- reusing the same color in different warehouses is allowed
- updating the color for the same rack keeps working

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.imports.tests_import_services_products_extra \
  wms.tests.imports.tests_import_services_locations_extra -v 2
```

Expected:
- FAIL because current logic only upserts `(warehouse, zone)` and does not check duplicate colors

**Step 3: Write minimal implementation**

Add server-side validation before `RackColor.objects.update_or_create(...)` so:

- conflicts are detected within the same warehouse
- the current rack can keep its own color
- the raised error is explicit enough to surface in import feedback

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 9: Re-Verify Targeted Flows And Repo-Reference Impact

**Files:**
- Modify if needed: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify if needed: `docs/repo-reference/03-impact-map.md`

**Step 1: Run focused verification**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.orders.tests_pack_handlers \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.scan.tests_scan_import_handlers \
  wms.tests.views.tests_views_imports \
  wms.tests.imports.tests_import_services_products_extra \
  wms.tests.imports.tests_import_services_locations_extra -v 2
```

Expected:
- PASS

**Step 2: Manual verification**

Check:

- `/scan/pack/`
- `/scan/carton/<id>/edit/`
- `/scan/import/`

Confirm:

- unknown pack product opens the overlay
- direct product-create button redirects to import
- import card exposes richer fields and selector behavior
- rack color is auto-filled for known racks and validated for new ones

**Step 3: Re-check repo-reference impact**

Confirm whether repo-reference wording needs an update because:

- `scan/pack` now exposes an explicit off-ramp to product creation
- `/scan/import/` product creation capabilities have materially changed

**Step 4: Update docs if needed**

If the operator-visible contract changed enough to deserve reference updates, update the relevant repo-reference sections in the same change.
