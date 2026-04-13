# Portal Shipper Inbound Multi-Shipment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add shipper-prepared inbound cartons, pickup/drop-off capture, order-level compliance documents, and manual multi-shipment allocation within the legacy portal and scan flows.

**Architecture:** Introduce a dedicated inbound-delivery aggregate under `Order`, a reusable pickup-address book keyed by the shipper organization, and an explicit `OrderShipmentLink` so one order can back many shipments. Keep order documents as the source of truth, create first-class `Carton` rows at receipt time for shipper-received cartons, and enforce the new blocking rules only at the shipment-ready transition.

**Tech Stack:** Django legacy portal/scan views, extracted domain models under `wms/models_domain/*`, legacy Bootstrap templates, Django `TestCase`, existing shipment/receipt/billing handlers

---

### Task 1: Lock the approved business contract with failing tests

**Files:**
- Create: `wms/tests/portal/tests_portal_order_inbound_flow.py`
- Create: `wms/tests/orders/tests_order_shipment_links.py`
- Create: `wms/tests/receipt/tests_receipt_shipper_cartons.py`
- Create: `wms/tests/shipment/tests_shipper_inbound_ready_gate.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_scan_orders.py`
- Modify: `wms/tests/views/tests_views_scan_receipts.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Add focused coverage for:

- portal order submission accepts shipper-carton declarations with no documents
- pickup mode requires the full pickup block except the optional desired pickup date
- access constraints pass either through `pickup_has_no_access_constraints=True` or a non-empty
  details field
- one order can link to more than one shipment
- a receipt linked to the inbound delivery creates one carton per declared carton
- shipper-received cartons stay unassigned until a shipment edit explicitly selects them
- `confirm_shipment_ready(...)` blocks shipments with shipper cartons when receipt or required docs
  are missing
- ASF-only shipments from the same order are not blocked by missing shipper-carton packing lists

Example snippets:

```python
def test_portal_order_submit_allows_shipper_inbound_without_documents(self):
    response = self.client.post(
        reverse("portal:portal_order_create"),
        {
            "recipient_id": str(self.recipient.id),
            "destination_id": str(self.destination.id),
            "has_shipper_inbound": "1",
            "arrival_mode": "dropoff_warehouse",
            "declared_carton_count": "4",
            "declared_out_of_format_count": "1",
        },
    )
    self.assertRedirects(response, reverse("portal:portal_order_detail", args=[1]))
```

```python
def test_confirm_shipment_ready_blocks_shipper_carton_shipment_without_receipt(self):
    with self.assertRaisesMessage(ValueError, "Réception association requise"):
        confirm_shipment_ready(shipment=self.shipment, user=self.user)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.portal.tests_portal_order_inbound_flow \
  wms.tests.orders.tests_order_shipment_links \
  wms.tests.receipt.tests_receipt_shipper_cartons \
  wms.tests.shipment.tests_shipper_inbound_ready_gate \
  wms.tests.views.tests_portal_bootstrap_ui \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_views_scan_orders \
  wms.tests.views.tests_views_scan_receipts \
  wms.tests.views.tests_views_scan_shipments -v 2
