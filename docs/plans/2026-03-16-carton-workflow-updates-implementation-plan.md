# Carton Workflow Updates Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver the legacy Django carton changes for linear MM/CN numbering, editable/deletable non-shipped cartons, per-product manual expiry input, and destination preassignment with mismatch confirmation.

**Architecture:** Extend the existing `Carton` and `CartonItem` domain model in place, keep stock truth on `ProductLot`, and thread the new carton metadata through legacy Scan forms, handlers, list views, and print context. Reuse unpack/repack behavior for carton editing and enforce destination mismatch confirmation in both JS and backend.

**Tech Stack:** Django, legacy Scan templates, vanilla JS in `wms/static/scan/scan.js`, Django ORM migrations, Django test suite.

---

### Task 1: Schema Foundation And Linear Numbering

**Files:**
- Modify: `wms/models_domain/inventory.py`
- Modify: `wms/models_domain/shipment.py`
- Modify: `wms/models.py`
- Modify: `wms/domain/stock.py`
- Create: `wms/migrations/0089_carton_sequences_preassignment_manual_expiry.py`
- Test: `wms/tests/domain/tests_domain_stock_extra.py`

**Step 1: Write the failing tests**

```python
def test_generate_carton_code_uses_family_sequence(self):
    self.assertEqual(generate_carton_code(type_code="MM"), "MM-00001")
    self.assertEqual(generate_carton_code(type_code="MM"), "MM-00002")
    self.assertEqual(generate_carton_code(type_code="CN"), "CN-00001")

def test_existing_carton_code_is_preserved_during_repack(self):
    carton = Carton.objects.create(code="MM-00007", status=CartonStatus.DRAFT)
    ensure_carton_code(carton, type_code="MM")
    carton.refresh_from_db()
    self.assertEqual(carton.code, "MM-00007")
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.domain.tests_domain_stock_extra -v 2
```

Expected: FAIL because the current generator still emits date-based carton codes and the new schema does not exist.

**Step 3: Write minimal implementation**

```python
class CartonSequence(models.Model):
    family = models.CharField(max_length=2, unique=True)
    last_number = models.PositiveIntegerField(default=0)

class Carton(models.Model):
    preassigned_destination = models.ForeignKey(...)

class CartonItem(models.Model):
    display_expires_on = models.DateField(null=True, blank=True)
```

- Replace date-based carton code parsing in `wms/domain/stock.py` with sequence-based generation backed by `CartonSequence`.
- Preserve already valid `MM-xxxxx` / `CN-xxxxx` codes during edit/repack.
- Export the new models/fields through `wms/models.py`.
- Add migration `0089_carton_sequences_preassignment_manual_expiry.py`.

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.domain.tests_domain_stock_extra -v 2
```

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/models_domain/inventory.py wms/models_domain/shipment.py wms/models.py wms/domain/stock.py wms/migrations/0089_carton_sequences_preassignment_manual_expiry.py wms/tests/domain/tests_domain_stock_extra.py
git commit -m "feat: add carton numbering and schema foundation"
```

### Task 2: Pack Flow Expiry And Preassignment Inputs

**Files:**
- Modify: `wms/forms.py`
- Modify: `wms/scan_pack_helpers.py`
- Modify: `wms/pack_handlers.py`
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/scan_carton_helpers.py`
- Modify: `templates/scan/pack.html`
- Modify: `wms/static/scan/scan.js`
- Test: `wms/tests/forms/tests_forms.py`
- Test: `wms/tests/views/tests_views.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing tests**

```python
def test_scan_pack_renders_preassignment_and_expiry_inputs(self):
    response = self.client.get(reverse("scan:scan_pack"))
    self.assertContains(response, "Destination pre-affectee")
    self.assertContains(response, "Date de peremption")

def test_build_pack_line_values_keeps_expiry_input(self):
    values = build_pack_line_values(1, {"line_1_expires_on": "2026-02-01"})
    self.assertEqual(values[0]["expires_on"], "2026-02-01")
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.forms.tests_forms wms.tests.views.tests_views wms.tests.views.tests_views_scan_shipments -v 2
```

