# No Legacy Final Cutover Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove remaining legacy contact write paths so Scan + Public Order run without legacy fallback code.

**Architecture:** Move every contact write path to org-role primitives (organization, organization contacts, role assignments, scopes, bindings), then remove `legacy_contact_write_enabled` from runtime model/config/forms. Keep legacy shipment tracking flag out of scope for this wave.

**Tech Stack:** Django views/forms/templates, Django ORM models + migrations, Django test suite (`manage.py test`), legacy `contacts` app models reused as organization backbone.

---

### Task 1: Lock target behavior with failing tests first

**Files:**
- Modify: `wms/tests/forms/tests_forms_org_roles_gate.py`
- Modify: `wms/tests/orders/tests_order_scan_handlers.py`
- Modify: `wms/tests/public/tests_public_order_helpers.py`
- Modify: `wms/tests/views/tests_views_scan_admin.py`
- Modify: `wms/tests/views/tests_views_scan_admin_contacts_cockpit.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add tests that encode final behavior:
- Scan order creation is no longer blocked by a legacy write flag.
- Public order helper does not write `ContactTag`/`ContactAddress` legacy artifacts.
- Scan admin contacts no longer exposes legacy create/update/delete actions at all.
- Bootstrap/admin pages no longer show "legacy disabled" messaging tied to removed gate.

```python
def test_scan_order_create_form_not_gated_by_legacy_write_flag(self):
    form = ScanOrderCreateForm(data=valid_payload)
    self.assertTrue(form.is_valid())
```

```python
def test_scan_admin_contacts_never_renders_legacy_actions(self):
    response = self.client.get(reverse("scan:scan_admin_contacts"))
    self.assertNotContains(response, 'value="create_contact"')
    self.assertNotContains(response, 'value="update_contact"')
    self.assertNotContains(response, 'value="delete_contact"')
```

**Step 2: Run test to verify it fails**

Run:
`./.venv/bin/python manage.py test wms.tests.forms.tests_forms_org_roles_gate wms.tests.orders.tests_order_scan_handlers wms.tests.public.tests_public_order_helpers wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_scan_admin_contacts_cockpit wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL on legacy assumptions.

**Step 3: Write minimal implementation**

No app implementation in this task; tests only.

**Step 4: Run test to verify it still fails for the right reason**

Run same command and confirm failures map to planned removals, not unrelated regressions.

**Step 5: Commit**

```bash
git add wms/tests/forms/tests_forms_org_roles_gate.py wms/tests/orders/tests_order_scan_handlers.py wms/tests/public/tests_public_order_helpers.py wms/tests/views/tests_views_scan_admin.py wms/tests/views/tests_views_scan_admin_contacts_cockpit.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "test(cutover): lock final no-legacy behavior expectations"
```

### Task 2: Cut over Scan order creation to org-role only

**Files:**
- Modify: `wms/forms.py`
- Modify: `wms/order_scan_handlers.py`
- Modify: `templates/scan/order.html`
- Modify: `wms/tests/forms/tests_forms_org_roles_gate.py`
- Modify: `wms/tests/orders/tests_order_scan_handlers.py`

**Step 1: Write the failing test**

Add or update tests to enforce:
- `ScanOrderCreateForm.clean()` has no legacy gate check.
- `handle_order_action(..., action="create_order")` validates shipper/recipient via org-role resolvers.
- Template keeps create flow but removes legacy-oriented wording/actions.

**Step 2: Run test to verify it fails**

Run:
`./.venv/bin/python manage.py test wms.tests.forms.tests_forms_org_roles_gate wms.tests.orders.tests_order_scan_handlers -v 2`

Expected: FAIL.

**Step 3: Write minimal implementation**

Implementation details:
- Remove `is_legacy_contact_write_enabled` import/usage from `ScanOrderCreateForm.clean`.
- In `handle_order_action`, remove legacy gate branch and always run org-role validation path for create.
- Keep contact fields mandatory for create flow (shipper and recipient).
- Keep correspondent optional.
- Adjust form labels/helper links to avoid legacy CRUD framing.

```python
# before creating the order
if shipper_contact is None:
    create_form.add_error("shipper_contact", "Expediteur requis.")
if recipient_contact is None:
    create_form.add_error("recipient_contact", "Destinataire requis.")
```

**Step 4: Run test to verify it passes**

Run:
`./.venv/bin/python manage.py test wms.tests.forms.tests_forms_org_roles_gate wms.tests.orders.tests_order_scan_handlers -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/forms.py wms/order_scan_handlers.py templates/scan/order.html wms/tests/forms/tests_forms_org_roles_gate.py wms/tests/orders/tests_order_scan_handlers.py
git commit -m "feat(scan-order): remove legacy gate and enforce org-role validation"
```

