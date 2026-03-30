# Local Exhaustive Seed Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a local-only exhaustive seed command that creates production-like fictional data for the main legacy Django business flows and leaves the app broadly operable for manual QA and targeted end-to-end verification.

**Architecture:** Build one management command entry point in `wms/management/commands/seed_local_exhaustive_data.py` over a dedicated orchestration module in `wms/local_exhaustive_seed.py`. Reuse stable reset and planning recipe logic where it already encodes business rules, but keep the new local recipe as the canonical place that ties together users, contacts, stock, cartons, shipments, portal, volunteer, billing, queues, and planning in one idempotent namespace.

**Tech Stack:** Django management commands, Django ORM, legacy `wms.models` facade, existing seed helpers (`wms/reset_operational_data.py`, `wms/planning/recipe_dataset.py`), Django test suite via `./.venv/bin/python manage.py test`

---

### Task 1: Lock Down The Command Contract With Failing Management Tests

**Files:**
- Create: `wms/tests/management/tests_management_seed_local_exhaustive_data.py`
- Reference: `wms/management/commands/seed_local_exhaustive_data.py`
- Reference: `wms/local_exhaustive_seed.py`

**Step 1: Write the failing tests**

Add management-command tests that describe the public contract:

```python
def test_command_creates_named_local_dataset_summary(self):
    output = StringIO()

    call_command(
        "seed_local_exhaustive_data",
        "--scenario=local-exhaustive",
        stdout=output,
    )

    self.assertIn("Scenario local-exhaustive ready", output.getvalue())
    self.assertIn("staff=", output.getvalue())
    self.assertIn("portal=", output.getvalue())
    self.assertIn("shipments=", output.getvalue())


def test_command_is_idempotent_for_same_namespace(self):
    call_command("seed_local_exhaustive_data", "--scenario=repeatable")
    first_counts = {
        "shipments": Shipment.objects.filter(reference__contains="REPEATABLE").count(),
        "profiles": AssociationProfile.objects.filter(
            user__username__contains="repeatable"
        ).count(),
    }

    call_command("seed_local_exhaustive_data", "--scenario=repeatable")

    self.assertEqual(
        Shipment.objects.filter(reference__contains="REPEATABLE").count(),
        first_counts["shipments"],
    )
    self.assertEqual(
        AssociationProfile.objects.filter(user__username__contains="repeatable").count(),
        first_counts["profiles"],
    )
```

Also add tests for:
- `--fresh` invoking the reset path
- `--with-planning-solve` creating a solved run
- `--with-queue-backlog` creating email/document queue rows

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.management.tests_management_seed_local_exhaustive_data -v 2
```

Expected:
- FAIL because the command and orchestration module do not exist yet

**Step 3: Write minimal implementation**

Create a minimal command shell and orchestration entry point:

```python
class Command(BaseCommand):
    help = "Seed an exhaustive local-only recipe dataset for manual QA and end-to-end checks."

    def add_arguments(self, parser):
        parser.add_argument("--scenario", default="local-exhaustive")
        parser.add_argument("--fresh", action="store_true")
        parser.add_argument("--with-planning-solve", action="store_true")
        parser.add_argument("--with-demo-documents", action="store_true")
        parser.add_argument("--with-queue-backlog", action="store_true")
        parser.add_argument("--with-e2e-baseline", action="store_true")

    def handle(self, *args, **options):
        summary = seed_local_exhaustive_dataset(**normalized_options)
        self.stdout.write(render_local_exhaustive_seed_summary(summary))
```

In `wms/local_exhaustive_seed.py`, add:
- scenario normalization
- summary dataclass
- stub orchestration function returning deterministic summary keys

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS with a minimal command contract and stable summary output

**Step 5: Commit**

```bash
git add wms/management/commands/seed_local_exhaustive_data.py wms/local_exhaustive_seed.py wms/tests/management/tests_management_seed_local_exhaustive_data.py
git commit -m "feat: add local exhaustive seed command scaffold"
```

### Task 2: Seed Shared References, Users, And Contact Graph

**Files:**
- Modify: `wms/local_exhaustive_seed.py`
- Test: `wms/tests/management/tests_management_seed_local_exhaustive_data.py`
- Reference: `wms/models.py`

**Step 1: Write the failing tests**

Add tests that assert the shared graph exists after seeding:

```python
def test_command_creates_local_users_profiles_and_contact_roles(self):
    call_command("seed_local_exhaustive_data", "--scenario=users")

    self.assertTrue(get_user_model().objects.filter(username="scan-users-staff").exists())
    self.assertGreaterEqual(AssociationProfile.objects.count(), 2)
    self.assertGreaterEqual(AssociationPortalContact.objects.count(), 4)
    self.assertGreaterEqual(ShipmentShipper.objects.count(), 2)
    self.assertGreaterEqual(ShipmentRecipientOrganization.objects.count(), 2)
    self.assertGreaterEqual(ShipmentAuthorizedRecipientContact.objects.count(), 2)
