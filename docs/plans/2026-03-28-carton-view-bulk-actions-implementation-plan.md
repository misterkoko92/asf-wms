# Carton View Bulk Actions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a lighter `Vue Colis`, a consultation-first `Fiche colis`, and V1 carton bulk actions for status changes, grouped picking, and grouped packing-list access.

**Architecture:** Keep the legacy Django `/scan/cartons/` route as the list entry point, but move carton-specific operations onto the existing carton detail route. Add a contextual bulk-action layer on top of the list, route grouped document actions through dedicated scan/print entry points, and normalize carton mutation rules so planned/disputed/late shipment states behave consistently across row actions, bulk actions, and carton detail.

**Tech Stack:** Django views/templates, legacy `wms/views_scan_shipments.py`, `wms/views_print_docs.py`, helper modules under `wms/`, Django test suite via `./.venv/bin/python manage.py test`

---

### Task 1: Lock Down The Target Through Failing View Tests

**Files:**
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Reference: `templates/scan/cartons_ready.html`

**Step 1: Write the failing tests**

Add view tests that assert the new carton list contract:

```python
def test_scan_cartons_ready_renders_selection_and_bulk_toolbar_shell(self):
    response = self.client.get(reverse("scan:scan_cartons_ready"))
    self.assertContains(response, 'name="selected_carton_ids"')
    self.assertContains(response, 'id="carton-bulk-actions"')
    self.assertContains(response, "Liste de colisage")
    self.assertContains(response, "Picking")
    self.assertContains(response, 'name="bulk_action"')


def test_scan_cartons_ready_removes_inline_cockpit_controls(self):
    with mock.patch(
        "wms.views_scan_shipments.build_cartons_ready_rows",
        return_value=[...],
    ):
        response = self.client.get(reverse("scan:scan_cartons_ready"))
    self.assertNotContains(response, "scan-carton-status-select-wrap")
    self.assertNotContains(response, "Modifier")
    self.assertNotContains(response, "Supprimer")
    self.assertContains(response, "Ouvrir")
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments.ScanShipmentViewsTests.test_scan_cartons_ready_renders_selection_and_bulk_toolbar_shell wms.tests.views.tests_views_scan_shipments.ScanShipmentViewsTests.test_scan_cartons_ready_removes_inline_cockpit_controls -v 2
```

Expected:
- FAIL because the current table still renders inline row controls and has no bulk toolbar shell

**Step 3: Write minimal implementation**

Do not implement behavior yet. Only reshape the template enough for the tests to pass later in Tasks 4 and 5:
- add a selection column placeholder
- add a hidden or inert bulk toolbar wrapper
- replace row-level cockpit buttons with a single `Ouvrir` placeholder

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS for the new structure assertions

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_scan_shipments.py templates/scan/cartons_ready.html
git commit -m "test: lock carton list structure around bulk toolbar"
```

### Task 2: Expand Carton Row Metadata For The New List

**Files:**
- Modify: `wms/carton_view_helpers.py`
- Test: `wms/tests/carton/tests_carton_view_helpers.py`

**Step 1: Write the failing test**

Add helper coverage for the new row payload:

```python
def test_build_cartons_ready_rows_exposes_summary_links_and_bulk_flags(self):
    rows = build_cartons_ready_rows([...], carton_capacity_cm3=5000)
    row = rows[0]
    assert row["detail_url"].endswith("/scan/carton/10/edit/")
    assert row["summary_line_count"] == 1
    assert row["summary_total_quantity"] == 2
    assert row["has_packing_list"] is True
    assert row["has_picking"] is True
    assert row["can_bulk_mark_labeled"] is True
    assert row["can_bulk_mark_assigned"] is False
```

Also add a case for a carton linked to a `PLANNED` shipment to confirm mutation flags are blocked.

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.carton.tests_carton_view_helpers -v 2
```

Expected:
- FAIL because the helper does not expose the new fields yet

**Step 3: Write minimal implementation**

Update `build_cartons_ready_rows` to expose:

```python
{
    "detail_url": reverse("scan:scan_carton_edit", args=[carton.id]),
    "summary_line_count": len(packing_list),
    "summary_total_quantity": sum(item["quantity"] for item in packing_list),
    "has_packing_list": bool(packing_list_url),
    "has_picking": bool(picking_url),
    "linked_shipment_url": (
        reverse("scan:scan_shipment_edit", args=[carton.shipment_id])
        if carton.shipment_id else ""
    ),
    "can_bulk_mark_labeled": ...,
    "can_bulk_mark_assigned": ...,
}
```

Normalize the mutation helper so cartons linked to planned/disputed/shipped/received-correspondent/delivered shipments are not exposed as mutable in the list payload.

**Step 4: Run test to verify it passes**

Run the same helper test module.

Expected:
- PASS with the new summary and eligibility fields

**Step 5: Commit**

```bash
git add wms/carton_view_helpers.py wms/tests/carton/tests_carton_view_helpers.py
git commit -m "feat: expose carton row metadata for lighter list"
```

### Task 3: Normalize Carton Mutation Rules And Add Bulk Status Tests

**Files:**
- Modify: `wms/carton_handlers.py`
- Test: `wms/tests/carton/tests_carton_handlers.py`

**Step 1: Write the failing tests**

Add test coverage for:

```python
def test_bulk_mark_cartons_labeled_updates_only_eligible_rows(self):
    request = self.factory.post("/scan/cartons/", {
        "action": "bulk_mark_cartons_labeled",
        "selected_carton_ids": [str(carton1.id), str(carton2.id)],
    })
    response = handle_carton_status_update(request)
    ...


def test_bulk_mark_cartons_assigned_updates_only_labeled_rows(self):
    ...


def test_delete_carton_is_ignored_when_shipment_is_planned(self):
    ...
```

The planned-shipment deletion test closes the current mismatch where FAQ wording says planned shipments lock carton modification, but deletion still allows a planned linked carton.

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.carton.tests_carton_handlers -v 2
```

Expected:
- FAIL because bulk actions do not exist and planned deletion is still allowed

**Step 3: Write minimal implementation**

In `handle_carton_status_update`:
- accept new actions:

```python
allowed_actions = {
    "update_carton_status",
    "mark_carton_labeled",
    "mark_carton_assigned",
    "delete_carton",
    "bulk_mark_cartons_labeled",
    "bulk_mark_cartons_assigned",
}
```

- add a helper that loads selected cartons in one query:

```python
def _selected_cartons(request):
    selected_ids = [value for value in request.POST.getlist("selected_carton_ids") if value]
    return list(
        Carton.objects.filter(id__in=selected_ids)
        .select_related("shipment")
        .order_by("id")
    )
```

- count processed and ignored cartons
- call `set_carton_status(...)` only for eligible cartons
- call `sync_shipment_ready_state(...)` once per touched shipment
- return through `redirect("scan:scan_cartons_ready")`

Also update mutation-blocking sets so planned shipments are treated as non-mutable for delete/edit/bulk mutations.

**Step 4: Run test to verify it passes**

Run the same handler test module.

Expected:
- PASS for bulk status actions
- PASS for planned-shipment mutation blocking

**Step 5: Commit**

```bash
git add wms/carton_handlers.py wms/tests/carton/tests_carton_handlers.py
git commit -m "feat: add bulk carton status actions and align locking rules"
```

### Task 4: Reshape `Vue Colis` Around Selection + `Ouvrir`

**Files:**
- Modify: `templates/scan/cartons_ready.html`
- Modify: `wms/views_scan_shipments.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Add tests that assert:
- the table renders a checkbox column
- the row action is `Ouvrir`
- the compact content summary replaces the full packing-list listing
- the bulk toolbar form posts back to `scan_cartons_ready`

Example:

```python
def test_scan_cartons_ready_renders_open_action_and_compact_summary(self):
    with mock.patch(...):
        response = self.client.get(reverse("scan:scan_cartons_ready"))
    self.assertContains(response, 'href="/scan/carton/1/edit/"')
    self.assertContains(response, "3 lignes / 18 unités")
    self.assertNotContains(response, "Imprimer / télécharger")
    self.assertNotContains(response, "Picking")
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments.ScanShipmentViewsTests.test_scan_cartons_ready_renders_open_action_and_compact_summary -v 2
```

Expected:
- FAIL because the current row still renders full inline controls

