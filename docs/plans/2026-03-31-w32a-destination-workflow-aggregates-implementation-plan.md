# W3.2a Destination Workflow Aggregates Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** add a first destination-level workflow aggregate endpoint on top of `ShipmentWorkflowProjection`

**Architecture:** the lot stays read-only and computes aggregates directly from the shipment workflow
projection table. Filters are applied to shipment projection rows first, then grouped into one row per
destination and sorted by operational criticity.

**Tech Stack:** Django, DRF, legacy `api/v1/views.py`, Django ORM aggregation helpers, repo-reference docs

---

### Task 1: Add failing API contract tests for destination aggregates

**Files:**
- Modify: `api/tests/tests_views_extra.py`
- Test: `api/tests/tests_views_extra.py`

**Step 1: Write the failing test**

Add tests that create multiple `ShipmentWorkflowProjection` rows across destinations and assert:

- one aggregate row per destination
- grouped counts match the source rows
- averages and max age are computed correctly

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test api.tests.tests_views_extra.ApiViewsExtraTests.test_workflow_projections_destinations_endpoint_returns_aggregated_rows -v 2`
Expected: FAIL because the endpoint does not exist yet

**Step 3: Write the failing filter/sort test**

Add a second test asserting:

- filters are applied before aggregation
- the default order prefers more critical destinations first

**Step 4: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test api.tests.tests_views_extra.ApiViewsExtraTests.test_workflow_projections_destinations_endpoint_applies_filters_before_grouping -v 2`
Expected: FAIL because the endpoint does not exist yet

### Task 2: Implement the destination aggregate helper

**Files:**
- Modify: `wms/workflow_projection.py`
- Test: `api/tests/tests_views_extra.py`

**Step 1: Write minimal aggregation helpers**

Add helper functions that:

- group filtered `ShipmentWorkflowProjection` rows by destination
- compute counts, averages, max age, top delay state, and top blockage category
- return JSON-ready rows

**Step 2: Run focused tests**

Run: `./.venv/bin/python manage.py test api.tests.tests_views_extra.ApiViewsExtraTests.test_workflow_projections_destinations_endpoint_returns_aggregated_rows -v 2`
Expected: still FAIL until the endpoint is wired

### Task 3: Add the DRF endpoint and route

**Files:**
- Modify: `api/v1/views.py`
- Modify: `api/v1/urls.py`
- Test: `api/tests/tests_views_extra.py`

**Step 1: Add the read-only endpoint**

Create `WorkflowProjectionDestinationsView` in `api/v1/views.py`.

Requirements:

- authenticated only
- reuse the same shipment-projection filter vocabulary where applicable
- aggregate after filtering
- order by critical count, dispute count, oldest age, then label

**Step 2: Add the route**

Register:

- `GET /api/v1/workflow-projections/destinations/`

**Step 3: Run the targeted API tests**

Run: `./.venv/bin/python manage.py test api.tests.tests_views_extra -v 2`
Expected: PASS

### Task 4: Update repo-reference and runbook if the contract changed

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Modify: `docs/operations.md` only if a new local operator action is introduced

**Step 1: Record the new contract**

Document:

- the destination aggregate endpoint
- its role relative to shipment workflow projections
- the reference tests that protect it

**Step 2: Re-check impact propagation**

Confirm that no legacy HTML mirror is required in this lot and that the contract remains API-first.

### Task 5: Verification and commit

**Files:**
- Modify: any files touched above

**Step 1: Run focused verification**

Run:

```bash
./.venv/bin/python manage.py test api.tests.tests_views_extra -v 2
uv run ruff check api/tests/tests_views_extra.py api/v1/views.py api/v1/urls.py wms/workflow_projection.py
```

Expected:

- tests PASS
- ruff PASS

**Step 2: Optional authenticated local smoke**

Run an authenticated local request against:

- `/api/v1/workflow-projections/destinations/`

Expected:

- `200`
- at least one destination row on the seeded local dataset

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: add destination workflow projection aggregates"
```
