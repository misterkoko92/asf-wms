# Org-Roles-Only Final Purge Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove every remaining runtime and test dependency on legacy contact management and finish the repository as a verified org-roles-only system.

**Architecture:** Execute the purge in two checkpoints: first remove all runtime and active-test legacy reads/writes while keeping the old schema in place for controlled transition, then delete the legacy schema and migration-review remnants once no runtime path references them. Prove completion with repo guardrails, full coverage, and a final canonical reset.

**Tech Stack:** Django ORM models and migrations, Django admin, Django templates/views/forms, scan/import/export services, `manage.py test`, `uv run make coverage`, canonical BE rebuild commands.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:verification-before-completion`, `@superpowers:systematic-debugging`, `@superpowers:requesting-code-review`.

### Task 1: Lock org-roles-only guardrails before deleting behavior

**Files:**
- Create: `wms/tests/core/tests_org_roles_only_guardrails.py`
- Modify: `wms/tests/core/tests_contact_filters.py`
- Modify: `contacts/tests/tests_admin.py`
- Modify: `wms/tests/portal/tests_portal_recipient_sync.py`

**Step 1: Write the failing test**

Add guard tests that fail when forbidden legacy runtime symbols remain in active code paths or when key surfaces still expose legacy controls.

```python
FORBIDDEN = [
    "ContactTag",
    ".tags",
    ".destination",
    ".destinations",
    "linked_shippers",
    "legacy_contact",
]

def test_runtime_code_has_no_legacy_contact_symbols(self):
    violations = scan_runtime_files(FORBIDDEN, allowlist=ALLOWLIST)
    self.assertEqual(violations, [])
```

Add behavior tests that enforce:
- Django admin form no longer exposes `tags`, `destinations`, or `linked_shippers`.
- Portal sync no longer falls back to a legacy synced contact search.
- Old contact filter helpers are either deleted or unreachable from runtime.

**Step 2: Run test to verify it fails**

Run:
`./.venv/bin/python manage.py test wms.tests.core.tests_org_roles_only_guardrails wms.tests.core.tests_contact_filters contacts.tests.tests_admin wms.tests.portal.tests_portal_recipient_sync -v 2`

Expected: FAIL on current legacy references.

**Step 3: Write minimal implementation**

No runtime implementation yet; tests only.

**Step 4: Run test to verify it still fails for the right reason**

Run the same command and confirm the failures point to the intended legacy surfaces.

**Step 5: Commit**

```bash
git add wms/tests/core/tests_org_roles_only_guardrails.py wms/tests/core/tests_contact_filters.py contacts/tests/tests_admin.py wms/tests/portal/tests_portal_recipient_sync.py
git commit -m "test(org-roles): add no-legacy guardrails"
```

### Task 2: Remove legacy surfaces from Django admin

**Files:**
- Modify: `contacts/admin.py`
- Modify: `contacts/tests/tests_admin.py`
- Modify: `wms/admin.py`
- Modify: `wms/tests/admin/test_admin_billing.py`

**Step 1: Write the failing test**

Extend admin tests to enforce:
- `ContactAdmin` exposes only org-role-safe fields.
- `ContactTagAdmin` is gone.
- legacy list filters and fieldsets are removed.
- org-role-related admins remain reachable.

```python
def test_contact_admin_excludes_legacy_fields(self):
    admin = ContactAdmin(Contact, admin.site)
    self.assertNotIn("tags", admin.filter_horizontal)
    self.assertNotIn("destinations", admin.filter_horizontal)
    self.assertNotIn("linked_shippers", admin.filter_horizontal)
