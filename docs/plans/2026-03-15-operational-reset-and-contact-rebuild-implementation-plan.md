# Operational Reset and Contact Rebuild Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a safe operational-data reset command and a replayable workbook-driven contact rebuild pipeline that recreates a clean runtime baseline from `BE 2025 full.xlsx`.

**Architecture:** Introduce one explicit reset service/command with allowlisted model scope and transaction-safe deletion ordering. Then build a separate workbook normalization and rebuild service that turns the BE export into canonical contacts, destinations, role assignments, shipper scopes, recipient bindings, legacy linked shippers, and review artifacts, with command wrappers for dry-run and apply modes.

**Tech Stack:** Django management commands, Django ORM, openpyxl, legacy contact import/domain models, Django TestCase

---

### Task 1: Add failing tests for the reset command contract

**Files:**
- Create: `wms/tests/management/tests_management_reset_operational_data.py`
- Verify: `contacts/models.py`
- Verify: `wms/models_domain/inventory.py`
- Verify: `wms/models_domain/planning.py`
- Verify: `wms/models_domain/portal.py`

**Step 1: Write the failing test**

Add tests that seed a minimal mix of preserved and deleted data, then lock the reset contract:

```python
class ResetOperationalDataCommandTests(TestCase):
    def test_dry_run_reports_deleted_and_preserved_models_without_writing(self):
        warehouse = Warehouse.objects.create(name="Main")
        location = Location.objects.create(warehouse=warehouse, zone="A", aisle="1", shelf="1")
        shipper = Contact.objects.create(name="Association A", contact_type=ContactType.ORGANIZATION)
        RuntimeSettings = WmsRuntimeSettings
        RuntimeSettings.objects.get_or_create(pk=1)

        out = io.StringIO()
        call_command("reset_operational_data", "--dry-run", stdout=out)

        self.assertIn("DRY RUN", out.getvalue())
        self.assertTrue(Contact.objects.filter(pk=shipper.pk).exists())
        self.assertTrue(Warehouse.objects.filter(pk=warehouse.pk).exists())
        self.assertTrue(Location.objects.filter(pk=location.pk).exists())
```

Add a second test for apply mode:

```python
    def test_apply_deletes_operational_models_and_preserves_reference_models(self):
        warehouse = Warehouse.objects.create(name="Main")
        location = Location.objects.create(warehouse=warehouse, zone="A", aisle="1", shelf="1")
        shipper = Contact.objects.create(name="Association A", contact_type=ContactType.ORGANIZATION)
        RuntimeSettings = WmsRuntimeSettings
        RuntimeSettings.objects.get_or_create(pk=1)

        call_command("reset_operational_data", "--apply")

        self.assertFalse(Contact.objects.exists())
        self.assertTrue(Warehouse.objects.filter(pk=warehouse.pk).exists())
        self.assertTrue(Location.objects.filter(pk=location.pk).exists())
        self.assertTrue(RuntimeSettings.objects.filter(pk=1).exists())
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.management.tests_management_reset_operational_data -v 2`

Expected: FAIL because the command does not exist yet.

**Step 3: Write minimal implementation**

No implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run: `.venv/bin/python manage.py test wms.tests.management.tests_management_reset_operational_data -v 2`

Expected: FAIL only because `reset_operational_data` is missing.

**Step 5: Commit**

```bash
git add wms/tests/management/tests_management_reset_operational_data.py
git commit -m "test: cover operational reset command contract"
```

### Task 2: Implement the reset service and management command

**Files:**
- Create: `wms/reset_operational_data.py`
- Create: `wms/management/commands/reset_operational_data.py`
- Modify: `wms/tests/management/tests_management_reset_operational_data.py`

**Step 1: Write the failing test**

Use the red tests from Task 1. Add one more assertion that `PlanningParameterSet` survives while `PlanningDestinationRule` is removed:

```python
self.assertTrue(PlanningParameterSet.objects.exists())
self.assertFalse(PlanningDestinationRule.objects.exists())
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.management.tests_management_reset_operational_data -v 2`