```

Also assert:
- warehouses and locations exist
- product categories, products, and unit equivalence rules exist
- communication templates include both email and WhatsApp channels
- billing profiles are created for seeded associations

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.management.tests_management_seed_local_exhaustive_data.SeedLocalExhaustiveDataCommandTests.test_command_creates_local_users_profiles_and_contact_roles -v 2
```

Expected:
- FAIL because the current seed shell does not create the shared reference graph

**Step 3: Write minimal implementation**

In `wms/local_exhaustive_seed.py`, add builder helpers for:
- staff, superuser, billing, portal, and volunteer users
- association contacts and `AssociationProfile`
- `AssociationPortalContact`
- destinations and correspondents
- shipment-party graph:
  - `ShipmentShipper`
  - `ShipmentRecipientOrganization`
  - `ShipmentRecipientContact`
  - `ShipmentShipperRecipientLink`
  - `ShipmentAuthorizedRecipientContact`
- warehouses, locations, categories, products, lots, equivalence rules
- communication templates and billing profiles

Use `get_or_create()` and `update_or_create()` consistently with the scenario namespace.

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS with deterministic shared references and reusable contact graph rows

**Step 5: Commit**

```bash
git add wms/local_exhaustive_seed.py wms/tests/management/tests_management_seed_local_exhaustive_data.py
git commit -m "feat: seed shared local users and contact graph"
```

### Task 3: Seed Operational Stock, Cartons, Shipments, And Dashboard Alerts

**Files:**
- Modify: `wms/local_exhaustive_seed.py`
- Test: `wms/tests/management/tests_management_seed_local_exhaustive_data.py`
- Reference: `wms/views_scan_dashboard.py`

**Step 1: Write the failing tests**

Add tests that assert the operational chain and alert cases exist:

```python
def test_command_creates_actionable_shipments_cartons_and_alert_rows(self):
    call_command("seed_local_exhaustive_data", "--scenario=ops", "--with-queue-backlog")

    self.assertTrue(Shipment.objects.filter(reference="EXP-TEMP-01").exists())
    self.assertGreaterEqual(Carton.objects.filter(status=CartonStatus.PACKED).count(), 1)
    self.assertGreaterEqual(Carton.objects.filter(status=CartonStatus.LABELED).count(), 1)
    self.assertGreaterEqual(
        Shipment.objects.filter(is_disputed=True).count(),
        1,
    )
    self.assertGreaterEqual(
        IntegrationEvent.objects.filter(source="wms.email").count(),
        1,
    )
```