**Step 3: Write minimal implementation**

Update `scan_cartons_ready` template and view context:
- keep the list under the existing route
- render:

```html
<form method="post" id="carton-bulk-actions" class="ui-comp-actions" hidden>
  {% csrf_token %}
  <button name="bulk_document" value="packing_lists">Liste de colisage</button>
  <button name="bulk_document" value="picking">Picking</button>
  <select name="bulk_action">
    <option value="">Changer le statut</option>
    <option value="bulk_mark_cartons_labeled">Marquer étiqueté</option>
    <option value="bulk_mark_cartons_assigned">Retirer étiquette</option>
  </select>
  <button type="submit">Appliquer</button>
</form>
```

- change row action to:

```html
<a href="{{ carton.detail_url }}" class="scan-scan-btn btn btn-tertiary">Ouvrir</a>
```

- render compact summary:

```html
{{ carton.summary_line_count }} ligne{{ carton.summary_line_count|pluralize }} / {{ carton.summary_total_quantity }} unité{{ carton.summary_total_quantity|pluralize }}
```

**Step 4: Run test to verify it passes**

Run the targeted test plus the existing carton list view tests:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2
```

Expected:
- PASS for the new carton list contract

**Step 5: Commit**

```bash
git add templates/scan/cartons_ready.html wms/views_scan_shipments.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: simplify carton list and add bulk action shell"
```

### Task 5: Add The Contextual Bulk Toolbar Behavior

**Files:**
- Modify: `wms/static/scan/scan.js`
- Modify: `templates/scan/cartons_ready.html`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Add a server-rendered assertion for the data hooks used by the JS controller:

```python
def test_scan_cartons_ready_exposes_bulk_selection_hooks(self):
    response = self.client.get(reverse("scan:scan_cartons_ready"))
    self.assertContains(response, 'data-carton-bulk-root="1"')
    self.assertContains(response, 'data-carton-select-all="1"')
    self.assertContains(response, 'data-carton-bulk-count="1"')
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments.ScanShipmentViewsTests.test_scan_cartons_ready_exposes_bulk_selection_hooks -v 2
```

Expected:
- FAIL because the JS hooks do not exist yet

**Step 3: Write minimal implementation**

Add small progressive-enhancement logic in `wms/static/scan/scan.js`:

```javascript
const roots = document.querySelectorAll('[data-carton-bulk-root="1"]');
roots.forEach((root) => {
  const checkboxes = [...root.querySelectorAll('input[name="selected_carton_ids"]')];
  const countNode = root.querySelector('[data-carton-bulk-count="1"]');
  const toolbar = root.querySelector('#carton-bulk-actions');
  ...
});
```

Behavior:
- show toolbar when selected count > 0
- update displayed count
- support select-all checkbox
- disable submit when no bulk action and no bulk document button was chosen

Keep the enhancement local to the carton page; do not introduce a shared primitive yet.

**Step 4: Run test to verify it passes**

Run the targeted test plus the full carton list view module.

Expected:
- PASS for the server hooks
- manual browser verification still needed later for the JS toggle

**Step 5: Commit**

```bash
git add wms/static/scan/scan.js templates/scan/cartons_ready.html wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: add carton bulk selection toolbar behavior"
```

### Task 6: Turn The Existing Carton Edit Page Into `Fiche colis`

**Files:**
- Modify: `templates/scan/pack.html`
- Modify: `wms/views_scan_shipments.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Add a view test for carton detail mode:

```python
def test_scan_carton_edit_renders_carton_fiche_sections(self):
    response = self.client.get(reverse("scan:scan_carton_edit", kwargs={"carton_id": carton.id}))
    self.assertContains(response, "Fiche colis")
    self.assertContains(response, "Synthèse")
    self.assertContains(response, "Documents")
    self.assertContains(response, "Modifier")
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments.ScanShipmentViewsTests.test_scan_carton_edit_renders_carton_fiche_sections -v 2
```

Expected:
- FAIL because `pack.html` still presents carton edit as a preparation form first

**Step 3: Write minimal implementation**

