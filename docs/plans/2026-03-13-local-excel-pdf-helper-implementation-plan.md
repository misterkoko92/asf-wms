# Local Excel PDF Helper Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace Graph-based interactive Excel-to-PDF flows with a local helper that uses Microsoft Excel desktop for strict workbook rendering and PDF assembly.

**Architecture:** Keep Django legacy views as the business orchestrator and XLSX generator. Extend the existing local helper with a generic PDF render endpoint, then use browser-side JS to fetch protected XLSX payloads from Django and hand them off to the helper for Excel conversion and optional merge/open actions. Defer server-side PDF artifact archival until after the helper path is stable.

**Tech Stack:** Django legacy views/templates/static JS, existing `tools/planning_comm_helper` HTTP server, Microsoft Excel desktop automation on macOS/Windows, `pypdf`, Django tests, helper unit tests.

---

### Task 1: Lock the local-helper rendering contract before changing behavior

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/tests/test_server.py`
- Modify: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/tests/test_planning_pdf.py`
- Create: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/tests/test_pdf_render.py`

**Step 1: Write failing helper endpoint tests**

Add tests covering:
- `POST /v1/pdf/render` with one workbook
- `POST /v1/pdf/render` with multiple workbooks and `merge=true`
- 422 response when `documents` is missing
- 422 response when a workbook is missing `filename` or `content_base64`

**Step 2: Write failing converter tests for strict mode hooks**

Add tests asserting that the generic Excel converter:
- rejects unsupported platforms without mentioning LibreOffice
- validates workbook existence
- forwards the expected output path

**Step 3: Run the helper test subset to confirm failure**

Run:
```bash
./.venv/bin/python -m pytest tools/planning_comm_helper/tests/test_server.py tools/planning_comm_helper/tests/test_planning_pdf.py tools/planning_comm_helper/tests/test_pdf_render.py -q
```

Expected:
- failures on missing render route / missing generic render helpers

**Step 4: Commit the red-phase checkpoint only if useful**

```bash
git add tools/planning_comm_helper/tests/test_server.py tools/planning_comm_helper/tests/test_planning_pdf.py tools/planning_comm_helper/tests/test_pdf_render.py
git commit -m "test(helper): define local pdf render contract"
```

Only commit here if the branch workflow allows red commits.

### Task 2: Extract a generic Excel desktop converter from the planning-specific module

**Files:**
- Create: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/excel_pdf.py`
- Modify: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/planning_pdf.py`
- Modify: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/tests/test_planning_pdf.py`

**Step 1: Implement the generic converter API**

Create:
- `ExcelPdfConversionError`
- `convert_workbook_to_pdf(workbook_path, pdf_path=None, strict=True)`

Move the platform dispatch logic into `excel_pdf.py`.

**Step 2: Add strict-render hooks**

Implement the minimal strict behavior available per platform:
- Windows: set calculation mode / recalculate before `ExportAsFixedFormat`
- macOS: keep AppleScript export path, and structure the function so later AppleScript workbook refresh improvements stay localized

Do not add any LibreOffice fallback.

**Step 3: Keep backward compatibility for planning**

Turn `planning_pdf.py` into a thin compatibility wrapper or alias layer so existing planning helper imports keep working.

**Step 4: Run the helper converter tests**

Run:
```bash
./.venv/bin/python -m pytest tools/planning_comm_helper/tests/test_planning_pdf.py -q
```

Expected:
- green tests for the generic converter surface and compatibility wrapper

**Step 5: Commit**

```bash
git add tools/planning_comm_helper/excel_pdf.py tools/planning_comm_helper/planning_pdf.py tools/planning_comm_helper/tests/test_planning_pdf.py
git commit -m "feat(helper): extract generic excel pdf converter"
```

### Task 3: Add multi-document PDF render and merge support to the local helper

**Files:**
- Create: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/pdf_render.py`
- Modify: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/server.py`
- Modify: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/tests/test_server.py`
- Modify: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/tests/test_pdf_render.py`

**Step 1: Write the minimal render service**

Implement a service that:
- materializes uploaded workbooks into a temp directory
- converts each workbook to PDF via `excel_pdf.convert_workbook_to_pdf(...)`
- merges PDFs when `merge=true`
- stores the final PDF under a deterministic temp filename
- optionally opens it locally when `open_after_render=true`

