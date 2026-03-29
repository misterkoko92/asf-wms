# Shipment Grouped Print HTML Bundles Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace grouped shipment print link pages for A4-compatible bundles with directly printable HTML documents while keeping the existing orchestrator and carton list roll printer flow.

**Architecture:** Keep `all` as the bundle chooser, convert `paper` and `standard_labels` into HTML bundle renders backed by reusable print partials, and leave `carton_lists` on its current per-carton action page. Reuse the existing print context builders so bundle output stays aligned with the single-document views.

**Tech Stack:** Django legacy views, Django templates, HTML/CSS print layouts, Django test suite

---

### Task 0: Worktree baseline

**Files:**
- Reference: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html`
- Test: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/wms/tests/views/tests_views_print_docs.py`

**Step 1: Verify the worktree is isolated**

Run: `git branch --show-current`
Expected: `codex/shipment-grouped-print-html`

**Step 2: Run a targeted bundle baseline**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs.PrintDocsViewsTests.test_scan_shipment_view_bundle_routes_paper_to_html_bundle_page wms.tests.views.tests_views_print_docs.PrintDocsViewsTests.test_scan_shipment_view_bundle_routes_standard_labels_to_html_bundle_page -v 2`
Expected: both tests pass before changes

### Task 1: Write failing tests for the new grouped HTML behavior

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/wms/tests/views/tests_views_print_docs.py`

**Step 1: Write the failing test for `paper`**

Add assertions proving that `print-bundle/paper` renders a printable bundle document rather than action links, and that the bundle contains the three expected A4 sections in order.

**Step 2: Run the `paper` test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs.PrintDocsViewsTests.test_scan_shipment_view_bundle_routes_paper_to_direct_printable_html -v 2`
Expected: FAIL because the view still renders the old link page

**Step 3: Write the failing test for `standard_labels`**

Add assertions proving that `print-bundle/standard_labels` renders a single printable HTML bundle with six A5 document slots for two cartons, ordered by type then carton code.

**Step 4: Run the `standard_labels` test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs.PrintDocsViewsTests.test_scan_shipment_view_bundle_routes_standard_labels_to_direct_printable_html -v 2`
Expected: FAIL because the view still renders the old per-carton action page

### Task 2: Extract reusable print partials

**Files:**
- Add: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/templates/print/partials/shipment_note_body.html`
- Add: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/templates/print/partials/customs_note_body.html`
- Add: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/templates/print/partials/packing_list_shipment_body.html`
- Add: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/templates/print/partials/contact_label_body.html`
- Add: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/templates/print/partials/shipment_label_body.html`
- Add: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/templates/print/partials/donation_certificate_body.html`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/templates/print/bon_expedition.html`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/templates/print/etiquette_contact.html`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/templates/print/etiquette_expedition.html`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/templates/print/attestation_donation.html`

**Step 1: Extract the shared bodies into partials**

Move the printable body markup into partials so single-document and grouped-document templates share the same content.

**Step 2: Keep single-document templates green**

Update the existing standalone templates to include the new partials without changing their public contract.

**Step 3: Run the closest print view tests**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs.PrintDocsViewsTests.test_scan_shipment_donation_certificate_renders_locked_template wms.tests.views.tests_views_print_docs.PrintDocsViewsTests.test_scan_shipment_view_document_routes_single_labels_per_carton -v 2`
Expected: PASS

### Task 3: Implement direct HTML rendering for the `paper` bundle

**Files:**
- Add: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/templates/print/shipment_bundle_a4.html`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/wms/views_print_docs.py`
- Test: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/wms/tests/views/tests_views_print_docs.py`

**Step 1: Build the ordered A4 sections**

Add a helper in `wms/views_print_docs.py` that assembles the three `paper` sections with their existing contexts.

**Step 2: Render `paper` through the new printable template**

Switch `scan_shipment_view_bundle(..., "paper")` from the link page to the bundle template.

**Step 3: Run the `paper` regression test**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs.PrintDocsViewsTests.test_scan_shipment_view_bundle_routes_paper_to_direct_printable_html -v 2`
Expected: PASS

### Task 4: Implement direct HTML rendering for the `standard_labels` bundle

**Files:**
- Add: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/templates/print/shipment_bundle_a5_two_up.html`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/wms/views_print_docs.py`
- Test: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/wms/tests/views/tests_views_print_docs.py`

**Step 1: Build ordered bundle items**

Add a helper that produces ordered printable items for contact labels, shipment labels, and donation certificates, grouped by document type then carton code.

**Step 2: Render `standard_labels` through the new two-up A4 template**

Switch `scan_shipment_view_bundle(..., "standard_labels")` from the per-carton action page to the direct printable bundle.

**Step 3: Run the `standard_labels` regression test**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs.PrintDocsViewsTests.test_scan_shipment_view_bundle_routes_standard_labels_to_direct_printable_html -v 2`
Expected: PASS

### Task 5: Run the targeted verification set

**Files:**
- Verify: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/wms/views_print_docs.py`
- Verify: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/templates/print/`
- Verify: `/Users/EdouardGonnu/asf-wms/.worktrees/shipment-grouped-print-html/wms/tests/views/tests_views_print_docs.py`

**Step 1: Run the grouped print view subset**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs.PrintDocsViewsTests.test_scan_shipment_view_bundle_routes_all_to_orchestrator_page wms.tests.views.tests_views_print_docs.PrintDocsViewsTests.test_scan_shipment_view_bundle_routes_carton_lists_to_html_bundle_page wms.tests.views.tests_views_print_docs.PrintDocsViewsTests.test_scan_shipment_view_bundle_routes_paper_to_direct_printable_html wms.tests.views.tests_views_print_docs.PrintDocsViewsTests.test_scan_shipment_view_bundle_routes_standard_labels_to_direct_printable_html -v 2`
Expected: PASS

**Step 2: Re-check repo reference impact**

Review `docs/repo-reference/03-impact-map.md` section "Change To Print / Document / Label Behavior" and confirm no extra shared-contract doc updates are required because routes and user-facing contracts stay on the same surfaces.

**Step 3: Inspect git diff**

Run: `git status --short`
Expected: only the planned print, template, test, and docs changes are present
