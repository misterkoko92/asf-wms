# Print Packs Excel Graph Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remplacer le moteur d'impression actuel par un moteur `packs A/B/C/D` piloté par templates Excel + conversion PDF Microsoft Graph, sans changer les boutons/routes existants.

**Architecture:** Les routes historiques scan/admin/API restent identiques mais délèguent à un `PrintPackEngine`. Le moteur résout les templates XLSX et mappings DB, remplit les cellules, convertit en PDF via Graph, fusionne si nécessaire, stocke l'artefact, puis envoie la synchro OneDrive via file asynchrone avec retries.

**Tech Stack:** Django 4.2, openpyxl, Microsoft Graph REST, pypdf (merge), tests Django (`manage.py test`), management command queue processor.

---

Skill refs to apply during execution: `@superpowers:test-driven-development`, `@superpowers:verification-before-completion`, `@superpowers:requesting-code-review`.

### Task 1: Add Print Pack Domain Models

**Files:**
- Create: `wms/tests/print/tests_print_pack_models.py`
- Modify: `wms/models_domain/shipment.py`
- Modify: `wms/models.py`
- Create: `wms/migrations/<auto>_print_pack_models.py`

**Step 1: Write the failing test**

```python
class PrintPackModelTests(TestCase):
    def test_pack_models_can_store_mapping_and_artifact_status(self):
        from wms.models import PrintPack
        self.assertTrue(hasattr(PrintPack, "code"))
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.print.tests_print_pack_models -v 2`
Expected: `ImportError`/`AttributeError` for missing models.

**Step 3: Write minimal implementation**

```python
class PrintPack(models.Model):
    code = models.CharField(max_length=4, unique=True)
```

Add models:
- `PrintPack`
- `PrintPackDocument`
- `PrintCellMapping`
- `GeneratedPrintArtifact`
- `GeneratedPrintArtifactItem`

Expose them in `wms/models.py`, then run `makemigrations`.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.print.tests_print_pack_models -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/models_domain/shipment.py wms/models.py wms/tests/print/tests_print_pack_models.py wms/migrations
git commit -m "feat(print): add print pack and artifact domain models"
```

### Task 2: Register Admin CRUD For Pack Config

**Files:**
- Modify: `wms/admin.py`
- Create: `wms/tests/admin/tests_admin_print_pack.py`

**Step 1: Write the failing test**

```python
response = self.client.get(reverse("admin:wms_printpack_changelist"))
self.assertEqual(response.status_code, 200)
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.admin.tests_admin_print_pack -v 2`
Expected: `NoReverseMatch` for missing admin registration.

**Step 3: Write minimal implementation**

```python
@admin.register(models.PrintPack)
class PrintPackAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "active")
```

Also register `PrintPackDocument`, `PrintCellMapping`, `GeneratedPrintArtifact` (read-only actions for artifacts).

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.admin.tests_admin_print_pack -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/admin.py wms/tests/admin/tests_admin_print_pack.py
git commit -m "feat(print): expose print pack mapping models in admin"
```

### Task 3: Implement Route-To-Pack Mapping Contract

**Files:**
- Create: `wms/print_pack_routing.py`
- Create: `wms/tests/print/tests_print_pack_routing.py`

**Step 1: Write the failing test**

```python
from wms.print_pack_routing import resolve_pack_request
self.assertEqual(resolve_pack_request("shipment_note").pack_code, "C")
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.print.tests_print_pack_routing -v 2`
Expected: module/function missing.

**Step 3: Write minimal implementation**

```python
DOC_TO_PACK = {
    "shipment_note": "C",
    "packing_list_shipment": "B",
    "donation_certificate": "B",
}
```

Add mapping helpers for:
- shipment-level docs
- carton picking (`A`)
- labels all/single (`D`)
- carton packing list single variant (`B/per_carton_single`)

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.print.tests_print_pack_routing -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/print_pack_routing.py wms/tests/print/tests_print_pack_routing.py
git commit -m "feat(print): add deterministic route-to-pack mapping"
```

### Task 4: Implement Excel Cell Mapping Service

**Files:**
- Create: `wms/print_pack_excel.py`
- Create: `wms/tests/print/tests_print_pack_excel.py`

**Step 1: Write the failing test**

```python
filled = fill_workbook_cells(workbook, mappings, payload)
self.assertEqual(filled["Main"]["D5"], "DOE John")
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.print.tests_print_pack_excel -v 2`
Expected: function missing.

**Step 3: Write minimal implementation**

```python
def fill_workbook_cells(workbook, mappings, payload):
    ws[cell] = value
