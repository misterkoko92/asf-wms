# Recipient Preference Table Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align the three canonical recipient preference edit tables and add a shared `Qté par colis (estimation)` column computed from the existing carton-capacity logic.

**Architecture:** Add one shared helper for per-carton unit capacity, expose it on the shared row payload used by portal and scan/admin recipient preference tables, then update the three templates and living tests to keep the contract aligned.

**Tech Stack:** Django views, Django templates, Django TestCase, shared helper functions in `wms/order_helpers.py`

---

### Task 1: Lock the new UI contract in tests

**Files:**
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/views/tests_views_scan_admin_shipment_parties.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Write the failing tests**

- Add a portal view test asserting `recipient_product_rows` expose a per-row carton estimate.
- Add a portal view test asserting the recipient-scoped preferences page renders the new estimate column and `--` fallback when unknown.
- Add a scan/admin view test asserting the admin recipient detail page renders the same estimate column.
- Add Bootstrap/UI assertions for the new column header and the width classes or inline width markers used to rebalance the table.

**Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAccountViewsTests wms.tests.views.tests_views_scan_admin_shipment_parties.ScanAdminShipmentPartiesViewTests wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests -v 2
```

Expected:

- failures because the shared row payload does not yet expose the estimate and the templates do not render the new column

### Task 2: Implement shared carton-capacity estimation

**Files:**
- Modify: `wms/order_helpers.py`
- Modify: `wms/views_portal_account.py`
- Modify: `wms/views_scan_admin.py`

**Step 1: Write minimal implementation**

- Extract a helper that returns the maximum units of one product per carton format, based on the current weight/volume rules.
- Reuse that helper from `estimate_cartons_for_line` to avoid double-maintaining the rule.
- Fetch the default carton format in the recipient preference context builders.
- Attach `units_per_carton_estimate` to each row.

**Step 2: Run focused tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAccountViewsTests wms.tests.views.tests_views_scan_admin_shipment_parties.ScanAdminShipmentPartiesViewTests -v 2
```

Expected:

- row-context tests pass once the estimate is available

### Task 3: Align the three templates

**Files:**
- Modify: `templates/portal/recipient_detail.html`
- Modify: `templates/portal/recipient_preferences.html`
- Modify: `templates/scan/admin_recipient_organization_detail.html`

**Step 1: Write minimal implementation**

- Add the `Qté par colis (estimation)` column after `Produit`.
- Render the estimate or `--`.
- Rebalance the editable columns so `Quantité cible` and `Notes` are narrower and `Statut` and `Période` are wider.
- Keep actions and existing validation UX untouched.

**Step 2: Run focused UI tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests wms.tests.views.tests_views_scan_admin_shipment_parties.ScanAdminShipmentPartiesViewTests -v 2
```

Expected:

- portal and scan/admin rendering assertions pass with the aligned contract

### Task 4: Update repo-reference shared contract

**Files:**
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Verify contract impact**

- Re-read the recipient preference shared contract section.
- Confirm that the line-by-line table contract now includes an estimate column and shared layout expectations across portal and scan/admin.

**Step 2: Update docs**

- Document the new estimate metadata and the expectation that the three line-by-line tables stay aligned.

### Task 5: Final verification

**Files:**
- Modify: `wms/order_helpers.py`
- Modify: `wms/views_portal_account.py`
- Modify: `wms/views_scan_admin.py`
- Modify: `templates/portal/recipient_detail.html`
- Modify: `templates/portal/recipient_preferences.html`
- Modify: `templates/scan/admin_recipient_organization_detail.html`
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/views/tests_views_scan_admin_shipment_parties.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Run the focused regression suite**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAccountViewsTests wms.tests.views.tests_views_scan_admin_shipment_parties.ScanAdminShipmentPartiesViewTests wms.tests.views.tests_portal_bootstrap_ui.PortalBootstrapUiTests -v 2
```

**Step 2: Re-run the shipment-party portal access safety net if needed**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.portal.tests_portal_access_grants wms.tests.portal.tests_portal_permissions -v 2
```

**Step 3: Inspect the diff**

Run:

```bash
git diff -- docs/repo-reference/04-shared-contracts.md docs/plans/2026-04-09-recipient-preference-table-alignment-design.md docs/plans/2026-04-09-recipient-preference-table-alignment-implementation-plan.md wms/order_helpers.py wms/views_portal_account.py wms/views_scan_admin.py templates/portal/recipient_detail.html templates/portal/recipient_preferences.html templates/scan/admin_recipient_organization_detail.html wms/tests/views/tests_views_portal.py wms/tests/views/tests_views_scan_admin_shipment_parties.py wms/tests/views/tests_portal_bootstrap_ui.py
```
