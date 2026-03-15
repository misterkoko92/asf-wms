# Recipient Selector Scope Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure promoted correspondents inherit destination scope and make the Scan shipment `Destinataire` selector show only recipients truly authorized for the selected `destination + shipper`.

**Architecture:** Fix the problem at the source by teaching the correspondent promotion service to derive destination scope from `Destination.correspondent_contact`, then reuse that same logic in the additive backfill path. Keep the server-side org-role gate unchanged and tighten the legacy Scan UI by removing non-authorized recipients from the rendered option list instead of leaving them visible-but-disabled.

**Tech Stack:** Django models/forms/management commands, legacy Scan JavaScript, Django test runner, optional Playwright UI tests

---

### Task 1: Sync correspondent destination scope during promotion

**Files:**
- Modify: `contacts/correspondent_recipient_promotion.py`
- Test: `wms/tests/core/tests_correspondent_recipient_promotion.py`
- Reference: `contacts/destination_scope.py`
- Reference: `wms/models.py`

**Step 1: Write the failing tests**

Add tests proving:
- a promoted correspondent linked as `Destination.correspondent_contact` on one active destination receives that destination scope
- a promoted correspondent linked on multiple active destinations receives all of them
- the legacy single `destination` field is populated only for a single scoped destination

```python
def test_promote_correspondent_scopes_single_destination_from_destination_reference(self):
    correspondent = Contact.objects.create(
        name="Scope Corr",
        contact_type=ContactType.PERSON,
        is_active=True,
    )
    destination = Destination.objects.create(
        city="Antananarivo",
        iata_code="TNR",
        country="Madagascar",
        correspondent_contact=correspondent,
        is_active=True,
    )
    correspondent.tags.add(self.correspondent_tag)

    correspondent.refresh_from_db()

    self.assertEqual(
        set(correspondent.destinations.values_list("id", flat=True)),
        {destination.id},
    )
    self.assertEqual(correspondent.destination_id, destination.id)
```

**Step 2: Run the focused promotion suite and verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.core.tests_correspondent_recipient_promotion -v 2`

Expected: the new scope assertions fail because the promotion service currently adds the recipient tag and role but leaves destination scope empty.

**Step 3: Write the minimal production change**

Update `contacts/correspondent_recipient_promotion.py` to:
- compute active destination ids from `Destination.objects.filter(correspondent_contact=contact, is_active=True)`
- apply them with `set_contact_destination_scope(contact=contact, destination_ids=...)` when at least one destination exists
- keep the scope on the promoted contact itself even when the backing recipient organization is `ASF - CORRESPONDANT`
- extend the result dataclass and change accounting only if you need to expose scope synchronization explicitly

```python
def _destination_ids_from_correspondent_assignments(contact) -> list[int]:
    return list(
        Destination.objects.filter(
            correspondent_contact=contact,
            is_active=True,
        ).values_list("id", flat=True)
    )


destination_ids = _destination_ids_from_correspondent_assignments(contact)
if destination_ids:
    set_contact_destination_scope(contact=contact, destination_ids=destination_ids)
```

**Step 4: Re-run the focused promotion suite**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.core.tests_correspondent_recipient_promotion -v 2`

Expected: PASS.

**Step 5: Commit the promotion scope fix**

```bash
git add contacts/correspondent_recipient_promotion.py \
  wms/tests/core/tests_correspondent_recipient_promotion.py
git commit -m "feat: sync promoted correspondent destination scope"
```

### Task 2: Lock backfill and shipment payload behavior against global correspondents

**Files:**
- Modify: `wms/tests/management/tests_management_backfill_correspondent_recipients.py`
- Modify: `wms/tests/shipment/tests_shipment_helpers.py`
- Optional modify: `wms/management/commands/backfill_correspondent_recipients.py`

**Step 1: Write the failing tests**

Add tests proving:
- `backfill_correspondent_recipients --apply` scopes existing correspondents from their destination references
- the second run is idempotent
- shipment recipient payloads expose the promoted correspondent with the expected `destination_ids` rather than an empty global scope

```python
def test_apply_syncs_correspondent_destination_scope_from_destination_reference(self):
    contact = Contact.objects.create(
        name="Backfill Corr",
        contact_type=ContactType.PERSON,
        is_active=True,
    )
    contact.tags.add(self.correspondent_tag)
    destination = Destination.objects.create(
        city="Libreville",
        iata_code="LBV",
        country="Gabon",
        correspondent_contact=contact,
        is_active=True,
    )

    call_command("backfill_correspondent_recipients", "--apply")

    contact.refresh_from_db()
    self.assertEqual(
        set(contact.destinations.values_list("id", flat=True)),
        {destination.id},
    )
```

**Step 2: Run the focused suites and verify they fail**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.management.tests_management_backfill_correspondent_recipients wms.tests.shipment.tests_shipment_helpers -v 2`

Expected: the new assertions fail until the promotion service changes are fully exercised through backfill and payload generation.

**Step 3: Make the smallest follow-up adjustments**

If Task 1 did not already make these tests pass, adjust only what is necessary:
- ensure the backfill path still routes through the shared promotion service
- update any summary expectations only if the command needs to report scope synchronization explicitly
- keep `wms/shipment_helpers.py` unchanged unless a payload test shows stale scope extraction

**Step 4: Re-run the focused suites**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.management.tests_management_backfill_correspondent_recipients wms.tests.shipment.tests_shipment_helpers -v 2`

Expected: PASS.

**Step 5: Commit the backfill and payload lock-in**