```

Expected: FAIL because the inbound models, pickup validation, multi-shipment links, receipt carton
materialization, and shipment-ready rules do not exist yet.

**Step 3: Write minimal implementation**

No production code in this task.

**Step 4: Run test to verify it still fails for the expected reasons**

Re-run the same command and confirm the failures are limited to the missing inbound workflow.

**Step 5: Commit**

```bash
git add wms/tests/portal/tests_portal_order_inbound_flow.py wms/tests/orders/tests_order_shipment_links.py wms/tests/receipt/tests_receipt_shipper_cartons.py wms/tests/shipment/tests_shipper_inbound_ready_gate.py wms/tests/views/tests_portal_bootstrap_ui.py wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_orders.py wms/tests/views/tests_views_scan_receipts.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "test: lock shipper inbound multi-shipment workflow"
```

### Task 2: Add the inbound-delivery, pickup-address, and order-shipment-link models

**Files:**
- Modify: `wms/models_domain/portal.py`
- Modify: `wms/models.py`
- Create: `wms/migrations/0119_order_inbound_delivery_and_links.py`
- Verify: `wms/admin.py`
- Verify: `wms/admin_misc.py`

**Step 1: Write the failing test**

Extend Task 1 model assertions to cover:

- one `OrderInboundDelivery` per order
- many `OrderShipmentLink` rows per order
- reusable pickup addresses belonging to the shipper organization
- order-level document type values include both packing-list variants

Example:

```python
def test_order_can_link_many_shipments(self):
    OrderShipmentLink.objects.create(order=self.order, shipment=self.shipment_a)
    OrderShipmentLink.objects.create(order=self.order, shipment=self.shipment_b)
    self.assertEqual(self.order.shipment_links.count(), 2)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.orders.tests_order_shipment_links \
  wms.tests.portal.tests_portal_order_inbound_flow -v 2
```

Expected: FAIL because the new models and enum values do not exist.

**Step 3: Write minimal implementation**

In `wms/models_domain/portal.py`, add:

- `OrderInboundArrivalMode`
- `AssociationPickupAddress`
- `OrderInboundDelivery`
- `OrderShipmentLink`
- new `OrderDocumentType` members:
  - `PACKING_LIST_GLOBAL`
  - `PACKING_LIST_BY_CARTON`

Recommended shape:

```python
class OrderShipmentLink(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="shipment_links")
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="order_links")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
```

Keep `Order.shipment` in place for compatibility. Add the new models to the `wms/models.py` facade.

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.orders.tests_order_shipment_links \
  wms.tests.portal.tests_portal_order_inbound_flow -v 2
```

Expected: PASS on persistence and enum coverage, while view-level tests still fail.

**Step 5: Commit**

```bash
git add wms/models_domain/portal.py wms/models.py wms/migrations/0119_order_inbound_delivery_and_links.py
git commit -m "feat: add order inbound delivery and shipment link models"
```

### Task 3: Add shipper compliance and carton provenance fields

**Files:**
- Modify: `contacts/models.py`
- Create: `contacts/migrations/0012_contact_humanitarian_attestation_exempt.py`
- Modify: `wms/models_domain/shipment.py`
- Modify: `wms/models.py`
- Create: `wms/migrations/0120_carton_receipt_provenance.py`
- Modify: `wms/tests/portal/tests_portal_shipment_parties.py`
- Modify: `wms/tests/shipment/tests_carton_status_events.py`

**Step 1: Write the failing test**

Add assertions for:

- shipper organization can be marked as humanitarian-attestation exempt
- a carton can record `source_kind="shipper_received"` and `source_receipt`
- existing warehouse-prepared cartons still default to the legacy behavior

Example:

```python
def test_shipper_received_carton_keeps_receipt_provenance(self):
    carton = Carton.objects.create(
        code="C-1",
        status=CartonStatus.PACKED,
        source_kind=CartonSourceKind.SHIPPER_RECEIVED,
        source_receipt=self.receipt,
    )
    self.assertEqual(carton.source_receipt_id, self.receipt.id)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.receipt.tests_receipt_shipper_cartons \
  wms.tests.shipment.tests_carton_status_events \
  wms.tests.portal.tests_portal_shipment_parties -v 2
```

Expected: FAIL because the new contact and carton fields do not exist.

**Step 3: Write minimal implementation**

In `contacts/models.py`, add:

```python
is_humanitarian_attestation_exempt = models.BooleanField(default=False)
```

In `wms/models_domain/shipment.py`, add:

```python
class CartonSourceKind(models.TextChoices):
    WAREHOUSE_PREPARED = "warehouse_prepared", "Préparation ASF"
    SHIPPER_RECEIVED = "shipper_received", "Réception expéditeur"
```