**Step 2: Expose the helper route**

Add `POST /v1/pdf/render` in `server.py`, following the existing header and JSON validation rules.

**Step 3: Keep the response simple**

Return JSON only:
- `ok`
- `output_filename`
- `opened`
- `warning_messages`

Do not return raw PDF bytes in V1.

**Step 4: Run the helper HTTP tests**

Run:
```bash
./.venv/bin/python -m pytest tools/planning_comm_helper/tests/test_server.py tools/planning_comm_helper/tests/test_pdf_render.py -q
```

Expected:
- green tests for one-workbook and multi-workbook render jobs

**Step 5: Commit**

```bash
git add tools/planning_comm_helper/pdf_render.py tools/planning_comm_helper/server.py tools/planning_comm_helper/tests/test_server.py tools/planning_comm_helper/tests/test_pdf_render.py
git commit -m "feat(helper): add generic pdf render endpoint"
```

### Task 4: Reuse the generic converter in Outlook draft attachment handling

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/outlook.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/planning/communication_actions.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/planning/tests_communication_actions.py`
- Modify: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/tests/test_outlook.py`

**Step 1: Introduce a generic Excel attachment type**

Replace the planning-only attachment assumption with a generic type such as:
- `excel_workbook`

Keep support for legacy `planning_workbook` during the migration window.

**Step 2: Update helper attachment materialization**

Make `outlook.py` convert all Excel workbook attachment types through the generic converter before attaching to Outlook.

**Step 3: Update Django payload builders**

Adjust communication payload tests and builders so planning-generated attachments can emit the generic type without breaking current user-facing flows.

**Step 4: Run focused tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.planning.tests_communication_actions -v 2
./.venv/bin/python -m pytest tools/planning_comm_helper/tests/test_outlook.py -q
```

Expected:
- planning helper payload tests stay green
- Outlook helper attachment conversion tests pass

**Step 5: Commit**

```bash
git add tools/planning_comm_helper/outlook.py wms/planning/communication_actions.py wms/tests/planning/tests_communication_actions.py tools/planning_comm_helper/tests/test_outlook.py
git commit -m "feat(helper): generalize excel attachments for outlook drafts"
```

### Task 5: Add a Django-side helper job builder for print-pack XLSX payloads

**Files:**
- Create: `/Users/EdouardGonnu/asf-wms/wms/local_document_helper.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print_docs.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print_labels.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_docs.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_labels.py`

**Step 1: Write failing JSON contract tests for helper jobs**

Add tests asserting that helper-enabled print endpoints can return a JSON payload describing:
- `documents`
- `output_filename`
- `merge`
- per-document download URLs

Keep the tests focused on Excel-based pack routes only.

**Step 2: Implement a helper job builder**

Use `render_pack_xlsx_documents(...)` to build a browser-consumable helper job:
- one entry per generated workbook
- deterministic final PDF filename
- no Graph conversion in this path

**Step 3: Add helper-job view support**

Expose helper job JSON through dedicated view branches or dedicated helper endpoints in the legacy Django views.

**Step 4: Run the targeted Django tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs wms.tests.views.tests_views_print_labels -v 2
```

Expected:
- helper job endpoints return stable JSON
- non-helper flows remain unchanged

**Step 5: Commit**

```bash
git add wms/local_document_helper.py wms/views_print_docs.py wms/views_print_labels.py wms/tests/views/tests_views_print_docs.py wms/tests/views/tests_views_print_labels.py
git commit -m "feat(print): expose local helper jobs for excel packs"
```

### Task 6: Extract reusable helper-install context for non-planning screens

**Files:**
- Create: `/Users/EdouardGonnu/asf-wms/wms/helper_install.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_planning.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print_docs.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print_labels.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_planning.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_docs.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_labels.py`

**Step 1: Move installer payload logic into a shared helper module**

Extract the existing platform-aware helper install payload builder from `views_planning.py`.

**Step 2: Reuse it on print screens**

Expose install/retry metadata to all legacy pages that can trigger helper-driven Excel rendering.