Also assert:
- at least one delivered-but-open shipment exists
- tracking events exist for planned, boarding, correspondent, and recipient milestones
- low-stock and non-low-stock products coexist
- shipment references and timestamps are namespaced and deterministic

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.management.tests_management_seed_local_exhaustive_data.SeedLocalExhaustiveDataCommandTests.test_command_creates_actionable_shipments_cartons_and_alert_rows -v 2
```

Expected:
- FAIL because the seed does not yet populate the operational workflow chain

**Step 3: Write minimal implementation**

Extend `wms/local_exhaustive_seed.py` to create:
- product lots in `available`, `hold`, `quarantined`, and `expired`
- cartons in all workflow states
- shipments covering:
  - draft `EXP-TEMP-XX`
  - picking
  - packed
  - planned
  - shipped
  - received correspondent
  - delivered and closable
  - delivered and already closed
  - disputed
- tracking events with realistic age offsets
- queue rows for email and document scan backlogs when the flag is enabled

Prefer helper functions that accept `created_at` offsets so the dashboard-alert shapes are explicit.

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS with action-ready operational rows and dashboard alert/backlog coverage

**Step 5: Commit**

```bash
git add wms/local_exhaustive_seed.py wms/tests/management/tests_management_seed_local_exhaustive_data.py
git commit -m "feat: seed operational workflow and alert scenarios"
```

### Task 4: Seed Portal, Public Intake, And Uploaded Documents

**Files:**
- Modify: `wms/local_exhaustive_seed.py`
- Test: `wms/tests/management/tests_management_seed_local_exhaustive_data.py`
- Reference: `wms/models_domain/portal.py`

**Step 1: Write the failing tests**

Add tests that assert portal and intake data is action-ready:

```python
def test_command_creates_portal_orders_documents_and_billing_requests(self):
    call_command(
        "seed_local_exhaustive_data",
        "--scenario=portal",
        "--with-demo-documents",
    )

    self.assertGreaterEqual(Order.objects.count(), 2)
    self.assertGreaterEqual(AccountDocument.objects.count(), 1)
    self.assertGreaterEqual(OrderDocument.objects.count(), 1)
    self.assertGreaterEqual(AssociationBillingChangeRequest.objects.count(), 1)
    self.assertGreaterEqual(AssociationRecipient.objects.count(), 2)
```

Also assert:
- document scan statuses span at least `clean`, `pending`, and a review-needed/error state
- one public account request exists
- one public order exists beside portal orders
- recipient sync inputs are present for both active and inactive cases

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.management.tests_management_seed_local_exhaustive_data.SeedLocalExhaustiveDataCommandTests.test_command_creates_portal_orders_documents_and_billing_requests -v 2
```

Expected:
- FAIL because portal/public documents and billing-change flows are not seeded yet

**Step 3: Write minimal implementation**

In `wms/local_exhaustive_seed.py`:
- create two portal association scenarios with differentiated portal contacts
- create active and inactive `AssociationRecipient` rows
- create portal orders and one public-order/intake path
- attach account and order documents using `ContentFile`/`SimpleUploadedFile`-style file creation
- assign document scan statuses
- create at least one `AssociationBillingChangeRequest`

Keep file names realistic:
- `account-iban-proof.pdf`
- `order-medical-list.xlsx`
- `association-registration.pdf`

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS with portal/public flows represented by realistic documents and request rows

**Step 5: Commit**

```bash
git add wms/local_exhaustive_seed.py wms/tests/management/tests_management_seed_local_exhaustive_data.py
git commit -m "feat: seed portal intake and uploaded document scenarios"
```

### Task 5: Reuse Planning Recipe Logic And Seed Volunteer Scenarios

**Files:**
- Modify: `wms/local_exhaustive_seed.py`
- Test: `wms/tests/management/tests_management_seed_local_exhaustive_data.py`
- Reference: `wms/planning/recipe_dataset.py`

**Step 1: Write the failing tests**

Add tests that describe the planning and volunteer contract:

```python
def test_command_can_seed_solved_planning_and_volunteer_profiles(self):
    call_command(
        "seed_local_exhaustive_data",
        "--scenario=planning",
        "--with-planning-solve",
    )

    self.assertGreaterEqual(VolunteerProfile.objects.count(), 3)
    run = PlanningRun.objects.get(name__icontains="planning")
    self.assertEqual(run.status, PlanningRunStatus.SOLVED)
    self.assertTrue(CommunicationTemplate.objects.filter(channel=CommunicationChannel.WHATSAPP).exists())
```

