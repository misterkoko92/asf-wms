# Scan Listing Entry Flow Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rework `Listing` into a two-step intake flow with a required file-type selector, optional receipt linking, an inline `Reception a creer` draft, and type-specific upload cards that no longer duplicate receipt metadata.

**Architecture:** Add a dedicated intake form/state layer in front of the existing listing upload pipeline. Persist the chosen file type and receipt linkage in listing pending session state, keep PDF/Excel/CSV processing mostly unchanged behind that intake gate, and create a real pallet `Receipt` only at final import time when no existing receipt was linked.

**Tech Stack:** Django 4.2 views/templates/forms/models, Django TestCase, legacy scan Bootstrap templates, existing listing session handlers in `wms/pallet_listing_handlers.py`

---

### Task 1: Lock the new listing intake contract with failing UI and view-state tests

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_scan_receipts.py`
- Modify: `wms/tests/receipt/tests_receipt_listing.py`
- Verify: `templates/scan/receive_listing.html`
- Verify: `wms/receipt_listing_state.py`

**Step 1: Write the failing test**

Add a shell test for the new intake card and selective type-card rendering:

```python
def test_scan_receive_listing_page_starts_with_intake_card(self):
    response = self.client.get(reverse("scan:scan_receive_listing"))

    self.assertContains(response, 'id="scan-receive-listing-intake-card"')
    self.assertContains(response, 'name="listing_entry_file_type"')
    self.assertContains(response, 'name="listing_entry_receipt_id"')
    self.assertNotContains(response, 'id="scan-receive-listing-pdf-card"')
```

Add a state-context test:

```python
def test_build_receive_listing_context_exposes_entry_selection(self):
    context = build_receive_listing_context(state)
    self.assertEqual(context["listing_entry_file_type"], "pdf")
    self.assertEqual(context["listing_entry_receipt_id"], "")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_receipts wms.tests.receipt.tests_receipt_listing -v 2`

Expected: FAIL because the page still renders all type cards at once and the listing state has no intake-specific fields.

**Step 3: Write minimal implementation**

No production code in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run the same targeted tests and confirm the failure is only the missing intake contract.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_receipts.py wms/tests/receipt/tests_receipt_listing.py
git commit -m "test: lock listing intake entry contract"
```

### Task 2: Add dedicated forms and listing-entry state for type selection and receipt linking

**Files:**
- Modify: `wms/forms.py`
- Modify: `wms/receipt_listing_state.py`
- Modify: `wms/views_scan_receipts.py`
- Test: `wms/tests/receipt/tests_receipt_listing.py`
- Test: `wms/tests/views/tests_views_scan_receipts.py`

**Step 1: Write the failing test**

Add a form/state test for the required file type and optional receipt link:

```python
def test_build_receive_listing_state_binds_entry_form_on_listing_configure(self):
    request = self._request(data={"action": "listing_configure", "listing_entry_file_type": "pdf"})
    state = build_receive_listing_state(request, action="listing_configure")

    self.assertTrue(state["listing_entry_form"].is_bound)
```

Add a view test ensuring `bulk_update_incomplete_products` does not break the intake state.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.receipt.tests_receipt_listing wms.tests.views.tests_views_scan_receipts -v 2`

Expected: FAIL because there is no dedicated entry form nor `listing_configure` action.

**Step 3: Write minimal implementation**

In `wms/forms.py`, add:

```python
class ScanListingEntryForm(forms.Form):
    listing_entry_file_type = forms.ChoiceField(...)
    listing_entry_receipt_id = forms.ModelChoiceField(...)
```

In `wms/receipt_listing_state.py`, expose:

```python
"listing_entry_form": entry_form,
"listing_entry_file_type": state["listing_entry_file_type"],
"listing_entry_receipt_id": state["listing_entry_receipt_id"],
```

In `wms/views_scan_receipts.py`, recognize `listing_configure` as a listing action.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.receipt.tests_receipt_listing wms.tests.views.tests_views_scan_receipts -v 2`

Expected: PASS with a dedicated intake form and context.

**Step 5: Commit**

```bash
git add wms/forms.py wms/receipt_listing_state.py wms/views_scan_receipts.py wms/tests/receipt/tests_receipt_listing.py wms/tests/views/tests_views_scan_receipts.py
git commit -m "feat: add listing intake entry state"
```

### Task 3: Add receipt option labeling and inline `Reception a creer` draft state

**Files:**
- Modify: `wms/forms.py`
- Modify: `wms/receipt_listing_state.py`
- Modify: `wms/pallet_listing_handlers.py`
- Test: `wms/tests/forms/test_forms_scan_receipts.py`
- Test: `wms/tests/receipt/tests_receipt_listing.py`

**Step 1: Write the failing test**

Add receipt label coverage:

```python
def test_listing_entry_form_labels_receipts_with_date_pallets_donor_and_carrier(self):
    form = ScanListingEntryForm()
    label = form.fields["listing_entry_receipt_id"].label_from_instance(receipt)
    self.assertIn("3 palettes", label)
```

Add state coverage for the draft reception block:

```python
def test_build_receive_listing_context_marks_draft_receipt_when_no_receipt_selected(self):
    self.assertTrue(context["listing_requires_receipt_draft"])
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.forms.test_forms_scan_receipts wms.tests.receipt.tests_receipt_listing -v 2`

Expected: FAIL because receipt labels are not in the target format and no draft-reception context exists.

**Step 3: Write minimal implementation**

Add a small helper in `wms/forms.py` for receipt labels, anti-chronological queryset ordering, and a dedicated draft form reused from the pallet contract.

Persist draft receipt data in listing pending/session state:

```python
"receipt_draft": {
    "received_on": "...",
    "pallet_count": 3,
    ...
}
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.forms.test_forms_scan_receipts wms.tests.receipt.tests_receipt_listing -v 2`

Expected: PASS with correct receipt labels and draft-state exposure.

**Step 5: Commit**

```bash
git add wms/forms.py wms/receipt_listing_state.py wms/pallet_listing_handlers.py wms/tests/forms/test_forms_scan_receipts.py wms/tests/receipt/tests_receipt_listing.py
git commit -m "feat: add listing receipt draft support"
```

### Task 4: Rebuild the `Listing` template so only the selected type card renders

**Files:**
- Modify: `templates/scan/receive_listing.html`
- Modify or replace: `templates/scan/includes/receive_pallet_listing_upload_card.html`
- Create if needed: `templates/scan/includes/receive_listing_intake_card.html`
- Create if needed: `templates/scan/includes/receive_listing_receipt_draft_card.html`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add UI assertions:

```python
def test_scan_receive_listing_only_renders_selected_type_card(self):
    session = self.client.session
    session["pallet_listing_pending"] = {"entry_file_type": "pdf", "token": "tok"}
    session.save()

    response = self.client.get(reverse("scan:scan_receive_listing"))
    self.assertContains(response, 'id="scan-receive-listing-pdf-card"')
    self.assertNotContains(response, 'id="scan-receive-listing-excel-card"')
    self.assertNotContains(response, 'id="scan-receive-listing-csv-card"')
```

Also assert the receipt fields are gone from the type card.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL because all three cards still render and the PDF card still contains receipt fields.

**Step 3: Write minimal implementation**

Render order should become:

```django
{% include "scan/includes/receive_listing_intake_card.html" %}
{% if listing_selected_type == "pdf" %}...{% endif %}
{% if listing_requires_receipt_draft %}...{% endif %}
{% include "scan/includes/receive_listing_incomplete_products_card.html" %}
```

Remove receipt metadata fields from the type-specific upload card(s).

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS with the new page structure and no duplicated receipt fields on PDF/Excel/CSV cards.

**Step 5: Commit**

```bash
git add templates/scan/receive_listing.html templates/scan/includes/receive_pallet_listing_upload_card.html templates/scan/includes/receive_listing_intake_card.html templates/scan/includes/receive_listing_receipt_draft_card.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: rework listing intake page layout"
```

### Task 5: Wire final import so it uses an existing receipt or creates one from the draft

**Files:**
- Modify: `wms/pallet_listing_handlers.py`
- Modify: `wms/import_services_pallet.py` if needed for explicit receipt injection
- Verify: `wms/receipt_pallet_handlers.py`
- Test: `wms/tests/pallet/tests_pallet_listing_handlers.py`
- Test: `wms/tests/imports/tests_import_services_pallet.py`

**Step 1: Write the failing test**

Add handler tests:

```python
def test_listing_confirm_import_uses_selected_receipt_when_present(self):
    ...

def test_listing_confirm_import_creates_receipt_from_draft_when_missing(self):
    ...

def test_listing_confirm_import_rejects_incomplete_receipt_draft(self):
    ...
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.pallet.tests_pallet_listing_handlers wms.tests.imports.tests_import_services_pallet -v 2`

Expected: FAIL because the flow still depends on listing form metadata captured at upload time.

**Step 3: Write minimal implementation**

At confirmation time:

```python
if selected_receipt_id:
    receipt = Receipt.objects.get(...)
else:
    receipt = Receipt.objects.create(...)
```

Move receipt metadata source-of-truth from the old upload form into either:

- the selected receipt id
- or the draft receipt payload stored in session

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.pallet.tests_pallet_listing_handlers wms.tests.imports.tests_import_services_pallet -v 2`

Expected: PASS with correct reuse or deferred creation of `Receipt`.

**Step 5: Commit**

```bash
git add wms/pallet_listing_handlers.py wms/import_services_pallet.py wms/tests/pallet/tests_pallet_listing_handlers.py wms/tests/imports/tests_import_services_pallet.py
git commit -m "feat: bind listing import to selected or draft receipt"
```

### Task 6: Update repo-reference docs and run full verification

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Verify: `docs/plans/2026-04-11-scan-listing-entry-flow-redesign-design.md`
- Verify: `docs/plans/2026-04-11-scan-listing-entry-flow-redesign-implementation-plan.md`

**Step 1: Write the failing test**

No automated failing test; this task is documentation and verification.

**Step 2: Run test to verify current behavior before doc updates**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_receipts wms.tests.receipt.tests_receipt_listing wms.tests.pallet.tests_pallet_listing_handlers wms.tests.imports.tests_import_services_pallet -v 1`

Expected: PASS before docs are updated.

**Step 3: Write minimal implementation**

Update repo-reference to reflect:

- `Listing` now starts with a shared intake step
- type-specific cards only render after validation
- receipt metadata lives either on a selected receipt or an inline draft block

**Step 4: Run full verification**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_receipts wms.tests.receipt.tests_receipt_listing wms.tests.pallet.tests_pallet_listing_handlers wms.tests.imports.tests_import_services_pallet wms.tests.imports.tests_import_utils wms.tests.imports.tests_import_services_products_extra -v 1`

Then run: `COVERAGE_FAIL_UNDER=93 TEST_PARALLEL=4 uv run make coverage`

Expected: PASS with coverage still at or above the configured threshold.

**Step 5: Commit**

```bash
git add docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md docs/plans/2026-04-11-scan-listing-entry-flow-redesign-design.md docs/plans/2026-04-11-scan-listing-entry-flow-redesign-implementation-plan.md
git commit -m "docs: record listing intake flow contract"
```