Expected: FAIL because no reset implementation exists.

**Step 3: Write minimal implementation**

Create a reset service with explicit allowlists:

```python
KEEP_MODEL_LABELS = {
    "auth.Group",
    "auth.Permission",
    "auth.User",
    "contenttypes.ContentType",
    "sessions.Session",
    "wms.Warehouse",
    "wms.Location",
    "wms.RackColor",
    "wms.Product",
    "wms.ProductCategory",
    "wms.ProductTag",
    "wms.ProductKitItem",
    "wms.CartonFormat",
    "wms.PrintTemplate",
    "wms.PrintPack",
    "wms.PrintPackDocument",
    "wms.PrintCellMapping",
    "wms.DocumentRequirementTemplate",
    "wms.CommunicationTemplate",
    "wms.PlanningParameterSet",
    "wms.BillingComputationProfile",
    "wms.BillingServiceCatalogItem",
    "wms.RoleEventPolicy",
    "wms.ShipmentUnitEquivalenceRule",
    "wms.WmsRuntimeSettings",
}
```

Add:
- ordered delete batches
- `dry_run` summary
- single transaction for apply mode
- post-run assertions for preserved models

Wrap it with a command:

```python
class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--apply", action="store_true")
```

Make `--dry-run` the default behavior when `--apply` is absent.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.management.tests_management_reset_operational_data -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/reset_operational_data.py wms/management/commands/reset_operational_data.py wms/tests/management/tests_management_reset_operational_data.py
git commit -m "feat: add operational reset command"
```

### Task 3: Add failing tests for workbook normalization and ambiguity reporting

**Files:**
- Create: `wms/tests/management/tests_management_rebuild_contacts_from_be_xlsx.py`
- Verify: `wms/import_utils.py`
- Verify: `wms/import_services_contacts.py`

**Step 1: Write the failing test**

Create a temporary workbook in the test with repeated and conflicting rows:

```python
def test_build_be_contact_dataset_groups_entities_and_surfaces_ambiguities(self):
    workbook_path = self._build_be_workbook(
        [
            {
                "ASSOCIATION_NOM": "AVIATION SANS FRONTIERES",
                "DESTINATAIRE_STRUCTURE": "Recipient A",
                "CORRESPONDANT_PRENOM": "Leontine",
                "CORRESPONDANT_NOM": "Rahazania",
                "BE_DESTINATION": "ANTANANARIVO",
                "BE_CODE_IATA": "TNR",
            },
            {
                "ASSOCIATION_NOM": "Aviation Sans Frontieres",
                "DESTINATAIRE_STRUCTURE": "Recipient A",
                "CORRESPONDANT_PRENOM": "Leontine",
                "CORRESPONDANT_NOM": "Rahazania",
                "BE_DESTINATION": "ANTANANARIVO",
                "BE_CODE_IATA": "TNR",
            },
        ]
    )

    dataset = build_be_contact_dataset(workbook_path)

    self.assertEqual(len(dataset.shippers), 1)
    self.assertEqual(len(dataset.recipients), 1)
    self.assertEqual(len(dataset.destinations), 1)
    self.assertEqual(dataset.review_items, [])
