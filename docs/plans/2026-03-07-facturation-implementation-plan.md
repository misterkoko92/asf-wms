# Facturation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a legacy Django billing module with configurable pricing/equivalence rules, quote/invoice drafting, receipt-to-shipment allocations, portal billing consultation, and PDF document generation.

**Architecture:** Introduce a dedicated billing aggregate in `wms/models_domain/billing.py`, keep logistics truth in `Shipment` and `Receipt`, and reuse the existing XLSX mapping/PDF rendering stack for billing documents. Billing formulas, mixed unit rules, and association-specific overrides are data-driven records editable from scan/admin pages rather than hardcoded branches.

**Tech Stack:** Django models/views/forms/templates (`wms`), legacy scan + portal routes, Django auth/groups, existing print-pack XLSX/PDF pipeline, Django test runner via `manage.py test`.

---

## Execution Notes

- Use `@test-driven-development` for each task.
- Use `@verification-before-completion` before claiming the feature is done.
- Execute coding in a dedicated worktree before starting implementation.
- Keep commits small and scoped to one task at a time.

## Assumptions To Validate During Implementation

- A dedicated billing staff group (for example `Billing_Staff`) is acceptable, with superuser bypass.
- Billing document template mapping will be handled by the existing print-template tooling rather than a second mapping UI.
- Billing preference change requests can live inside the portal account flow or the new portal billing area, as long as approval remains explicit.

### Task 1: Add the billing domain model scaffold

**Files:**
- Create: `wms/models_domain/billing.py`
- Modify: `wms/models.py`
- Create: `wms/tests/billing/test_models_billing.py`
- Create: `wms/migrations/00xx_billing_domain_initial.py`

**Step 1: Write the failing model tests**

Add tests in `wms/tests/billing/test_models_billing.py` for:
- `AssociationBillingProfile` one-to-one creation from an `AssociationProfile`
- `BillingDocument` default statuses and kind-specific numbering rules
- `ReceiptShipmentAllocation` uniqueness per receipt/shipment pair

```python
def test_billing_document_invoice_requires_manual_number():
    document = BillingDocument(kind=BillingDocumentKind.INVOICE)
    with pytest.raises(ValidationError):
        document.full_clean()
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.billing.test_models_billing -v 2`
Expected: FAIL with missing billing model imports/modules.

**Step 3: Write minimal implementation**

Create `wms/models_domain/billing.py` with initial models and enums:
- `AssociationBillingProfile`
- `AssociationBillingChangeRequest`
- `BillingComputationProfile`
- `BillingServiceCatalogItem`
- `BillingAssociationPriceOverride`
- `ReceiptShipmentAllocation`
- `BillingDocument`
- `BillingDocumentShipment`
- `BillingDocumentReceipt`
- `BillingDocumentLine`
- `BillingPayment`
- `BillingIssue`

Update `wms/models.py` to export the new models.

```python
class BillingDocumentKind(models.TextChoices):
    QUOTE = "quote", "Quote"
    INVOICE = "invoice", "Invoice"
    CREDIT_NOTE = "credit_note", "Credit note"
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.billing.test_models_billing -v 2`
Expected: PASS for the new model tests.

**Step 5: Commit**

```bash
git add wms/models_domain/billing.py wms/models.py wms/tests/billing/test_models_billing.py wms/migrations/00xx_billing_domain_initial.py
git commit -m "feat: add billing domain models"
```

### Task 2: Extend association receipts for pickup billing metadata

**Files:**
- Modify: `wms/models_domain/inventory.py`
- Modify: `wms/forms.py`
- Modify: `wms/receipt_handlers.py`
- Modify: `templates/scan/receive_association.html`
- Create: `wms/tests/receipt/test_receipt_association_billing_fields.py`

**Step 1: Write the failing receipt tests**

Add tests for:
- pickup amount/currency/comment/proof fields on association receipts
- association receipt form accepting and persisting those fields

```python
def test_association_receipt_stores_pickup_billing_fields(self):
    receipt = Receipt.objects.create(
        receipt_type=ReceiptType.ASSOCIATION,
        pickup_charge_amount=Decimal("35.00"),
        pickup_charge_currency="EUR",
    )
    self.assertEqual(receipt.pickup_charge_currency, "EUR")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.receipt.test_receipt_association_billing_fields -v 2`
Expected: FAIL with unknown receipt fields.