and extend `Carton` with `source_kind` and `source_receipt`.

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.receipt.tests_receipt_shipper_cartons \
  wms.tests.shipment.tests_carton_status_events \
  wms.tests.portal.tests_portal_shipment_parties -v 2
```

Expected: PASS on the new persistence layer.

**Step 5: Commit**

```bash
git add contacts/models.py contacts/migrations/0012_contact_humanitarian_attestation_exempt.py wms/models_domain/shipment.py wms/models.py wms/migrations/0120_carton_receipt_provenance.py wms/tests/portal/tests_portal_shipment_parties.py wms/tests/shipment/tests_carton_status_events.py
git commit -m "feat: add shipper compliance and carton provenance fields"
```

### Task 4: Refactor order-to-shipment services and singular-order aggregators

**Files:**
- Modify: `wms/domain/orders.py`
- Modify: `wms/services.py`
- Modify: `wms/order_helpers.py`
- Modify: `wms/order_view_helpers.py`
- Modify: `wms/order_view_handlers.py`
- Modify: `wms/order_scan_state.py`
- Modify: `wms/application/portal/dashboard_queries.py`
- Modify: `wms/portal_dashboard_helpers.py`
- Modify: `wms/status_presenters.py`
- Modify: `wms/tests/domain/tests_domain_orders_extra.py`
- Modify: `wms/tests/views/tests_views_portal.py`

**Step 1: Write the failing test**

Add service and presenter coverage for:

- creating a shipment for an order now appends an `OrderShipmentLink`
- `Order.shipment` is no longer the source of truth for dashboards and row builders
- portal dashboard KPIs aggregate linked shipments instead of a single pointer
- the scan order list allows `Créer l'expédition` while still showing existing linked shipments

Example:

```python
def test_create_shipment_for_order_adds_a_new_link(self):
    shipment_a = create_shipment_for_order(order=self.order)
    shipment_b = create_shipment_for_order(order=self.order, force_new=True)
    self.assertNotEqual(shipment_a.id, shipment_b.id)
    self.assertEqual(self.order.shipment_links.count(), 2)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.domain.tests_domain_orders_extra \
  wms.tests.orders.tests_order_shipment_links \
  wms.tests.views.tests_views_portal \
  wms.tests.views.tests_views_scan_orders -v 2
```

Expected: FAIL because the order service and presenter helpers still assume a single shipment.

**Step 3: Write minimal implementation**

In `wms/domain/orders.py`:

- keep `create_shipment_for_order(order=...)` for compatibility
- add a `force_new` path that creates a fresh shipment and `OrderShipmentLink`
- ensure the first created shipment can continue to populate `Order.shipment` as a compatibility
  pointer

In helpers/presenters:

- add helper(s) such as `order_linked_shipments(order)` and `order_primary_shipment(order)`
- update dashboard and next-step logic to aggregate linked shipments, not the one-to-one field

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.domain.tests_domain_orders_extra \
  wms.tests.orders.tests_order_shipment_links \
  wms.tests.views.tests_views_portal \
  wms.tests.views.tests_views_scan_orders -v 2
