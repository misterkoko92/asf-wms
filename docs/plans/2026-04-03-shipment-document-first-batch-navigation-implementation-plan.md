# Shipment Document-First, Carton Batch Actions, and Masthead Navigation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow definitive shipment creation without cartons, add batch carton assignment and improved batch print outputs in `Vue Colis`, and add shared previous/next masthead buttons across the legacy UI.

**Architecture:** Keep the internal shipment status `draft` as the existing `Création` state, but remove the visible `EXP-TEMP-*` draft workflow and create shipments directly with definitive references. Extend the existing legacy Django handlers, templates, and grouped print routes instead of introducing parallel flows. Add masthead history buttons through a shared include plus lightweight JS so the behavior stays consistent across scan, portal, planning, and volunteer surfaces.

**Tech Stack:** Django forms/views/templates, legacy plain JavaScript, Django test runner, Bootstrap-based legacy UI.

---

**Execution rules**

- `@test-driven-development`: no production code before the new failing test for the current task.
- `@verification-before-completion`: run the listed targeted tests before claiming the task is done.
- `@repo-reference-governance`: update repo reference docs if the flow, route, or shared UI contract changes during implementation.

### Task 1: Replace draft-only creation assumptions with zero-carton definitive creation tests

**Files:**
- Modify: `wms/tests/scan/tests_scan_shipment_handlers.py`
- Modify: `wms/tests/views/tests_views.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

```python
def test_handle_shipment_create_post_allows_creation_without_cartons(self):
    request = self._request({})
    form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=0))

    with mock.patch("wms.scan_shipment_handlers.Shipment.objects.create") as create_mock:
        response, carton_count, line_values, line_errors = handle_shipment_create_post(
            request,
            form=form,
            available_carton_ids=set(),
        )

    self.assertEqual(carton_count, 0)
    self.assertEqual(line_values, [])
    self.assertEqual(line_errors, {})
    create_mock.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.scan.tests_scan_shipment_handlers.ScanShipmentHandlersTests.test_handle_shipment_create_post_allows_creation_without_cartons -v 2`

Expected: FAIL because the current count parsing and line parsing still force at least one carton line.

**Step 3: Write minimal implementation**

```python
def _parse_carton_count(raw_value):
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)
```

```python
if carton_count == 0:
    line_values, line_items, line_errors = [], [], {}
else:
    line_values, line_items, line_errors = parse_shipment_lines(...)
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.scan.tests_scan_shipment_handlers.ScanShipmentHandlersTests.test_handle_shipment_create_post_allows_creation_without_cartons -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/tests/scan/tests_scan_shipment_handlers.py wms/scan_shipment_handlers.py
git commit -m "test: cover zero-carton shipment creation"
```

### Task 2: Convert shipment creation to immediate definitive references and remove visible draft actions

**Files:**
- Modify: `wms/scan_shipment_handlers.py`
- Modify: `wms/models_domain/shipment.py`
- Modify: `wms/tests/views/tests_views.py`
- Modify: `wms/tests/shipment/tests_shipment_party_snapshot.py`
- Modify: `wms/tests/scan/tests_scan_shipment_handlers.py`

**Step 1: Write the failing test**

```python
def test_scan_shipment_create_creates_definitive_reference_without_save_draft(self):
    response = self.client.post(
        reverse("scan:scan_shipment_create"),
        {
            "destination": str(self.destination.id),
            "shipper_contact": str(self.shipper.id),
            "recipient_contact": str(self.recipient.id),
            "correspondent_contact": str(self.correspondent.id),
            "carton_count": "",
        },
    )

    shipment = Shipment.objects.latest("id")
    self.assertFalse(shipment.reference.startswith("EXP-TEMP-"))
    self.assertEqual(shipment.status, ShipmentStatus.DRAFT)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views.ScanViewsTests.test_scan_shipment_create_creates_definitive_reference_without_save_draft -v 2`

Expected: FAIL because the current flow still uses save-draft actions and temporary references.

**Step 3: Write minimal implementation**

```python
shipment = Shipment.objects.create(
    reference=generate_shipment_reference(),
    status=ShipmentStatus.DRAFT,
    ...
)
```

```python
def _should_promote_temp_reference(self) -> bool:
    return False