**Step 3: Write minimal implementation**

- Add pickup billing fields to `Receipt`
- Extend `ScanReceiptAssociationForm`
- Persist the fields in `handle_receipt_association_post`
- Render the new inputs in `templates/scan/receive_association.html`

```python
pickup_charge_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
pickup_charge_currency = models.CharField(max_length=3, blank=True, default="EUR")
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.receipt.test_receipt_association_billing_fields -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/models_domain/inventory.py wms/forms.py wms/receipt_handlers.py templates/scan/receive_association.html wms/tests/receipt/test_receipt_association_billing_fields.py
git commit -m "feat: add pickup billing fields to association receipts"
```

### Task 3: Add unit equivalence and configurable computation profiles

**Files:**
- Modify: `wms/models_domain/billing.py`
- Create: `wms/billing_calculations.py`
- Create: `wms/tests/billing/test_billing_calculations.py`

**Step 1: Write the failing calculation tests**

Add tests covering:
- mixed standard carton units (`MM` / `CN` -> `1`)
- hors format equivalence rules
- default receipt-linked formula using allocated received units
- manual override hooks

```python
def test_receipt_linked_formula_uses_allocated_received_units():
    result = build_billing_breakdown(
        shipped_units=14,
        allocated_received_units=10,
        base_step_units=10,
        base_step_price=Decimal("75.00"),
        extra_unit_price=Decimal("10.00"),
    )
    assert result.base_amount == Decimal("75.00")
    assert result.extra_amount == Decimal("40.00")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.billing.test_billing_calculations -v 2`
Expected: FAIL because the calculation helper does not exist.

**Step 3: Write minimal implementation**

- Add `ShipmentUnitEquivalenceRule` to the billing domain if not already added
- Create `wms/billing_calculations.py`
- Implement helpers for:
  - unit resolution from shipment content + hors format rules
  - breakdown calculation from `BillingComputationProfile`
  - document-level override application

```python
def compute_started_block_count(units: int, step_size: int) -> int:
    return 0 if units <= 0 else ((units - 1) // step_size) + 1
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.billing.test_billing_calculations -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/models_domain/billing.py wms/billing_calculations.py wms/tests/billing/test_billing_calculations.py
git commit -m "feat: add configurable billing calculation engine"
```

### Task 4: Add billing permissions and scan route skeleton

