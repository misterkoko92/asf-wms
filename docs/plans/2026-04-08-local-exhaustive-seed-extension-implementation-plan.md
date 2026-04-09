# Local Exhaustive Seed Extension Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the local exhaustive dataset so one resettable seed covers portal shipper and recipient scopes, multi-scope portal access, actionable warehouse preparation runs, and actionable flight planning runs for local end-to-end QA.

**Architecture:** Build on the existing `seed_local_exhaustive_data` entrypoint instead of adding a parallel seed. Keep the current local exhaustive scenario as the single disposable QA recipe, extend it with explicit portal grants plus seeded preparation and planning runs in different states, and make the command summary expose the exact local accounts and URLs needed by a human tester.

**Tech Stack:** Django management commands, Django ORM seed helpers, legacy Django scan and portal views, planning and preparation runtime modules, Django test suite via `./.venv/bin/python manage.py test`.

---

### Task 1: Add regression coverage for the new seed contract

**Files:**
- Modify: `wms/tests/management/tests_management_seed_local_exhaustive_data.py`
- Reference: `wms/local_exhaustive_seed.py`
- Reference: `wms/models.py`

**Step 1: Write the failing tests**

Add tests that assert:

- the seed creates explicit `PortalAccessGrant` rows for shipper, recipient, and multi-scope portal users
- the seed creates actionable `PreparationRun` rows in multiple statuses, including at least one converted run with converted shipments
- the seed creates two planning runs: one ready for manual launch and one already solved

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.management.tests_management_seed_local_exhaustive_data -v 2
```

Expected: failures on missing portal grants and missing seeded preparation/planning run states.

**Step 3: Write minimal implementation**

Extend the seed helper only enough to satisfy the new test contract:

- explicit portal grants and users
- preparation runs seeded in `generated`, `frozen`, and `converted`
- planning runs seeded in `ready` and `solved`

**Step 4: Run the targeted tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.management.tests_management_seed_local_exhaustive_data -v 2
```

Expected: PASS.

### Task 2: Extend the local exhaustive seed runtime

**Files:**
- Modify: `wms/local_exhaustive_seed.py`
- Reference: `wms/preparation/generation.py`
- Reference: `wms/preparation/review.py`
- Reference: `wms/preparation/conversion.py`
- Reference: `wms/planning/recipe_dataset.py`
- Reference: `wms/portal_access.py`

**Step 1: Add portal scope seed helpers**

Create or extend helpers so the seed produces:

- `portal-<scenario>-recipient`
- `portal-<scenario>-multi`
- `PortalAccessGrant` rows for one shipper scope, one recipient scope, and one multi-scope user

**Step 2: Add preparation run seed helpers**

Seed operationally useful warehouse preparation runs:

- one run that remains generated for review
- one run that is frozen with mixed proposal decisions
- one run converted into real `Shipment` and `Carton` rows

**Step 3: Add planning run seed helpers**

Seed one planning run that is ready but unsolved and one planning run already solved, both with coherent flights, shipments, volunteers, and parameter sets.

**Step 4: Extend the seed summary output**

Print the additional accounts, URLs, and flow hints needed by local QA.

### Task 3: Verify the local QA workflow end to end

**Files:**
- Modify: `README.md`
- Reference: `docs/operations.md`
- Reference: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Reference: `docs/repo-reference/03-impact-map.md`

**Step 1: Update user-facing seed documentation if the command contract changed**

Document any new seeded users or new local QA guarantees in `README.md` if needed.

**Step 2: Rerun the relevant verification commands**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.management.tests_management_seed_local_exhaustive_data -v 2
./.venv/bin/python manage.py seed_local_exhaustive_data --scenario=local-exhaustive --fresh --with-demo-documents --with-queue-backlog --with-planning-solve --with-e2e-baseline
```

Expected: seed command completes and prints the new accounts and URLs.

**Step 3: Start the local server and capture access info**

Run:

```bash
./.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Expected: local server starts without startup errors.

**Step 4: Deliver the local QA handoff**

Report:

- local base URL
- seeded accounts and passwords
- which users cover shipper, recipient, multi-scope, staff, billing, admin, volunteer
- E2E and partial scenarios for run magasin, run vol, portal, shipment, cartons, disputes, and billing
