# Shipment And Admin Contacts UI Adjustments Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update shipment party selectors and the admin contacts cockpit UI without changing the canonical shipment-party model.

**Architecture:** Keep all business rules in the existing `Contact` and `Shipment*` helpers. Extend payload metadata and templates so the legacy Django pages render the new grouping, formatting, collapse, and table-tool behavior.

**Tech Stack:** Django templates/views/forms, existing scan bootstrap JS, Django test suite.

---

### Task 1: Lock the requested shipment selector behavior with failing tests

**Files:**
- Modify: `wms/tests/shipment/tests_shipment_party_labels.py`
- Modify: `wms/tests/forms/tests_forms.py`

**Step 1: Write the failing tests**

- Assert shipper labels render as `Structure, Title First LAST`
- Assert destination correspondents render as `Correspondant ASF - IATA - Title First LAST`
- Assert shipment form payload keeps ASF first, then scoped shippers sorted by structure

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.shipment.tests_shipment_party_labels wms.tests.forms.tests_forms -v 2`

**Step 3: Write minimal implementation**

- Update label helpers and shipment contact payload metadata

**Step 4: Run test to verify it passes**

Run the same command and expect green.

### Task 2: Lock the admin contacts UI changes with failing tests

**Files:**
- Modify: `wms/tests/views/tests_views_scan_admin.py`
- Modify: `wms/tests/views/tests_views_scan_admin_shipment_parties.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing tests**

- Assert destination filter is rendered and preserved
- Assert tables are inside closed collapses
- Assert all admin contacts tables use `data-table-tools="1"`
- Assert shipment JS contains the new instructional options

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_scan_admin_shipment_parties wms.tests.views.tests_scan_bootstrap_ui -v 2`

**Step 3: Write minimal implementation**

- Update view/template/cockpit filtering and JS rendering

**Step 4: Run test to verify it passes**

Run the same command and expect green.

### Task 3: Implement the shipment selector rendering

**Files:**
- Modify: `wms/contact_labels.py`
- Modify: `wms/shipment_helpers.py`
- Modify: `wms/static/scan/scan.js`

**Step 1: Implement label helpers**

- Make shipper and regular recipient labels use `Structure, person`
- Keep a dedicated correspondent-recipient label builder for the first recipient block

**Step 2: Implement grouped payload metadata**

- Add sortable structure metadata for shippers and recipients
- Add instructional option metadata for the third block

**Step 3: Implement JS grouped rendering**

- Preserve separators
- Render ASF block, active block, and final instructional disabled option

**Step 4: Verify targeted tests**

Run shipment label/form tests again.

### Task 4: Implement the admin contacts cockpit UX changes

**Files:**
- Modify: `wms/views_scan_admin.py`
- Modify: `wms/scan_admin_contacts_cockpit.py`
- Modify: `templates/scan/admin_contacts.html`

**Step 1: Add destination filter plumbing**

- Read `destination_id`
- Filter cockpit tables and correspondents only
- Preserve query parameters across actions

**Step 2: Render collapses**

- Wrap each table card in closed `<details>` blocks with consistent summaries

**Step 3: Turn on table tools**

- Add `data-table-tools="1"` to each admin contacts table

**Step 4: Verify targeted tests**

Run admin contacts view/bootstrap tests again.

### Task 5: Final verification and commit

**Files:**
- Review modified files only

**Step 1: Run focused regression suite**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.shipment.tests_shipment_party_labels \
  wms.tests.forms.tests_forms \
  wms.tests.views.tests_views_scan_admin \
  wms.tests.views.tests_views_scan_admin_shipment_parties \
  wms.tests.views.tests_scan_bootstrap_ui -v 2
```

**Step 2: Commit**

```bash
git add docs/plans wms/contact_labels.py wms/shipment_helpers.py wms/static/scan/scan.js wms/views_scan_admin.py wms/scan_admin_contacts_cockpit.py templates/scan/admin_contacts.html wms/tests/shipment/tests_shipment_party_labels.py wms/tests/forms/tests_forms.py wms/tests/views/tests_views_scan_admin.py wms/tests/views/tests_views_scan_admin_shipment_parties.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat(scan): refine shipment and contacts selectors"
```