```

Add a second test with a true conflict:

```python
self.assertEqual(len(dataset.review_items), 1)
self.assertIn("conflicting", dataset.review_items[0]["reason"])
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.management.tests_management_rebuild_contacts_from_be_xlsx -v 2`

Expected: FAIL because the normalization service does not exist yet.

**Step 3: Write minimal implementation**

No implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run the same command.

Expected: FAIL only because the dataset builder is missing.

**Step 5: Commit**

```bash
git add wms/tests/management/tests_management_rebuild_contacts_from_be_xlsx.py
git commit -m "test: cover BE workbook normalization"
```

### Task 4: Implement workbook normalization and review artifact generation

**Files:**
- Create: `wms/contact_rebuild.py`
- Modify: `wms/tests/management/tests_management_rebuild_contacts_from_be_xlsx.py`

**Step 1: Write the failing test**

Extend Task 3 coverage to lock the normalized output shape:

```python
self.assertEqual(dataset.recipient_bindings, [
    {
        "recipient_key": "recipient a",
        "shipper_key": "aviation sans frontieres",
        "destination_iata": "TNR",
    }
])
```

Add a report-rendering test:

```python
report = render_review_report(dataset.review_items)
self.assertIn("Recipient A", report)
self.assertIn("conflicting shipper evidence", report)
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.management.tests_management_rebuild_contacts_from_be_xlsx -v 2`

Expected: FAIL because the normalization service is incomplete.

**Step 3: Write minimal implementation**

Create:
- workbook row reader
- canonicalization helpers for organization names, cities, countries, and IATA codes
- grouping logic for donors/shippers/recipients/correspondents/destinations
- relationship extraction for shipper scopes and recipient bindings
- review-item collection for ambiguous cases
- report renderer for ambiguity output

Use a structured dataset object:

```python
@dataclass
class BeContactDataset:
    donors: list[dict]
    shippers: list[dict]
    recipients: list[dict]
    correspondents: list[dict]
    destinations: list[dict]
    shipper_scopes: list[dict]
    recipient_bindings: list[dict]
    review_items: list[dict]
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.management.tests_management_rebuild_contacts_from_be_xlsx -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/contact_rebuild.py wms/tests/management/tests_management_rebuild_contacts_from_be_xlsx.py
git commit -m "feat: normalize BE workbook contact dataset"
```

### Task 5: Add failing persistence tests for contact, destination, and org-role rebuild

**Files:**
- Modify: `wms/tests/management/tests_management_rebuild_contacts_from_be_xlsx.py`
- Verify: `contacts/models.py`
- Verify: `wms/portal_recipient_sync.py`
- Verify: `wms/organization_roles_backfill.py`

**Step 1: Write the failing test**

Add a persistence test that loads a normalized dataset into an empty post-reset database:

```python
def test_apply_be_contact_dataset_creates_contacts_destinations_and_org_role_links(self):
    dataset = BeContactDataset(
        donors=[{"name": "Donor A"}],
        shippers=[{"name": "AVIATION SANS FRONTIERES", "destinations": ["TNR"]}],
        recipients=[{"name": "Recipient A", "destinations": ["TNR"]}],
        correspondents=[{"name": "Leontine Rahazania"}],
        destinations=[{"city": "ANTANANARIVO", "country": "Madagascar", "iata_code": "TNR", "correspondent_name": "Leontine Rahazania"}],
        shipper_scopes=[{"shipper_name": "AVIATION SANS FRONTIERES", "destination_iata": "TNR"}],
        recipient_bindings=[{"recipient_name": "Recipient A", "shipper_name": "AVIATION SANS FRONTIERES", "destination_iata": "TNR"}],
        review_items=[],
    )

    apply_be_contact_dataset(dataset)

    recipient = Contact.objects.get(name="Recipient A")
    shipper = Contact.objects.get(name="AVIATION SANS FRONTIERES")
    destination = Destination.objects.get(iata_code="TNR")

    self.assertTrue(recipient.linked_shippers.filter(pk=shipper.pk).exists())
    self.assertTrue(OrganizationRoleAssignment.objects.filter(organization=shipper, role=OrganizationRole.SHIPPER).exists())
    self.assertTrue(RecipientBinding.objects.filter(shipper_org=shipper, recipient_org=recipient, destination=destination).exists())
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.management.tests_management_rebuild_contacts_from_be_xlsx -v 2`

Expected: FAIL because the persistence layer does not exist yet.

**Step 3: Write minimal implementation**

No implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run the same command.

Expected: FAIL only because `apply_be_contact_dataset` is missing.

**Step 5: Commit**

```bash
git add wms/tests/management/tests_management_rebuild_contacts_from_be_xlsx.py
git commit -m "test: cover BE workbook rebuild persistence"
```

### Task 6: Implement rebuild persistence and the command wrapper

**Files:**
- Modify: `wms/contact_rebuild.py`
- Create: `wms/management/commands/rebuild_contacts_from_be_xlsx.py`
- Modify: `wms/tests/management/tests_management_rebuild_contacts_from_be_xlsx.py`

**Step 1: Write the failing test**

Add command-level tests for dry-run/apply:

```python
def test_rebuild_contacts_from_be_xlsx_dry_run_reports_actions_without_writing(self):
    out = io.StringIO()
    call_command(
        "rebuild_contacts_from_be_xlsx",
        "--source", str(self.workbook_path),
        "--dry-run",
        stdout=out,
    )
    self.assertIn("DRY RUN", out.getvalue())
    self.assertFalse(Contact.objects.exists())