```

**Step 2: Run test to verify it fails**

Run:
`./.venv/bin/python manage.py test contacts.tests.tests_admin wms.tests.admin.test_admin_billing -v 2`

Expected: FAIL.

**Step 3: Write minimal implementation**

Implementation details:
- strip legacy help text and field wiring from `ContactAdminForm`;
- remove `ContactTagAdmin`;
- reduce the contact admin form to identity, organization membership, addresses, status, and read-only identifiers;
- ensure role/scopes/bindings remain manageable through existing org-role admins or dedicated inlines if already present.

**Step 4: Run test to verify it passes**

Run:
`./.venv/bin/python manage.py test contacts.tests.tests_admin wms.tests.admin.test_admin_billing -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add contacts/admin.py contacts/tests/tests_admin.py wms/admin.py wms/tests/admin/test_admin_billing.py
git commit -m "feat(admin): remove legacy contact admin surfaces"
```

### Task 3: Replace scan contact import and export with org-role-only contracts

**Files:**
- Modify: `wms/import_services_contacts.py`
- Modify: `wms/import_services_tags.py`
- Modify: `wms/scan_import_handlers.py`
- Modify: `wms/exports.py`
- Modify: `wms/tests/imports/tests_import_services_contacts.py`
- Modify: `wms/tests/scan/tests_scan_import_handlers.py`
- Modify: `wms/tests/exports/tests_exports.py`

**Step 1: Write the failing test**

Cover:
- contact import rejects or ignores legacy columns without creating legacy artifacts;
- scan import selector data no longer includes `contact_tags`;
- contact export no longer emits `tags`, `destinations`, `linked_shippers`, or `destination` columns.

```python
def test_export_contacts_csv_has_org_role_columns_only(self):
    response = export_contacts_csv()
    header = response.content.decode("utf-8-sig").splitlines()[0]
    self.assertNotIn("linked_shippers", header)
    self.assertNotIn("destinations", header)
    self.assertNotIn("tags", header)
```

**Step 2: Run test to verify it fails**

Run:
`./.venv/bin/python manage.py test wms.tests.imports.tests_import_services_contacts wms.tests.scan.tests_scan_import_handlers wms.tests.exports.tests_exports -v 2`

Expected: FAIL.

**Step 3: Write minimal implementation**

Implementation details:
- redesign `import_contacts` around org-role-safe columns only;
- remove `ContactTag` creation and tag parsing from contact import;
- stop returning `contact_tags` in scan selector payloads;
- replace the exported flat legacy columns with canonical org-role columns, for example:
  - `roles`
  - `organization_contacts`
  - `shipper_scopes`
  - `recipient_bindings`
  - `primary_destination_correspondent`

**Step 4: Run test to verify it passes**

Run:
`./.venv/bin/python manage.py test wms.tests.imports.tests_import_services_contacts wms.tests.scan.tests_scan_import_handlers wms.tests.exports.tests_exports -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/import_services_contacts.py wms/import_services_tags.py wms/scan_import_handlers.py wms/exports.py wms/tests/imports/tests_import_services_contacts.py wms/tests/scan/tests_scan_import_handlers.py wms/tests/exports/tests_exports.py
git commit -m "feat(scan): replace legacy contact import export contracts"
```

### Task 4: Remove legacy helper modules and portal fallbacks

**Files:**
- Modify: `wms/portal_recipient_sync.py`
- Modify: `wms/view_utils.py`
- Modify: `wms/forms.py`
- Modify: `contacts/destination_scope.py`
- Modify: `contacts/correspondent_recipient_promotion.py`
- Delete: `wms/contact_filters.py`
- Modify: `wms/tests/forms/tests_forms.py`
- Modify: `wms/tests/portal/tests_portal_recipient_sync.py`
- Modify: `contacts/tests/tests_destination_scope.py`
- Modify: `wms/tests/core/tests_contact_filters.py`

**Step 1: Write the failing test**

Cover:
- portal sync resolves only marker-based or org-role-safe contacts;
- no runtime import path relies on `wms.contact_filters`;
- correspondent promotion no longer uses legacy tags or destination M2M syncing;
- shipment forms still resolve valid org-role recipients and correspondents after helper removal.

```python
def test_sync_association_recipient_does_not_use_legacy_lookup(self):
    with self.assertNumQueries(expected_queries):
        sync_association_recipient_to_contact(recipient)
    self.assertFalse(hasattr(module, "_find_legacy_synced_contact"))