```

Remove the `save_draft` and `save_draft_pack` create-time branch from `handle_shipment_create_post`, then migrate tests that currently assert `EXP-TEMP-*` behavior to assert definitive reference creation instead.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.scan.tests_scan_shipment_handlers wms.tests.views.tests_views wms.tests.shipment.tests_shipment_party_snapshot -v 2`

Expected: PASS for the updated shipment-create tests

**Step 5: Commit**

```bash
git add wms/scan_shipment_handlers.py wms/models_domain/shipment.py wms/tests/scan/tests_scan_shipment_handlers.py wms/tests/views/tests_views.py wms/tests/shipment/tests_shipment_party_snapshot.py
git commit -m "feat: create shipments with definitive references"
```

### Task 3: Update shipment create form, JS, and copy for the document-first flow

**Files:**
- Modify: `wms/forms.py`
- Modify: `wms/shipment_form_helpers.py`
- Modify: `wms/views_scan_shipments.py`
- Modify: `templates/scan/includes/shipment_create_details_panel.html`
- Modify: `templates/scan/includes/shipment_create_intro.html`
- Modify: `templates/scan/faq.html`
- Modify: `wms/static/scan/scan.js`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

```python
def test_scan_shipment_create_hides_secondary_draft_button_and_keeps_primary_submit(self):
    response = self.client.get(reverse("scan:scan_shipment_create"))

    self.assertNotContains(response, 'name="action" value="save_draft"')
    self.assertContains(response, 'type="submit" class="scan-submit btn btn-primary"')
    self.assertContains(response, 'for="id_carton_count"')
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments.ScanShipmentsViewsTests.test_scan_shipment_create_hides_secondary_draft_button_and_keeps_primary_submit -v 2`

Expected: FAIL because the secondary draft button is still rendered.

**Step 3: Write minimal implementation**

```python
carton_count = forms.IntegerField(
    label=_("Nombre de colis"),
    min_value=0,
    required=False,
    widget=forms.NumberInput(attrs={"min": 0}),
)
```

```javascript
const resolveCount = value => {
  const parsed = parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return 0;
  }
  return parsed;
};
```

Render empty totals when there are no lines and update copy so the form no longer advertises visible draft behavior.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS for the updated create-form contract tests

**Step 5: Commit**

```bash
git add wms/forms.py wms/shipment_form_helpers.py wms/views_scan_shipments.py templates/scan/includes/shipment_create_details_panel.html templates/scan/includes/shipment_create_intro.html templates/scan/faq.html wms/static/scan/scan.js wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: switch shipment create UI to document-first flow"
```

### Task 4: Add failing tests for batch carton assignment to an existing shipment

**Files:**
- Modify: `wms/tests/carton/tests_carton_handlers.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

```python
def test_bulk_assign_cartons_to_shipment_updates_only_eligible_rows(self):
    target_shipment = Shipment.objects.create(
        shipper_name="ASF",
        recipient_name="Dest",
        destination_address="1 Rue Test",
        destination_country="France",
        status=ShipmentStatus.DRAFT,
    )
    eligible_carton = Carton.objects.create(code="C-ELIGIBLE", status=CartonStatus.PACKED)
    locked_carton = Carton.objects.create(code="C-LOCKED", status=CartonStatus.SHIPPED)

    request = self.factory.post(
        "/scan/cartons/",
        {
            "bulk_action": "bulk_assign_cartons_shipment",
            "bulk_shipment_id": str(target_shipment.id),
            "selected_carton_ids": [str(eligible_carton.id), str(locked_carton.id)],
        },
    )
```

Assert that only the eligible carton is assigned and the handler responds with the usual redirect.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.carton.tests_carton_handlers.CartonHandlersTests.test_bulk_assign_cartons_to_shipment_updates_only_eligible_rows -v 2`

Expected: FAIL because the action does not exist yet.

**Step 3: Write minimal implementation**

