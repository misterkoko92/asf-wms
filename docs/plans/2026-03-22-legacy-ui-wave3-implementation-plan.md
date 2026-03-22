# Legacy UI Wave 3 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor `scan/shipment_create` into smaller partial-based sections, document shipment workflow UI contracts in the `UI Lab`, and preserve every existing shipment JS/document hook while improving maintainability.

**Architecture:** Keep the legacy UI approach hybrid. Reuse existing leaf primitives (`ui_button`, `ui_alert`) where the markup is closed, but represent shipment workflow layout patterns as explicit HTML/CSS contracts rendered in the page and catalogued in `scan/ui-lab/`. Split `shipment_create` by business responsibility rather than by superficial markup blocks so tests and future maintenance align with the actual shipment flow.

**Tech Stack:** Django templates, Django inclusion tags, Django TestCase, Bootstrap bridge CSS, legacy scan JS hooks, local document helper integration

---

### Task 1: Lock the wave 3 shipment UI contracts with failing tests

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Verify: `templates/scan/shipment_create.html`
- Verify: `templates/scan/ui_lab.html`
- Verify: `wms/static/scan/scan.js`

**Step 1: Write the failing test**

Add assertions that describe the target wave 3 state:
- `scan_shipment_create` uses shared action wrappers for draft/save areas and edit-mode document action groups.
- top-level non-field errors and critical empty-state messages render through the shared alert contract instead of raw `scan-message error` blocks.
- the preassignment confirmation overlay remains present and identifiable after decomposition.
- the `UI Lab` exposes shipment workflow examples for a document action group and a confirmation overlay contract.

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments -v 2`

Expected: FAIL because `shipment_create.html` is still monolithic and the `UI Lab` does not yet document the target shipment workflow contracts.

**Step 3: Write minimal implementation**

No production implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments -v 2`

Expected: FAIL only on the newly added wave 3 assertions.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "test: lock legacy ui wave 3 shipment contracts"
```

### Task 2: Extend the UI Lab with shipment workflow contracts

**Files:**
- Modify: `templates/scan/ui_lab.html`
- Modify: `wms/static/scan/ui-lab.css`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `wms/static/scan/scan-bootstrap.css`

**Step 1: Write the failing test**

Use the red tests from Task 1 for:
- shipment document action group examples,
- shipment workflow panel examples,
- shipment confirmation overlay examples.

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL because the `UI Lab` does not yet expose those shipment workflow patterns.

**Step 3: Write minimal implementation**

- add one `UI Lab` section showing a shipment workflow panel with notes and CTA hierarchy,
- add one example of a document action strip using the existing tertiary button contract,
- add one read-only confirmation overlay example consistent with the shipment preassignment modal,
- add only the CSS needed to present these examples clearly without introducing a new generic component API.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS for the `UI Lab` contract assertions, with any remaining failures limited to the still-monolithic shipment page.

**Step 5: Commit**

```bash
git add templates/scan/ui_lab.html wms/static/scan/ui-lab.css wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "docs: add shipment workflow contracts to the ui lab"
```

### Task 3: Refactor the shipment creation flow into partials

**Files:**
- Modify: `templates/scan/shipment_create.html`
- Create: `templates/scan/includes/shipment_create_intro.html`
- Create: `templates/scan/includes/shipment_create_destination_panel.html`
- Create: `templates/scan/includes/shipment_create_party_sections.html`
- Create: `templates/scan/includes/shipment_create_details_panel.html`
- Create: `templates/scan/includes/shipment_create_preassignment_overlay.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Verify: `wms/views_scan_shipments.py`
- Verify: `wms/static/scan/scan.js`

**Step 1: Write the failing test**

Add or tighten tests that assert:
- the destination panel, party panels, and details panel keep their `id`, `name`, and `data-*` hooks,
- non-field errors are rendered through `ui_alert`,
- the draft/save action areas sit inside shared action wrappers,
- the preassignment overlay still exposes the same modal IDs and action button IDs.

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments -v 2`

Expected: FAIL because `shipment_create.html` has not yet been decomposed into the target partials and shared alert/action contracts.

**Step 3: Write minimal implementation**

- load `wms_ui` in `templates/scan/shipment_create.html` if needed for `ui_button` and `ui_alert`,
- move title/helper/non-field alert handling into `shipment_create_intro.html`,
- isolate destination into `shipment_create_destination_panel.html`,
- group shipper/recipient/correspondent sections into `shipment_create_party_sections.html`,
- isolate line builder, totals, pack CTA, and save buttons into `shipment_create_details_panel.html`,
- isolate the preassignment modal into `shipment_create_preassignment_overlay.html`,
- preserve exactly:
  - `shipment-form`,
  - `shipment-lines`,
  - `shipment-details-section`,
  - `shipment-preassignment-*`,
  - `shipment-correspondent-single`,
  - all existing `data-*` guidance attributes.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments -v 2`

