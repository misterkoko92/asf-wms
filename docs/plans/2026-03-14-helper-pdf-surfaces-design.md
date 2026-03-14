# Helper PDF Surfaces Design

**Date:** 2026-03-14

**Goal:** Extend the legacy local helper only to UI buttons whose target routes already support the helper job contract for local PDF rendering.

## Scope

- Keep existing helper-enabled pages unchanged:
  - `scan/cartons_ready`
  - `scan/shipments_ready`
  - `admin/wms/shipment/change_form`
  - `planning/version_detail`
- Add helper wiring to missing legacy scan surfaces that already point to helper-compatible routes:
  - `scan/prepare_kits` for the single-carton picking route only
  - `scan/pack`
  - `scan/shipment_create`

## Non-Goals

- Do not attach the helper to arbitrary `doc.file.url` downloads.
- Do not attach the helper to server-rendered PDFs that do not implement the `?helper=1` / `?helper_document=` contract.
- Do not change `portal` or `benevole` pages unless a helper-compatible PDF generation surface is discovered.

## Approach

- Reuse the existing scan helper pattern:
  - `helper_install`
  - `local_document_helper_origin`
  - `templates/wms/_local_document_helper_install_panel.html`
  - `wms/static/wms/local_document_helper.js`
- Only mark links with `data-local-document-helper-link="1"` when their target route is already handled by `wms/views_print_docs.py` or `wms/views_print_labels.py`.
- On `scan/prepare_kits`, mark the picking button only when the generated result points to `scan_carton_picking`; leave the multi-carton `scan_prepare_kits_picking` HTML print route untouched.
- Leave mixed pages with uploaded documents untouched except for the specific generated-document buttons that already support helper jobs.

## Validation

- Add red/green tests for helper metadata on the new scan pages.
- Verify the existing planning/admin helper tests still pass.