**Files:**
- Create: `wms/billing_permissions.py`
- Create: `wms/views_scan_billing.py`
- Modify: `wms/views_scan.py`
- Modify: `wms/views.py`
- Modify: `wms/scan_urls.py`
- Modify: `templates/scan/base.html`
- Create: `wms/tests/views/test_views_scan_billing.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing routing and permission tests**

Add tests for:
- `scan:scan_billing_settings`
- `scan:scan_billing_equivalence`
- `scan:scan_billing_editor`
- superuser access to settings/equivalence
- billing group access to editor only

```python
def test_scan_billing_settings_requires_superuser(self):
    response = self.client.get(reverse("scan:scan_billing_settings"))
    self.assertEqual(response.status_code, 403)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.test_views_scan_billing wms.tests.views.tests_scan_bootstrap_ui -v 2`
Expected: FAIL because the routes and nav entries do not exist.

**Step 3: Write minimal implementation**

- Add a group-aware decorator/helper in `wms/billing_permissions.py`
- Add placeholder views in `wms/views_scan_billing.py`
- Re-export them in `wms/views_scan.py` and `wms/views.py`
- Add scan URLs
- Add the top-level `Facturation` nav entry in `templates/scan/base.html`

```python
@scan_staff_required
def scan_billing_editor(request):
    require_billing_staff_or_superuser(request)
    return render(request, "scan/billing_editor.html", {"active": "billing"})
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.test_views_scan_billing wms.tests.views.tests_scan_bootstrap_ui -v 2`
Expected: PASS for route and nav assertions.

**Step 5: Commit**

```bash
git add wms/billing_permissions.py wms/views_scan_billing.py wms/views_scan.py wms/views.py wms/scan_urls.py templates/scan/base.html wms/tests/views/test_views_scan_billing.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add billing scan routes and permissions"
```

### Task 5: Build the `Parametres` page

**Files:**
- Create: `wms/forms_billing.py`
- Modify: `wms/views_scan_billing.py`
- Create: `templates/scan/billing_settings.html`
- Create: `wms/tests/forms/test_forms_billing.py`
- Modify: `wms/tests/views/test_views_scan_billing.py`

**Step 1: Write the failing settings tests**

Add tests for:
- creating/editing computation profiles
- creating/editing service catalog items
- creating/editing association price overrides
- page rendering the configured records

```python
def test_billing_settings_updates_computation_profile(self):
    response = self.client.post(
        reverse("scan:scan_billing_settings"),
        {"action": "save_profile", "label": "Receipt linked", "base_step_units": 10},
    )
    self.assertEqual(response.status_code, 302)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.forms.test_forms_billing wms.tests.views.test_views_scan_billing -v 2`
Expected: FAIL due to missing forms/page behavior.

**Step 3: Write minimal implementation**

- Add forms for computation profiles, services, and overrides
- Render them on `billing_settings.html`
- Implement POST handlers in `scan_billing_settings`

```python
class BillingComputationProfileForm(forms.ModelForm):
    class Meta:
        model = BillingComputationProfile
        fields = ("label", "base_unit_source", "base_step_units", "base_step_price", "extra_unit_mode", "extra_unit_price", "is_active")
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.forms.test_forms_billing wms.tests.views.test_views_scan_billing -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/forms_billing.py wms/views_scan_billing.py templates/scan/billing_settings.html wms/tests/forms/test_forms_billing.py wms/tests/views/test_views_scan_billing.py
git commit -m "feat: add billing settings page"
```

### Task 6: Build the `Equivalence` page

**Files:**
- Modify: `wms/forms_billing.py`
- Modify: `wms/views_scan_billing.py`
- Create: `templates/scan/billing_equivalence.html`
- Modify: `wms/tests/forms/test_forms_billing.py`
- Modify: `wms/tests/views/test_views_scan_billing.py`

**Step 1: Write the failing equivalence tests**

Add tests for:
- creating/editing category-depth equivalence rules
- creating/editing hors format rules
- ordering by specificity/priority in the page

```python
def test_billing_equivalence_page_lists_active_rules(self):
    response = self.client.get(reverse("scan:scan_billing_equivalence"))
    self.assertContains(response, "Hors format")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.forms.test_forms_billing wms.tests.views.test_views_scan_billing -v 2`
Expected: FAIL on missing equivalence form/page behavior.

**Step 3: Write minimal implementation**

- Add `ShipmentUnitEquivalenceRuleForm`
- Implement CRUD handling in `scan_billing_equivalence`
- Render active rules and edit/create forms

```python
class ShipmentUnitEquivalenceRuleForm(forms.ModelForm):
    class Meta:
        model = ShipmentUnitEquivalenceRule
        fields = ("label", "applies_to_kind", "category", "category_depth", "units_per_item", "priority", "is_active")
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.forms.test_forms_billing wms.tests.views.test_views_scan_billing -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/forms_billing.py wms/views_scan_billing.py templates/scan/billing_equivalence.html wms/tests/forms/test_forms_billing.py wms/tests/views/test_views_scan_billing.py
git commit -m "feat: add billing equivalence page"
```

### Task 7: Add receipt-to-shipment allocation workflow

**Files:**
- Modify: `wms/views_scan_receipts.py`
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/forms_billing.py`
- Modify: `templates/scan/receive_association.html`
- Modify: `templates/scan/shipment_create.html`
- Create: `wms/tests/billing/test_receipt_shipment_allocations.py`

**Step 1: Write the failing allocation tests**

Add tests for:
- linking one receipt to multiple shipments with allocated units
- linking multiple receipts to one shipment while enforcing same association
- showing allocation metadata in the shipment editor context

```python
def test_allocation_rejects_receipts_from_different_associations(self):
    with self.assertRaises(ValidationError):
        ReceiptShipmentAllocation.objects.create(
            receipt=receipt_b,
            shipment=shipment_a,
            allocated_received_units=10,
        )
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.billing.test_receipt_shipment_allocations -v 2`
Expected: FAIL because allocation validation/view support is missing.

**Step 3: Write minimal implementation**

- Add allocation validation in the model/service layer
- Add basic allocation forms/widgets where staff can attach receipts and allocated units
- Surface allocation summaries in receipt/shipment pages