```bash
git add wms/tests/management/tests_management_backfill_correspondent_recipients.py \
  wms/tests/shipment/tests_shipment_helpers.py \
  wms/management/commands/backfill_correspondent_recipients.py
git commit -m "test: lock correspondent scope backfill behavior"
```

### Task 3: Remove non-authorized recipients from the Scan selector

**Files:**
- Modify: `wms/static/scan/scan.js`
- Modify: `wms/tests/forms/tests_forms_org_roles_gate.py`
- Modify: `wms/tests/core/tests_ui.py`
- Reference: `wms/forms.py`

**Step 1: Write the failing tests**

Add coverage for both backend filtering and the rendered UI:
- keep the existing form queryset test proving only bound recipients are eligible server-side
- add a UI regression test showing that after selecting `destination + shipper`, a blocked recipient does not exist in the `Destinataire` `<select>` at all when org roles are enabled

```python
def test_scan_shipment_form_filters_recipients_from_bindings_when_engine_enabled(self):
    form = ScanShipmentForm(
        destination_id=str(destination.id),
        initial={"shipper_contact": str(shipper.id)},
    )

    recipient_ids = set(form.fields["recipient_contact"].queryset.values_list("id", flat=True))
    self.assertIn(recipient_allowed.id, recipient_ids)
    self.assertNotIn(recipient_blocked.id, recipient_ids)
```

```python
def test_shipment_create_hides_unbound_recipients_when_org_roles_enabled(self):
    page.get_by_label("Destination", exact=True).select_option(str(self.destination.id))
    page.get_by_label("Expediteur", exact=True).select_option(str(self.shipper_contact.id))

    blocked_option = page.locator(
        f'label:has-text("Destinataire") select option[value="{self.blocked_recipient.id}"]'
    )
    self.assertEqual(blocked_option.count(), 0)
```

**Step 2: Run the focused tests and verify the UI expectation fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.forms.tests_forms_org_roles_gate -v 2`

Then, if Playwright is available locally:

Run: `RUN_UI_TESTS=1 /Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.core.tests_ui.ScanUiTests.test_shipment_create_hides_unbound_recipients_when_org_roles_enabled -v 2`

Expected: the UI test fails because `scan.js` still renders the `otherRecipientOptions` bucket as disabled items.

**Step 3: Write the minimal JS change**

Update `wms/static/scan/scan.js` so that when `orgRolesEngineEnabled` is true:
- `recipientOptions` contains only:
  - the destination correspondent recipient when it matches the binding pair
  - recipients matching the binding pair
- the non-matching recipient bucket is dropped instead of rendered disabled

```javascript
const pairRecipientOptions = destinationRecipients
  .filter(recipient => isRecipientPairMatched(recipient))
  .map(recipient => decorateOption(recipient));

recipientOptions = orgRolesEngineEnabled
  ? [priorityRecipientOptions, pairRecipientOptions]
  : [priorityRecipientOptions, pairRecipientOptions, otherRecipientOptions];
```

**Step 4: Re-run the focused selector tests**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.forms.tests_forms_org_roles_gate wms.tests.shipment.tests_shipment_helpers wms.tests.core.tests_correspondent_recipient_promotion wms.tests.management.tests_management_backfill_correspondent_recipients -v 2`

If available, also run:

Run: `RUN_UI_TESTS=1 /Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.core.tests_ui.ScanUiTests.test_shipment_create_hides_unbound_recipients_when_org_roles_enabled -v 2`

Expected: PASS.

**Step 5: Commit the strict selector rendering**

```bash
git add wms/static/scan/scan.js \
  wms/tests/forms/tests_forms_org_roles_gate.py \
  wms/tests/core/tests_ui.py \
  wms/tests/shipment/tests_shipment_helpers.py \
  wms/tests/core/tests_correspondent_recipient_promotion.py \
  wms/tests/management/tests_management_backfill_correspondent_recipients.py
git commit -m "fix: hide unbound recipients in shipment selector"
```

### Task 4: Final verification and deployment handoff

**Files:**
- Verify only: `contacts/correspondent_recipient_promotion.py`
- Verify only: `wms/static/scan/scan.js`
- Verify only: `wms/tests/core/tests_correspondent_recipient_promotion.py`
- Verify only: `wms/tests/management/tests_management_backfill_correspondent_recipients.py`
- Verify only: `wms/tests/shipment/tests_shipment_helpers.py`
- Verify only: `wms/tests/forms/tests_forms_org_roles_gate.py`
- Verify only: `wms/tests/core/tests_ui.py`

**Step 1: Run the non-UI regression bundle**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.core.tests_correspondent_recipient_promotion wms.tests.management.tests_management_backfill_correspondent_recipients wms.tests.shipment.tests_shipment_helpers wms.tests.forms.tests_forms_org_roles_gate -v 2`

Expected: PASS.

**Step 2: Run formatting / git hygiene checks**

Run: `git diff --check`

Expected: no output.

**Step 3: Run full coverage if the branch is headed to PR**

Run: `/bin/zsh -lc 'COVERAGE_FAIL_UNDER=93 TEST_PARALLEL=4 uv run make coverage'`

Expected: PASS with total coverage still above `93`.

**Step 4: Record PythonAnywhere rollout steps in the handoff**

After merge, run:

```bash
cd /home/messmed/asf-wms
git pull
source /home/messmed/.virtualenvs/asf-wms/bin/activate
source /home/messmed/.asf-wms.env
python manage.py backfill_correspondent_recipients --apply
```

Then reload the web app from the PythonAnywhere Web tab.

**Step 5: Commit only if handoff artifacts changed**

```bash
git status --short
```

Expected: clean working tree.
