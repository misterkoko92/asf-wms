# Correspondent Recipient Promotion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make every `Correspondant` automatically recipient-ready, including existing contacts and future creations, by promoting them to `Destinataire` and ensuring a backing recipient organization exists.

**Architecture:** Introduce one idempotent promotion service in the legacy contacts layer, hook it into the existing tag change signal, and expose a backfill management command that reuses the same service. Keep default ASF bindings delegated to the existing `OrganizationRoleAssignment` post-save signal instead of duplicating binding logic.

**Tech Stack:** Django models/signals/management commands, legacy WMS contact and org-role domain, Django test runner

---

### Task 1: Add the failing service tests

**Files:**
- Create: `wms/tests/core/tests_correspondent_recipient_promotion.py`
- Reference: `wms/tests/core/tests_contact_filters.py`
- Reference: `wms/tests/shipment/tests_shipment_party_rules.py`

**Step 1: Write the failing test**

```python
def test_promote_correspondent_org_adds_recipient_tag_and_role(self):
    correspondent_tag = ContactTag.objects.create(name="correspondant")
    org = Contact.objects.create(
        name="Correspondent Org",
        contact_type=ContactType.ORGANIZATION,
        is_active=True,
    )

    promote_correspondent_to_recipient_ready(org, tags=[correspondent_tag])

    self.assertTrue(org.tags.filter(name__iexact="destinataire").exists())
    self.assertTrue(
        OrganizationRoleAssignment.objects.filter(
            organization=org,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
        ).exists()
    )
```

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.core.tests_correspondent_recipient_promotion -v 2
```

Expected: FAIL because the promotion service does not exist yet.

**Step 3: Write minimal implementation**

Create a dedicated service module, likely `contacts/correspondent_recipient_promotion.py`, with:

```python
def promote_correspondent_to_recipient_ready(contact, *, tags=None) -> bool:
    ...
```

Implement only enough to satisfy the organization path first.

**Step 4: Run test to verify it passes**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.core.tests_correspondent_recipient_promotion -v 2
```

Expected: PASS for the new organization test.

**Step 5: Commit**

```bash
git add contacts/correspondent_recipient_promotion.py wms/tests/core/tests_correspondent_recipient_promotion.py
git commit -m "feat: add correspondent recipient promotion service"
```

### Task 2: Extend the service for person correspondents and support-org reuse

**Files:**
- Modify: `contacts/correspondent_recipient_promotion.py`
- Modify: `wms/tests/core/tests_correspondent_recipient_promotion.py`

**Step 1: Write the failing tests**

Add tests for:

```python
def test_promote_person_with_org_reuses_existing_org(self):
    ...

def test_promote_person_without_org_creates_shared_support_org(self):
    ...

def test_promote_person_without_org_reuses_existing_support_org(self):
    ...
```

Assert that:

- a person with `organization` uses that organization
- a person without `organization` is attached to `ASF - CORRESPONDANT`
- repeated promotions reuse the same support organization instead of creating duplicates

**Step 2: Run tests to verify they fail**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.core.tests_correspondent_recipient_promotion -v 2
```

Expected: FAIL on the new person-path assertions.

**Step 3: Write minimal implementation**

Add helpers such as:

```python
SUPPORT_ORGANIZATION_NAME = "ASF - CORRESPONDANT"

def _resolve_recipient_organization(contact) -> Contact:
    ...

def _get_or_create_support_organization() -> Contact:
    ...
```

Ensure the support organization:

- is an active `ORGANIZATION`
- is reused by name
- can be marked in `notes` as technical support data

**Step 4: Run tests to verify they pass**

Run the same test module and confirm all current tests pass.

**Step 5: Commit**

```bash
git add contacts/correspondent_recipient_promotion.py wms/tests/core/tests_correspondent_recipient_promotion.py
git commit -m "feat: support person correspondents in recipient promotion"
```

### Task 3: Hook the promotion service into the tag signal

**Files:**
- Modify: `contacts/models.py`
- Modify: `wms/tests/core/tests_correspondent_recipient_promotion.py`

**Step 1: Write the failing tests**

Add signal-oriented tests such as:

```python
def test_adding_correspondent_tag_triggers_promotion(self):
    ...

def test_readding_tags_is_idempotent(self):
    ...
```

Drive the behavior through:

```python
contact.tags.add(correspondent_tag)
```

Assert that the recipient tag and role appear automatically.

**Step 2: Run tests to verify they fail**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.core.tests_correspondent_recipient_promotion -v 2
```

Expected: FAIL because the signal still only handles ASF ids and default shipper links.

**Step 3: Write minimal implementation**

Update the `Contact.tags` `post_add` handler in `contacts/models.py` to call the new promotion service before or alongside the current recipient-default-shipper logic.

Guard against recursion by making the service idempotent and safe when the recipient tag is already present.

