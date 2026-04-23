# Cartons Ready Preassignment Mismatch Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a guarded destination-mismatch confirmation flow to bulk shipment assignment on `/scan/cartons/` so cartons preassigned to one destination cannot be silently assigned to a shipment targeting another destination.

**Architecture:** Keep the legacy Django cartons list and existing bulk assignment handler, but extend the list payload with preassignment metadata, add a page-local mismatch confirmation modal in the cartons-ready JS module, and enforce the same confirmation server-side before assigning conflicting cartons. Reuse the current editable shipment dataset rather than introducing a new batching UI.

**Tech Stack:** Django views/templates/helpers, legacy scan static modules, Django test suite via `./.venv/bin/python manage.py test`

---

### Task 1: Lock The Current Mismatch And Assignment Expectations In Tests

**Files:**
- Modify: `wms/tests/carton/tests_carton_handlers.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Add handler coverage for:

- bulk assignment with no destination mismatch still succeeding
- bulk assignment with mismatch being rejected when confirmation is missing
- confirmed mismatch assignment succeeding and clearing `preassigned_destination`

Add view coverage for:

- `Vue Colis` rendering the mismatch modal shell
- the table exposing carton preassignment metadata needed by page JS

Example assertions:

```python
self.assertRedirects(response, reverse("scan:scan_cartons_ready"))
carton.refresh_from_db()
self.assertEqual(carton.shipment_id, shipment.id)
self.assertIsNone(carton.preassigned_destination_id)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.carton.tests_carton_handlers \
  wms.tests.views.tests_views_scan_shipments \
  -v 2
```

Expected:
- FAIL because the cartons-ready bulk assignment flow does not yet expose or enforce mismatch confirmation

**Step 3: Write minimal implementation**

Do not implement behavior yet beyond the smallest payload or assertions needed to move to the next failing slice.

**Step 4: Run test to verify it still fails for the intended reason**

Run the same command.

Expected:
- FAIL only on the new mismatch-specific assertions

**Step 5: Commit**

```bash
git add wms/tests/carton/tests_carton_handlers.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "test: cover cartons ready destination mismatch flow"
```

### Task 2: Add Server-Side Mismatch Validation For Bulk Assignment

**Files:**
- Modify: `wms/carton_handlers.py`
- Modify: `wms/tests/carton/tests_carton_handlers.py`

**Step 1: Write the failing test**

Add focused cases for:

- mixed selection where one carton matches and one conflicts
- confirmation flag allowing only the conflicting cartons to override
- warning/success messaging reflecting updated vs ignored cartons

Example POST payload:

```python
{
    "action": "bulk_assign_cartons_shipment",
    "selected_carton_ids": [str(carton.id)],
    "bulk_shipment_id": str(target_shipment.id),
    "confirm_preassigned_destination_mismatch": "1",
}
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.carton.tests_carton_handlers -v 2
```

Expected:
- FAIL because the handler does not yet distinguish destination mismatch from normal assignment

**Step 3: Write minimal implementation**

In `wms/carton_handlers.py`:

- add a helper that determines whether a selected carton conflicts with the target shipment destination
- require explicit confirmation for conflicting cartons on `bulk_assign_cartons_shipment`
- clear `preassigned_destination` when a confirmed override is applied
- keep existing shipment editability and carton mutability protections
- keep non-conflicting cartons on the current assignment path

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

**Step 5: Commit**

```bash
git add wms/carton_handlers.py wms/tests/carton/tests_carton_handlers.py
git commit -m "feat: guard cartons ready destination override"
```

### Task 3: Add The Cartons-Ready Modal And Client-Side Selection Flow

**Files:**
- Modify: `templates/scan/cartons_ready.html`
- Modify: `wms/static/scan/modules/cartons-ready.js`
- Modify if needed: `wms/carton_view_helpers.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Add view assertions for:

- dedicated mismatch modal DOM ids
- hidden form inputs for mismatch confirmation state
- carton row metadata for preassigned destination id and code

If existing payload is insufficient, add helper coverage for the row metadata in:

- `wms/tests/carton/tests_carton_view_helpers.py`

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.carton.tests_carton_view_helpers \
  -v 2
```

Expected:
- FAIL because the modal and metadata are not rendered yet

**Step 3: Write minimal implementation**

In `templates/scan/cartons_ready.html`:

- add a dedicated mismatch confirmation modal
- add hidden inputs for mismatch confirmation flow
- expose carton preassignment metadata through `data-*` attributes

In `wms/static/scan/modules/cartons-ready.js`:

- intercept bulk assignment submit when a shipment is selected
- identify conflicting cartons from the selected rows
- open the mismatch modal only when conflicts exist
- implement the three actions:
  - continue anyway
  - remove conflicting cartons and submit
  - cancel
- preserve the existing skip-status confirmation behavior

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

**Step 5: Commit**

```bash
git add templates/scan/cartons_ready.html wms/static/scan/modules/cartons-ready.js wms/carton_view_helpers.py wms/tests/views/tests_views_scan_shipments.py wms/tests/carton/tests_carton_view_helpers.py
git commit -m "feat: add cartons ready mismatch modal"
```

### Task 4: Verify The Focused Flow And Re-Check Repo-Reference Impact

**Files:**
- Modify if needed: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Run focused verification**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.carton.tests_carton_handlers \
  wms.tests.carton.tests_carton_view_helpers \
  wms.tests.views.tests_views_scan_shipments \
  -v 2
```

Expected:
- PASS with the impacted handler, helper, and view suites green

**Step 2: Re-check repo-reference impact**

Confirm whether the new mismatch modal changed the durable `Vue Colis` list contract enough to justify a short note in `docs/repo-reference/04-shared-contracts.md`.

Expected outcome:
- likely no repo-reference doc update unless the list contract now formally includes this guardrail

**Step 3: Make only the minimal doc update required**

If documentation is needed:

- add a short note about bulk shipment assignment warning on destination mismatch
- avoid broad wording changes outside `/scan/cartons/`

**Step 4: Re-run focused verification if runtime files changed during doc alignment**

Run the same command if needed.

Expected:
- PASS

**Step 5: Commit**

```bash
git add docs/repo-reference/04-shared-contracts.md
git commit -m "docs: align cartons ready mismatch contract"
```