### Task 3: Replace public order legacy upsert with org-role onboarding service

**Files:**
- Modify: `wms/public_order_helpers.py`
- Modify: `wms/public_order_handlers.py`
- Modify: `wms/contact_payloads.py`
- Modify: `wms/views_public_order.py`
- Modify: `templates/scan/public_order.html`
- Modify: `wms/tests/public/tests_public_order_helpers.py`
- Modify: `wms/tests/views/tests_views_public_order.py`

**Step 1: Write the failing test**

Cover:
- Public order contact upsert no longer writes `ContactTag` or `ContactAddress`.
- Existing organization match remains supported (by id/name).
- New organization onboarding creates org-role structures (`OrganizationRoleAssignment`, `OrganizationContact`, `OrganizationRoleContact`) instead of legacy side-effects.
- Frontend payload no longer depends on `association_contact_id`.

**Step 2: Run test to verify it fails**

Run:
`./.venv/bin/python manage.py test wms.tests.public.tests_public_order_helpers wms.tests.views.tests_views_public_order -v 2`

Expected: FAIL.

**Step 3: Write minimal implementation**

Refactor `upsert_public_order_contact` into org-role-safe behavior:
- Resolve/create `Contact(contact_type=organization, is_active=True)`.
- Ensure recipient role assignment + primary organization contact records exist.
- Stop creating/updating legacy `ContactAddress` and `ContactTag`.
- Update payload builder for public form autocomplete to query org-role-backed organizations.
- Remove hidden `association_contact_id` dependency from template + JS.

```python
assignment, _ = OrganizationRoleAssignment.objects.get_or_create(
    organization=organization,
    role=OrganizationRole.RECIPIENT,
    defaults={"is_active": True},
)
```

**Step 4: Run test to verify it passes**

Run:
`./.venv/bin/python manage.py test wms.tests.public.tests_public_order_helpers wms.tests.views.tests_views_public_order -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/public_order_helpers.py wms/public_order_handlers.py wms/contact_payloads.py wms/views_public_order.py templates/scan/public_order.html wms/tests/public/tests_public_order_helpers.py wms/tests/views/tests_views_public_order.py
git commit -m "feat(public-order): migrate association onboarding to org-role model"
```

### Task 4: Remove legacy contact CRUD from Scan admin contacts

**Files:**
- Modify: `wms/views_scan_admin.py`
- Modify: `templates/scan/admin_contacts.html`
- Modify: `wms/tests/views/tests_views_scan_admin.py`
- Modify: `wms/tests/views/tests_views_scan_admin_contacts_cockpit.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Cover:
- No more `create_contact`, `update_contact`, `delete_contact` actions.
- No `ScanAdminContactForm` create/edit sections rendered.
- Org-role cockpit actions still available and functional.
- Admin fallback links remain visible.

**Step 2: Run test to verify it fails**

Run:
`./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_scan_admin_contacts_cockpit wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL.

**Step 3: Write minimal implementation**

Implementation details:
- Delete legacy action constants and action branches.
- Remove legacy gate variable/context.
- Drop template blocks wrapped around `legacy_contact_write_enabled`.
- Keep only cockpit forms + readonly tables + admin rescue links.

```python
# remove branch:
# if action == ACTION_CREATE_CONTACT: ...
# if action == ACTION_UPDATE_CONTACT: ...
# if action == ACTION_DELETE_CONTACT: ...
```

**Step 4: Run test to verify it passes**

Run:
`./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_scan_admin_contacts_cockpit wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_scan_admin.py templates/scan/admin_contacts.html wms/tests/views/tests_views_scan_admin.py wms/tests/views/tests_views_scan_admin_contacts_cockpit.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat(scan-admin): remove legacy contact CRUD surface"
```

### Task 5: Remove runtime flag `legacy_contact_write_enabled` from domain model and config

**Files:**
- Modify: `wms/models_domain/integration.py`
- Modify: `wms/runtime_settings.py`
- Modify: `wms/forms_scan_settings.py`
- Modify: `wms/views_scan_settings.py`
- Modify: `wms/organization_role_resolvers.py`
- Modify: `wms/forms.py`
- Modify: `wms/order_scan_handlers.py`
- Modify: `wms/public_order_helpers.py`
- Create: `wms/migrations/0074_remove_legacy_contact_write_enabled.py`
- Modify: `wms/tests/core/tests_runtime_role_migration_flags.py`
- Modify: `wms/tests/forms/tests_forms_scan_settings.py`
- Modify: `wms/tests/views/tests_views_scan_settings.py`
- Modify: `wms/tests/domain/tests_domain_orders_org_roles.py`

**Step 1: Write the failing test**

