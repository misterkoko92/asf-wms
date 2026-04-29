# Preparateur Rangement Stock Modes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the preparateur rangement flow explicitly validate either stock receipt or stock transfer batches, with mandatory quantities and default-location routing.

**Architecture:** Keep the legacy Django `/scan/preparateur/rangement/` surface and existing session batch, but turn scans into draft lines that are only applied on batch validation. Reuse existing product resolution, product-creation modal, stock receipt primitives, and FEFO stock selection for partial transfers.

**Tech Stack:** Django views/templates, existing scan JavaScript, Django TestCase, stock domain helpers.

---

### Task 1: Batch Contract Tests

**Files:**
- Modify: `wms/tests/views/tests_views_scan_preparateur.py`

**Steps:**
1. Add failing tests proving scan requires a mode and quantity.
2. Add failing tests proving known-product scans only add draft batch lines and do not create stock before validation.
3. Add failing tests proving batch validation creates `IN` movements for receipt mode.
4. Add failing tests proving transfer mode can move a partial quantity via FEFO lots.
5. Add failing tests proving missing default location blocks validation and can be fixed with a dedicated default-location action.
6. Run the focused test file and confirm the new tests fail for the expected missing behavior.

### Task 2: Rangement Batch Domain

**Files:**
- Modify: `wms/preparateur_rangement.py`

**Steps:**
1. Add mode constants for receipt and transfer.
2. Store draft batch items with mode, quantity, default destination, validity state, and source summary.
3. Add validation helpers that apply stock movements atomically.
4. Implement receipt validation with `receive_stock`.
5. Implement partial transfer validation by splitting lots when needed and creating `TRANSFER` movements.
6. Keep the five distinct product limit and duplicate scan merge behavior.

### Task 3: View And Template Flow

**Files:**
- Modify: `wms/views_scan_preparateur.py`
- Modify: `templates/scan/preparateur_rangement.html`

**Steps:**
1. Add mode selection and keep a batch locked to one mode.
2. Require quantity for scan lines.
3. Add a validate-batch action distinct from finish/clear.
4. Keep unknown-product creation, then add the created product to the draft batch.
5. Add the default-location correction action for known products missing an emplacement.
6. Change finish/next-batch behavior to clear the batch and stay on the rangement page.

### Task 4: Documentation And Verification

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts/03-scan-operations.md`
- Modify: `wms/faq_changelog.py`

**Steps:**
1. Update scan flow docs to describe receipt/transfer modes and validation-time stock writes.
2. Update shared scan operations contracts if session or movement semantics changed.
3. Add a FAQ changelog entry with `pr_number=None`.
4. Run focused tests for preparateur and scan bootstrap UI.
5. Re-check git diff for unintended changes.