**Step 3: Run the view tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_planning wms.tests.views.tests_views_print_docs wms.tests.views.tests_views_print_labels -v 2
```

Expected:
- planning still renders its helper install surface
- print screens now expose the same helper install contract

**Step 4: Commit**

```bash
git add wms/helper_install.py wms/views_planning.py wms/views_print_docs.py wms/views_print_labels.py wms/tests/views/tests_views_planning.py wms/tests/views/tests_views_print_docs.py wms/tests/views/tests_views_print_labels.py
git commit -m "feat(helper): share installer context across planning and print screens"
```

### Task 7: Add browser-side helper orchestration for Excel print actions

**Files:**
- Create: `/Users/EdouardGonnu/asf-wms/wms/static/wms/local_document_helper.js`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/scan/shipments_ready.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/scan/cartons_ready.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/admin/wms/shipment/change_form.html`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/core/tests_ui.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/admin/tests_admin_extra.py`

**Step 1: Add a dedicated helper JS module**

Follow the proven pattern from `planning_communications_helper.js`:
- fetch JSON helper job from Django
- download each workbook in authenticated context
- POST the hydrated job to `http://127.0.0.1:38555/v1/pdf/render`
- surface install / retry / error feedback in-page

**Step 2: Mark Excel-pack buttons with helper data attributes**

Convert the relevant scan/admin buttons from passive links to helper-triggering actions.

Do not change unrelated legacy document buttons.

**Step 3: Run focused UI and admin tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.core.tests_ui wms.tests.admin.tests_admin_extra -v 2
```

Expected:
- pages still expose the expected buttons
- helper data attributes and script include are present

**Step 4: Commit**

```bash
git add wms/static/wms/local_document_helper.js templates/scan/shipments_ready.html templates/scan/cartons_ready.html templates/admin/wms/shipment/change_form.html wms/tests/core/tests_ui.py wms/tests/admin/tests_admin_extra.py
git commit -m "feat(print): wire excel print actions to local helper"
```

### Task 8: Remove Graph from the interactive legacy print path

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print_docs.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print_labels.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_docs.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_labels.py`

**Step 1: Write failing behavior tests**

Assert that helper-enabled Excel pack actions:
- no longer depend on Graph success for the nominal interactive path
- return an explicit helper-oriented error surface when the helper is unavailable

**Step 2: Implement the path switch**

Make Graph non-nominal for interactive legacy print actions.

Keep any remaining Graph-only archival code isolated and out of the user-triggered path.

**Step 3: Run the focused tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs wms.tests.views.tests_views_print_labels -v 2
```

Expected:
- interactive routes prefer helper job flow
- tests documenting old Graph fallback behavior are updated or removed

**Step 4: Commit**

```bash
git add wms/views_print_docs.py wms/views_print_labels.py wms/tests/views/tests_views_print_docs.py wms/tests/views/tests_views_print_labels.py
git commit -m "refactor(print): remove graph from interactive excel render flow"
```

### Task 9: Document rollout and operator prerequisites

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/tools/planning_comm_helper/README.md`
- Create: `/Users/EdouardGonnu/asf-wms/docs/plans/2026-03-13-local-excel-pdf-helper-rollout.md`

**Step 1: Update helper README**

Document:
- the new generic PDF render route
- Excel desktop prerequisite
- no LibreOffice fallback
- how print-pack flows use the helper

**Step 2: Add a short rollout/runbook doc**

Capture:
- install steps by platform
- smoke test checklist
- helper unavailable troubleshooting
- explicit statement that Graph is no longer required for interactive Excel print flows

**Step 3: Commit**

```bash
git add tools/planning_comm_helper/README.md docs/plans/2026-03-13-local-excel-pdf-helper-rollout.md
git commit -m "docs(helper): add local excel pdf rollout notes"
```

### Task 10: Run the full targeted verification subset

**Files:**
- No code changes expected

**Step 1: Run helper tests**

Run:
```bash
./.venv/bin/python -m pytest tools/planning_comm_helper/tests -q
```

Expected:
- all helper tests pass

**Step 2: Run focused Django tests for planning and print helper flows**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.planning.tests_communication_actions wms.tests.views.tests_views_planning wms.tests.views.tests_views_print_docs wms.tests.views.tests_views_print_labels wms.tests.admin.tests_admin_extra wms.tests.core.tests_ui -v 2
```

Expected:
- all focused legacy Django helper integration tests pass

**Step 3: Commit final polish only if verification required follow-up edits**

```bash
git add -A
git commit -m "test(helper): verify local excel render migration"
```

Only create this commit if verification forces code or doc adjustments.
