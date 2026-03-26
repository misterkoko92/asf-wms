# Brother Carton Content Label Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a legacy Django carton content label that staff can open on a phone and print through the native iOS / Android print dialog to a Brother QL-1110NWB on continuous media.

**Architecture:** Keep the feature outside the Excel print-pack pipeline. Build one dedicated carton-label context builder, one dedicated printable HTML template, and a pair of carton-level scan routes that render the label directly from legacy Django views. Expose the new label from one narrow operator-facing legacy UI surface instead of changing the existing packing-list routes.

**Tech Stack:** Django views, Django templates, legacy scan routes, Django tests

---

### Task 1: Add failing tests for the carton content label context

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/print/tests_print_context.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/print_context.py`

**Step 1: Write the failing test**

Add focused tests for a new `build_carton_content_label_context()` helper.

Cover at least:

```python
context = build_carton_content_label_context(carton)

self.assertEqual(context["carton_code"], "C-40")
self.assertEqual(len(context["item_rows"]), 2)
self.assertEqual(context["item_rows"][0]["product_name"], "Mask")
self.assertEqual(context["item_rows"][0]["quantity"], 2)
self.assertEqual(context["item_rows"][0]["expires_on"], date(2026, 2, 1))
```

Also add an expiry fallback assertion similar to the existing carton document tests:

```python
self.assertEqual(context["item_rows"][0]["expires_on"], date(2026, 4, 1))
```

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.print.tests_print_context.PrintContextTests -v 2
```

Expected:
- failure because `build_carton_content_label_context` does not exist yet

**Step 3: Implement the minimal context helper**

In `/Users/EdouardGonnu/asf-wms/wms/print_context.py`, add:

```python
def build_carton_content_label_context(carton):
    item_rows = []
    for item in carton.cartonitem_set.select_related("product_lot", "product_lot__product"):
        item_rows.append(
            {
                "product_name": item.product_lot.product.name,
                "quantity": item.quantity,
                "expires_on": resolve_carton_item_expires_on(item),
            }
        )
    return {
        "carton_code": carton.code,
        "item_rows": item_rows,
        "hide_footer": True,
    }
```

Keep the helper narrow. Do not reuse the broader `packing_list_carton` payload with lot, weight, or shipment-summary fields.

**Step 4: Run test to verify it passes**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.print.tests_print_context.PrintContextTests -v 2
```

Expected:
- the new carton content label context tests pass
- existing print-context tests stay green

**Step 5: Commit**

```bash
git add wms/print_context.py wms/tests/print/tests_print_context.py
git commit -m "feat: add carton content label context"
```

### Task 2: Add the printable thermal label template

**Files:**
- Create: `/Users/EdouardGonnu/asf-wms/templates/print/carton_content_label.html`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_docs.py`

**Step 1: Write the failing view assertions first**

In `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_docs.py`, add a test that expects the new template to render identifiable markup:

```python
self.assertContains(response, 'id="carton-content-label"')
self.assertContains(response, 'id="carton-content-label-header"')
self.assertContains(response, 'id="carton-content-label-table"')
self.assertContains(response, "Colis:")
```

Also assert that the row content appears:

```python
self.assertContains(response, "Produit Print")
self.assertContains(response, ">2<", html=True)
```

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs.PrintDocsViewsTests -v 2
```

Expected:
- failure because the new label route / template is not wired yet

**Step 3: Create the minimal print template**

Create `/Users/EdouardGonnu/asf-wms/templates/print/carton_content_label.html` as a standalone print page.

Use a compact structure such as:

```html
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Carton content label</title>
  <style>
    @page { margin: 4mm; }
    body { margin: 0; font-family: Arial, sans-serif; color: #000; }
    .label-shell { width: 94mm; padding: 4mm; }
    .label-header { margin-bottom: 3mm; font-size: 11pt; font-weight: 700; }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    th, td { border: 1px solid #000; padding: 2mm 1.5mm; font-size: 9pt; vertical-align: top; }
    .col-product { width: 64%; }
    .col-quantity { width: 12%; text-align: center; white-space: nowrap; }
    .col-expiry { width: 24%; white-space: nowrap; }
    .product-name {
      white-space: normal;
      overflow-wrap: anywhere;
      line-height: 1.2;
    }
  </style>
</head>
```

Important:
- keep the page monochrome-friendly
- keep side margins explicit
- do not depend on `base_a5.html`
- do not add logos or footers
- do not truncate long product names; let the row grow if needed

**Step 4: Run tests to verify template rendering passes**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs.PrintDocsViewsTests -v 2
```

Expected:
- the new markup assertions pass once the view is wired

**Step 5: Commit**

```bash
git add templates/print/carton_content_label.html wms/tests/views/tests_views_print_docs.py
git commit -m "feat: add carton content label template"
```

### Task 3: Add carton content label routes and views

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print_docs.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/scan_urls.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_docs.py`

**Step 1: Add failing route tests**

Add tests for:
- shipment-linked carton label route
- standalone carton label route

Example assertions:

```python
response = self.client.get(
    reverse("scan:scan_shipment_carton_content_label", kwargs={"shipment_id": shipment.id, "carton_id": carton.id})
)
self.assertEqual(response.status_code, 200)
self.assertContains(response, carton.code)
```

```python
response = self.client.get(
    reverse("scan:scan_carton_content_label", kwargs={"carton_id": carton.id})
)
self.assertEqual(response.status_code, 200)
self.assertContains(response, carton.code)
```

Also add the shipment/carton mismatch `404` case.

**Step 2: Run tests to verify they fail**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs.PrintDocsViewsTests -v 2
```

Expected:
- failure because the new routes and view exports do not exist yet

**Step 3: Implement the shared render helper and route handlers**

In `/Users/EdouardGonnu/asf-wms/wms/views_print_docs.py`, add:

```python
TEMPLATE_CARTON_CONTENT_LABEL = "print/carton_content_label.html"

def _render_carton_content_label(request, carton):
    context = build_carton_content_label_context(carton)
    return render(request, TEMPLATE_CARTON_CONTENT_LABEL, context)
```

Then add:

```python
@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_carton_content_label(request, shipment_id, carton_id):
    shipment = _get_shipment_by_id(shipment_id)
    carton = _get_shipment_carton_or_404(shipment, carton_id)
    return _render_carton_content_label(request, carton)

@scan_staff_required
@require_http_methods(["GET"])
def scan_carton_content_label(request, carton_id):
    carton = get_object_or_404(Carton, pk=carton_id)
    return _render_carton_content_label(request, carton)
```

Wire the exports in:
- `/Users/EdouardGonnu/asf-wms/wms/views_print.py`
- `/Users/EdouardGonnu/asf-wms/wms/views.py`
- `/Users/EdouardGonnu/asf-wms/wms/scan_urls.py`

Recommended route names:
- `scan:scan_shipment_carton_content_label`
- `scan:scan_carton_content_label`

**Step 4: Run targeted tests**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs.PrintDocsViewsTests -v 2
```

Expected:
- the new route tests pass
- existing carton print-doc tests remain green

**Step 5: Commit**

```bash
git add wms/views_print_docs.py wms/views_print.py wms/views.py wms/scan_urls.py wms/tests/views/tests_views_print_docs.py
git commit -m "feat: add carton content label print routes"
```

### Task 4: Expose one operator-facing entry point in the legacy scan UI

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/templates/scan/includes/shipment_create_generated_documents_panel.html`
- Optional Modify: `/Users/EdouardGonnu/asf-wms/templates/scan/cartons_ready.html`
- Optional Modify: `/Users/EdouardGonnu/asf-wms/templates/scan/includes/pack_result_lists.html`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views.py`

**Step 1: Write the failing UI assertion**

Add one focused assertion that the shipment-generated-documents panel exposes the new label link for each carton:

```python
self.assertContains(
    response,
    reverse("scan:scan_shipment_carton_content_label", args=[shipment.id, carton.id]),
)
```

Keep the assertion narrow. Do not redesign the surrounding actions in this step.

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views -v 2
```

Expected:
- failure because the new action is not rendered yet

**Step 3: Add the new tertiary action**

In `/Users/EdouardGonnu/asf-wms/templates/scan/includes/shipment_create_generated_documents_panel.html`, add one extra carton-level action next to the existing packing-list / label actions.

Suggested label:

```html
Etiquette contenu
```

Keep it:
- tertiary
- carton-level
- `target="_blank"`
- `rel="noopener"`

Do not remove or rename the existing packing-list action.

**Step 4: Run the targeted UI tests**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views wms.tests.views.tests_views_print_docs -v 1
```

Expected:
- the new link assertion passes
- no legacy carton document links regress

**Step 5: Commit**

```bash
git add templates/scan/includes/shipment_create_generated_documents_panel.html wms/tests/views/tests_views.py
git commit -m "feat: expose carton content label action"
```

### Task 5: Final verification on code and device assumptions

**Files:**
- Modify: none
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/print/tests_print_context.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_docs.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views.py`

**Step 1: Run the full targeted verification set**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.print.tests_print_context wms.tests.views.tests_views_print_docs wms.tests.views.tests_views -v 1
git diff --check
git status --short --branch
```

Expected:
- targeted Django tests pass
- no whitespace or diff hygiene issues
- only the intended legacy Django files are changed

**Step 2: Manual browser verification**

Verify in a browser that:
- the label page has no footer or A5 framing
- carton code appears once above the table
- long product names wrap cleanly
- row count can grow without clipping

**Step 3: Real device and printer validation**

Validate with:
- one iPhone on the same Wi-Fi as the Brother printer
- one Android phone on the same Wi-Fi as the Brother printer
- wide continuous media loaded in the QL-1110NWB

Check:
- the page opens readably on phone
- the native print dialog can see the Brother printer
- the printed result uses one continuous label
- long labels do not clip left or right edges

**Step 4: Commit**

```bash
git add -A
git commit -m "docs: finalize carton content label delivery"
```

**Step 5: Stop before SDK work**

Do not add Brother SDK or mobile app work in this execution plan. If operators later need one-tap silent printing, that should be a separate design and implementation track.
