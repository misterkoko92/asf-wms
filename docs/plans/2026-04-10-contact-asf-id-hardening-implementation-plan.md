# Contact ASF ID Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `Contact.asf_id` the canonical identifier for contacts and structures by auto-generating it for new rows, backfilling existing rows, and preferring it on critical resolution paths.

**Architecture:** Introduce one shared `asf_id` helper under `contacts/` that owns generation and missing-ID backfill. Wire that helper into `Contact.save()` and a dedicated management command, then update the critical runtime resolution paths to prefer exact `asf_id` while keeping bounded legacy fallback by name.

**Tech Stack:** Django models, Django management commands, legacy Django service modules, Django `TestCase`, `./.venv/bin/python manage.py test`

---

### Task 1: Add the shared ASF ID helper

**Files:**
- Create: `contacts/asf_ids.py`
- Test: `contacts/tests/test_asf_ids.py`

**Step 1: Write the failing helper tests**

```python
from django.test import TestCase

from contacts.asf_ids import build_generated_asf_id


class ContactAsfIdsTests(TestCase):
    def test_build_generated_asf_id_uses_reserved_namespace(self):
        self.assertEqual(build_generated_asf_id(42), "ASF-C-00000042")

    def test_build_generated_asf_id_rejects_missing_pk(self):
        with self.assertRaises(ValueError):
            build_generated_asf_id(None)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test contacts.tests.test_asf_ids -v 2`

Expected: FAIL because `contacts.asf_ids` does not exist yet.

**Step 3: Write minimal implementation**

```python
def build_generated_asf_id(contact_pk: int | None) -> str:
    if not contact_pk:
        raise ValueError("Contact primary key is required.")
    return f"ASF-C-{contact_pk:08d}"
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test contacts.tests.test_asf_ids -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add contacts/asf_ids.py contacts/tests/test_asf_ids.py
git commit -m "feat: add shared contact asf id helper"
```

### Task 2: Auto-generate ASF IDs for new contacts

**Files:**
- Modify: `contacts/models.py`
- Modify: `contacts/tests/tests_models.py`
- Test: `contacts/tests/test_asf_ids.py`

**Step 1: Write the failing model tests**

Add tests that prove:

```python
def test_contact_save_generates_asf_id_for_new_contact(self):
    contact = Contact.objects.create(
        name="Generated Org",
        contact_type=ContactType.ORGANIZATION,
    )
    self.assertEqual(contact.asf_id, f"ASF-C-{contact.pk:08d}")


def test_contact_save_does_not_override_existing_asf_id(self):
    contact = Contact.objects.create(
        name="Existing Org",
        contact_type=ContactType.ORGANIZATION,
        asf_id="PFX-9999",
    )
    self.assertEqual(contact.asf_id, "PFX-9999")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test contacts.tests.tests_models contacts.tests.test_asf_ids -v 2`

Expected: FAIL because new contacts still save without generated `asf_id`.

**Step 3: Write minimal implementation**

Implement a small helper in `contacts/asf_ids.py` such as `ensure_contact_asf_id(contact)` and
call it from `Contact.save()` only after the initial insert when:

- `self.pk` exists
- `self.asf_id` is empty

Keep the update localized and never overwrite a defined value.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test contacts.tests.tests_models contacts.tests.test_asf_ids -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add contacts/models.py contacts/asf_ids.py contacts/tests/tests_models.py contacts/tests/test_asf_ids.py
git commit -m "feat: auto-generate asf ids for new contacts"
```

### Task 3: Add the backfill command for existing contacts

**Files:**
- Create: `contacts/management/commands/backfill_contact_asf_ids.py`
- Test: `contacts/tests/test_backfill_contact_asf_ids.py`

**Step 1: Write the failing command tests**

Cover these cases:

```python
def test_dry_run_reports_missing_contacts_without_writing(self):
    ...


def test_apply_assigns_asf_ids_only_to_missing_contacts(self):
    ...


def test_apply_keeps_existing_manual_asf_ids(self):
    ...
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test contacts.tests.test_backfill_contact_asf_ids -v 2`

Expected: FAIL because the command does not exist.

**Step 3: Write minimal implementation**

Create a command with:

- `--dry-run`
- `--apply`
- a guard that defaults to dry-run behavior unless `--apply` is passed
- summary output showing how many contacts were missing an `asf_id`

Use the shared helper to assign IDs. Iterate over every `Contact` with missing `asf_id`,
including inactive rows.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test contacts.tests.test_backfill_contact_asf_ids -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add contacts/management/commands/backfill_contact_asf_ids.py contacts/tests/test_backfill_contact_asf_ids.py contacts/asf_ids.py
git commit -m "feat: add contact asf id backfill command"
```

### Task 4: Harden default ASF shipper resolution

**Files:**
- Modify: `wms/default_shipper_bindings.py`
- Modify: `wms/admin_account_request_approval.py`
- Test: `wms/tests/portal/tests_default_shipper_bindings.py`
- Test: `wms/tests/portal/tests_portal_role_review_gate.py`

**Step 1: Write the failing resolution tests**

Add tests that prove:

```python
def test_resolve_default_shipper_prefers_matching_asf_id_over_name(self):
    ...


def test_recipient_approval_still_rejects_when_no_default_shipper_can_be_resolved(self):
    ...
```