Expected: FAIL because pack UI and helpers do not expose the new fields.

**Step 3: Write minimal implementation**

```python
class ScanPackForm(forms.Form):
    shipment_reference = forms.CharField(required=False)
    current_location = forms.ModelChoiceField(..., required=False)
    preassigned_destination = forms.ModelChoiceField(queryset=Destination.objects.filter(is_active=True), required=False)
```

- Add `expires_on` to pack line values and parsing.
- Add optional `preassigned_destination` to `ScanPackForm`.
- Pass expiry and preassignment through `handle_pack_post()`.
- When a real shipment is resolved, ignore or clear preassignment.
- Update pack template and JS to render the new fields beside quantity.

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.forms.tests_forms wms.tests.views.tests_views wms.tests.views.tests_views_scan_shipments -v 2
```

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/forms.py wms/scan_pack_helpers.py wms/pack_handlers.py wms/views_scan_shipments.py wms/scan_carton_helpers.py templates/scan/pack.html wms/static/scan/scan.js wms/tests/forms/tests_forms.py wms/tests/views/tests_views.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: add pack expiry and preassignment inputs"
```

### Task 3: Shipment Assignment Lines And Destination Mismatch Confirmation

**Files:**
- Modify: `wms/shipment_helpers.py`
- Modify: `wms/shipment_form_helpers.py`
- Modify: `wms/scan_shipment_handlers.py`
- Modify: `wms/views_scan_shipments.py`
- Modify: `templates/scan/shipment_create.html`
- Modify: `wms/static/scan/scan.js`
- Test: `wms/tests/scan/tests_scan_shipment_handlers.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing tests**

```python
def test_parse_shipment_lines_keeps_expiry_and_confirmation(self):
    values, items, errors = parse_shipment_lines(
        carton_count=1,
        data={"line_1_product_code": "SKU", "line_1_quantity": "2", "line_1_expires_on": "2026-02-01"},
        allowed_carton_ids=set(),
    )
    self.assertEqual(values[0]["expires_on"], "2026-02-01")

def test_handle_shipment_create_post_rejects_preassigned_destination_mismatch_without_confirmation(self):
    self.assertIn((None, "Ce colis a ete pre-affecte ..."), form.errors)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.scan.tests_scan_shipment_handlers wms.tests.views.tests_views_scan_shipments -v 2
```

Expected: FAIL because shipment lines and handlers do not yet track expiry or mismatch confirmation.

**Step 3: Write minimal implementation**

```python
line_items.append({
    "product": product,
    "quantity": quantity,
    "expires_on": expires_on,
})
```

- Extend shipment line parsing with `expires_on`.
- Include preassigned destination metadata in carton JSON payloads and select labels.
- Add JS confirmation before submitting mismatched preassigned cartons.
- Add backend confirmation flag validation in create/edit handlers.
- Clear `preassigned_destination` whenever a carton is attached to a real shipment.

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.scan.tests_scan_shipment_handlers wms.tests.views.tests_views_scan_shipments -v 2
```

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/shipment_helpers.py wms/shipment_form_helpers.py wms/scan_shipment_handlers.py wms/views_scan_shipments.py templates/scan/shipment_create.html wms/static/scan/scan.js wms/tests/scan/tests_scan_shipment_handlers.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: add shipment expiry inputs and mismatch confirmation"
```

### Task 4: Carton List Display, Edit Route, And Delete Flow

**Files:**
- Modify: `wms/carton_view_helpers.py`
- Modify: `wms/carton_handlers.py`
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/scan_urls.py`
- Modify: `templates/scan/cartons_ready.html`
- Modify: `wms/domain/stock.py`
- Test: `wms/tests/carton/tests_carton_view_helpers.py`
- Test: `wms/tests/carton/tests_carton_handlers.py`
- Test: `wms/tests/views/tests_views.py`

**Step 1: Write the failing tests**

