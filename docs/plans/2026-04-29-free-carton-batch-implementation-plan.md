# Free Carton Batch Preparation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a safe `Batch colis libres` mode that creates N identical available cartons without destination or shipment, then lets staff assign them later from `Vue Colis`.

**Architecture:** Reuse the legacy Django `/scan/pack/` workflow and existing `pack_carton` stock mutation path. Add one explicit batch action whose line quantities mean "per carton", not "total quantity to split". Keep `Vue Colis` as the assignment surface and add only the filters needed to find free available cartons.

**Tech Stack:** Django views/forms/templates, legacy scan JS/CSS, Django TestCase, existing `wms.pack_handlers`, `wms.scan_pack_helpers`, `wms.carton_handlers`, `wms.carton_view_helpers`.

---

### Task 1: Lock The Batch Semantics With Handler Tests

**Files:**
- Modify: `wms/tests/orders/tests_pack_handlers.py`

**Step 1: Add failing tests**

Add tests near the existing `handle_pack_post` forced-carton tests:

```python
def test_handle_pack_post_free_batch_creates_identical_available_cartons(self):
    product = self._create_product_with_stock(
        sku="SYRINGE",
        name="Seringues",
        quantity_on_hand=4000,
        weight_g=10,
        length_cm=1,
        width_cm=1,
        height_cm=1,
    )
    request = self._request(
        {
            "action": "prepare_available_batch",
            "free_batch_carton_count": "32",
            "confirm_free_carton_batch": "1",
            "line_count": "1",
            "line_1_product_code": product.sku,
            "line_1_quantity": "100",
            "confirm_defaults": "1",
        }
    )

    response, state = handle_pack_post(request, form=ScanPackForm(data=request.POST), default_format=self.default_format)

    self.assertEqual(response.status_code, 302)
    cartons = Carton.objects.filter(shipment__isnull=True, preassigned_destination__isnull=True)
    self.assertEqual(cartons.count(), 32)
    self.assertTrue(all(carton.status == CartonStatus.PACKED for carton in cartons))
    self.assertTrue(all(carton.cartonitem_set.get().quantity == 100 for carton in cartons))
    product.productlot_set.get().refresh_from_db()
    self.assertEqual(product.productlot_set.get().quantity_on_hand, 800)
```

Add companion tests:

```python
def test_handle_pack_post_free_batch_requires_confirmation(self): ...
def test_handle_pack_post_free_batch_rejects_destination_or_shipment(self): ...
def test_handle_pack_post_free_batch_rolls_back_when_stock_is_insufficient(self): ...
def test_handle_pack_post_free_batch_rejects_carton_type_that_does_not_fit_once(self): ...
```

For preparateur coverage, add:

```python
def test_handle_pack_post_preparateur_free_batch_uses_active_volunteer(self): ...
def test_handle_pack_post_preparateur_free_batch_rejects_mixed_mm_cn_families(self): ...
```

**Step 2: Run test to verify failure**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.orders.tests_pack_handlers -v 2
```

Expected: FAIL because `prepare_available_batch`, `free_batch_carton_count`, and confirmation handling do not exist.

**Step 3: Checkpoint**

Do not commit unless the user has explicitly approved committing. Suggested message if approval exists:

```bash
git add wms/tests/orders/tests_pack_handlers.py
git commit -m "test: define free carton batch preparation"
```

### Task 2: Add Batch Parsing And Creation Logic

**Files:**
- Modify: `wms/scan_pack_helpers.py`
- Modify: `wms/pack_handlers.py`

**Step 1: Add helper tests if needed**

If the repeated-carton logic becomes non-trivial, add helper tests in:

- `wms/tests/scan/tests_scan_pack_helpers.py`

Target helper:

```python
def build_identical_carton_batch_bins(line_items, carton_size, carton_count, *, apply_defaults):
    single_bins, errors, warnings = build_packing_bins(
        line_items,
        carton_size,
        apply_defaults=apply_defaults,
    )
    if errors:
        return None, errors, warnings
    if len(single_bins or []) != 1:
        return None, ["Le colis type doit tenir dans un seul colis."], warnings
    return [copy.deepcopy(single_bins[0]) for _ in range(carton_count)], [], warnings