```

Support:
- `source_key` resolution (`shipment.*`, `carton.*`, `contact.*`)
- transforms (`upper`, `date_fr`)
- required-field errors with explicit message (`worksheet/cell/source_key`)

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.print.tests_print_pack_excel -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/print_pack_excel.py wms/tests/print/tests_print_pack_excel.py
git commit -m "feat(print): add excel cell mapping and transform service"
```

### Task 5: Add Graph PDF Converter Client

**Files:**
- Create: `wms/print_pack_graph.py`
- Modify: `asf_wms/settings.py`
- Create: `wms/tests/print/tests_print_pack_graph.py`

**Step 1: Write the failing test**

```python
pdf_bytes = convert_excel_to_pdf_via_graph(xlsx_bytes, filename="pack_b.xlsx")
self.assertTrue(pdf_bytes.startswith(b"%PDF"))
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.print.tests_print_pack_graph -v 2`
Expected: missing Graph client/config.

**Step 3: Write minimal implementation**

```python
def convert_excel_to_pdf_via_graph(xlsx_bytes, filename):
    token = get_client_credentials_token()
    return graph_export_pdf(token, xlsx_bytes, filename)
```

Add settings/env keys:
- `GRAPH_TENANT_ID`
- `GRAPH_CLIENT_ID`
- `GRAPH_CLIENT_SECRET`
- `GRAPH_DRIVE_ID`
- `GRAPH_WORK_DIR`

Use strict timeout + structured error class.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.print.tests_print_pack_graph -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/print_pack_graph.py asf_wms/settings.py wms/tests/print/tests_print_pack_graph.py
git commit -m "feat(print): implement microsoft graph excel to pdf conversion client"
```

### Task 6: Add PDF Merge Utility

**Files:**
- Modify: `requirements.txt`
- Create: `wms/print_pack_pdf.py`
- Create: `wms/tests/print/tests_print_pack_pdf.py`

**Step 1: Write the failing test**

```python
merged = merge_pdf_documents([pdf_a, pdf_b])
self.assertGreater(len(merged), len(pdf_a))
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.print.tests_print_pack_pdf -v 2`
Expected: merge function/dependency missing.

**Step 3: Write minimal implementation**

```python
from pypdf import PdfReader, PdfWriter
```

Implement `merge_pdf_documents(pdf_list: list[bytes]) -> bytes` with input validation.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.print.tests_print_pack_pdf -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add requirements.txt wms/print_pack_pdf.py wms/tests/print/tests_print_pack_pdf.py
git commit -m "feat(print): add pdf merge helper for multi-document packs"
```

### Task 7: Implement Pack Engine Orchestration

**Files:**
- Create: `wms/print_pack_engine.py`
- Create: `wms/tests/print/tests_print_pack_engine.py`

**Step 1: Write the failing test**

```python
artifact = generate_pack(pack_code="B", shipment=shipment, user=user)
self.assertEqual(artifact.pack_code, "B")
self.assertTrue(artifact.pdf_file.name.endswith(".pdf"))
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.print.tests_print_pack_engine -v 2`
Expected: engine missing.

**Step 3: Write minimal implementation**

```python
def generate_pack(*, pack_code, shipment=None, carton=None, user=None, variant=None):
    # resolve templates -> fill xlsx -> graph pdf -> optional merge -> persist artifact
```

Implement sequence logic for `A/B/C/D`, including B order:
- global list -> carton lists -> donation.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.print.tests_print_pack_engine -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/print_pack_engine.py wms/tests/print/tests_print_pack_engine.py
git commit -m "feat(print): add pack orchestration engine for A B C D"
```

### Task 8: Wire Scan Print Views To Pack Engine

**Files:**
- Modify: `wms/views_print_docs.py`
- Modify: `wms/shipment_view_helpers.py`
- Modify: `wms/views_print_labels.py`
- Modify: `wms/tests/views/tests_views_print_docs.py`
- Modify: `wms/tests/views/tests_views_print_labels.py`

**Step 1: Write the failing test**

```python
response = self.client.get(reverse("scan:scan_shipment_document", args=[shipment.id, "shipment_note"]))
self.assertEqual(response["Content-Type"], "application/pdf")
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs wms.tests.views.tests_views_print_labels -v 2`
Expected: still rendering HTML templates.

**Step 3: Write minimal implementation**

```python
artifact = generate_pack_from_doc_route(...)
return FileResponse(artifact.pdf_file.open("rb"), content_type="application/pdf")
```

Keep existing route signatures and permissions unchanged.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs wms.tests.views.tests_views_print_labels -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_print_docs.py wms/shipment_view_helpers.py wms/views_print_labels.py wms/tests/views/tests_views_print_docs.py wms/tests/views/tests_views_print_labels.py
git commit -m "feat(print): route legacy scan print endpoints through pack engine"
```

