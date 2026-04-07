# Scan Receipts And Pack Adjustments Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persist receipt conformity and observation data, widen the prepare-kits top panel, and upgrade the scan pack shipment selector/default switch behavior.

**Architecture:** Add a receipt-level conformity choice field on the existing `Receipt` model, map new/renamed form controls onto existing receipt creation flows, and keep `scan/pack` handler compatibility by rendering shipment selection as a reference-backed select. Restrict layout work to local scan template/CSS rules and prove each change with focused TDD-style regressions.

**Tech Stack:** Django models/forms/views/templates, legacy scan Bootstrap CSS, Django test suite

---

### Task 1: Document the new receipt conformity persistence contract

**Files:**
- Modify: `wms/models_domain/inventory.py`
- Create: `wms/migrations/<generated>.py`
- Test: `wms/tests/views/tests_views.py`

**Step 1: Write the failing test**

Add a view-level creation test asserting a newly created pallet or association receipt stores the expected conformity status.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views.ViewTests.test_scan_receive_pallet_creates_receipt wms.tests.views.tests_views.ViewTests.test_scan_receive_association_creates_receipt -v 2`

Expected: FAIL because `Receipt` does not yet expose a conformity status field/assertion target.

**Step 3: Write minimal implementation**

- add `ReceiptConformityStatus`
- add `Receipt.conformity_status`
- generate migration

**Step 4: Run test to verify it passes**

Run the same targeted tests and confirm the updated expectations pass.

**Step 5: Commit**

```bash
git add wms/models_domain/inventory.py wms/migrations wms/tests/views/tests_views.py
git commit -m "feat(scan): persist receipt conformity status"
```

### Task 2: Add pallet conformity and observation validation

**Files:**
- Modify: `wms/forms.py`
- Modify: `wms/receipt_pallet_handlers.py`
- Modify: `templates/scan/includes/receive_pallet_create_card.html`
- Test: `wms/tests/forms/tests_forms.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_views.py`

**Step 1: Write the failing test**

Add:

- a form test proving pallet observation is required when non-conform is checked
- a view test proving pallet receipt creation persists `notes`
- a bootstrap/template test proving the new controls render

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.forms.tests_forms.FormsTests.test_scan_receipt_pallet_form_requires_observation_when_non_conform wms.tests.views.tests_views.ViewTests.test_scan_receive_pallet_creates_receipt wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_receive_pallet_breaks_into_named_workflow_sections -v 2`

Expected: FAIL on missing fields and missing persistence.

**Step 3: Write minimal implementation**

- add `observation` + `is_non_conform` fields to `ScanReceiptPalletForm`
- enforce conditional validation
- persist `notes` and `conformity_status`
- render the new field and switch

**Step 4: Run test to verify it passes**

Re-run the targeted test command and confirm green.

**Step 5: Commit**

```bash
git add wms/forms.py wms/receipt_pallet_handlers.py templates/scan/includes/receive_pallet_create_card.html wms/tests/forms/tests_forms.py wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views.py
git commit -m "feat(scan): capture pallet receipt conformity"
```

### Task 3: Add association conformity validation while keeping pickup comment storage

**Files:**
- Modify: `wms/forms.py`
- Modify: `wms/receipt_handlers.py`
- Modify: `templates/scan/includes/receive_association_create_card.html`
- Test: `wms/tests/forms/tests_forms.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_views.py`
- Test: `wms/tests/receipt/test_receipt_association_billing_fields.py`

**Step 1: Write the failing test**

Add:

- a form test proving association observation is required when non-conform is checked
- update/create a view test proving `pickup_charge_comment` plus `conformity_status` persist
- a bootstrap/template test asserting the observation label and switch render

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.forms.tests_forms.FormsTests.test_scan_receipt_association_form_requires_observation_when_non_conform wms.tests.views.tests_views.ViewTests.test_scan_receive_association_creates_receipt wms.tests.receipt.test_receipt_association_billing_fields -v 2`

Expected: FAIL on missing validation/persistence.

**Step 3: Write minimal implementation**

- add `is_non_conform` to `ScanReceiptAssociationForm`
- require `pickup_charge_comment` when non-conform
- persist `conformity_status`
- rename the visible label to `Observation`

**Step 4: Run test to verify it passes**

Re-run the targeted command and confirm green.

**Step 5: Commit**

```bash
git add wms/forms.py wms/receipt_handlers.py templates/scan/includes/receive_association_create_card.html wms/tests/forms/tests_forms.py wms/tests/views/tests_views.py wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/receipt/test_receipt_association_billing_fields.py
git commit -m "feat(scan): capture association receipt conformity"
```

### Task 4: Fix prepare-kits top panel width

**Files:**
- Modify: `wms/static/scan/scan-bootstrap.css`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Add a CSS contract test asserting the top panel no longer carries the desktop width cap.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_prepare_kits_uses_full_width_top_panel_contract -v 2`

Expected: FAIL because the CSS still contains `max-width`.

**Step 3: Write minimal implementation**

Remove the width cap from the desktop bootstrap rule while preserving the existing full-row placement.

**Step 4: Run test to verify it passes**

Re-run the targeted CSS/UI tests.

**Step 5: Commit**

```bash
git add wms/static/scan/scan-bootstrap.css wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "fix(scan): keep prepare-kits top panel full width"
```

### Task 5: Convert scan pack shipment reference to a descending select and default confirmation to true

**Files:**
- Modify: `wms/forms.py`
- Modify: `wms/views_scan_shipments.py`
- Modify: `templates/scan/includes/pack_shipping_section.html`
- Test: `wms/tests/forms/tests_forms.py`
- Test: `wms/tests/views/tests_views.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add:

- a form test proving shipment choices are ordered Z-A and labeled `reference - IATA`
- a view test proving GET defaults `confirm_defaults` to true
- a template test proving the shipment field is rendered as a select

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.forms.tests_forms.FormsTests.test_scan_pack_form_exposes_descending_shipment_reference_choices wms.tests.views.tests_views_scan_shipments.ScanShipmentsViewsTests.test_scan_pack_get_uses_session_pack_results_and_defaults wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_pack_uses_shipment_select_contract -v 2`

Expected: FAIL because shipment reference is still a text input and GET still defaults `confirm_defaults` to false.

**Step 3: Write minimal implementation**

- switch `shipment_reference` to a reference-backed `ModelChoiceField`
- keep submitted value equal to `Shipment.reference`
- order by descending reference
- format labels with destination IATA
- default `confirm_defaults = True` on GET

**Step 4: Run test to verify it passes**

Re-run the targeted pack tests and confirm green.

**Step 5: Commit**

```bash
git add wms/forms.py wms/views_scan_shipments.py templates/scan/includes/pack_shipping_section.html wms/tests/forms/tests_forms.py wms/tests/views/tests_views.py wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat(scan): refine pack shipment selection defaults"
```

### Task 6: Update repo-reference docs for the changed contracts

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Write the failing check**

Identify the exact new contract statements that are now true after implementation:

- scan receipts capture conformity + observation
- `scan/pack` shipment select is an explicit descending-reference exception

**Step 2: Run doc verification**

Read the relevant repo-reference sections and confirm they do not yet describe the new contract.

**Step 3: Write minimal implementation**

Update the two reference docs only where the contract materially changed.

**Step 4: Run final verification**

Run the full targeted suite for receipts, pack, prepare-kits, and bootstrap UI.

**Step 5: Commit**

```bash
git add docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md
git commit -m "docs(repo-reference): record scan receipt and pack UI contracts"
```