```

Expected: PASS with multi-shipment linkage established and old singular assumptions reduced to
compatibility only.

**Step 5: Commit**

```bash
git add wms/domain/orders.py wms/services.py wms/order_helpers.py wms/order_view_helpers.py wms/order_view_handlers.py wms/order_scan_state.py wms/application/portal/dashboard_queries.py wms/portal_dashboard_helpers.py wms/status_presenters.py wms/tests/domain/tests_domain_orders_extra.py wms/tests/views/tests_views_portal.py
git commit -m "feat: refactor order shipment linkage for multi-shipment flow"
```

### Task 5: Implement portal inbound declaration, pickup validation, and saved pickup addresses

**Files:**
- Modify: `wms/views_portal_orders.py`
- Modify: `wms/portal_order_handlers.py`
- Modify: `templates/portal/order_create.html`
- Create: `templates/portal/includes/order_create_shipper_inbound_card.html`
- Create: `templates/portal/includes/order_create_pickup_card.html`
- Create: `templates/portal/includes/order_create_pickup_saved_addresses_card.html`
- Modify: `wms/tests/portal/tests_portal_order_handlers.py`
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Write the failing test**

Add portal coverage for:

- submit shipper-carton-only order
- submit mixed shipper-carton + ASF-stock order
- pickup form enforces all required fields except desired pickup date
- at least one phone is required
- saved pickup address can prefill the form and snapshots into the order inbound delivery

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.portal.tests_portal_order_handlers \
  wms.tests.portal.tests_portal_order_inbound_flow \
  wms.tests.views.tests_views_portal \
  wms.tests.views.tests_portal_bootstrap_ui -v 2
```

Expected: FAIL because the portal still only parses stock lines and internal ready cartons.

**Step 3: Write minimal implementation**

In `wms/views_portal_orders.py`:

- parse `has_shipper_inbound`, `arrival_mode`, and the pickup block
- validate the access-constraints rule:

```python
if not has_no_access_constraints and not access_constraints_details.strip():
    errors["pickup_access_constraints_details"] = "Renseignez une contrainte ou cochez Aucune contrainte d'accès."
```

- keep order submission non-blocking for documents

In `wms/portal_order_handlers.py`:

- stop auto-creating a shipment during portal order creation
- create the order, optional inbound delivery snapshot, and ASF stock lines only

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.portal.tests_portal_order_handlers \
  wms.tests.portal.tests_portal_order_inbound_flow \
  wms.tests.views.tests_views_portal \
  wms.tests.views.tests_portal_bootstrap_ui -v 2
```

Expected: PASS with the portal creating declared inbound deliveries and pickup snapshots correctly.

**Step 5: Commit**

```bash
git add wms/views_portal_orders.py wms/portal_order_handlers.py templates/portal/order_create.html templates/portal/includes/order_create_shipper_inbound_card.html templates/portal/includes/order_create_pickup_card.html templates/portal/includes/order_create_pickup_saved_addresses_card.html wms/tests/portal/tests_portal_order_handlers.py wms/tests/views/tests_views_portal.py wms/tests/views/tests_portal_bootstrap_ui.py
git commit -m "feat: add portal shipper inbound declaration flow"
```

### Task 6: Unlock order document upload earlier and expose inbound/order summaries on the portal dossier

**Files:**
- Modify: `wms/views_portal_orders.py`
- Modify: `wms/order_helpers.py`
- Modify: `templates/portal/order_detail.html`
- Create: `templates/portal/includes/order_detail_inbound_delivery_card.html`
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Write the failing test**

Add detail-page coverage for:

- upload allowed before approval
- both packing-list document types are available
- inbound summary shows arrival mode, pickup/drop-off details, and receipt state
- order detail lists multiple linked shipments instead of one implicit shipment field

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_portal \
  wms.tests.views.tests_portal_bootstrap_ui -v 2
```

Expected: FAIL because the order detail page still blocks upload before approval and only renders a
single shipment status line.

**Step 3: Write minimal implementation**

In `wms/views_portal_orders.py`:

- remove the `APPROVED` upload gate
- extend `_build_order_detail_context(...)` with:
  - inbound delivery summary
  - linked shipments summary
  - required/missing document summary

Keep `attach_order_documents_to_shipment(...)` limited to the attestation types if shipment-local
print flows still need them.

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_portal \
  wms.tests.views.tests_portal_bootstrap_ui -v 2
