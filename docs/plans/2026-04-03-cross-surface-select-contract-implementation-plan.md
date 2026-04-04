# Cross-Surface Select Contract Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Standardize legacy Django select controls across `scan`, `portal`, `planning`, and `benevole` with shared visual affordance, fixed-width size classes, alphabetical ordering by default, preserved grouped options, and explicit per-select sort exceptions.

**Architecture:** Keep native `<select>` controls and the existing Bootstrap `form-select` base. Add one canonical Python sorting helper for flat and grouped choices, one shared CSS contract in `scan-bootstrap.css` for icon/padding/width behavior, then adopt the contract surface by surface with explicit exceptions such as descending shipment ordering on `/scan/cartons/`. Update repo-reference governance docs once the runtime contract is real.

**Tech Stack:** Django forms/views/templates, legacy CSS, Bootstrap-based legacy UI, Django test runner.

---

**Execution rules**

- `@test-driven-development`: no production code before the new failing test for the current task.
- `@verification-before-completion`: run the listed targeted tests before claiming the task is done.
- `@repo-reference-governance`: update repo-reference docs when the shared select contract becomes real.

### Task 1: Add canonical select-sorting helpers for flat and grouped choices

**Files:**
- Modify: `wms/view_utils.py`
- Modify: `wms/forms.py`
- Test: `wms/tests/views/tests_view_utils.py`

**Step 1: Write the failing test**

```python
def test_sorted_choices_keeps_placeholder_first_and_sorts_grouped_choices(self):
    choices = [
        ("", "---------"),
        ("group-a", (("b", "Zulu"), ("a", "alpha"))),
        ("group-b", (("d", "delta"), ("c", "Charlie"))),
    ]

    self.assertEqual(
        sorted_choices(choices),
        [
            ("", "---------"),
            ("group-a", (("a", "alpha"), ("b", "Zulu"))),
            ("group-b", (("c", "Charlie"), ("d", "delta"))),
        ],
    )


def test_sorted_choices_supports_descending_order(self):
    choices = [("a", "alpha"), ("c", "Charlie"), ("b", "Zulu")]

    self.assertEqual(
        sorted_choices(choices, order="desc"),
        [("b", "Zulu"), ("c", "Charlie"), ("a", "alpha")],
    )
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_view_utils -v 2`

Expected: FAIL because `sorted_choices` currently handles only flat choices and has no descending or grouped support.

**Step 3: Write minimal implementation**

```python
def sorted_choices(choices, *, order="asc"):
    reverse = order == "desc"
    placeholder_choices = []
    grouped_choices = []
    regular_choices = []

    for choice in choices:
        value, label = choice
        if value == "":
            placeholder_choices.append(choice)
        elif isinstance(label, (list, tuple)) and label and isinstance(label[0], (list, tuple)):
            grouped_choices.append(
                (value, tuple(sorted(label, key=_choice_label_key, reverse=reverse)))
            )
        else:
            regular_choices.append(choice)

    return (
        placeholder_choices
        + sorted(grouped_choices, key=lambda item: str(item[0] or "").lower(), reverse=reverse)
        + sorted(regular_choices, key=_choice_label_key, reverse=reverse)
    )
```

```python
def _sorted_choices(choices, *, order="asc"):
    return sorted_choices(list(choices), order=order)
```

Keep the helper small and deterministic. Do not add JS ordering logic.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_view_utils -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/view_utils.py wms/forms.py wms/tests/views/tests_view_utils.py
git commit -m "feat: add canonical select choice sorting helper"
```

### Task 2: Add the shared select CSS contract and size classes

**Files:**
- Modify: `wms/static/scan/scan-bootstrap.css`
- Modify: `templates/scan/ui_lab.html`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

```python
def test_scan_bootstrap_css_defines_shared_select_contract(self):
    css_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "scan-bootstrap.css"
    css_content = css_path.read_text(encoding="utf-8")

    self.assertIn(".scan-bootstrap-enabled .form-select {", css_content)
    self.assertIn("background-image:", css_content)
    self.assertIn(".scan-bootstrap-enabled .form-select.ui-select--sm", css_content)
    self.assertIn(".scan-bootstrap-enabled .form-select.ui-select--md", css_content)
    self.assertIn(".scan-bootstrap-enabled .form-select.ui-select--lg", css_content)
    self.assertIn(".scan-bootstrap-enabled .form-select.ui-select--xl", css_content)
```

Add a small UI Lab assertion in the same test file that checks at least one demo select renders one of the new classes.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_bootstrap_css_defines_shared_select_contract -v 2`

