# Print Pack XLSX Mapping Editor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remplacer `/scan/templates/` (éditeur layout HTML legacy) par un éditeur superuser de templates XLSX pack avec upload/remplacement, mapping batch, gestion des cellules fusionnées et rollback versionné.

**Architecture:** Le parcours legacy scan conserve les mêmes URLs d'entrée, mais les vues basculent de `PrintTemplate` vers `PrintPackDocument`/`PrintCellMapping`. Chaque sauvegarde crée un snapshot versionné (`PrintPackDocumentVersion`) contenant fichier XLSX + mappings. Les restaurations réappliquent un snapshot complet et créent une nouvelle version d'audit.

**Tech Stack:** Django 4.2, ORM/migrations, templates Django + JS vanilla léger, openpyxl (inspection merged cells), tests Django (`manage.py test`), pré-commit.

---

Skill refs to apply during execution: `@superpowers:test-driven-development`, `@superpowers:systematic-debugging`, `@superpowers:verification-before-completion`, `@superpowers:requesting-code-review`.

### Task 1: Add Snapshot Version Model For XLSX + Mappings

**Files:**
- Create: `wms/tests/print/tests_print_pack_document_versions.py`
- Modify: `wms/models_domain/shipment.py`
- Modify: `wms/models.py`
- Create: `wms/migrations/<auto>_add_printpackdocumentversion.py`

**Step 1: Write the failing test**

```python
class PrintPackDocumentVersionModelTests(TestCase):
    def test_can_store_xlsx_snapshot_and_mapping_snapshot(self):
        self.assertTrue(hasattr(models, "PrintPackDocumentVersion"))
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.print.tests_print_pack_document_versions -v 2`
Expected: FAIL (`AttributeError`/import error).

**Step 3: Write minimal implementation**

```python
class PrintPackDocumentVersion(models.Model):
    pack_document = models.ForeignKey(PrintPackDocument, ...)
    version = models.PositiveIntegerField()
    xlsx_template_file = models.FileField(upload_to="print_pack_template_versions/", null=True, blank=True)
    mappings_snapshot = models.JSONField(default=list, blank=True)
```

Add fields `change_type`, `change_note`, `created_at`, `created_by`, and uniqueness `(pack_document, version)`.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.print.tests_print_pack_document_versions -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/models_domain/shipment.py wms/models.py wms/tests/print/tests_print_pack_document_versions.py wms/migrations
git commit -m "feat(print): add version model for print pack xlsx snapshots"
```

### Task 2: Add Mapping Catalog + Workbook Cell Normalization Helpers

**Files:**
- Create: `wms/print_pack_mapping_catalog.py`
- Create: `wms/print_pack_workbook.py`
- Create: `wms/tests/print/tests_print_pack_workbook.py`

**Step 1: Write the failing test**

```python
def test_normalize_cell_ref_returns_anchor_for_merged_cell(self):
    normalized, merged_range = normalize_cell_ref(...)
    self.assertEqual(normalized, "B5")
    self.assertEqual(merged_range, "B5:B7")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.print.tests_print_pack_workbook -v 2`
Expected: FAIL (module/function missing).

**Step 3: Write minimal implementation**

```python
ALLOWED_SOURCE_KEYS = (
    "shipment.reference",
    "shipment.shipper.title",
    ...
)
```

Helpers:
- parse workbook sheet names
- column choices `A..XFD`
- row choices from sheet max row
- normalize merged cell ref to anchor
- validate source key from allow-list only

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.print.tests_print_pack_workbook -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/print_pack_mapping_catalog.py wms/print_pack_workbook.py wms/tests/print/tests_print_pack_workbook.py
git commit -m "feat(print): add workbook mapping helpers and source-key catalog"
```

### Task 3: Add Versioning Service For Save And Restore

**Files:**
- Create: `wms/print_pack_template_versions.py`
- Create: `wms/tests/print/tests_print_pack_template_versions.py`

**Step 1: Write the failing test**

```python
def test_save_snapshot_creates_incremental_version(self):
    version = save_print_pack_document_snapshot(...)
    self.assertEqual(version.version, 1)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.print.tests_print_pack_template_versions -v 2`
Expected: FAIL (service missing).

**Step 3: Write minimal implementation**

