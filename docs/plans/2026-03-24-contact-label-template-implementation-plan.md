# Contact Label Template Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remap the legacy contact label XLSX document to the new merged-cell workbook layout with uppercase display fields.

**Architecture:** Reuse the existing shipment-party display helpers already present in the print-pack engine, and update only the seeded `contact_label` cell mappings with a new forward-only migration. Limit the behavior change to the contact label document.

**Tech Stack:** Django migrations, print-pack seeded mappings, Django tests, openpyxl-backed XLSX mapping.

---

### Task 1: Add failing tests for the new contact label mapping

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/print/tests_print_pack_models.py`

**Step 1: Write the failing test**

- Update the seeded contact-label mapping assertions to the new merged-cell coordinates and display source keys.
- Assert that text fields use the `upper` transform.

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.print.tests_print_pack_models wms.tests.print.tests_print_pack_engine -v 2
```

Expected: failure on the old contact-label mapping expectations.

### Task 2: Implement the minimal mapping change

**Files:**
- Create: `/Users/EdouardGonnu/asf-wms/wms/migrations/0098_update_contact_label_print_pack_mapping.py`

**Step 1: Write minimal implementation**

- Seed the new contact-label mapping with uppercase transforms and the same display fields as the shipment note.

**Step 2: Run tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.print.tests_print_pack_models wms.tests.print.tests_print_pack_engine -v 2
```

Expected: targeted contact-label tests pass.