Expected: FAIL because the shared icon/size-class contract does not exist yet.

**Step 3: Write minimal implementation**

```css
.scan-bootstrap-enabled .form-select {
  padding-right: calc(var(--wms-input-padding-x) * 2.75);
  background-image: url("data:image/svg+xml,...");
  background-position: right 0.85rem center;
  background-size: 0.8rem 0.8rem;
}

.scan-bootstrap-enabled .form-select.ui-select--sm { width: 10rem; }
.scan-bootstrap-enabled .form-select.ui-select--md { width: 14rem; }
.scan-bootstrap-enabled .form-select.ui-select--lg { width: 18rem; }
.scan-bootstrap-enabled .form-select.ui-select--xl { width: 24rem; }
```

Add one `ui_lab` example so the contract remains visible in the design-system sandbox.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS for the shared select CSS contract assertions.

**Step 5: Commit**

```bash
git add wms/static/scan/scan-bootstrap.css templates/scan/ui_lab.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add shared select visual contract"
```

### Task 3: Adopt the contract on scan operational selects and add the shipment descending exception

**Files:**
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/forms.py`
- Modify: `templates/scan/admin_product_labels.html`
- Modify: `templates/scan/billing_editor.html`
- Modify: `templates/scan/cartons_ready.html`
- Modify: `templates/scan/dashboard.html`
- Modify: `templates/scan/orders_view.html`
- Modify: `templates/scan/pack.html`
- Modify: `templates/scan/public_account_request.html`
- Modify: `templates/scan/receipts_view.html`
- Modify: `templates/scan/settings.html`
- Modify: `templates/scan/shipment_tracking.html`
- Modify: `templates/scan/shipments_tracking.html`
- Modify: `templates/scan/stock.html`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

```python
def test_scan_cartons_ready_uses_fixed_width_select_classes_and_descending_shipment_order(self):
    response = self.client.get(reverse("scan:scan_cartons_ready"))

    self.assertContains(response, "scan-carton-bulk-action-select")
    self.assertContains(response, "scan-carton-bulk-shipment-select")
    self.assertContains(response, "ui-select--sm")
    self.assertContains(response, "ui-select--xl")
    self.assertLess(
        response.content.decode().index("260014"),
        response.content.decode().index("250999"),
    )
```

Add a second assertion on one other scan page, for example `scan_stock`, to confirm the new fixed-width classes are applied outside `Vue Colis`.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments.ScanShipmentsViewsTests.test_scan_cartons_ready_uses_fixed_width_select_classes_and_descending_shipment_order -v 2`

Expected: FAIL because the selects still use `w-auto` and the shipment list is not yet forced through the explicit descending exception path.

**Step 3: Write minimal implementation**

```python
def _build_carton_assignment_shipment_options():
    shipments = Shipment.objects.filter(...).order_by("-reference", "-id")
    return [
        {"id": shipment.id, "label": shipment.reference}
        for shipment in shipments
    ]
```

```html
<select name="bulk_action" class="form-select form-select-sm ui-select--sm scan-carton-bulk-action-select">
<select name="bulk_shipment_id" class="form-select form-select-sm ui-select--xl scan-carton-bulk-shipment-select">
```

Apply the same `ui-select--*` classes to the other scan operational pages based on content length. Remove `w-auto` from workflow-critical selects.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS for the updated scan select contract and shipment-order exception.

**Step 5: Commit**

```bash
git add wms/views_scan_shipments.py wms/forms.py templates/scan/admin_product_labels.html templates/scan/billing_editor.html templates/scan/cartons_ready.html templates/scan/dashboard.html templates/scan/orders_view.html templates/scan/pack.html templates/scan/public_account_request.html templates/scan/receipts_view.html templates/scan/settings.html templates/scan/shipment_tracking.html templates/scan/shipments_tracking.html templates/scan/stock.html wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: standardize scan select sizing and ordering"
```

### Task 4: Apply the same contract to scan admin/import templates and form widgets