```

**Step 2: Run test to verify it fails**

Run:
`./.venv/bin/python manage.py test wms.tests.forms.tests_forms wms.tests.portal.tests_portal_recipient_sync contacts.tests.tests_destination_scope wms.tests.core.tests_contact_filters -v 2`

Expected: FAIL.

**Step 3: Write minimal implementation**

Implementation details:
- delete legacy portal fallback helper and route all matching through current org-role-safe identifiers;
- remove or inline old `view_utils` contact-tag lookup utilities;
- delete `wms/contact_filters.py` and update every importer to org-role resolvers;
- refactor correspondent promotion so it either becomes org-role-native or is deleted if no longer needed.

**Step 4: Run test to verify it passes**

Run:
`./.venv/bin/python manage.py test wms.tests.forms.tests_forms wms.tests.portal.tests_portal_recipient_sync contacts.tests.tests_destination_scope wms.tests.core.tests_contact_filters -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/portal_recipient_sync.py wms/view_utils.py wms/forms.py contacts/destination_scope.py contacts/correspondent_recipient_promotion.py wms/tests/forms/tests_forms.py wms/tests/portal/tests_portal_recipient_sync.py contacts/tests/tests_destination_scope.py wms/tests/core/tests_contact_filters.py
git rm wms/contact_filters.py
git commit -m "feat(runtime): remove legacy contact helper paths"
```

### Task 5: Remove migration-review runtime dependencies

**Files:**
- Modify: `wms/admin_organization_roles_review.py`
- Modify: `wms/models_domain/portal.py`
- Modify: `wms/management/commands/export_org_roles_review_template.py`
- Modify: `wms/tests/portal/tests_organization_roles_review.py`
- Modify: `wms/tests/management/tests_management_export_org_roles_review_template.py`

**Step 1: Write the failing test**

Cover:
- no runtime code reads `legacy_contact`;
- migration review tooling is either removed or rewritten to be organization-only;
- export template no longer exposes legacy-contact columns.

```python
def test_review_template_has_no_legacy_contact_columns(self):
    header = build_review_template_header()
    self.assertNotIn("legacy_contact", header)
```

**Step 2: Run test to verify it fails**

Run:
`./.venv/bin/python manage.py test wms.tests.portal.tests_organization_roles_review wms.tests.management.tests_management_export_org_roles_review_template -v 2`

Expected: FAIL.

**Step 3: Write minimal implementation**

Implementation details:
- if migration review remains useful, make it organization-only and binding/scope-based;
- otherwise delete the review view and export command entirely;
- remove `legacy_contact` usage from runtime model logic before schema deletion.

**Step 4: Run test to verify it passes**

Run:
`./.venv/bin/python manage.py test wms.tests.portal.tests_organization_roles_review wms.tests.management.tests_management_export_org_roles_review_template -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/admin_organization_roles_review.py wms/models_domain/portal.py wms/management/commands/export_org_roles_review_template.py wms/tests/portal/tests_organization_roles_review.py wms/tests/management/tests_management_export_org_roles_review_template.py
git commit -m "feat(portal): remove legacy migration review runtime dependencies"
```

### Task 6: Align all active fixtures and secondary domains to org-roles-only

**Files:**
- Modify: `api/tests/tests_ui_endpoints.py`
- Modify: `api/tests/tests_ui_e2e_workflows.py`
- Modify: `wms/tests/views/tests_views.py`
- Modify: `wms/tests/receipt/test_receipt_association_billing_fields.py`
- Modify: `wms/tests/planning/tests_*`
- Modify: `wms/tests/print/tests_*`
- Modify: `wms/tests/portal/tests_*`

**Step 1: Write the failing test**

Add or update tests so that:
- no active fixture creates `ContactTag` or uses `destinations.add(...)` / `linked_shippers.add(...)`;
- planning, print, volunteer, and communication tests pass with org-role-only fixtures;
- any direct legacy fixture helper fails loudly.

```python
def assert_org_roles_fixture(contact):
    self.assertFalse(hasattr(contact, "linked_shippers"))