Add/update tests to assert:
- Runtime config no longer exposes `legacy_contact_write_enabled`.
- Runtime settings form/changed-fields do not track removed flag.
- Role migration flag tests only cover `org_roles_engine_enabled` and review threshold.

**Step 2: Run test to verify it fails**

Run:
`./.venv/bin/python manage.py test wms.tests.core.tests_runtime_role_migration_flags wms.tests.forms.tests_forms_scan_settings wms.tests.views.tests_views_scan_settings wms.tests.domain.tests_domain_orders_org_roles -v 2`

Expected: FAIL.

**Step 3: Write minimal implementation**

Implementation details:
- Remove model field + defaults + save logic references.
- Remove dataclass/config field and fallback setting read.
- Remove helper `is_legacy_contact_write_enabled()`.
- Remove remaining imports/calls.
- Add schema migration dropping column.

```python
class RuntimeConfig:
    # removed: legacy_contact_write_enabled
    org_roles_engine_enabled: bool
```

**Step 4: Run test to verify it passes**

Run:
`./.venv/bin/python manage.py test wms.tests.core.tests_runtime_role_migration_flags wms.tests.forms.tests_forms_scan_settings wms.tests.views.tests_views_scan_settings wms.tests.domain.tests_domain_orders_org_roles -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/models_domain/integration.py wms/runtime_settings.py wms/forms_scan_settings.py wms/views_scan_settings.py wms/organization_role_resolvers.py wms/forms.py wms/order_scan_handlers.py wms/public_order_helpers.py wms/migrations/0074_remove_legacy_contact_write_enabled.py wms/tests/core/tests_runtime_role_migration_flags.py wms/tests/forms/tests_forms_scan_settings.py wms/tests/views/tests_views_scan_settings.py wms/tests/domain/tests_domain_orders_org_roles.py
git commit -m "refactor(runtime): remove legacy contact write flag end-to-end"
```

### Task 6: Remove dead references and align docs

**Files:**
- Modify: `docs/plans/2026-03-04-organization-roles-contact-governance-rollout-checklist.md`
- Modify: `docs/operations.md`
- Modify: `docs/backlog.md` (only items tied to removed legacy contact write gate)

**Step 1: Write the failing test**

Create a grep-based regression check in local verification notes:

```bash
rg -n "legacy_contact_write_enabled|is_legacy_contact_write_enabled|action\\\" value=\\\"create_contact|action\\\" value=\\\"update_contact|action\\\" value=\\\"delete_contact" wms templates
```

Expected after implementation: no runtime code hits.

**Step 2: Run check to verify it fails before cleanup**

Run command above and capture remaining references.

**Step 3: Write minimal implementation**

Remove stale docs/code comments and update rollout wording to final no-legacy state.

**Step 4: Run check to verify it passes**

Run same `rg` command; expected: zero runtime/template references (docs can keep historical notes only if explicitly marked archival).

**Step 5: Commit**

```bash
git add docs/plans/2026-03-04-organization-roles-contact-governance-rollout-checklist.md docs/operations.md docs/backlog.md
git commit -m "docs(cutover): update runbooks for final no-legacy state"
```

### Task 7: Full verification matrix before merge

**Files:**
- Modify: `docs/plans/2026-03-05-no-legacy-final-cutover-verification.md`

**Step 1: Run targeted suites**

Run:
- `./.venv/bin/python manage.py test wms.tests.forms.tests_forms_org_roles_gate -v 2`
- `./.venv/bin/python manage.py test wms.tests.orders.tests_order_scan_handlers -v 2`
- `./.venv/bin/python manage.py test wms.tests.public.tests_public_order_helpers -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_public_order -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`
- `./.venv/bin/python manage.py test wms.tests.core.tests_runtime_role_migration_flags wms.tests.forms.tests_forms_scan_settings wms.tests.views.tests_views_scan_settings -v 2`

Expected: PASS.

**Step 2: Run integration/regression slice**

Run:
- `./.venv/bin/python manage.py test wms.tests.domain.tests_domain_orders_org_roles wms.tests.domain.tests_domain_orders_extra wms.tests.forms.tests_forms wms.tests.views.tests_views -v 2`

Expected: PASS or documented unrelated failures.

**Step 3: Run migration and smoke checks**

Run:
- `./.venv/bin/python manage.py migrate`
- `./.venv/bin/python manage.py test wms.tests.core.tests_runtime_settings -v 2`

Expected:
- migration applies cleanly,
- runtime config tests pass with removed field.

**Step 4: Write verification report**

Document:
- executed commands,
- pass/fail counts,
- residual risks,
- explicit go/no-go decision.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-05-no-legacy-final-cutover-verification.md
git commit -m "docs(verification): capture final no-legacy cutover evidence"
```
