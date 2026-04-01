# W3.2c Destination Week Workflow Aggregates Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a read-only API endpoint that aggregates shipment workflow projections by destination and ISO week of `planned_at`.

**Architecture:** Reuse `ShipmentWorkflowProjection` as the only source of truth, add one aggregation helper in `wms/workflow_projection.py`, expose it through a dedicated DRF view and URL, and document the new shared contract in repo-reference. Keep the lot local-first, read-only, and API-first.

**Tech Stack:** Django, DRF, ORM read-model queries, legacy repo-reference docs, Django test suite

---

### Task 1: Add the failing API contract tests

**Files:**
- Modify: `api/tests/tests_views_extra.py`

**Step 1: Write the failing test**

Add one test proving that `GET /api/v1/workflow-projections/destination-weeks/` groups rows by
`destination + iso_year + iso_week` of `planned_at`, excludes rows with no `planned_at`, and
returns the expected counts and dominant blockage.

Add one second test proving that `iso_year`, `iso_week`, `delay_state`, and `has_open_dispute`
are applied before grouping.

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test api.tests.tests_views_extra.WorkflowProjectionApiTests -v 2
```

Expected:

- failure because the new route does not exist yet

### Task 2: Implement the aggregation helper

**Files:**
- Modify: `wms/workflow_projection.py`

**Step 1: Write minimal implementation**

Add a helper that:

- filters out rows with null `planned_at`
- derives ISO year and ISO week from `planned_at`
- groups rows by destination and week
- computes the local contract fields
- applies the stable default sort and optional limit

Keep the implementation read-only and aligned with the existing destination aggregate helper.

**Step 2: Run the focused API test**

Run:

```bash
./.venv/bin/python manage.py test api.tests.tests_views_extra.WorkflowProjectionApiTests -v 2
```

Expected:

- failures move from missing helper/route to contract mismatches

### Task 3: Expose the new endpoint

**Files:**
- Modify: `api/v1/views.py`
- Modify: `api/v1/urls.py`

**Step 1: Write minimal implementation**

Add `WorkflowProjectionDestinationWeeksView` that:

- starts from `ShipmentWorkflowProjection.objects.select_related("destination")`
- reuses `_apply_workflow_projection_filters`
- reads `iso_year`, `iso_week`, and `limit`
- calls the new aggregation helper
- returns the list payload directly

Register the route:

- `/api/v1/workflow-projections/destination-weeks/`

**Step 2: Run the focused API test**

Run:

```bash
./.venv/bin/python manage.py test api.tests.tests_views_extra.WorkflowProjectionApiTests -v 2
```

Expected:

- the new destination-week tests pass

### Task 4: Update the shared contract docs

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Create: `docs/plans/2026-03-31-w32c-destination-week-workflow-aggregates-design.md`
- Create: `docs/plans/2026-03-31-w32c-destination-week-workflow-aggregates-implementation-plan.md`

**Step 1: Document the new contract**

Record:

- the new endpoint location
- the `(destination, iso week)` row shape
- the `planned_at` anchor rule
- the supported filters and sort order
- the reference tests to keep in sync

### Task 5: Run verification and commit

**Files:**
- Modify: `api/tests/tests_views_extra.py`
- Modify: `api/v1/views.py`
- Modify: `api/v1/urls.py`
- Modify: `wms/workflow_projection.py`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Run targeted verification**

Run:

```bash
./.venv/bin/python manage.py test api.tests.tests_views_extra wms.tests.test_workflow_projection -v 2
uv run ruff check api/tests/tests_views_extra.py api/v1/views.py api/v1/urls.py wms/workflow_projection.py
```

Expected:

- tests green
- lint green

**Step 2: Commit**

```bash
git add api/tests/tests_views_extra.py api/v1/views.py api/v1/urls.py wms/workflow_projection.py docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md docs/plans/2026-03-31-w32c-destination-week-workflow-aggregates-design.md docs/plans/2026-03-31-w32c-destination-week-workflow-aggregates-implementation-plan.md
git commit -m "feat: add destination week workflow aggregates"
```