```python
def save_print_pack_document_snapshot(*, pack_document, mappings, xlsx_file, user, change_type):
    ...
```

Add restore helper:
- load snapshot mappings
- replace active `PrintCellMapping`
- replace active `xlsx_template_file`
- write new version with `change_type="restore"`

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.print.tests_print_pack_template_versions -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/print_pack_template_versions.py wms/tests/print/tests_print_pack_template_versions.py
git commit -m "feat(print): add transactional save and restore services for xlsx template versions"
```

### Task 4: Replace Templates List View With PrintPackDocument List

**Files:**
- Modify: `wms/views_print_templates.py`
- Modify: `templates/scan/print_template_list.html`
- Modify: `wms/tests/views/tests_views_print_templates.py`

**Step 1: Write the failing test**

```python
response = self.client.get(reverse("scan:scan_print_templates"))
self.assertContains(response, "Pack")
self.assertContains(response, "Variant")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_print_templates.PrintTemplateViewsTests.test_scan_print_templates_list_displays_override_state -v 2`
Expected: FAIL (legacy `PrintTemplate` assertions).

**Step 3: Write minimal implementation**

Switch `_build_template_list_items()` to `PrintPackDocument` rows:
- `pack.code`, `doc_type`, `variant`
- active xlsx filename
- mapping count
- latest version metadata

Update list template columns and modify link target to same edit route with `pack_document_id`.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_print_templates -v 2`
Expected: PASS on updated list tests.

**Step 5: Commit**

```bash
git add wms/views_print_templates.py templates/scan/print_template_list.html wms/tests/views/tests_views_print_templates.py
git commit -m "feat(print): replace legacy templates list with print pack document list"
```

### Task 5: Build New Edit Page UI For Batch Mapping + Upload

**Files:**
- Modify: `templates/scan/print_template_edit.html`
- Create: `wms/static/scan/print_pack_mapping_editor.js`
- Create: `wms/static/scan/print_pack_mapping_editor.css`
- Modify: `wms/tests/views/tests_views_print_templates.py`

**Step 1: Write the failing test**

```python
response = self.client.get(self._edit_url(pack_document.id))
self.assertContains(response, "Template XLSX")
self.assertContains(response, "Enregistrer toutes les modifications")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_print_templates -v 2`
Expected: FAIL (old layout editor markup).

**Step 3: Write minimal implementation**

Replace page body with:
- XLSX upload section
- mapping grid (row add/remove client-side)
- dropdowns for worksheet/column/row/source key
- history table with restore buttons

No free-text source-key input.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_print_templates -v 2`
Expected: PASS on updated UI assertions.

**Step 5: Commit**

```bash
git add templates/scan/print_template_edit.html wms/static/scan/print_pack_mapping_editor.js wms/static/scan/print_pack_mapping_editor.css wms/tests/views/tests_views_print_templates.py
git commit -m "feat(print): add legacy scan ui for xlsx upload and batch mapping edition"
```

### Task 6: Implement Edit POST Save With Batch Validation + Merged Cell Handling

**Files:**
- Modify: `wms/views_print_templates.py`
- Create: `wms/tests/views/tests_views_print_pack_template_edit_post.py`

**Step 1: Write the failing test**

```python
response = self.client.post(edit_url, payload_with_multiple_rows_and_file)
self.assertEqual(response.status_code, 302)
self.assertEqual(PrintCellMapping.objects.filter(pack_document=doc).count(), 3)
```

Add failing cases:
- invalid source key rejected
- invalid worksheet rejected
- merged cell normalized

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_print_pack_template_edit_post -v 2`
Expected: FAIL (POST workflow missing).

**Step 3: Write minimal implementation**

On POST `action=save`:
- parse rows payload
- validate against catalog + workbook metadata
- normalize merged cells
- update `PrintCellMapping` in batch
- replace xlsx if file provided
- create new version snapshot