**Files:**
- Modify: `wms/forms_admin_contacts_contact.py`
- Modify: `wms/forms_admin_contacts_destination.py`
- Modify: `wms/forms_scan_design.py`
- Modify: `templates/scan/includes/admin_contacts_contact_form.html`
- Modify: `templates/scan/includes/admin_contacts_destination_form.html`
- Modify: `templates/scan/includes/admin_contacts_directory_action_panel.html`
- Modify: `templates/scan/includes/admin_contacts_directory_card.html`
- Modify: `templates/scan/includes/admin_contacts_filters_card.html`
- Modify: `templates/scan/includes/admin_contacts_shipment_cockpit.html`
- Modify: `templates/scan/includes/imports_product_match_review.html`
- Modify: `templates/scan/includes/imports_users_card.html`
- Modify: `templates/scan/includes/receive_pallet_listing_upload_card.html`
- Modify: `templates/scan/includes/receive_pallet_mapping_card.html`
- Modify: `templates/scan/includes/receive_pallet_review_card.html`
- Modify: `templates/scan/print_template_edit.html`
- Test: `wms/tests/forms/tests_forms_admin_contacts_contact.py`
- Test: `wms/tests/forms/tests_forms_admin_contacts_destination.py`
- Test: `wms/tests/views/tests_views_scan_admin.py`

**Step 1: Write the failing test**

```python
def test_contact_crud_form_select_widgets_use_shared_select_classes(self):
    form = ContactCrudForm()

    self.assertIn("ui-select--md", form.fields["business_type"].widget.attrs["class"])
    self.assertIn("ui-select--lg", form.fields["destination_id"].widget.attrs["class"])
    self.assertIn("ui-select--xl", form.fields["allowed_shipper_ids"].widget.attrs["class"])
```

Add one view-level assertion that a representative scan admin template still renders grouped/manual selects with `form-select`.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.forms.tests_forms_admin_contacts_contact wms.tests.forms.tests_forms_admin_contacts_destination wms.tests.views.tests_views_scan_admin -v 2`

Expected: FAIL because these widgets/templates do not yet carry the shared size classes.

**Step 3: Write minimal implementation**

```python
elif isinstance(widget, forms.SelectMultiple):
    widget.attrs.setdefault("class", "form-select ui-select--xl")
elif isinstance(widget, forms.Select):
    widget.attrs.setdefault("class", "form-select ui-select--md")
```

For the few scan admin/import templates with literal `<select>` tags, add explicit `ui-select--*` classes in the template instead of relying on browser default width.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.forms.tests_forms_admin_contacts_contact wms.tests.forms.tests_forms_admin_contacts_destination wms.tests.views.tests_views_scan_admin -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/forms_admin_contacts_contact.py wms/forms_admin_contacts_destination.py wms/forms_scan_design.py templates/scan/includes/admin_contacts_contact_form.html templates/scan/includes/admin_contacts_destination_form.html templates/scan/includes/admin_contacts_directory_action_panel.html templates/scan/includes/admin_contacts_directory_card.html templates/scan/includes/admin_contacts_filters_card.html templates/scan/includes/admin_contacts_shipment_cockpit.html templates/scan/includes/imports_product_match_review.html templates/scan/includes/imports_users_card.html templates/scan/includes/receive_pallet_listing_upload_card.html templates/scan/includes/receive_pallet_mapping_card.html templates/scan/includes/receive_pallet_review_card.html templates/scan/print_template_edit.html wms/tests/forms/tests_forms_admin_contacts_contact.py wms/tests/forms/tests_forms_admin_contacts_destination.py wms/tests/views/tests_views_scan_admin.py
git commit -m "feat: apply shared select classes to scan admin surfaces"
```

### Task 5: Preserve portal optgroups while applying alphabetic ordering and fixed widths

**Files:**
- Modify: `wms/views_portal_orders.py`
- Modify: `templates/portal/includes/account_billing_card.html`
- Modify: `templates/portal/includes/account_contact_row.html`
- Modify: `templates/portal/includes/order_create_routing_card.html`
- Modify: `templates/portal/includes/recipient_contact_fields.html`
- Modify: `templates/portal/recipients.html`
- Test: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Test: `wms/tests/views/tests_views_portal.py`

**Step 1: Write the failing test**

```python
def test_portal_order_create_keeps_destination_optgroups_and_sorts_each_group(self):
    response = self.client.get(reverse("portal:portal_order_create"))

    self.assertContains(response, "Destinations disponibles")
    self.assertContains(response, "Autres destinations")
    self.assertContains(response, 'id="destination_id"')
    self.assertContains(response, "ui-select--lg")
```

Add a context-level assertion in `tests_views_portal.py` that `destination_options` and `disabled_destination_options` are each sorted by label before rendering.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal -v 2`

Expected: FAIL because grouped ordering is still ad hoc and the new size classes are missing.

**Step 3: Write minimal implementation**

```python
def _sorted_option_dicts(options, *, order="asc"):
    return sorted(
        options,
        key=lambda item: str(item["label"] or "").lower(),
        reverse=order == "desc",
    )


def _build_destination_options(destinations):
    options = [{"id": str(destination.id), "label": str(destination)} for destination in destinations]
    return _sorted_option_dicts(options)