```

Expected: PASS with order-level document upload available immediately and inbound summaries visible.

**Step 5: Commit**

```bash
git add wms/views_portal_orders.py wms/order_helpers.py templates/portal/order_detail.html templates/portal/includes/order_detail_inbound_delivery_card.html wms/tests/views/tests_views_portal.py wms/tests/views/tests_portal_bootstrap_ui.py
git commit -m "feat: expose inbound delivery and early documents on portal orders"
```

### Task 7: Link receipts to inbound deliveries and materialize shipper cartons at reception

**Files:**
- Modify: `wms/forms.py`
- Modify: `wms/receipt_handlers.py`
- Modify: `wms/views_scan_receipts.py`
- Modify: `templates/scan/receive_association.html`
- Modify: `templates/scan/includes/receive_association_create_card.html`
- Modify: `wms/tests/receipt/tests_receipt_handlers.py`
- Modify: `wms/tests/receipt/tests_receipt_shipper_cartons.py`
- Modify: `wms/tests/views/tests_views_scan_receipts.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add receipt coverage for:

- scan receipt form can target an inbound delivery
- saving the receipt links it back to the inbound delivery
- saving the receipt creates the expected count of `Carton` rows with `source_kind=shipper_received`
- the created cartons are `PACKED`, unassigned, and selectable later

Example:

```python
self.assertEqual(
    Carton.objects.filter(source_receipt=receipt, source_kind=CartonSourceKind.SHIPPER_RECEIVED).count(),
    4,
)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.receipt.tests_receipt_handlers \
  wms.tests.receipt.tests_receipt_shipper_cartons \
  wms.tests.views.tests_views_scan_receipts \
  wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected: FAIL because receipt creation does not yet know about order inbound deliveries or carton
materialization.

**Step 3: Write minimal implementation**

In `wms/forms.py`, add an optional `order_inbound_delivery` selector to `ScanReceiptAssociationForm`.

In `wms/receipt_handlers.py`:

- resolve the inbound delivery from the form
- after saving the receipt, assign it back to the inbound delivery
- create one carton per declared carton using the existing carton-code generator

Minimal helper shape:

```python
def _create_shipper_received_cartons(*, receipt, inbound_delivery, user):
    for _index in range(inbound_delivery.declared_carton_count):
        Carton.objects.create(
            code=generate_carton_code(),
            status=CartonStatus.PACKED,
            source_kind=CartonSourceKind.SHIPPER_RECEIVED,
            source_receipt=receipt,
            prepared_by=user,
        )
```

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.receipt.tests_receipt_handlers \
  wms.tests.receipt.tests_receipt_shipper_cartons \
  wms.tests.views.tests_views_scan_receipts \
  wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected: PASS with inbound receipts producing real selectable cartons.

**Step 5: Commit**

```bash
git add wms/forms.py wms/receipt_handlers.py wms/views_scan_receipts.py templates/scan/receive_association.html templates/scan/includes/receive_association_create_card.html wms/tests/receipt/tests_receipt_handlers.py wms/tests/receipt/tests_receipt_shipper_cartons.py wms/tests/views/tests_views_scan_receipts.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: create shipper cartons from inbound receipts"
```

### Task 8: Update scan order pages for inbound visibility and repeatable shipment creation

**Files:**
- Modify: `wms/views_scan_orders.py`
- Modify: `wms/order_view_helpers.py`
- Modify: `wms/order_view_handlers.py`
- Modify: `templates/scan/orders_view.html`
- Modify: `templates/scan/order.html`
- Modify: `wms/tests/views/tests_views_scan_orders.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add scan-order coverage for:

- orders view shows inbound-delivery state and linked shipment count
- approved orders can create another shipment even when one already exists
- scan order detail shows unassigned shipper-received carton count and receipt state

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_orders \
  wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected: FAIL because the scan order pages still assume one shipment and no inbound-delivery state.

**Step 3: Write minimal implementation**

In `wms/order_view_handlers.py`:

- let `action == "create_shipment"` create a fresh shipment link instead of refusing once one
  shipment exists
- attach order attestations to each new shipment if required by the existing document exports

In `wms/order_view_helpers.py` and templates:

- replace singular shipment wording with:
  - shipment count
  - latest/primary shipment badge
  - inbound/receipt summary

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_orders \
  wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected: PASS with scan order pages supporting repeatable shipment creation.

**Step 5: Commit**

```bash
git add wms/views_scan_orders.py wms/order_view_helpers.py wms/order_view_handlers.py templates/scan/orders_view.html templates/scan/order.html wms/tests/views/tests_views_scan_orders.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: adapt scan order pages to multi-shipment inbound flow"
```

### Task 9: Add manual shipper-carton selection to the shipment dossier

**Files:**
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/views_scan_shipments_support.py`
- Modify: `wms/scan_shipment_handlers.py`
- Modify: `wms/shipment_form_helpers.py`
- Modify: `wms/shipment_view_helpers.py`
- Modify: `templates/scan/shipment_dossier.html`
- Create: `templates/scan/includes/shipment_dossier_order_inbound_panel.html`
- Modify: `wms/tests/scan/tests_scan_shipment_handlers.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add shipment-edit coverage for:

- available carton list includes shipper-received cartons with origin metadata
- operator can mix shipper-received cartons and ASF cartons in the same shipment
- a shipper-received carton already assigned to another shipment is rejected
- dossier shows the parent order documents and receipt summary

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.scan.tests_scan_shipment_handlers \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected: FAIL because shipment edit does not yet expose or label shipper-received cartons.

**Step 3: Write minimal implementation**

In `wms/shipment_form_helpers.py` and `wms/shipment_view_helpers.py`, include provenance in carton
options:

```python
{
    "id": carton.id,
    "code": carton.code,
    "origin_label": "Réception expéditeur" if carton.source_kind == CartonSourceKind.SHIPPER_RECEIVED else "Préparation ASF",
}
```

In `wms/scan_shipment_handlers.py`, keep using `Carton.shipment` as the single assignment field and
reject cartons already linked elsewhere.

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.scan.tests_scan_shipment_handlers \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected: PASS with manual selection and mixed-shipment composition working.

**Step 5: Commit**

```bash
git add wms/views_scan_shipments.py wms/views_scan_shipments_support.py wms/scan_shipment_handlers.py wms/shipment_form_helpers.py wms/shipment_view_helpers.py templates/scan/shipment_dossier.html templates/scan/includes/shipment_dossier_order_inbound_panel.html wms/tests/scan/tests_scan_shipment_handlers.py wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add shipper carton selection to shipment dossier"
```

### Task 10: Enforce the shipment-ready gate for order documents and inbound receipts

**Files:**
- Modify: `wms/shipment_status.py`
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/order_helpers.py`
- Modify: `wms/tests/shipment/tests_shipment_status.py`
- Modify: `wms/tests/shipment/tests_shipper_inbound_ready_gate.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Add readiness coverage for:

- all linked shipments require order-level donation attestation
- humanitarian attestation is skipped when the shipper organization is exempt
- only shipments with shipper-received cartons require receipt + both packing lists
- non-conform receipt blocks `PICKING -> PACKED`

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.shipment.tests_shipment_status \
  wms.tests.shipment.tests_shipper_inbound_ready_gate \
  wms.tests.views.tests_views_scan_shipments -v 2
```

Expected: FAIL because the ready gate only checks current shipment-local carton state.

**Step 3: Write minimal implementation**

Add a shipment gate helper in `wms/shipment_status.py`, for example:

```python
def _validate_order_requirements_for_shipment(*, shipment):
    order = shipment.order_links.select_related("order__association_contact").first().order
    ...
```

Use it inside `confirm_shipment_ready(...)` before mutating the shipment status. Surface clear
messages through `wms/views_scan_shipments.py`.

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.shipment.tests_shipment_status \
  wms.tests.shipment.tests_shipper_inbound_ready_gate \
  wms.tests.views.tests_views_scan_shipments -v 2
```

Expected: PASS with the correct blocking semantics before planning.