Reuse `scan_carton_edit`, but adjust the rendering so `editing_carton` mode gets:
- page title `Fiche colis`
- synthesis block above the form
- documents block with `packing_list_url` and `picking_url`
- one operation area
- edit form behind a `Modifier` section

Pass the extra summary/document context from `scan_carton_edit`:

```python
extra_context={
    "editing_carton": editing_carton,
    "carton_summary": ...,
    "carton_documents": {
        "packing_list_url": ...,
        "picking_url": ...,
    },
}
```

**Step 4: Run test to verify it passes**

Run the targeted carton detail test plus the existing `scan_pack` tests.

Expected:
- PASS for carton detail presentation
- PASS for pack mode regressions

**Step 5: Commit**

```bash
git add templates/scan/pack.html wms/views_scan_shipments.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: present carton edit as consultation-first fiche"
```

### Task 7: Add Multi-Carton Picking Route And Helper

**Files:**
- Create: `wms/carton_bulk_document_helpers.py`
- Modify: `wms/views_print_docs.py`
- Modify: `wms/scan_urls.py`
- Test: `wms/tests/views/tests_views.py`
- Test: `wms/tests/views/tests_views_print_docs.py`

**Step 1: Write the failing tests**

Add tests for a new grouped carton picking route:

```python
def test_scan_cartons_picking_renders_grouped_rows(self):
    response = self.client.get(
        reverse("scan:scan_cartons_picking"),
        {"carton_ids": f"{carton1.id},{carton2.id}"},
    )
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "Liste picking - colis")
    self.assertContains(response, carton1.code)
    self.assertContains(response, carton2.code)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views.TestViews.test_scan_cartons_picking_renders_grouped_rows wms.tests.views.tests_views_print_docs -v 2
```

Expected:
- FAIL because the route and helper do not exist

**Step 3: Write minimal implementation**

Create a neutral bulk helper:

```python
def build_cartons_picking_context(carton_ids):
    cartons = list(
        Carton.objects.filter(id__in=carton_ids)
        .prefetch_related("cartonitem_set__product_lot__product", "cartonitem_set__product_lot__location")
        .order_by("code", "id")
    )
    ...
    return {
        "carton_ids": [...],
        "carton_codes": [...],
        "item_rows": [...],
    }
```

Then add:
- route: `path("cartons/picking/", views.scan_cartons_picking, name="scan_cartons_picking")`
- view using the new helper
- neutral template title `Liste picking - colis`

If helpful, let the old kits helper delegate to the new generic helper rather than duplicating logic.

**Step 4: Run test to verify it passes**

Run the targeted grouped picking tests plus the existing single-carton and prepare-kits picking tests.

Expected:
- PASS for the new grouped route
- PASS for existing picking routes

**Step 5: Commit**

```bash
git add wms/carton_bulk_document_helpers.py wms/views_print_docs.py wms/scan_urls.py wms/tests/views/tests_views.py wms/tests/views/tests_views_print_docs.py
git commit -m "feat: add grouped carton picking route"
```

### Task 8: Add Selected-Carton Packing-List Bundle Route

**Files:**
- Modify: `wms/views_print_docs.py`
- Modify: `wms/scan_urls.py`
- Create: `templates/scan/carton_print_bundle_lot.html`
- Test: `wms/tests/views/tests_views_print_docs.py`

**Step 1: Write the failing test**

Add a test for a selected-carton bundle page:

```python
def test_scan_cartons_view_bundle_routes_packing_lists_to_html_bundle_page(self):
    response = self.client.get(
        reverse("scan:scan_cartons_view_bundle", kwargs={"bundle_key": "packing_lists"}),
        {"carton_ids": f"{carton1.id},{carton2.id}"},
    )
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "Lot listes colisage")
    self.assertContains(response, carton1.code)
    self.assertContains(response, carton2.code)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs.CartonPrintDocsTests.test_scan_cartons_view_bundle_routes_packing_lists_to_html_bundle_page -v 2
```

Expected:
- FAIL because the route and template do not exist

**Step 3: Write minimal implementation**

Mirror the shipment bundle style with a selected-carton bundle:

```python
def scan_cartons_view_bundle(request, bundle_key):
    carton_ids = _parse_carton_ids(request.GET.get("carton_ids"))
    cartons = _selected_cartons_for_bundle(carton_ids)
    ...
```