Also assert:
- volunteer availabilities and constraints exist
- a password-change-required or first-login case exists
- solved planning data includes assignments and communication drafts

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.management.tests_management_seed_local_exhaustive_data.SeedLocalExhaustiveDataCommandTests.test_command_can_seed_solved_planning_and_volunteer_profiles -v 2
```

Expected:
- FAIL because planning recipe integration and volunteer scenarios are not wired into the exhaustive seed yet

**Step 3: Write minimal implementation**

In `wms/local_exhaustive_seed.py`:
- add volunteer account builders with:
  - profile
  - phone
  - availabilities
  - unavailabilities
  - constraints
  - one `must_change_password` case
- call the planning recipe builder or command-equivalent service with the scenario namespace
- when `--with-planning-solve` is enabled, ensure the planning run is solved and recorded in the summary

Do not reimplement planning dataset logic if the recipe builder already provides the correct business structures.

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS with volunteer and planning records visible and solved when requested

**Step 5: Commit**

```bash
git add wms/local_exhaustive_seed.py wms/tests/management/tests_management_seed_local_exhaustive_data.py
git commit -m "feat: reuse planning recipe data in exhaustive seed"
```

### Task 6: Seed Billing Lifecycle Coverage

**Files:**
- Modify: `wms/local_exhaustive_seed.py`
- Test: `wms/tests/management/tests_management_seed_local_exhaustive_data.py`
- Reference: `wms/billing_document_handlers.py`

**Step 1: Write the failing tests**

Add billing-focused seed assertions:

```python
def test_command_creates_billing_documents_across_periods_and_states(self):
    call_command("seed_local_exhaustive_data", "--scenario=billing")

    self.assertGreaterEqual(BillingDocument.objects.count(), 4)
    self.assertTrue(BillingDocument.objects.filter(kind=BillingDocumentKind.QUOTE).exists())
    self.assertTrue(BillingDocument.objects.filter(status=BillingDocumentStatus.ISSUED).exists())
    self.assertTrue(BillingDocument.objects.filter(status=BillingDocumentStatus.PARTIALLY_PAID).exists())
```

Also assert:
- links exist to shipments and receipts
- at least one correction chain exists
- at least two associations expose different billing frequencies/grouping modes

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.management.tests_management_seed_local_exhaustive_data.SeedLocalExhaustiveDataCommandTests.test_command_creates_billing_documents_across_periods_and_states -v 2
```

Expected:
- FAIL because billing lifecycle rows are not seeded yet

**Step 3: Write minimal implementation**

Use `wms/billing_document_handlers.py` where practical to build realistic documents:
- draft quote
- issued invoice
- partially paid invoice
- corrected invoice or in-review correction case

Also seed:
- multiple billing frequencies and grouping modes
- optional exchange-rate and override scenarios
- receipt-linked and shipment-linked documents when the models support it

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS with billing rows that drive scan and portal billing screens

**Step 5: Commit**

```bash
git add wms/local_exhaustive_seed.py wms/tests/management/tests_management_seed_local_exhaustive_data.py
git commit -m "feat: seed billing lifecycle scenarios"
```

### Task 7: Add Targeted Smoke Alignment And Local Operator Docs

**Files:**
- Modify: `README.md`
- Modify: `wms/tests/management/tests_management_seed_local_exhaustive_data.py`
- Optional Modify: `api/tests/tests_ui_e2e_workflows.py`

**Step 1: Write the failing tests**

Add final assertions on command output so the seed remains operator-friendly:

```python
def test_command_summary_lists_accounts_urls_and_named_records(self):
    output = StringIO()

    call_command(
        "seed_local_exhaustive_data",
        "--scenario=docs",
        "--with-planning-solve",
        "--with-queue-backlog",
        stdout=output,
    )

    summary = output.getvalue()
    self.assertIn("/scan/dashboard/", summary)
    self.assertIn("/portal/login/", summary)
    self.assertIn("/benevole/login/", summary)
    self.assertIn("billing operator", summary.lower())
    self.assertIn("closable shipment", summary.lower())
```

If the implementation exposed a meaningful new smoke gap, add one targeted integration/E2E assertion instead of a monolithic new smoke suite.

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.management.tests_management_seed_local_exhaustive_data -v 2
```

Expected:
- FAIL because the current summary and docs do not yet describe the operator entry points

**Step 3: Write minimal implementation**

Complete the seed summary renderer and update [`README.md`](/Users/EdouardGonnu/asf-wms/README.md):
- add local exhaustive seed command usage
- document main options
- note that the dataset is local-only and fictional
- mention the main user accounts and URL entry points at a high level

Only add extra E2E coverage if a concrete multi-layer gap remains after the management tests are in place.

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.management.tests_management_seed_local_exhaustive_data -v 2
```

Expected:
- PASS with stable summary output and developer documentation

**Step 5: Commit**

```bash
git add README.md wms/tests/management/tests_management_seed_local_exhaustive_data.py
git commit -m "docs: document local exhaustive seed workflow"
```