**Step 5: Commit**

```bash
git add wms/shipment_status.py wms/views_scan_shipments.py wms/order_helpers.py wms/tests/shipment/tests_shipment_status.py wms/tests/shipment/tests_shipper_inbound_ready_gate.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: gate shipment readiness on inbound receipt and order documents"
```

### Task 11: Inject pickup charges into billing drafts

**Files:**
- Modify: `wms/billing_document_handlers.py`
- Modify: `wms/views_scan_billing.py`
- Modify: `wms/tests/billing/test_billing_document_handlers.py`
- Modify: `wms/tests/views/test_views_scan_billing.py`

**Step 1: Write the failing test**

Add billing coverage for:

- a shipped shipment allocated to a pickup receipt adds one automatic transport line to the draft
- drop-off receipts do not add that line
- the pickup line is only created once even when a receipt is linked through multiple allocations

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.billing.test_billing_document_handlers \
  wms.tests.views.test_views_scan_billing -v 2
```

Expected: FAIL because billing drafts currently ignore `pickup_charge_amount`.

**Step 3: Write minimal implementation**

In `wms/billing_document_handlers.py`:

- collect pickup-charged receipt ids from the selected shipments
- add one auto-generated `BillingDocumentLine` per qualifying receipt after the shipment lines

Suggested label:

```python
label=f"Enlèvement {receipt.reference}"
```

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.billing.test_billing_document_handlers \
  wms.tests.views.test_views_scan_billing -v 2
```

Expected: PASS with pickup transport automatically entering the draft.

**Step 5: Commit**

```bash
git add wms/billing_document_handlers.py wms/views_scan_billing.py wms/tests/billing/test_billing_document_handlers.py wms/tests/views/test_views_scan_billing.py
git commit -m "feat: bill pickup charges from inbound receipts"
```

### Task 12: Update repo-reference docs and run the bounded regression suite

**Files:**
- Modify: `docs/repo-reference/03-impact-map.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Modify: `docs/operations.md`
- Verify: `docs/release_checklist.md`

**Step 1: Write the failing test**

No automated failing test for the docs themselves. Instead, write down the contracts that changed:

- portal order create/detail now support shipper inbound and early documents
- scan orders and shipment dossier are multi-shipment aware
- `Réception association` can materialize shipper cartons
- shipment-ready gate depends on order-level docs and inbound receipt state

**Step 2: Run test to verify the code suite is green before updating docs**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.portal.tests_portal_order_inbound_flow \
  wms.tests.orders.tests_order_shipment_links \
  wms.tests.receipt.tests_receipt_shipper_cartons \
  wms.tests.shipment.tests_shipper_inbound_ready_gate \
  wms.tests.views.tests_views_portal \
  wms.tests.views.tests_portal_bootstrap_ui \
  wms.tests.views.tests_views_scan_orders \
  wms.tests.views.tests_views_scan_receipts \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.billing.test_billing_document_handlers \
  wms.tests.views.test_views_scan_billing -v 2
```

Expected: PASS before the docs are finalized.

**Step 3: Write minimal implementation**

Update `docs/repo-reference/04-shared-contracts.md` with a new section describing:

- `OrderInboundDelivery`
- `OrderShipmentLink`
- shipper-received carton provenance
- the shipment-ready gate semantics

Update `docs/repo-reference/03-impact-map.md` so future changes to portal orders, receipts, and
shipment dossiers explicitly re-check this flow.

Refresh `docs/operations.md` with the operational sequence for:

- pickup request
- warehouse receipt
- carton allocation to shipments
- planning readiness

**Step 4: Run test to verify the suite still passes**

Re-run the same bounded regression suite and confirm the docs changed with no code regression.

**Step 5: Commit**

```bash
git add docs/repo-reference/03-impact-map.md docs/repo-reference/04-shared-contracts.md docs/operations.md
git commit -m "docs: record shipper inbound multi-shipment contracts"
```