```

**Step 2: Implement minimal handler constants**

In `wms/pack_handlers.py`:

```python
PACK_ACTION_PREPARE_AVAILABLE_BATCH = "prepare_available_batch"
FREE_BATCH_CONFIRM_FIELD = "confirm_free_carton_batch"
```

Add parser:

```python
def _parse_free_batch_carton_count(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(_("Nombre de colis batch invalide.")) from exc
    if count <= 0:
        raise ValueError(_("Nombre de colis batch invalide."))
    return count
```

**Step 3: Enforce server-side safety**

Inside `handle_pack_post`, when action is `prepare_available_batch`:

- require `confirm_free_carton_batch == "1"`;
- require no shipment reference;
- require no preassigned destination;
- require `free_batch_carton_count >= 2` or allow `1` but treat it as normal available pack;
- preserve missing default checks;
- reject if no product lines.

**Step 4: Create cartons atomically**

Use `transaction.atomic()` and the existing `pack_carton` path:

```python
for bin_data in batch_bins:
    carton = None
    for entry in bin_data["items"].values():
        carton = pack_carton(
            user=request.user,
            product=entry["product"],
            quantity=entry["quantity"],
            carton=carton,
            carton_code=None,
            shipment=None,
            preassigned_destination=None,
            display_expires_on=entry.get("expires_on"),
            current_location=current_location,
            carton_size=carton_size,
            skip_picking_status=True,
            prepared_by_user=prepared_by_user,
            volunteer_profile=active_volunteer,
            actor_user=request.user,
        )
    set_carton_status(
        carton=carton,
        new_status=CartonStatus.PACKED,
        reason="scan_pack_free_batch_available",
        user=request.user,
    )
```

For non-preparateur mode, reuse `_resolve_ready_location_for_available_pack(line_items)` for the ready location.

For preparateur mode, reuse current family resolution and standard family format/location rules. If more than one MM/CN family is present, return an error for V1.

**Step 5: Run focused tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.orders.tests_pack_handlers wms.tests.scan.tests_scan_pack_helpers -v 2
```

Expected: PASS.

**Step 6: Checkpoint**

Commit only with explicit user approval. Suggested message:

```bash
git add wms/pack_handlers.py wms/scan_pack_helpers.py wms/tests/orders/tests_pack_handlers.py wms/tests/scan/tests_scan_pack_helpers.py
git commit -m "feat: create free carton batches from pack flow"
```

### Task 3: Add The Pack UI And Confirmation Popup

**Files:**
- Modify: `templates/scan/pack.html`
- Modify: `templates/scan/includes/pack_shipping_section.html`
- Modify: `wms/static/scan/scan.js`
- Modify if service worker version bump is needed: `wms/views_scan_misc.py`
- Modify if service worker version bump is needed: `templates/scan/base.html`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Add failing view tests**

Add assertions to `test_scan_pack_shows_dual_prepare_buttons_and_hides_location_admin_action` or a new test:

```python
self.assertContains(response, 'id="id_free_batch_carton_count"')
self.assertContains(response, 'value="prepare_available_batch"')
self.assertContains(response, 'id="free-carton-batch-confirmation-overlay"')
self.assertContains(response, 'name="confirm_free_carton_batch"')
```

Add a POST test proving missing confirmation returns no created carton and renders an error.

**Step 2: Add template controls**

Add a separate field label:

```html
<label class="form-label" for="id_free_batch_carton_count">Nombre de colis identiques</label>
<input type="number" name="free_batch_carton_count" id="id_free_batch_carton_count" min="1" step="1">
<input type="hidden" name="confirm_free_carton_batch" value="" data-free-carton-batch-confirm-input="1">
```

Keep the existing `forced_carton_count` text distinct. It remains the split/auto-packing tool.

Add action:

```html
<button type="submit" name="action" value="prepare_available_batch" class="scan-submit btn btn-success" data-free-carton-batch-submit="1">
  Batch colis libres
</button>
```

**Step 3: Add confirmation overlay**

The modal text must include:

- requested carton count;
- product line quantities per carton;
- total units consumed;
- "sans destination ni expedition".

Do not rely only on JavaScript. The hidden confirmation input is just an acknowledgement marker; backend validation remains authoritative.

**Step 4: Add JS interception**

In `wms/static/scan/scan.js`, inside the existing pack-page initializer, intercept the batch submitter:

```javascript
if (submitter && submitter.dataset.freeCartonBatchSubmit === '1') {
  const count = parseInt(batchCountInput.value || '0', 10);
  if (count > 1 && confirmInput.value !== '1') {
    event.preventDefault();
    openFreeCartonBatchConfirmation();
  }
}
```

When accepted:

```javascript
confirmInput.value = '1';
form.requestSubmit(batchSubmitButton);
```

**Step 5: Service worker cache check**

Because `wms/static/scan/scan.js` changes, bump the scan service worker version in:

- `wms/views_scan_misc.py`
- `templates/scan/base.html`

**Step 6: Run tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected: PASS.

### Task 4: Add Vue Colis Filters For Next-Day Assignment

**Files:**
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/carton_view_helpers.py` only if row metadata is missing
- Modify: `templates/scan/cartons_ready.html`
- Modify: `wms/static/scan/modules/cartons-ready.js` only if filter behavior needs client support
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Add failing tests**

Add tests proving:

```python
def test_scan_cartons_ready_filters_free_available_cartons(self): ...
def test_scan_cartons_ready_filters_by_product_query(self): ...
def test_scan_cartons_ready_filters_by_created_date(self): ...
def test_scan_cartons_ready_filters_by_prepared_volunteer(self): ...
```

Minimum useful V1 filters:

- `assignment=free`;
- `status=packed`;
- `q=seringue` matching product name/SKU/barcode/EAN;
- `created_on=YYYY-MM-DD`;
- `prepared_by=<volunteer_profile_id>` when volunteer activity exists.

**Step 2: Implement queryset filters**

In `scan_cartons_ready`, apply filters before `build_cartons_ready_rows`:

```python
if assignment_filter == "free":
    cartons_qs = cartons_qs.filter(shipment__isnull=True, preassigned_destination__isnull=True)
if status_filter == CartonStatus.PACKED:
    cartons_qs = cartons_qs.filter(status=CartonStatus.PACKED)
if q:
    cartons_qs = cartons_qs.filter(
        Q(code__icontains=q)
        | Q(cartonitem__product_lot__product__name__icontains=q)
        | Q(cartonitem__product_lot__product__sku__icontains=q)
        | Q(cartonitem__product_lot__product__barcode__icontains=q)
        | Q(cartonitem__product_lot__product__ean__icontains=q)
    )
```

Use `.distinct()` after product filters.

**Step 3: Add compact filter UI**

At the top of `templates/scan/cartons_ready.html`, add a small GET form:

- search input;
- assignment select;
- status select;
- created date;
- volunteer select if rows exist.

Keep existing `shipment_reference` filter behavior.

**Step 4: Run tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments wms.tests.carton.tests_carton_view_helpers -v 2
```

Expected: PASS.

### Task 5: Update Operational Docs And Changelog

**Files:**
- Modify: `wms/faq_changelog.py`
- Modify: `templates/scan/faq.html`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts/03-scan-operations.md`
- Modify: `docs/release_checklist.md`

**Step 1: Add FAQ/changelog entry**

Document:

- `Batch colis libres` creates real available cartons;
- line quantities are per carton;
- the batch has no shipment and no destination;
- later assignment happens through `Vue Colis`.

Use `PR TBD` until a PR number exists.

**Step 2: Update repo-reference contracts**

In `03-scan-operations.md`, add that free carton batch:

- starts from `/scan/pack/`;
- creates real cartons immediately;
- requires popup and server confirmation;
- consumes stock immediately;
- leaves shipment/preassignment blank.

**Step 3: Add release smoke**

In `docs/release_checklist.md`, add a smoke check:

```markdown
- [ ] Always-on smoke: create a free carton batch from `/scan/pack/`, verify N independent `Disponible` cartons with no shipment/destination, then assign a subset from `Vue Colis`.
```

**Step 4: Documentation impact check**

Because user-visible behavior changes, documentation update is required. Do not claim
"No documentation update required."

### Task 6: Final Verification

**Files:**
- No new files unless tests reveal drift.

**Step 1: Run focused tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.orders.tests_pack_handlers wms.tests.views.tests_views_scan_shipments wms.tests.views.tests_scan_bootstrap_ui wms.tests.carton.tests_carton_handlers -v 2
```

Expected: PASS.

**Step 2: Run broader scan/shipment safety tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.core.tests_flow wms.tests.shipment.tests_carton_volunteer_activity wms.tests.shipment.tests_shipment_status -v 2
```

Expected: PASS.

**Step 3: Recheck AGENTS completion rules**

Confirm:

- stock is decremented immediately;
- batch creation is atomic;
- no shipment readiness is changed;
- no destination or shipment is set;
- `Vue Colis` assignment still respects existing mismatch/status confirmations;
- docs and FAQ were updated;
- scan service worker was bumped if shared scan JS changed.

**Step 4: Commit only if explicitly approved**

Suggested final message:

```bash
git add wms/pack_handlers.py wms/scan_pack_helpers.py templates/scan/pack.html templates/scan/includes/pack_shipping_section.html wms/static/scan/scan.js wms/views_scan_misc.py templates/scan/base.html wms/views_scan_shipments.py templates/scan/cartons_ready.html wms/faq_changelog.py templates/scan/faq.html docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts/03-scan-operations.md docs/release_checklist.md wms/tests/orders/tests_pack_handlers.py wms/tests/scan/tests_scan_pack_helpers.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: add free carton batch preparation"
```