```python
def clean(self):
    if self.shipment_id and self.receipt_id and self.shipment.shipper_contact_ref_id != self.receipt.source_contact_id:
        raise ValidationError("All linked receipts must belong to the shipment association.")
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.billing.test_receipt_shipment_allocations -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_scan_receipts.py wms/views_scan_shipments.py wms/forms_billing.py templates/scan/receive_association.html templates/scan/shipment_create.html wms/tests/billing/test_receipt_shipment_allocations.py
git commit -m "feat: add receipt shipment allocations"
```

### Task 8: Build the quote/invoice editor draft workflow

**Files:**
- Create: `wms/billing_document_handlers.py`
- Modify: `wms/views_scan_billing.py`
- Create: `templates/scan/billing_editor.html`
- Create: `wms/tests/billing/test_billing_document_handlers.py`
- Modify: `wms/tests/views/test_views_scan_billing.py`

**Step 1: Write the failing draft workflow tests**

Add tests for:
- drafting a quote from eligible shipments
- drafting an invoice from eligible shipments
- excluding shipments already invoiced
- choosing per-period eligible shipments based on shipment date

```python
def test_editor_excludes_shipments_already_invoiced(self):
    rows = build_editor_candidates(profile=self.profile, kind=BillingDocumentKind.INVOICE)
    self.assertNotIn(self.already_invoiced_shipment.id, [row.shipment_id for row in rows])
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.billing.test_billing_document_handlers wms.tests.views.test_views_scan_billing -v 2`
Expected: FAIL because draft building and candidate filtering do not exist.

**Step 3: Write minimal implementation**

- Build handlers for:
  - eligible shipment selection
  - quote/invoice draft creation
  - document line generation from computation profiles
  - manual line/discount injection
- Render the editor form and draft preview

```python
def build_editor_candidates(*, association_profile, kind, period=None):
    queryset = Shipment.objects.filter(shipper_contact_ref=association_profile.contact, status=ShipmentStatus.SHIPPED)
    if kind == BillingDocumentKind.INVOICE:
        queryset = queryset.exclude(billing_links__document__kind=BillingDocumentKind.INVOICE, billing_links__document__status=BillingDocumentStatus.ISSUED)
    return queryset.order_by("-created_at")
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.billing.test_billing_document_handlers wms.tests.views.test_views_scan_billing -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/billing_document_handlers.py wms/views_scan_billing.py templates/scan/billing_editor.html wms/tests/billing/test_billing_document_handlers.py wms/tests/views/test_views_scan_billing.py
git commit -m "feat: add billing document editor"
```

### Task 9: Add quote numbering, manual invoice numbering, and issue flow

**Files:**
- Modify: `wms/models_domain/billing.py`
- Modify: `wms/billing_document_handlers.py`
- Modify: `wms/views_scan_billing.py`
- Modify: `wms/tests/billing/test_models_billing.py`
- Modify: `wms/tests/billing/test_billing_document_handlers.py`

**Step 1: Write the failing numbering tests**

Add tests for:
- auto quote number generation (`DEV-2026-0001`)
- blocking invoice issue without a manual invoice number
- freezing document snapshots at issue time

```python
def test_quote_number_is_generated_on_save(self):
    document = BillingDocument.objects.create(kind=BillingDocumentKind.QUOTE)
    self.assertRegex(document.quote_number, r"^DEV-\d{4}-\d{4}$")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.billing.test_models_billing wms.tests.billing.test_billing_document_handlers -v 2`
Expected: FAIL on numbering/issue rules.

**Step 3: Write minimal implementation**

- Add annual quote sequence logic
- Add invoice-number validation before issue
- Snapshot billed identity, exchange-rate fields, and computed line totals on issue

```python
def can_issue_invoice(document):
    return bool((document.invoice_number or "").strip())
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.billing.test_models_billing wms.tests.billing.test_billing_document_handlers -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/models_domain/billing.py wms/billing_document_handlers.py wms/views_scan_billing.py wms/tests/billing/test_models_billing.py wms/tests/billing/test_billing_document_handlers.py
git commit -m "feat: add billing numbering and issue flow"
```

### Task 10: Integrate exchange-rate fetching and manual fallback

**Files:**
- Create: `wms/billing_exchange_rates.py`
- Modify: `wms/views_scan_billing.py`
- Modify: `wms/forms_billing.py`
- Create: `wms/tests/billing/test_billing_exchange_rates.py`

**Step 1: Write the failing exchange-rate tests**

