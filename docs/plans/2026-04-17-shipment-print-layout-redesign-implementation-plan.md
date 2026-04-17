# Shipment Print Layout Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the legacy Django shipment print bundles so `Imprimer dossier papier` prints the shipment note, customs note, and two portrait general packing lists in that order, while `Imprimer étiquettes cartons` prints one `A4 portrait` four-block page per carton.

**Architecture:** Keep the existing `/scan/shipment/<id>/print-bundle/<bundle_key>/` routes and the legacy Django print partials, but change the grouped bundle composers in `wms/views_print_docs.py`, convert the shipment note/customs/general packing-list templates to portrait-oriented layouts, and add a dedicated per-carton composition template that arranges four compact partials in a fixed `2 x 2` `A6` grid.

**Tech Stack:** Django views/templates/helpers, legacy print partials, Django test suite via `./.venv/bin/python manage.py test`

---

### Task 1: Lock The Bundle Contracts With Failing Tests

**Files:**
- Modify: `wms/tests/views/tests_views_print_docs.py`
- Modify: `wms/tests/shipment/tests_shipment_view_helpers.py`

**Step 1: Write the failing tests**

Add coverage for:

- `paper` bundle ordering:
  - shipment note before customs
  - customs before first shipment packing list
  - first shipment packing list before second shipment packing list
- the `paper` bundle rendering the shipment packing-list sheet twice
- `standard_labels` bundle rendering one page per carton with four block markers:
  - donation
  - shipment label
  - contact
  - carton packing list
- grouped action label rename from `Imprimer toutes les étiquettes standard` to
  `Imprimer étiquettes cartons`

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_print_docs \
  wms.tests.shipment.tests_shipment_view_helpers -v 2
```

Expected:
- FAIL because the bundle order, duplication, and grouped carton-label output still reflect the old behavior

**Step 3: Write minimal implementation**

Update the bundle context builders and helper labels just enough to satisfy the new contract.

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 2: Convert Shipment Note, Customs, And General Packing List To Portrait

**Files:**
- Modify: `templates/print/bon_expedition.html`
- Modify: `templates/print/attestation_douane.html`
- Modify: `templates/print/liste_colisage_lot.html`
- Modify if needed: `templates/print/partials/shipment_note_body.html`
- Modify if needed: `templates/print/partials/customs_note_body.html`
- Modify if needed: `templates/print/partials/packing_list_shipment_body.html`

**Step 1: Write the failing tests**

Extend print-view tests to assert:

- portrait-specific root ids still render
- the paper bundle now includes two shipment packing-list sections
- standalone shipment packing-list route still renders the same template

If there is no direct CSS assertion worth keeping, use structure/order assertions and reserve visual fitting to manual browser print review.

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_print_docs.PrintDocsViewsTests.test_scan_shipment_view_bundle_routes_paper_to_direct_printable_html \
  -v 2
```

Expected:
- FAIL on the missing extra packing-list section and old layout assumptions

**Step 3: Write minimal implementation**

Update the templates to:

- use `A4 portrait`
- tighten spacing and typography enough for portrait fitting
- keep the existing data fields and ids stable where possible
- keep a recoverable landscape backup in code comments/structure or backup classes so rollback is localized

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 3: Build The Per-Carton Four-Block `A4` Bundle

**Files:**
- Modify: `wms/views_print_docs.py`
- Modify if needed: `wms/print_context.py`
- Create: `templates/print/shipment_carton_documents_a4.html`

**Step 1: Write the failing tests**

Add assertions for:

- one `.carton-documents-page` per carton
- one donation block per carton page
- one shipment-label block per carton page
- one contact block per carton page
- one packing-list block per carton page
- stable page order matching carton order

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_print_docs.PrintDocsViewsTests.test_scan_shipment_view_bundle_routes_standard_labels_to_direct_printable_html \
  -v 2
```

Expected:
- FAIL because the current bundle still renders grouped runs of three document types rather than one four-block page per carton

**Step 3: Write minimal implementation**

In `wms/views_print_docs.py`:

- replace the current standard-label bundle item builder with a per-carton page builder
- keep carton ordering stable with `_ordered_shipment_cartons(shipment)`
- pass each page the donation, shipment-label, contact, and carton-packing contexts

In the new template:

- render `A4 portrait`
- create a `2 x 2` grid of compact quadrants
- emit stable `data-print-doc-type` markers per quadrant

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 4: Add Compact `A6` CSS For The Four-Block Page

**Files:**
- Modify: `templates/print/shipment_carton_documents_a4.html`
- Reuse only: `templates/print/partials/donation_certificate_body.html`
- Reuse only: `templates/print/partials/shipment_label_body.html`
- Reuse only: `templates/print/partials/contact_label_body.html`
- Reuse only: `templates/print/partials/packing_list_carton_body.html`

**Step 1: Write the failing tests**

If useful, extend the direct-print test to assert the presence of compact wrapper classes and block ids.
Keep assertions structural; do not overfit CSS text values unless they encode a critical contract.

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_print_docs.PrintDocsViewsTests.test_scan_shipment_view_bundle_routes_standard_labels_to_direct_printable_html \
  -v 2
```

Expected:
- FAIL if compact wrappers or page markers are still missing

**Step 3: Write minimal implementation**

Add scoped compact CSS in the new template so:

- each quadrant fits within `A6`
- logos, headings, row spacing, and table cell padding shrink locally
- standalone document templates remain unchanged outside the bundle

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 5: Re-Verify Focused Flows And Repo-Reference Impact

**Files:**
- Modify if needed: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify if needed: `docs/repo-reference/03-impact-map.md`

**Step 1: Run focused verification**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_print_docs \
  wms.tests.shipment.tests_shipment_view_helpers -v 2
```

Expected:
- PASS

**Step 2: Re-check repo-reference impact**

Confirm whether the print/document flow wording needs an update because:

- `paper` bundle ordering changed
- shipment packing-list output became portrait and duplicated in the paper bundle
- the grouped carton-label action now means one four-block `A4` page per carton

**Step 3: Update docs if needed**

If the existing print/document flow wording no longer matches runtime reality, update the relevant
repo-reference sections in the same change.