```

**Step 2: Run test to verify it fails**

Run a focused suite:
`./.venv/bin/python manage.py test api.tests.tests_ui_endpoints api.tests.tests_ui_e2e_workflows wms.tests.views.tests_views wms.tests.receipt.test_receipt_association_billing_fields -v 2`

Expected: FAIL where fixtures still assume legacy fields.

**Step 3: Write minimal implementation**

Implementation details:
- centralize org-role fixture builders;
- replace remaining legacy setup patterns with `OrganizationRoleAssignment`, `ShipperScope`, `RecipientBinding`, and `Destination.correspondent_contact`;
- confirm planning/print/volunteer domains do not need runtime code changes beyond fixtures.

**Step 4: Run test to verify it passes**

Run the focused suite again, then expand to any planning/print suites touched.

Expected: PASS.

**Step 5: Commit**

```bash
git add api/tests/tests_ui_endpoints.py api/tests/tests_ui_e2e_workflows.py wms/tests/views/tests_views.py wms/tests/receipt/test_receipt_association_billing_fields.py wms/tests/planning wms/tests/print wms/tests/portal
git commit -m "test(org-roles): align active fixtures and secondary domains"
```

### Task 7: Delete the legacy schema

**Files:**
- Modify: `contacts/models.py`
- Modify: `contacts/querysets.py`
- Modify: `contacts/rules.py`
- Modify: `contacts/__init__.py`
- Modify: `wms/contact_rebuild.py`
- Modify: `wms/reset_operational_data.py`
- Modify: `wms/models.py`
- Modify: `wms/models_domain/portal.py`
- Create: `contacts/migrations/0008_remove_legacy_contact_fields.py`
- Create: `wms/migrations/0090_remove_legacy_contact_review_fields.py`

**Step 1: Write the failing test**

Add schema-level and runtime tests that enforce:
- `ContactTag` model is gone from runtime imports;
- `Contact` no longer defines `destination`, `destinations`, `linked_shippers`, or `tags`;
- canonical rebuild no longer creates legacy tags;
- migration review no longer exposes `legacy_contact`.

```python
def test_contact_model_has_no_legacy_fields(self):
    field_names = {field.name for field in Contact._meta.get_fields()}
    self.assertNotIn("destinations", field_names)
    self.assertNotIn("linked_shippers", field_names)
    self.assertNotIn("tags", field_names)
```

**Step 2: Run test to verify it fails**

Run:
`./.venv/bin/python manage.py test contacts.tests.tests_models wms.tests.management.tests_management_rebuild_contacts_from_be_xlsx wms.tests.core.tests_org_roles_only_guardrails -v 2`

Expected: FAIL.

**Step 3: Write minimal implementation**

Implementation details:
- remove legacy model fields and helper modules from runtime imports;
- stop creating legacy tags during canonical rebuild;
- add forward migrations that drop obsolete schema;
- update reset logic so it no longer references `contacts.ContactTag`.

**Step 4: Run test to verify it passes**

Run:
`./.venv/bin/python manage.py test contacts.tests.tests_models wms.tests.management.tests_management_rebuild_contacts_from_be_xlsx wms.tests.core.tests_org_roles_only_guardrails -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add contacts/models.py contacts/querysets.py contacts/rules.py contacts/__init__.py wms/contact_rebuild.py wms/reset_operational_data.py wms/models.py wms/models_domain/portal.py contacts/migrations/0008_remove_legacy_contact_fields.py wms/migrations/0090_remove_legacy_contact_review_fields.py
git commit -m "feat(schema): remove legacy contact schema"
```

### Task 8: Run full verification and prepare the final reset

**Files:**
- Modify: `audits/reports/2026-03-18_org-roles-only-final-purge-baseline-audit.md`
- Modify: `audits/projects/asf-wms.md`
- Modify: `docs/plans/2026-03-18-org-roles-only-final-purge-design.md`
- Modify: `docs/plans/2026-03-18-org-roles-only-final-purge-implementation-plan.md`

**Step 1: Write the failing test**

No new product test here; this task verifies the completed implementation and updates evidence.

**Step 2: Run verification**

Run, in order:
- `./.venv/bin/python manage.py makemigrations --check`
- `./.venv/bin/python manage.py test wms.tests.core.tests_org_roles_only_guardrails -v 2`
- `COVERAGE_FAIL_UNDER=93 TEST_PARALLEL=4 uv run make coverage`
- `./.venv/bin/python manage.py rebuild_contacts_org_roles_canonical --source /absolute/path/to/BE_2024_2025_2026.xlsx --dry-run`

Expected:
- no pending migrations,
- guardrails pass,
- coverage threshold met,
- canonical rebuild dry-run succeeds without legacy artifacts.

**Step 3: Update audit evidence**

Fill the audit report with:
- confirmed removed surfaces,
- commands run and results,
- residual risks if any,
- final recommendation for the production reset.

**Step 4: Commit**

```bash
git add audits/reports/2026-03-18_org-roles-only-final-purge-baseline-audit.md audits/projects/asf-wms.md docs/plans/2026-03-18-org-roles-only-final-purge-design.md docs/plans/2026-03-18-org-roles-only-final-purge-implementation-plan.md
git commit -m "docs(org-roles): record final purge verification evidence"
```