### Task 9: Wire Admin Print Buttons To Pack Engine

**Files:**
- Modify: `wms/admin.py`
- Modify: `wms/tests/admin/tests_admin_extra.py`

**Step 1: Write the failing test**

```python
response = self.client.get(reverse("admin:wms_shipment_print_doc", args=[shipment.id, "shipment_note"]))
self.assertEqual(response["Content-Type"], "application/pdf")
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.admin.tests_admin_extra -v 2`
Expected: admin route returns HTML render template behavior.

**Step 3: Write minimal implementation**

```python
artifact = generate_pack_from_admin_route(...)
return FileResponse(..., content_type="application/pdf")
```

Keep existing admin URLs unchanged.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.admin.tests_admin_extra -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/admin.py wms/tests/admin/tests_admin_extra.py
git commit -m "feat(print): switch admin print actions to pack engine"
```

### Task 10: Implement OneDrive Sync Queue Processor

**Files:**
- Create: `wms/print_pack_sync.py`
- Create: `wms/management/commands/process_print_artifact_queue.py`
- Create: `wms/tests/print/tests_print_pack_sync.py`

**Step 1: Write the failing test**

```python
result = process_print_artifact_queue(limit=5)
self.assertEqual(result["processed"], 1)
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.print.tests_print_pack_sync -v 2`
Expected: missing command/service.

**Step 3: Write minimal implementation**

```python
def process_print_artifact_queue(limit=20):
    # claim sync_pending artifacts and push to OneDrive
```

Implement retry/backoff updates on `GeneratedPrintArtifact`.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.print.tests_print_pack_sync -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/print_pack_sync.py wms/management/commands/process_print_artifact_queue.py wms/tests/print/tests_print_pack_sync.py
git commit -m "feat(print): add async onedrive sync queue processor for generated artifacts"
```

### Task 11: Validate Existing Button Mapping End-To-End

**Files:**
- Modify: `api/tests/tests_ui_endpoints.py`
- Modify: `wms/tests/shipment/tests_shipment_view_helpers.py`
- Modify: `wms/tests/carton/tests_carton_view_helpers.py`
- Modify: `wms/tests/core/tests_ui.py`

**Step 1: Write the failing test**

```python
self.assertTrue(payload["shipments"][0]["documents"]["shipment_note_url"].endswith("/doc/shipment_note/"))
```

Add E2E assertions that clicking current UI buttons still returns valid PDF responses.

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test api.tests.tests_ui_endpoints wms.tests.shipment.tests_shipment_view_helpers wms.tests.carton.tests_carton_view_helpers wms.tests.core.tests_ui -v 2`
Expected: failures while new engine behavior is not fully wired for all paths.

**Step 3: Write minimal implementation**

Adjust wiring and DTO helper invariants to keep existing links stable while backend behavior changes.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test api.tests.tests_ui_endpoints wms.tests.shipment.tests_shipment_view_helpers wms.tests.carton.tests_carton_view_helpers wms.tests.core.tests_ui -v 2`
Expected: PASS on impacted tests.

**Step 5: Commit**

```bash
git add api/tests/tests_ui_endpoints.py wms/tests/shipment/tests_shipment_view_helpers.py wms/tests/carton/tests_carton_view_helpers.py wms/tests/core/tests_ui.py
git commit -m "test(print): lock legacy button mapping to new print pack engine"
```

### Task 12: Final Verification And Developer Docs

**Files:**
- Modify: `docs/plans/2026-03-01-print-packs-excel-graph-design.md`
- Create: `docs/plans/2026-03-01-print-packs-rollout-checklist.md`

**Step 1: Write verification checklist doc**

```markdown
- [ ] Pack A generated from cartons_ready Picking button
- [ ] Pack B generated from shipment_note/donation routes mapping
```

**Step 2: Run full impacted suites**

Run:
- `.venv/bin/python manage.py test wms.tests.print -v 2`
- `.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs wms.tests.views.tests_views_print_labels wms.tests.admin.tests_admin_extra api.tests.tests_ui_endpoints -v 2`
- `.venv/bin/python manage.py check`

Expected: PASS + no system check errors.

**Step 3: Capture migration/apply smoke**

Run:
- `.venv/bin/python manage.py makemigrations --check`
- `.venv/bin/python manage.py migrate --plan`

Expected: clean migration state and predictable plan.

**Step 4: Request review**

Use `@superpowers:requesting-code-review` and resolve findings before merge.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-01-print-packs-excel-graph-design.md docs/plans/2026-03-01-print-packs-rollout-checklist.md
git commit -m "docs(print): add rollout and verification checklist for print pack engine"
```
