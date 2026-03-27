# Shipping Print Templates XLSX Fidelity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild shipment logistics HTML print templates from the legacy `.xlsx` sources, while keeping `etiquette colis` unchanged and aligning the dossier `Documents` panel action rows.

**Architecture:** Keep the current HTML-first print routing, but rewrite the document templates to follow the spreadsheet sources more closely. Use a small shared print-form styling approach so V1 can stay faithful and V2 can modernize later without changing the document contexts or route contracts.

**Tech Stack:** Django templates, legacy Django views, HTML/CSS print layouts, Django tests, coverage gate via `uv run make coverage`

---

### Task 1: Save the validated design and lock the execution scope

**Files:**
- Create: `docs/plans/2026-03-27-shipping-print-templates-xlsx-fidelity-design.md`
- Create: `docs/plans/2026-03-27-shipping-print-templates-xlsx-fidelity-implementation-plan.md`

**Step 1: Save the approved design**

- Record the V1 faithful reproduction goal.
- Record the V2 modernization follow-up direction.
- Record that `etiquette colis` remains unchanged.

**Step 2: Save the implementation plan**

- Break work into dossier panel alignment plus document template rewrites.

**Step 3: Commit later with implementation**

- Keep docs in the same branch and PR as the implementation unless the user asks otherwise.

### Task 2: Align dossier `Documents` group layouts with the `Par colis` pattern

**Files:**
- Modify: `templates/scan/includes/shipment_dossier_documents_panel.html`
- Test: `wms/tests/views/tests_views_scan_shipments.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write or update the failing tests**

- Extend the dossier-related view tests so they assert the grouped sections use the same row/action structure pattern as `Par colis`.

**Step 2: Run the targeted tests to verify failure**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_scan_bootstrap_ui \
  -v 1
```

**Step 3: Implement the minimal template change**

- Update grouped sections so each has a label/meta row plus a single `ui-comp-actions` line.
- Preserve existing IDs and route links.

**Step 4: Re-run the targeted tests**

- Verify dossier panel tests pass.

### Task 3: Rebuild `bon d’expédition` and `document douane` from the `.xlsx` forms

**Files:**
- Modify: `templates/print/bon_expedition.html`
- Modify: `templates/print/attestation_douane.html`
- Reference: `data/print_templates/C__shipment_note__shipment.xlsx`
- Reference: `data/print_templates/C__customs_note__shipment.xlsx`
- Test: `wms/tests/views/tests_views_print_docs.py`
- Test: `wms/tests/views/tests_print_strict_fidelity.py`

**Step 1: Write or update failing tests**

- Add assertions for the expected title blocks and form sections based on the `.xlsx` structure.
- Ensure the shipment note no longer embeds the donation certificate content if that is no longer part of the V1 faithful layout.

**Step 2: Run targeted tests to verify failure**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_print_docs \
  wms.tests.views.tests_print_strict_fidelity \
  -v 1
```

**Step 3: Implement the templates**

- Rework the documents into form-style printable layouts.
- Keep existing context variable usage where possible.
- Avoid changing routes or context builders unless a template truly needs missing data.

**Step 4: Re-run targeted tests**

- Confirm the updated templates still render through the dossier HTML-first flow.

### Task 4: Rebuild `liste générale` and `liste colisage par carton` from the `.xlsx` sources

**Files:**
- Modify: `templates/print/liste_colisage_lot.html`
- Modify: `templates/print/liste_colisage_carton.html`
- Reference: `data/print_templates/B__packing_list_shipment__shipment.xlsx`
- Reference: `data/print_templates/B__packing_list_carton__per_carton_single.xlsx`
- Test: `wms/tests/views/tests_views_print_docs.py`

**Step 1: Write or update failing tests**

- Assert the V1 title/subtitle structure and expected table headers.

**Step 2: Run the targeted tests to verify failure**

**Step 3: Implement the minimal template rewrite**

- Keep the existing data rows.
- Rebuild the title and framing to match the spreadsheet structure more closely.

**Step 4: Re-run targeted tests**

- Confirm per-shipment and per-carton HTML routes still work.

### Task 5: Rebuild `attestation donation` and `étiquette contact` from the `.xlsx` sources

**Files:**
- Modify: `templates/print/attestation_donation.html`
- Modify: `templates/print/etiquette_contact.html`
- Reference: `data/print_templates/B__donation_certificate__shipment.xlsx`
- Reference: `data/print_templates/C__contact_label__shipment.xlsx`
- Test: `wms/tests/views/tests_views_print_docs.py`
- Test: `wms/tests/views/tests_views_print_labels.py`
- Test: `wms/tests/views/tests_print_strict_fidelity.py`

**Step 1: Write or update failing tests**

- Donation certificate: assert locked content remains present while the main layout matches the source better.
- Contact label: assert field sections and headings follow the source label structure.

**Step 2: Run targeted tests to verify failure**

**Step 3: Implement the template rewrites**

- Keep donation content exact.
- Keep label context and carton metadata routing intact.

**Step 4: Re-run targeted tests**

- Confirm both routes and strict-fidelity checks pass.

### Task 6: Run the full verification gate and update the PR

**Files:**
- Modify as needed based on failures from previous tasks

**Step 1: Run focused print and dossier tests**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_views_print_docs \
  wms.tests.views.tests_views_print_labels \
  wms.tests.views.tests_print_delivery \
  wms.tests.views.tests_print_strict_fidelity \
  -v 1
```

**Step 2: Run diff hygiene**

Run:

```bash
git diff --check
```

**Step 3: Run the full coverage gate**

Run:

```bash
COVERAGE_FAIL_UNDER=93 TEST_PARALLEL=4 uv run make coverage
```

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: align shipping print templates with xlsx sources"
```

**Step 5: Push and update PR**

```bash
git push
gh pr checks 94
```