Use one canonical `asf_id` constant for the ASF default shipper in the test fixtures.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.portal.tests_default_shipper_bindings wms.tests.portal.tests_portal_role_review_gate -v 2`

Expected: FAIL because `_resolve_default_shipper()` still anchors on organization name first.

**Step 3: Write minimal implementation**

Refactor `wms/default_shipper_bindings.py` so `_resolve_default_shipper()`:

1. prefers an active organization with the canonical ASF `asf_id`
2. falls back to the current name-based lookup only when the canonical ID does not resolve

Keep the canonical ASF identifier in one small constant/helper, not repeated inline in multiple
modules. Update `wms/admin_account_request_approval.py` only as needed to align with the new
resolver behavior.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.portal.tests_default_shipper_bindings wms.tests.portal.tests_portal_role_review_gate -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/default_shipper_bindings.py wms/admin_account_request_approval.py wms/tests/portal/tests_default_shipper_bindings.py wms/tests/portal/tests_portal_role_review_gate.py
git commit -m "feat: prefer asf id for default shipper resolution"
```

### Task 5: Harden contact import reuse by ASF ID

**Files:**
- Modify: `wms/import_services_contacts.py`
- Modify: `wms/tests/imports/tests_import_services_contacts_extra.py`

**Step 1: Write the failing import tests**

Add tests that prove:

```python
def test_import_contacts_reuses_existing_contact_by_exact_asf_id(self):
    ...


def test_import_contacts_creates_contact_without_input_asf_id_and_generated_id_is_assigned(self):
    ...
```

Keep the existing preservation test for manual `asf_id` values.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.imports.tests_import_services_contacts_extra -v 2`

Expected: FAIL because the importer still looks up contacts by `name__iexact` first.

**Step 3: Write minimal implementation**

Change `wms/import_services_contacts.py` so the importer:

1. looks up by exact `asf_id` when the row provides one
2. falls back to the current nominal lookup only when `asf_id` is absent
3. keeps the existing rule that an already populated `asf_id` is not silently replaced

Do not duplicate generation logic in the importer. Let the model-level generation path handle new
contacts created without an input ID.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.imports.tests_import_services_contacts_extra -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/import_services_contacts.py wms/tests/imports/tests_import_services_contacts_extra.py
git commit -m "feat: prefer asf id in contact imports"
```

### Task 6: Harden shared-profile and sync reuse paths

**Files:**
- Modify: `wms/application/parties/use_cases.py`
- Modify: `wms/parties/sync.py`
- Test: `wms/tests/core/tests_parties_use_cases.py`
- Test: `wms/tests/portal/tests_portal_recipient_sync.py`

**Step 1: Write the failing reuse tests**

Add tests that prove:

```python
def test_shared_profile_reuses_existing_structure_by_asf_id_when_available(self):
    ...


def test_portal_recipient_sync_prefers_asf_id_before_exact_name(self):
    ...
```

Include one fallback regression test proving that exact-name reuse still works when the legacy
input has no `asf_id`.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_parties_use_cases wms.tests.portal.tests_portal_recipient_sync -v 2`

Expected: FAIL because the relevant helpers still only reuse by exact name/email/person fields.

**Step 3: Write minimal implementation**

Refactor the critical reuse helpers so they can accept or derive `asf_id` where available and
prefer it before nominal fallback. Keep the fallback explicit and local to the affected helper
functions.

Do not attempt a full rewrite of all projection and rebuild flows in this task.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_parties_use_cases wms.tests.portal.tests_portal_recipient_sync -v 2`

Expected: PASS

**Step 5: Commit**

```bash
git add wms/application/parties/use_cases.py wms/parties/sync.py wms/tests/core/tests_parties_use_cases.py wms/tests/portal/tests_portal_recipient_sync.py
git commit -m "feat: prefer asf id in recipient reuse paths"
```

### Task 7: Run the cross-cutting verification set

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Update docs only if the runtime contract changed in a user-visible or maintenance-critical way**

If implementation changes the canonical maintenance contract, add a concise note to the relevant
repo-reference sections about:

- `Contact.asf_id` as the preferred identifier for contact/structure reuse
- temporary nominal fallback during the transition

Do not update repo-reference docs if the implementation remains fully internal and the runtime
maintenance contract is unchanged.

**Step 2: Run the focused verification suite**

Run:

```bash
./.venv/bin/python manage.py test \
  contacts.tests.tests_models \
  contacts.tests.test_asf_ids \
  contacts.tests.test_backfill_contact_asf_ids \
  wms.tests.imports.tests_import_services_contacts_extra \
  wms.tests.portal.tests_default_shipper_bindings \
  wms.tests.portal.tests_portal_role_review_gate \
  wms.tests.core.tests_parties_use_cases \
  wms.tests.portal.tests_portal_recipient_sync \
  -v 2
```

Expected: PASS

**Step 3: Run one admin-adjacent regression slice**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.scan.tests_admin_contacts_duplicate_detection \
  wms.tests.scan.tests_admin_contacts_contact_service \
  wms.tests.views.tests_views_scan_admin_contacts_crud \
  -v 2
```

Expected: PASS

**Step 4: Commit**

```bash
git add docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md
git commit -m "docs: record contact asf id hardening contract"
```

### Task 8: Dry-run and apply the backfill locally

**Files:**
- No source changes expected

**Step 1: Run the dry-run**

Run:

```bash
./.venv/bin/python manage.py backfill_contact_asf_ids --dry-run
```

Expected: reports the number of contacts missing an `asf_id`, with no database writes.

**Step 2: Run the apply mode**

Run:

```bash
./.venv/bin/python manage.py backfill_contact_asf_ids --apply
```

Expected: assigns generated IDs only to rows that were missing one.

**Step 3: Re-run the dry-run to verify idempotence**

Run:

```bash
./.venv/bin/python manage.py backfill_contact_asf_ids --dry-run
```

Expected: reports zero pending changes.

**Step 4: Commit operational note if needed**

If rollout notes or runbook text changed as part of the implementation, commit those changes with:

```bash
git add <updated-doc-files>
git commit -m "docs: add contact asf id rollout notes"
```