```python
if action == "bulk_assign_cartons_shipment":
    shipment = Shipment.objects.filter(pk=request.POST.get("bulk_shipment_id")).first()
    ...
    selected_carton.shipment = shipment
    selected_carton.preassigned_destination = None
    set_carton_status(...)
```

Add the form controls to `cartons_ready` so the shipment selector is available alongside the existing batch actions.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.carton.tests_carton_handlers wms.tests.views.tests_views_scan_shipments -v 2`

Expected: PASS for the new batch assignment tests

**Step 5: Commit**

```bash
git add wms/carton_handlers.py wms/views_scan_shipments.py templates/scan/cartons_ready.html wms/tests/carton/tests_carton_handlers.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: add batch carton assignment to shipments"
```

### Task 5: Make grouped picking render one block per carton

**Files:**
- Modify: `wms/prepare_kits_helpers.py`
- Modify: `templates/print/picking_list_kits.html`
- Modify: `wms/views_print_docs.py`
- Modify: `wms/tests/views/tests_views.py`

**Step 1: Write the failing test**

```python
def test_scan_cartons_picking_renders_one_section_per_carton(self):
    response = self.client.get(
        reverse("scan:scan_cartons_picking"),
        {"carton_ids": f"{carton_a.id},{carton_b.id}"},
    )

    self.assertContains(response, carton_a.code)
    self.assertContains(response, carton_b.code)
    self.assertContains(response, 'data-carton-picking-block="1"', count=2)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views.ViewTests.test_scan_cartons_picking_renders_one_section_per_carton -v 2`

Expected: FAIL because the current grouped context aggregates all rows together.

**Step 3: Write minimal implementation**

```python
return {
    "carton_blocks": [
        {
            "carton_id": carton.id,
            "carton_code": carton.code,
            "item_rows": [...],
        }
        for carton in cartons
    ],
}
```

Update the grouped picking template to iterate `carton_blocks` and render one table per block.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views.ViewTests.test_scan_cartons_picking_renders_one_section_per_carton -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/prepare_kits_helpers.py templates/print/picking_list_kits.html wms/views_print_docs.py wms/tests/views/tests_views.py
git commit -m "feat: render grouped carton picking per carton"
```

### Task 6: Add global batch packing-list print actions for continuous roll and A4 four-up

**Files:**
- Modify: `wms/views_print_docs.py`
- Modify: `templates/scan/shipment_print_bundle_lot.html`
- Modify: grouped print templates/routes used by carton packing-list documents
- Modify: `wms/tests/views/tests_views_print_docs.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

```python
def test_scan_cartons_view_bundle_exposes_global_packing_list_actions(self):
    response = self.client.get(
        reverse("scan:scan_cartons_view_bundle", args=["packing_lists"]),
        {"carton_ids": f"{carton_a.id},{carton_b.id}"},
    )

    self.assertContains(response, "Imprimer toutes les listes")
    self.assertContains(response, "4 par page")
    self.assertContains(response, "format rouleau")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs.ViewsPrintDocsTests.test_scan_cartons_view_bundle_exposes_global_packing_list_actions -v 2`

Expected: FAIL because the bundle page currently exposes per-carton links only.

**Step 3: Write minimal implementation**

```python
"bundle_actions": [
    {"label": _("Imprimer toutes les listes - rouleau"), "url": ...},
    {"label": _("Imprimer toutes les listes - 4 par page"), "url": ...},
]
```

Keep the per-carton actions and add explicit global batch actions at the top of the bundle page.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs wms.tests.views.tests_views_scan_shipments -v 2`

Expected: PASS for the updated bundle-page tests

**Step 5: Commit**

```bash
git add wms/views_print_docs.py templates/scan/shipment_print_bundle_lot.html wms/tests/views/tests_views_print_docs.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: add global carton packing list bundle actions"
```

### Task 7: Add shared previous/next history buttons to legacy mastheads