```python
def test_build_cartons_ready_rows_prefers_preassigned_iata_when_no_shipment(self):
    self.assertEqual(row["shipment_reference"], "(NKC)")

def test_handle_carton_status_update_can_delete_non_shipped_carton(self):
    response = handle_carton_status_update(request)
    self.assertFalse(Carton.objects.filter(pk=carton.pk).exists())
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.carton.tests_carton_view_helpers wms.tests.carton.tests_carton_handlers wms.tests.views.tests_views -v 2
```

Expected: FAIL because carton list rows, actions, and routes do not exist yet.

**Step 3: Write minimal implementation**

```python
path("carton/<int:carton_id>/edit/", views.scan_carton_edit, name="scan_carton_edit")
```

- Show `(IATA)` in carton rows when only preassignment exists.
- Add action buttons and visibility guards in the carton list.
- Add carton edit route reusing pack logic in single-carton mode.
- Relax carton edit/delete locking to allow planned shipments but still block disputes and shipped cartons.
- Implement delete as unpack then model delete.

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.carton.tests_carton_view_helpers wms.tests.carton.tests_carton_handlers wms.tests.views.tests_views -v 2
```

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/carton_view_helpers.py wms/carton_handlers.py wms/views_scan_shipments.py wms/scan_urls.py templates/scan/cartons_ready.html wms/domain/stock.py wms/tests/carton/tests_carton_view_helpers.py wms/tests/carton/tests_carton_handlers.py wms/tests/views/tests_views.py
git commit -m "feat: add carton edit delete and preassignment display"
```

### Task 5: Manual Expiry Display In Packing Documents

**Files:**
- Modify: `wms/print_context.py`
- Modify: `wms/print_pack_engine.py`
- Test: `wms/tests/print/tests_print_context.py`
- Test: `wms/tests/views/tests_views_print_docs.py`

**Step 1: Write the failing tests**

```python
def test_build_carton_document_context_prefers_manual_expiry(self):
    self.assertEqual(context["item_rows"][0]["expires_on"], date(2026, 2, 1))

def test_build_carton_document_context_falls_back_to_lot_expiry(self):
    self.assertEqual(context["item_rows"][0]["expires_on"], lot.expires_on)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.print.tests_print_context wms.tests.views.tests_views_print_docs -v 2
```

Expected: FAIL because print context still reads only `product_lot.expires_on`.

**Step 3: Write minimal implementation**

```python
expires_on = item.display_expires_on or item.product_lot.expires_on
```

- Update print context and pack engine serializers to prefer manual carton-item expiry.
- Preserve existing keys so templates remain unchanged.

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.print.tests_print_context wms.tests.views.tests_views_print_docs -v 2
```

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/print_context.py wms/print_pack_engine.py wms/tests/print/tests_print_context.py wms/tests/views/tests_views_print_docs.py
git commit -m "feat: prefer manual carton expiry in print output"
```

### Task 6: Regression Verification

**Files:**
- Modify as needed from previous tasks only
- Test: `wms/tests/domain/tests_domain_stock_extra.py`
- Test: `wms/tests/scan/tests_scan_shipment_handlers.py`
- Test: `wms/tests/carton/tests_carton_handlers.py`
- Test: `wms/tests/carton/tests_carton_view_helpers.py`
- Test: `wms/tests/forms/tests_forms.py`
- Test: `wms/tests/views/tests_views.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`
- Test: `wms/tests/print/tests_print_context.py`
- Test: `wms/tests/views/tests_views_print_docs.py`

**Step 1: Run focused regression suite**

```bash
./.venv/bin/python manage.py test \
  wms.tests.domain.tests_domain_stock_extra \
  wms.tests.scan.tests_scan_shipment_handlers \
  wms.tests.carton.tests_carton_handlers \
  wms.tests.carton.tests_carton_view_helpers \
  wms.tests.forms.tests_forms \
  wms.tests.views.tests_views \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.print.tests_print_context \
  wms.tests.views.tests_views_print_docs \
  -v 2
```

Expected: PASS.

**Step 2: Run targeted UI regression if the previous suite is green**

```bash
./.venv/bin/python manage.py test wms.tests.core.tests_ui -v 2
```

Expected: PASS or a small set of intentional snapshot/text updates matching the new UI.

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: update carton workflows"
```