For V1:
- only support `bundle_key == "packing_lists"`
- render one orchestrator page
- each row exposes one `Liste colisage` HTML link
- do not open one browser tab per selected carton automatically

**Step 4: Run test to verify it passes**

Run the targeted new test plus the existing shipment bundle tests to ensure no regression.

Expected:
- PASS for the selected-carton bundle page
- PASS for shipment bundle tests

**Step 5: Commit**

```bash
git add wms/views_print_docs.py wms/scan_urls.py templates/scan/carton_print_bundle_lot.html wms/tests/views/tests_views_print_docs.py
git commit -m "feat: add selected carton packing list bundle"
```

### Task 9: Wire Bulk Toolbar Submission To The New Status/Document Routes

**Files:**
- Modify: `wms/views_scan_shipments.py`
- Modify: `templates/scan/cartons_ready.html`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing tests**

Add tests for the list POST behavior:

```python
def test_scan_cartons_ready_bulk_picking_redirects_to_grouped_route(self):
    response = self.client.post(
        reverse("scan:scan_cartons_ready"),
        {"bulk_document": "picking", "selected_carton_ids": [carton.id]},
    )
    self.assertRedirects(response, f"{reverse('scan:scan_cartons_picking')}?carton_ids={carton.id}")


def test_scan_cartons_ready_bulk_packing_lists_redirects_to_bundle_route(self):
    ...
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2
```

Expected:
- FAIL because the view does not route bulk document actions yet

**Step 3: Write minimal implementation**

In `scan_cartons_ready`, before loading the queryset:
- check for bulk document posts
- normalize selected carton IDs
- redirect to:

```python
reverse("scan:scan_cartons_picking") + "?" + urlencode({"carton_ids": ",".join(...)})
```

or:

```python
reverse("scan:scan_cartons_view_bundle", args=["packing_lists"]) + "?" + urlencode(...)
```

Leave bulk status actions handled by `handle_carton_status_update`.

**Step 4: Run test to verify it passes**

Run the same view module.

Expected:
- PASS for bulk document redirects
- PASS for existing carton list view tests

**Step 5: Commit**

```bash
git add wms/views_scan_shipments.py templates/scan/cartons_ready.html wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: wire carton bulk toolbar to grouped routes"
```

### Task 10: Update Docs And Run Final Verification

**Files:**
- Modify: `templates/scan/faq.html`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Optional review: `docs/mvp_spec.md`

**Step 1: Write the failing test**

Add or update an FAQ/copy assertion in the nearest legacy view tests:

```python
def test_scan_faq_mentions_carton_fiche_and_grouped_actions(self):
    response = self.client.get(reverse("scan:scan_faq"))
    self.assertContains(response, "Fiche colis")
    self.assertContains(response, "actions groupées")
```

If no existing FAQ test exists, add the smallest targeted test in the nearest view test module already covering scan copy.

**Step 2: Run test to verify it fails**

Run the targeted FAQ/copy test plus the final focused suite:

```bash
./.venv/bin/python manage.py test \
  wms.tests.carton.tests_carton_view_helpers \
  wms.tests.carton.tests_carton_handlers \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_views \
  wms.tests.views.tests_views_print_docs \
  -v 2
```

Expected:
- FAIL until the copy/docs are updated

**Step 3: Write minimal implementation**

Update:
- FAQ wording so `Vue Colis` is described as a lighter list with grouped actions
- carton detail wording to mention `Fiche colis`
- repo reference flow note so the scan stock -> carton -> shipment flow reflects the lighter carton list + grouped document actions

Review whether `docs/mvp_spec.md` needs wording updates for the new user path. If not needed, document that decision in the PR summary instead of forcing an unnecessary edit.

**Step 4: Run test to verify it passes**

Run the focused suite above. Then run one final high-signal command:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected:
- PASS on the targeted carton/view/print suite
- PASS on the scan UI regression suite

**Step 5: Commit**

```bash
git add templates/scan/faq.html docs/repo-reference/02-key-flows-and-living-tests.md docs/mvp_spec.md wms/tests/views/tests_views_scan_shipments.py
git commit -m "docs: align carton guidance with lighter list and bulk actions"
```