**Step 4: Run tests to verify they pass**

Run the focused promotion test module again.

**Step 5: Commit**

```bash
git add contacts/models.py wms/tests/core/tests_correspondent_recipient_promotion.py
git commit -m "feat: trigger correspondent recipient promotion from tag changes"
```

### Task 4: Verify integration with existing recipient surfaces

**Files:**
- Modify: `wms/tests/shipment/tests_shipment_party_rules.py`
- Optionally modify: `wms/tests/core/tests_contact_filters.py`

**Step 1: Write the failing tests**

Add one integration-style test proving a promoted person correspondent linked to an organization becomes eligible through the existing recipient resolution layer:

```python
def test_promoted_correspondent_person_is_eligible_recipient_contact(self):
    ...
```

If useful, add a filter-level assertion that the contact shows up in `filter_structure_contacts(contacts_with_tags(TAG_RECIPIENT))`.

**Step 2: Run tests to verify they fail**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.core.tests_correspondent_recipient_promotion \
  wms.tests.shipment.tests_shipment_party_rules \
  -v 2
```

Expected: FAIL until the promotion state is fully aligned with the existing filters and org-role path.

**Step 3: Write minimal implementation**

Adjust the promotion service only if needed. Do not patch selectors first; use the current selector rules unless tests prove a real mismatch.

**Step 4: Run tests to verify they pass**

Run the same targeted subset again and confirm green.

**Step 5: Commit**

```bash
git add wms/tests/shipment/tests_shipment_party_rules.py wms/tests/core/tests_correspondent_recipient_promotion.py
git commit -m "test: cover promoted correspondents in recipient surfaces"
```

### Task 5: Add the backfill management command

**Files:**
- Create: `wms/management/commands/backfill_correspondent_recipients.py`
- Modify: `wms/tests/management/tests_management_backfill_correspondent_recipients.py`
- Reference: `wms/management/commands/migrate_contacts_to_org_roles.py`
- Reference: `wms/management/commands/rebuild_contacts_from_be_xlsx.py`

**Step 1: Write the failing tests**

Create command tests for:

```python
def test_dry_run_reports_changes_without_persisting(self):
    ...

def test_apply_updates_existing_correspondents(self):
    ...
```

Assert that the command:

- scans only correspondents
- reports counts
- supports `--dry-run`
- reuses `ASF - CORRESPONDANT` instead of multiplying support organizations

**Step 2: Run tests to verify they fail**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.management.tests_management_backfill_correspondent_recipients \
  -v 2
```

Expected: FAIL because the command does not exist yet.

**Step 3: Write minimal implementation**

Implement a management command with:

```python
class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--apply", action="store_true")
```

Inside `handle`, iterate correspondents and call the shared promotion service.

**Step 4: Run tests to verify they pass**

Run the focused management-command test module again.

**Step 5: Commit**

```bash
git add wms/management/commands/backfill_correspondent_recipients.py wms/tests/management/tests_management_backfill_correspondent_recipients.py
git commit -m "feat: add correspondent recipient backfill command"
```

### Task 6: Add the non-regression tests for removal behavior

**Files:**
- Modify: `wms/tests/core/tests_correspondent_recipient_promotion.py`

**Step 1: Write the failing tests**

Add:

```python
def test_removing_correspondent_tag_does_not_remove_recipient_tag(self):
    ...

def test_removing_correspondent_tag_does_not_remove_recipient_role(self):
    ...
```

Drive the case by removing the correspondent tag after promotion and asserting the promoted state remains.

**Step 2: Run tests to verify they fail if behavior regresses**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.core.tests_correspondent_recipient_promotion -v 2
```

Expected: PASS once the code is stable; these tests protect the approved additive-only rule.

**Step 3: Write minimal implementation**

No implementation may be needed. If so, keep the code unchanged and use the tests as a regression fence.

**Step 4: Run tests to verify they pass**

Run the same test module again.

**Step 5: Commit**

```bash
git add wms/tests/core/tests_correspondent_recipient_promotion.py
git commit -m "test: lock additive removal behavior for correspondents"
```

### Task 7: Run the final targeted verification set

**Files:**
- Reference only

**Step 1: Run the complete targeted suite**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.core.tests_contact_filters \
  wms.tests.core.tests_correspondent_recipient_promotion \
  wms.tests.shipment.tests_shipment_party_rules \
  wms.tests.portal.tests_default_shipper_bindings \
  wms.tests.management.tests_management_backfill_correspondent_recipients \
  -v 2
```

Expected: all targeted tests PASS.

**Step 2: Run diff hygiene**

Run:

```bash
git diff --check
```

Expected: no whitespace or patch formatting errors.

**Step 3: Commit final verification state**

```bash
git add -A
git commit -m "test: verify correspondent recipient promotion flow"
```