Expected: PASS for create-mode and shared contract assertions.

**Step 5: Commit**

```bash
git add templates/scan/shipment_create.html templates/scan/includes/shipment_create_intro.html templates/scan/includes/shipment_create_destination_panel.html templates/scan/includes/shipment_create_party_sections.html templates/scan/includes/shipment_create_details_panel.html templates/scan/includes/shipment_create_preassignment_overlay.html wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "refactor: split shipment creation flow into shared ui sections"
```

### Task 4: Refactor edit-mode shipment follow-up and document panels

**Files:**
- Modify: `templates/scan/shipment_create.html`
- Create: `templates/scan/includes/shipment_create_tracking_panel.html`
- Create: `templates/scan/includes/shipment_create_generated_documents_panel.html`
- Create: `templates/scan/includes/shipment_create_additional_documents_panel.html`
- Create: `templates/scan/includes/shipment_create_receipt_allocations_panel.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Verify: `wms/views_scan_shipments.py`

**Step 1: Write the failing test**

Add or tighten tests that assert:
- edit mode keeps the tracking section and document link groups under shared action/document wrappers,
- upload and delete actions keep their secondary/danger semantics,
- receipt allocation markup still renders in edit mode,
- helper-local document links still preserve `data-local-document-helper-link="1"` where expected.

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments -v 2`

Expected: FAIL because the edit-only portion of `shipment_create.html` is still inline and not organized around the target contracts.

**Step 3: Write minimal implementation**

- split the edit-only blocks into:
  - `shipment_create_tracking_panel.html`,
  - `shipment_create_generated_documents_panel.html`,
  - `shipment_create_additional_documents_panel.html`,
  - `shipment_create_receipt_allocations_panel.html`,
- use shared button levels consistently for:
  - tertiary document links,
  - secondary upload,
  - danger delete,
- preserve tracking URL, document URLs, upload form action, delete form action, and helper-local attributes.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments -v 2`

Expected: PASS for edit-mode shipment rendering and document action assertions.

**Step 5: Commit**

```bash
git add templates/scan/shipment_create.html templates/scan/includes/shipment_create_tracking_panel.html templates/scan/includes/shipment_create_generated_documents_panel.html templates/scan/includes/shipment_create_additional_documents_panel.html templates/scan/includes/shipment_create_receipt_allocations_panel.html wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "refactor: decompose shipment edit panels onto shared ui contracts"
```

### Task 5: Final focused verification and wave 4 handoff

**Files:**
- Verify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `wms/tests/views/tests_views_scan_shipments.py`
- Verify: `templates/scan/shipment_create.html`
- Verify: `templates/scan/ui_lab.html`

**Step 1: Write the failing test**

No new tests in this task. Use the full wave 3 regression set from the previous tasks.

**Step 2: Run test to verify the final branch state**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments -v 2`

Expected: PASS.

**Step 3: Record deferred scope**

Record explicitly in the task notes or final summary that wave 4 starts with:
- `templates/scan/imports.html`
- then `templates/scan/admin_contacts.html`

**Step 4: Re-run the same command to confirm stability**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments -v 2`

Expected: PASS again.

**Step 5: Commit**

```bash
git add templates/scan/shipment_create.html templates/scan/ui_lab.html templates/scan/includes/shipment_create_intro.html templates/scan/includes/shipment_create_destination_panel.html templates/scan/includes/shipment_create_party_sections.html templates/scan/includes/shipment_create_details_panel.html templates/scan/includes/shipment_create_preassignment_overlay.html templates/scan/includes/shipment_create_tracking_panel.html templates/scan/includes/shipment_create_generated_documents_panel.html templates/scan/includes/shipment_create_additional_documents_panel.html templates/scan/includes/shipment_create_receipt_allocations_panel.html wms/static/scan/ui-lab.css wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "refactor: deliver legacy ui wave 3 shipment contracts"
```
