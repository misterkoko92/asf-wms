# Order Multi-Shipment Preparation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make scan order-to-shipment preparation idempotent, support explicit multi-shipment preparation, and expose picking/document actions on shipment dossiers.

**Architecture:** Keep behavior in the legacy Django scan stack. Add focused domain helpers in `wms/domain/orders.py` for estimation and preparation, route scan form actions through `wms/order_view_handlers.py`, and keep templates thin. Reuse existing carton assignment and print routes instead of creating parallel workflows.

**Tech Stack:** Django views/templates/forms, `unittest` Django tests, existing `OrderShipmentLink`, `Shipment`, `Carton`, and print bundle routes.

---

### Task 1: Packing Defaults For Order Preparation

**Files:**
- Modify: `wms/domain/orders.py`
- Test: `wms/tests/domain/tests_domain_orders_extra.py`

**Steps:**
1. Add a failing test proving `prepare_order()` succeeds when a product has missing weight and volume.
2. Assert the test records or exposes warning messages without mutating the product dimensions.
3. Run the focused domain order test and verify it fails on the old blocking error.
4. Pass `apply_defaults=True` to `build_packing_bins()` during order preparation.
5. Surface packing warnings to scan handlers.
6. Run the focused test again.

### Task 2: Idempotent Scan Order Buttons

**Files:**
- Modify: `wms/order_view_handlers.py`
- Modify: `wms/order_view_helpers.py`
- Test: `wms/tests/orders/tests_order_view.py`

**Steps:**
1. Add tests proving `create_shipment` opens an existing linked shipment.
2. Add tests proving `create_shipment_and_cartons` completes an existing linked shipment instead of creating a new one.
3. Run focused order view tests and verify failures.
4. Replace `force_new=True` in quick scan actions with existing-shipment reuse.
5. Adjust button labels/state when one or more linked shipments already exist.
6. Re-run focused order view tests.

### Task 3: Explicit Multi-Shipment Preparation

**Files:**
- Modify: `wms/domain/orders.py`
- Modify: `wms/order_view_handlers.py`
- Modify: `wms/order_view_helpers.py`
- Modify: `templates/scan/order_detail.html`
- Test: `wms/tests/domain/tests_domain_orders_extra.py`
- Test: `wms/tests/orders/tests_order_view.py`

**Steps:**
1. Add domain tests for `ceil(carton_count / 10)` recommendation.
2. Add domain tests for creating N linked shipments and distributing generated cartons by batches of 10.
3. Add view tests for the confirmation step and explicit `shipment_count`.
4. Run focused tests and verify failures.
5. Implement estimation helper and multi-shipment preparation helper.
6. Add confirmation UI in the order detail action area.
7. Re-run focused tests.

### Task 4: Shipment Dossier Actions

**Files:**
- Modify: `wms/shipment_view_helpers.py`
- Modify: `templates/scan/includes/shipment_dossier_header.html`
- Test: `wms/tests/shipment/tests_shipment_view_helpers.py`
- Test: `wms/tests/views/tests_views.py`

**Steps:**
1. Add tests for `Picking Général` under paper actions and `Picking` under per-carton actions.
2. Add tests for a top-level "Créer tous les colis" action on eligible order-linked shipment dossiers.
3. Run focused tests and verify failures.
4. Add action URLs using existing print and pack/preparation routes.
5. Re-run focused tests.

### Task 5: Documentation, Changelog, And Verification

**Files:**
- Modify: `wms/faq_changelog.py`
- Review: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Review: `docs/repo-reference/03c-impact-shipments.md`
- Review: `docs/repo-reference/04-shared-contracts/05-shipments-tracking.md`

**Steps:**
1. Add a FAQ changelog entry for the user-visible scan workflow change.
2. Update repo-reference docs only if the shared contract changes beyond documented document-first and multi-link behavior.
3. Run focused test suite:
   `./.venv/bin/python manage.py test wms.tests.domain.tests_domain_orders_extra wms.tests.orders.tests_order_view wms.tests.shipment.tests_shipment_view_helpers -v 2`
4. Run nearby view/print tests if route or document action behavior changed.
5. Report test results and documentation impact.