Use one DB transaction.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_print_pack_template_edit_post -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_print_templates.py wms/tests/views/tests_views_print_pack_template_edit_post.py
git commit -m "feat(print): implement transactional save for xlsx upload and batch mappings"
```

### Task 7: Implement Restore Action From Version History

**Files:**
- Modify: `wms/views_print_templates.py`
- Modify: `wms/tests/views/tests_views_print_pack_template_edit_post.py`

**Step 1: Write the failing test**

```python
response = self.client.post(edit_url, {"action": "restore", "version_id": v1.id})
self.assertEqual(response.status_code, 302)
self.assertEqual(active_mapping.source_key, "shipment.reference")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_print_pack_template_edit_post -v 2`
Expected: FAIL (restore not wired).

**Step 3: Write minimal implementation**

Wire restore action:
- load selected `PrintPackDocumentVersion`
- apply snapshot to current file + mappings
- persist audit snapshot `change_type=restore`

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_print_pack_template_edit_post -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_print_templates.py wms/tests/views/tests_views_print_pack_template_edit_post.py
git commit -m "feat(print): add version rollback for scan xlsx mapping editor"
```

### Task 8: Remove Legacy HTML Layout Editing Behavior From Scan Templates Flow

**Files:**
- Modify: `wms/views_print_templates.py`
- Modify: `wms/tests/views/tests_views_print_templates.py`

**Step 1: Write the failing test**

```python
response = self.client.post(edit_url, {"layout_json": "{}"})
self.assertEqual(response.status_code, 400)
```

Expected behavior:
- old layout payload no longer accepted on this flow
- no writes to `PrintTemplate` / `PrintTemplateVersion`

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_print_templates -v 2`
Expected: FAIL (legacy behavior still available).

**Step 3: Write minimal implementation**

Remove branching dependent on:
- `PrintTemplate`
- `PrintTemplateVersion`
- `layout_json`

Keep route name for backward compatibility but new semantics only.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_print_templates -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_print_templates.py wms/tests/views/tests_views_print_templates.py
git commit -m "refactor(print): retire legacy html template editing from scan templates route"
```

### Task 9: Add Migration Backfill For Initial Version Snapshots

**Files:**
- Create: `wms/migrations/<auto>_backfill_print_pack_document_versions.py`
- Create: `wms/tests/print/tests_print_pack_document_versions_backfill.py`

**Step 1: Write the failing test**

```python
self.assertEqual(PrintPackDocumentVersion.objects.filter(pack_document=doc).count(), 1)
```

Simulate document with mappings and ensure backfill creates version `1`.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.print.tests_print_pack_document_versions_backfill -v 2`
Expected: FAIL (no backfill).

**Step 3: Write minimal implementation**

Migration logic:
- iterate `PrintPackDocument`
- snapshot active mappings
- copy active xlsx if present
- create missing version `1` only

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.print.tests_print_pack_document_versions_backfill -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/migrations wms/tests/print/tests_print_pack_document_versions_backfill.py
git commit -m "feat(print): backfill initial xlsx mapping snapshots for existing pack documents"
```

### Task 10: Final Verification + Documentation

**Files:**
- Modify: `docs/operations.md`
- Create: `docs/plans/2026-03-02-print-pack-xlsx-mapping-rollout-checklist.md`

**Step 1: Write rollout checklist doc**

```markdown
- [ ] Upload xlsx from /scan/templates/<id> works
- [ ] Batch mapping save updates print output
- [ ] Restore version reverts xlsx and mappings
```

**Step 2: Run full impacted suites**

Run:
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_print_templates wms.tests.views.tests_views_print_pack_template_edit_post -v 2`
- `./.venv/bin/python manage.py test wms.tests.print.tests_print_pack_document_versions wms.tests.print.tests_print_pack_template_versions wms.tests.print.tests_print_pack_workbook -v 2`
- `./.venv/bin/python manage.py test wms.tests.print.tests_print_pack_engine -v 2`
- `./.venv/bin/python manage.py check`

Expected: PASS + no system check errors.

**Step 3: Migration integrity checks**

Run:
- `./.venv/bin/python manage.py makemigrations --check`
- `./.venv/bin/python manage.py migrate --plan`

Expected: clean migration state and deterministic plan.

**Step 4: Request review**

Use `@superpowers:requesting-code-review` and resolve findings before merge.

**Step 5: Commit**

```bash
git add docs/operations.md docs/plans/2026-03-02-print-pack-xlsx-mapping-rollout-checklist.md
git commit -m "docs(print): add rollout checklist for scan xlsx mapping editor"
```