**Files:**
- Create: `templates/includes/history_nav_buttons.html`
- Modify: `templates/scan/base.html`
- Modify: `templates/portal/base.html`
- Modify: `templates/planning/base.html`
- Modify: `templates/benevole/base.html`
- Modify: `wms/static/scan/scan.js`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_planning.py`
- Modify: `wms/tests/views/tests_views_volunteer.py`

**Step 1: Write the failing test**

```python
def test_scan_shell_exposes_history_nav_buttons_in_masthead(self):
    response = self.client.get(reverse("scan:scan_dashboard"))

    self.assertContains(response, 'id="wms-history-back"')
    self.assertContains(response, 'id="wms-history-forward"')
    self.assertContains(response, 'aria-label="Page précédente"')
    self.assertContains(response, 'aria-label="Page suivante"')
```

Mirror equivalent assertions in the portal, planning, and volunteer shell tests.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_planning wms.tests.views.tests_views_volunteer -v 2`

Expected: FAIL because the masthead controls do not exist yet.

**Step 3: Write minimal implementation**

```html
<div class="ui-comp-actions wms-history-nav" data-history-nav="1">
  <button type="button" id="wms-history-back" class="btn btn-tertiary btn-sm" aria-label="{% trans "Page précédente" %}">←</button>
  <button type="button" id="wms-history-forward" class="btn btn-tertiary btn-sm" aria-label="{% trans "Page suivante" %}">→</button>
</div>
```

```javascript
document.addEventListener('click', event => {
  if (event.target.closest('#wms-history-back')) {
    window.history.back();
  }
  if (event.target.closest('#wms-history-forward')) {
    window.history.forward();
  }
});
```

Use the same include in all four base templates rather than hand-copying markup.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_planning wms.tests.views.tests_views_volunteer -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add templates/includes/history_nav_buttons.html templates/scan/base.html templates/portal/base.html templates/planning/base.html templates/benevole/base.html wms/static/scan/scan.js wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_portal_bootstrap_ui.py wms/tests/views/tests_views_planning.py wms/tests/views/tests_views_volunteer.py
git commit -m "feat: add shared masthead history buttons"
```

### Task 8: Update flow docs and run focused verification before completion

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/mvp_spec.md`
- Modify: `docs/release_checklist.md`
- Modify: `docs/operations.md`
- Modify: `templates/scan/faq.html`

**Step 1: Write the failing test**

```python
def test_scan_shipment_create_faq_no_longer_mentions_exp_temp_drafts(self):
    response = self.client.get(reverse("scan:scan_faq"))
    self.assertNotContains(response, "EXP-TEMP-")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc -v 2`

Expected: FAIL if the FAQ and help text still mention temporary drafts.

**Step 3: Write minimal implementation**

```markdown
- shipment creation now assigns a definitive reference immediately
- operators can create a shipment dossier before attaching cartons
- grouped carton actions include shipment assignment and batch print entrypoints
```

Update the referenced operator docs and repo-reference flow notes to match the implemented behavior.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add docs/repo-reference/02-key-flows-and-living-tests.md docs/mvp_spec.md docs/release_checklist.md docs/operations.md templates/scan/faq.html
git commit -m "docs: align shipment and carton workflow references"
```

### Task 9: Run the final focused regression suite and record anything deferred

**Files:**
- Modify if needed: `docs/deferred-follow-ups.md`

**Step 1: Run the shipment and carton regression subset**

Run: `./.venv/bin/python manage.py test wms.tests.scan.tests_scan_shipment_handlers wms.tests.carton.tests_carton_handlers wms.tests.views.tests_views wms.tests.views.tests_views_scan_shipments wms.tests.views.tests_views_print_docs wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_planning wms.tests.views.tests_views_volunteer wms.tests.shipment.tests_shipment_party_snapshot -v 2`

Expected: PASS

**Step 2: Run the higher-level flow proof if the targeted subset is green**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_flow api.tests.tests_ui_e2e_workflows -v 2`

Expected: PASS or a clearly explained existing unrelated failure

**Step 3: Update deferred follow-ups only if something was intentionally postponed**

```markdown
- no deferred follow-up if the design shipped in full
- otherwise record the exact remaining batch-print or doc-alignment scope
```

**Step 4: Commit**

```bash
git add docs/deferred-follow-ups.md
git commit -m "chore: record deferred follow-ups for shipment flow changes"
```

Skip this commit if no deferred file change was needed.