Add tests for:
- ECB-backed currencies (`USD`, `CHF`, `CNY`) prefill successfully
- manual-only currencies (`VND`, `XOF`, `XAF`) skip remote fetch
- editor falls back to manual rate entry when fetch fails

```python
def test_manual_only_currency_returns_no_remote_rate():
    rate = resolve_exchange_rate(document_currency="XOF", base_currency="EUR")
    self.assertIsNone(rate.provider_name)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.billing.test_billing_exchange_rates -v 2`
Expected: FAIL because the exchange-rate helper does not exist.

**Step 3: Write minimal implementation**

- Add an ECB client wrapper with a pure function boundary for mocking
- Add supported currency logic
- Wire rate prefill into the billing editor form

```python
ECB_AUTO_CURRENCIES = {"USD", "CHF", "CNY"}
MANUAL_ONLY_CURRENCIES = {"VND", "XOF", "XAF"}
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.billing.test_billing_exchange_rates -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/billing_exchange_rates.py wms/views_scan_billing.py wms/forms_billing.py wms/tests/billing/test_billing_exchange_rates.py
git commit -m "feat: add billing exchange rate support"
```

### Task 11: Reuse the print-template pipeline for billing PDFs

**Files:**
- Modify: `wms/print_context.py`
- Modify: `wms/print_pack_mapping_catalog.py`
- Modify: `wms/views_print_templates.py`
- Modify: `wms/billing_document_handlers.py`
- Create: `wms/tests/billing/test_billing_print_context.py`

**Step 1: Write the failing print-context tests**

Add tests for:
- quote context
- invoice context
- credit-note context
- allowed source keys include billing document fields

```python
def test_build_preview_context_supports_billing_invoice(self):
    context = build_preview_context("billing_invoice", billing_document=self.document)
    self.assertEqual(context["billing"]["kind"], "invoice")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.billing.test_billing_print_context -v 2`
Expected: FAIL because billing print contexts are unsupported.

**Step 3: Write minimal implementation**

- Extend `build_preview_context` to accept billing documents
- Add allowed billing source keys
- Add billing doc type handling in the template editor preview flow
- Call the existing print-pack engine from billing issue/regenerate actions

```python
if doc_type in {"billing_quote", "billing_invoice", "billing_credit_note"}:
    return build_billing_document_context(billing_document, doc_type)
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.billing.test_billing_print_context -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/print_context.py wms/print_pack_mapping_catalog.py wms/views_print_templates.py wms/billing_document_handlers.py wms/tests/billing/test_billing_print_context.py
git commit -m "feat: add billing pdf rendering context"
```

### Task 12: Add portal billing list, detail, and correction requests

**Files:**
- Create: `wms/views_portal_billing.py`
- Modify: `wms/views_portal.py`
- Modify: `wms/views.py`
- Modify: `wms/portal_urls.py`
- Modify: `templates/portal/base.html`
- Create: `templates/portal/billing_list.html`
- Create: `templates/portal/billing_detail.html`
- Modify: `wms/views_portal_account.py`
- Modify: `templates/portal/account.html`
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Write the failing portal tests**

Add tests for:
- portal billing list route and nav link
- portal billing detail visibility only for issued documents
- correction request submission creating `BillingIssue`
- billing preference change request submission from the portal

```python
def test_portal_billing_detail_hides_draft_documents(self):
    response = self.client.get(reverse("portal:portal_billing_detail", args=[self.draft_document.id]))
    self.assertEqual(response.status_code, 404)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.views.tests_portal_bootstrap_ui -v 2`
Expected: FAIL because portal billing routes and templates do not exist.

**Step 3: Write minimal implementation**

- Add portal billing routes/views
- Add portal nav link
- Render list/detail templates
- Add correction request form and preference change request form

```python
@login_required(login_url="portal:portal_login")
@association_required
def portal_billing(request):
    documents = BillingDocument.objects.filter(association_profile=request.association_profile, visible_in_portal=True)
    return render(request, "portal/billing_list.html", {"documents": documents})
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.views.tests_portal_bootstrap_ui -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_portal_billing.py wms/views_portal.py wms/views.py wms/portal_urls.py templates/portal/base.html templates/portal/billing_list.html templates/portal/billing_detail.html wms/views_portal_account.py templates/portal/account.html wms/tests/views/tests_views_portal.py wms/tests/views/tests_portal_bootstrap_ui.py
git commit -m "feat: add portal billing consultation flows"
```