```

```python
def _split_destination_options_by_availability(destination_options, *, available_destination_ids):
    ...
    return _sorted_option_dicts(available_options), _sorted_option_dicts(disabled_options)
```

```html
<select class="form-select ui-select--lg" id="destination_id" name="destination_id" required>
<select class="form-select ui-select--lg" id="recipient_id" name="recipient_id" required>
```

Keep the `optgroup` split exactly as-is; only the ordering inside each bucket changes.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/views_portal_orders.py templates/portal/includes/account_billing_card.html templates/portal/includes/account_contact_row.html templates/portal/includes/order_create_routing_card.html templates/portal/includes/recipient_contact_fields.html templates/portal/recipients.html wms/tests/views/tests_portal_bootstrap_ui.py wms/tests/views/tests_views_portal.py
git commit -m "feat: standardize portal select grouping and sizing"
```

### Task 6: Apply the contract to planning and benevole selects

**Files:**
- Modify: `wms/forms_volunteer.py`
- Modify: `wms/views_volunteer.py`
- Modify: `templates/planning/_version_planning_block.html`
- Modify: `templates/planning/_version_unassigned_block.html`
- Modify: `templates/benevole/availability_recap.html`
- Modify: `templates/benevole/availability_week_form.html`
- Test: `wms/tests/views/tests_views_planning.py`
- Test: `wms/tests/views/tests_views_volunteer.py`

**Step 1: Write the failing test**

```python
def test_planning_assignment_editor_selects_use_shared_small_width_classes(self):
    response = self.client.get(reverse("planning:version_detail", args=[self.make_operator_version()["version"].id]))

    self.assertContains(response, 'data-flight-date-select')
    self.assertContains(response, "ui-select--sm")
```

```python
def test_volunteer_week_selects_use_shared_fixed_width_classes(self):
    response = self.client.get(reverse("volunteer:availability_recap"))

    self.assertContains(response, 'id="id_week"')
    self.assertContains(response, "ui-select--md")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_planning wms.tests.views.tests_views_volunteer -v 2`

Expected: FAIL because planning and volunteer templates still rely on default `form-select` sizing or inline style.

**Step 3: Write minimal implementation**

```html
<select class="form-select form-select-sm ui-select--sm" ...>
```

```python
def _quarter_hour_select_widget():
    return forms.Select(
        choices=_quarter_hour_choices(),
        attrs={"class": "form-select ui-select--md"},
    )
```

Replace the inline `style="min-width: 16rem;"` week picker with the shared named-size class.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_planning wms.tests.views.tests_views_volunteer -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/forms_volunteer.py wms/views_volunteer.py templates/planning/_version_planning_block.html templates/planning/_version_unassigned_block.html templates/benevole/availability_recap.html templates/benevole/availability_week_form.html wms/tests/views/tests_views_planning.py wms/tests/views/tests_views_volunteer.py
git commit -m "feat: apply shared select contract to planning and benevole"
```

### Task 7: Update repo-reference docs and run the full targeted verification set

**Files:**
- Modify: `docs/repo-reference/03-impact-map.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Write the failing doc/test assertion**

Add a small regression assertion in an existing UI contract suite if helpful, but the primary failure here is documentation drift: the repo-reference currently does not mention the shared select contract.

**Step 2: Run verification before doc changes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_view_utils wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments wms.tests.forms.tests_forms_admin_contacts_contact wms.tests.forms.tests_forms_admin_contacts_destination wms.tests.views.tests_views_scan_admin wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal wms.tests.views.tests_views_planning wms.tests.views.tests_views_volunteer -v 2`

Expected: PASS once Tasks 1-6 are complete.

**Step 3: Write minimal documentation updates**

Add explicit maintenance bullets such as:

```md
- shared select contract: native `form-select` plus named width classes `ui-select--sm|md|lg|xl`
- default select ordering is alphabetical by visible label
- preserve `optgroup` structure and sort options within each group
- explicit descending exceptions must be documented in the owning view/helper
```

Update the impact map so future shared-select changes check `scan`, `portal`, `planning`, and `benevole` together.

**Step 4: Run final verification**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_view_utils wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments wms.tests.forms.tests_forms_admin_contacts_contact wms.tests.forms.tests_forms_admin_contacts_destination wms.tests.views.tests_views_scan_admin wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal wms.tests.views.tests_views_planning wms.tests.views.tests_views_volunteer -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add docs/repo-reference/03-impact-map.md docs/repo-reference/04-shared-contracts.md
git commit -m "docs: document shared select contract"
```
