# Shipment Note Template Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remap the legacy shipment note XLSX document to the new merged-cell workbook layout with uppercase display fields.

**Architecture:** Keep the print-pack engine responsible for building display-ready party payload fields, and update the seeded `shipment_note` cell mappings with a new forward-only migration. Limit the change to shipment-note behavior.

**Tech Stack:** Django migrations, print-pack engine payload builders, Django tests, openpyxl-backed XLSX mapping.

---

### Task 1: Add failing tests for the new shipment note behavior

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/print/tests_print_pack_models.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/print/tests_print_pack_engine.py`

**Step 1: Write the failing tests**

- Update the seeded shipment-note mapping assertions to the new merged-cell coordinates and display source keys.
- Add assertions for `display_name` and `postal_address_display`.

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.print.tests_print_pack_models wms.tests.print.tests_print_pack_engine -v 2
```

Expected: failures on the old shipment-note mapping and missing display payload fields.

### Task 2: Implement the minimal payload and mapping changes

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/print_pack_engine.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/print_pack_mapping_catalog.py`
- Create: `/Users/EdouardGonnu/asf-wms/wms/migrations/0097_update_shipment_note_print_pack_mapping.py`

**Step 1: Write minimal implementation**

- Add `display_name` and `postal_address_display` to party payloads.
- Keep current payload fields intact for compatibility.
- Seed the new shipment-note mapping with uppercase transforms and blank unsupported cells left unmapped.

**Step 2: Run tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.print.tests_print_pack_models wms.tests.print.tests_print_pack_engine -v 2
```

Expected: targeted shipment-note tests pass.

### Task 3: Sanity-check the shipment note output path

**Files:**
- Reuse existing files only

**Step 1: Run focused verification**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.print.tests_print_pack_engine.PrintPackEngineTests.test_render_pack_xlsx_documents_uses_seeded_templates_when_filefields_missing -v 2
```

Expected: the seeded template path still renders the shipment pack documents.