### Task 13: Add invoice payments, dispute states, and correction chain

**Files:**
- Modify: `wms/models_domain/billing.py`
- Modify: `wms/billing_document_handlers.py`
- Modify: `wms/views_scan_billing.py`
- Modify: `templates/scan/billing_editor.html`
- Create: `wms/tests/billing/test_billing_payments_and_corrections.py`

**Step 1: Write the failing payment/correction tests**

Add tests for:
- multiple payments updating invoice status
- portal dispute moving document into review state
- creating a credit note linked to an issued invoice
- replacement invoice preserving the original audit trail

```python
def test_invoice_becomes_partially_paid_after_first_payment(self):
    add_payment(self.invoice, amount=Decimal("20.00"), payment_method="wire")
    self.invoice.refresh_from_db()
    self.assertEqual(self.invoice.status, BillingDocumentStatus.PARTIALLY_PAID)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.billing.test_billing_payments_and_corrections -v 2`
Expected: FAIL because payment and correction flows are incomplete.

**Step 3: Write minimal implementation**

- Add payment recording helpers and balance recomputation
- Add dispute/review status helpers
- Add credit-note creation flow and replacement invoice linkage

```python
def recompute_invoice_status(document):
    paid = sum(payment.amount for payment in document.payments.all())
    if paid <= 0:
        return BillingDocumentStatus.ISSUED
    if paid < document.total_amount:
        return BillingDocumentStatus.PARTIALLY_PAID
    return BillingDocumentStatus.PAID
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.billing.test_billing_payments_and_corrections -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/models_domain/billing.py wms/billing_document_handlers.py wms/views_scan_billing.py templates/scan/billing_editor.html wms/tests/billing/test_billing_payments_and_corrections.py
git commit -m "feat: add billing payments and correction chain"
```

### Task 14: Register billing models in Django admin

**Files:**
- Create: `wms/admin_billing.py`
- Modify: `wms/admin.py`
- Create: `wms/tests/admin/test_admin_billing.py`

**Step 1: Write the failing admin tests**

Add tests for:
- billing models visible in admin for superusers
- useful list displays/search fields for documents, payments, allocations, profiles

```python
def test_billing_document_admin_changelist_loads(self):
    response = self.client.get(reverse("admin:wms_billingdocument_changelist"))
    self.assertEqual(response.status_code, 200)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.admin.test_admin_billing -v 2`
Expected: FAIL because billing admin registrations do not exist.

**Step 3: Write minimal implementation**

- Add `wms/admin_billing.py`
- Import it for side effects from `wms/admin.py`
- Register models with practical list displays and filters

```python
@admin.register(models.BillingDocument)
class BillingDocumentAdmin(admin.ModelAdmin):
    list_display = ("kind", "status", "association_profile", "quote_number", "invoice_number", "issued_at")
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.admin.test_admin_billing -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/admin_billing.py wms/admin.py wms/tests/admin/test_admin_billing.py
git commit -m "feat: add billing admin registrations"
```

### Task 15: Run focused regression suites and manual QA

**Files:**
- Modify tests only if regressions surface.

**Step 1: Run focused billing suites**

Run: `./.venv/bin/python manage.py test wms.tests.billing wms.tests.views.test_views_scan_billing -v 2`
Expected: PASS.

**Step 2: Run portal and receipt regressions**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_scan_receipts -v 2`
Expected: PASS.

**Step 3: Run scan navigation and print-template regressions**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_print_templates -v 2`
Expected: PASS.

**Step 4: Manual QA checklist**

- Scan nav shows `Facturation`.
- `Parametres` and `Equivalence` are superuser-only.
- Billing staff can access `Edition Devis/Facture`.
- Receipt pickup billing fields persist and display.
- Allocation rules reject cross-association receipt mixes.
- Quote numbering auto-generates.
- Invoice issue blocks until a manual invoice number is provided.
- Period filtering uses shipment date, not creation date.
- Issued documents appear in the portal, drafts do not.
- Portal correction requests create review items.
- PDF generation works from the billing editor using the XLSX template pipeline.
- Invoice payments update the balance/status.

**Step 5: Final commit(s) and review request**

```bash
git status --short
git add <scoped files>
git commit -m "feat: deliver legacy billing module"
```