```

```python
def test_rebuild_contacts_from_be_xlsx_apply_writes_review_report_and_runtime_data(self):
    report_path = self.temp_dir / "review.md"
    call_command(
        "rebuild_contacts_from_be_xlsx",
        "--source", str(self.workbook_path),
        "--apply",
        "--report-path", str(report_path),
    )
    self.assertTrue(Contact.objects.exists())
    self.assertTrue(report_path.exists())
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.management.tests_management_rebuild_contacts_from_be_xlsx -v 2`

Expected: FAIL because the command wrapper and persistence logic are incomplete.

**Step 3: Write minimal implementation**

Implement:
- contact/tag/address creation/upsert
- destination creation with correspondent contact linkage
- organization role assignment creation per actor role
- shipper scope creation from normalized shipper/destination pairs
- recipient binding creation from normalized recipient/shipper/destination triples
- legacy linked-shipper mirroring from the same normalized bindings
- command options:

```python
parser.add_argument("--source", required=True)
parser.add_argument("--dry-run", action="store_true")
parser.add_argument("--apply", action="store_true")
parser.add_argument("--report-path", default="docs/import/be_contact_rebuild_review.md")
```

Make dry-run the default behavior when `--apply` is absent.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.management.tests_management_rebuild_contacts_from_be_xlsx -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/contact_rebuild.py wms/management/commands/rebuild_contacts_from_be_xlsx.py wms/tests/management/tests_management_rebuild_contacts_from_be_xlsx.py
git commit -m "feat: rebuild contacts and org roles from BE workbook"
```

### Task 7: Run focused verification and local dry-runs

**Files:**
- Verify: `wms/tests/management/tests_management_reset_operational_data.py`
- Verify: `wms/tests/management/tests_management_rebuild_contacts_from_be_xlsx.py`
- Verify: `wms/contact_rebuild.py`
- Verify: `wms/reset_operational_data.py`

**Step 1: Run the targeted automated suite**

Run: `.venv/bin/python manage.py test wms.tests.management.tests_management_reset_operational_data wms.tests.management.tests_management_rebuild_contacts_from_be_xlsx -v 2`

Expected: PASS.

**Step 2: Run the reset dry-run against the local database**

Run: `.venv/bin/python manage.py reset_operational_data --dry-run`

Expected: a per-model purge summary with preserved reference/configuration counts.

**Step 3: Run the rebuild dry-run against the user workbook**

Run: `.venv/bin/python manage.py rebuild_contacts_from_be_xlsx --source "/Users/EdouardGonnu/Library/CloudStorage/OneDrive-AviationSansFrontieres/4-Enregistrements/Stats/stats annuelles completes/BE 2025 full.xlsx" --dry-run --report-path docs/import/be_contact_rebuild_review.md`

Expected: a summary of normalized entities, bindings, review items, and planned writes, without touching the database.

**Step 4: Run final hygiene checks**

Run: `git diff --check`

Expected: no whitespace or patch-format issues.

**Step 5: Commit**

```bash
git add docs/import/be_contact_rebuild_review.md
git commit -m "test: verify reset and rebuild dry runs"
```
