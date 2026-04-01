# W2.1 Centre Litiges Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** enrich the legacy shipment tracking flow with a structured local dispute center so operators can assign, qualify, follow, and resolve shipment disputes without introducing a dedicated case table yet.

**Architecture:** keep `Shipment.is_disputed` as the existing lock signal and extend `Shipment` with a small set of structured dispute fields. Reuse the current tracking detail and tracking list surfaces as the only operator entry points: detail for declaration and resolution, list for prioritization and filtering. Keep history local and lightweight by deriving a visible timeline from shipment fields and dossier activity rather than creating a new dispute event model.

**Tech Stack:** Django 4.2 models and migrations, legacy scan templates, `wms/views_scan_shipments.py`, `wms/shipment_tracking_handlers.py`, `wms/shipment_view_helpers.py`, Django tests under `wms/tests/views`, repo-reference docs.

---

### Task 1: Lock The W2.1 Design In Docs

**Files:**
- Create: `docs/plans/2026-03-31-w21-centre-litiges-design.md`
- Create: `docs/plans/2026-03-31-w21-centre-litiges-implementation-plan.md`
- Inspect: `docs/plans/2026-03-31-pilotage-flux-roadmap.md`
- Inspect: `docs/repo-reference/03-impact-map.md`

**Step 1: Write the design note**

Document:
- why local-first stays on `Shipment`,
- which fields are added,
- which vocabularies are intentionally short,
- what the detail and list screens must expose,
- which risks are deliberately deferred.

**Step 2: Write the implementation plan**

Break the work into TDD-sized tasks covering:
- model and migration,
- dispute handler behavior,
- tracking detail rendering,
- tracking list filters,
- docs and verification.

**Step 3: Sanity check the plan against repo-reference**

Confirm the plan names the correct touchpoints:
- `wms/models_domain/shipment.py`
- `wms/shipment_tracking_handlers.py`
- `wms/views_scan_shipments.py`
- `wms/views_scan_shipments_support.py`
- `wms/shipment_view_helpers.py`
- `templates/scan/shipment_tracking.html`
- `templates/scan/shipments_tracking.html`
- `wms/tests/views/tests_views_tracking_dispute.py`
- `wms/tests/views/tests_views_scan_shipments.py`
- `docs/repo-reference/04-shared-contracts.md`

### Task 2: Add The First Failing Dispute Detail Tests

**Files:**
- Modify: `wms/tests/views/tests_views_tracking_dispute.py`
- Reference: `wms/shipment_tracking_handlers.py`
- Reference: `templates/scan/shipment_tracking.html`

**Step 1: Write a failing test for structured dispute creation**

Add a test covering:

```python
def test_set_disputed_stores_structured_reason_owner_status_due_at(self):
    due_at = timezone.now() + timedelta(days=2)
    response = self.client.post(
        reverse("scan:scan_shipment_track", args=[shipment.tracking_token]),
        {
            "action": "set_disputed",
            "dispute_reason": "docs_missing",
            "dispute_owner": "qualite",
            "dispute_status": "open",
            "dispute_due_at": due_at.strftime("%Y-%m-%dT%H:%M"),
        },
    )
```

Assert:
- redirect,
- `shipment.is_disputed` is true,
- fields were saved,
- opened timestamp exists,
- dossier activity label reflects a dispute opening.

**Step 2: Run that test and verify RED**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_tracking_dispute.ShipmentTrackingDisputeFlowTests.test_set_disputed_stores_structured_reason_owner_status_due_at -v 2
```

Expected:
- FAIL because the new fields and parsing do not exist yet.

**Step 3: Write a failing test for required resolution notes**

Add a test covering:
- open disputed shipment,
- post `action=resolve_dispute` without notes,
- expect `200`,
- expect shipment still disputed,
- expect a form or message error.

**Step 4: Run that test and verify RED**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_tracking_dispute.ShipmentTrackingDisputeFlowTests.test_resolve_dispute_requires_resolution_notes -v 2
```

Expected:
- FAIL because resolution currently succeeds without notes.

### Task 3: Add The First Failing Tracking List Filter Tests

**Files:**
- Modify: `wms/tests/views/tests_views_tracking_dispute.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Reference: `wms/views_scan_shipments.py`
- Reference: `wms/views_scan_shipments_support.py`
- Reference: `wms/shipment_view_helpers.py`

**Step 1: Write a failing test for `dispute=open`**

Create multiple shipments and assert that:
- the list only keeps disputed open cases,
- non-disputed rows are excluded,
- response contains the open dispute row.

**Step 2: Run the test and verify RED**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_tracking_dispute.ShipmentTrackingDisputeFlowTests.test_shipments_tracking_filter_open_disputes_only -v 2
```

**Step 3: Write a failing test for `dispute=overdue` and `dispute=unassigned`**

Assert that:
- overdue means `is_disputed=True` and `dispute_due_at < now`,
- unassigned means `is_disputed=True` and blank owner,
- the correct shipment references are shown and the others are not.

**Step 4: Run the tests and verify RED**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_tracking_dispute.ShipmentTrackingDisputeFlowTests.test_shipments_tracking_filter_overdue_disputes_only -v 2
./.venv/bin/python manage.py test wms.tests.views.tests_views_tracking_dispute.ShipmentTrackingDisputeFlowTests.test_shipments_tracking_filter_unassigned_disputes_only -v 2
```

### Task 4: Implement The Shipment Dispute Data Model

**Files:**
- Modify: `wms/models_domain/shipment.py`
- Create: `wms/migrations/0100_shipment_structured_dispute_fields.py`
- Optional inspect: `wms/models.py`

**Step 1: Add the fields and local enums**

In `wms/models_domain/shipment.py`, add:
- `ShipmentDisputeReason`
- `ShipmentDisputeStatus`
- `ShipmentDisputeOwner`

Then extend `Shipment` with:

```python
dispute_reason = models.CharField(max_length=40, choices=..., blank=True, default="")
dispute_owner = models.CharField(max_length=20, choices=..., blank=True, default="")
dispute_status = models.CharField(max_length=20, choices=..., blank=True, default="")
dispute_due_at = models.DateTimeField(null=True, blank=True)
dispute_opened_at = models.DateTimeField(null=True, blank=True)
dispute_resolved_at = models.DateTimeField(null=True, blank=True)
dispute_resolution_notes = models.TextField(blank=True)
```

**Step 2: Add the migration**

Create `0100_shipment_structured_dispute_fields.py` with the new shipment fields.

**Step 3: Run the targeted tests again**

Run the RED tests from tasks 2 and 3.

Expected:
- still FAIL, but now because behavior is not implemented rather than fields missing.

### Task 5: Implement Structured Dispute Handler Logic

**Files:**
- Modify: `wms/shipment_tracking_handlers.py`
- Optional modify: `wms/workflow_observability.py`
- Reference: `wms/shipment_dossier_activity.py`

**Step 1: Add minimal parsing and validation helpers**

Implement helpers for:
- accepted reason/owner/status vocabularies,
- parsing `dispute_due_at`,
- validating required fields on opening,
- validating `dispute_resolution_notes` on resolution.

**Step 2: Update `set_disputed`**

Behavior:
- if shipment is not already disputed, open it,
- if already disputed, treat the post as an update to the active dispute,
- persist reason, owner, status, due date, opened timestamp,
- clear resolution fields while dispute is active,
- keep the current redirect behavior.

**Step 3: Update `resolve_dispute`**

Behavior:
- reject empty `dispute_resolution_notes`,
- keep the page rendered with an error when notes are missing,
- on success, set:
  - `is_disputed=False`
  - `dispute_status="resolved"`
  - `dispute_resolved_at=timezone.now()`
  - `dispute_resolution_notes=<submitted notes>`
- preserve the current shipment/carton reset logic.

**Step 4: Enrich workflow logging**

Pass through structured payload such as:
- `dispute_reason`
- `dispute_owner`
- `dispute_status`
- `dispute_due_at`

Keep the event type unchanged for now.

**Step 5: Run the dispute flow tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_tracking_dispute -v 2
```

Expected:
- detail flow tests now pass or fail only on rendering gaps.

### Task 6: Render The Structured Dispute Panel In Tracking Detail

**Files:**
- Modify: `wms/views_scan_shipments.py`
- Modify: `templates/scan/shipment_tracking.html`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/tests/views/tests_views_tracking_dispute.py`

**Step 1: Write the failing rendering tests**

Add tests asserting that tracking detail context or HTML now exposes:
- `dispute_summary`
- `dispute_timeline`
- current owner / reason / due date
- resolution notes once resolved

**Step 2: Run those tests and verify RED**

Run the specific test methods you added.

**Step 3: Build the minimal context**

In `wms/views_scan_shipments.py`, derive:
- a `dispute_summary` dict for the current or last dispute,
- a `dispute_timeline` list from opened/resolved/activity timestamps.

**Step 4: Render the UI**

In `templates/scan/shipment_tracking.html`:
- replace the binary dispute controls with structured fields,
- keep the update-tracking block locked when disputed,
- show the dispute summary and derived timeline.

**Step 5: Re-run the new detail tests**

Confirm the tracking detail tests pass.

### Task 7: Add The Dispute Filters And Row Metadata To The Tracking List

**Files:**
- Modify: `wms/views_scan_shipments_support.py`
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/shipment_view_helpers.py`
- Modify: `templates/scan/shipments_tracking.html`
- Modify: `wms/tests/views/tests_views_tracking_dispute.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Implement filter parsing**

Add a normalized `dispute_filter` parameter with allowed values:
- `all`
- `open`
- `overdue`
- `unassigned`

Default should be `all`.

**Step 2: Apply queryset filters**

In `scan_shipments_tracking`:
- `open`: `is_disputed=True`
- `overdue`: `is_disputed=True` and `dispute_due_at__lt=timezone.now()`
- `unassigned`: `is_disputed=True` and blank `dispute_owner`

**Step 3: Extend row payloads**

In `build_shipments_tracking_rows`, expose:
- `dispute_reason_display`
- `dispute_owner_display`
- `dispute_status_display`
- `dispute_due_at`
- `is_dispute_overdue`
- refined `next_action_label`

**Step 4: Update the template**

Add:
- a `dispute` filter select,
- row-side dispute metadata in the primary or action columns.

**Step 5: Run the list tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_tracking_dispute wms.tests.views.tests_views_scan_shipments -v 2
```

Expected:
- filter and row tests pass.

### Task 8: Update Repo Reference And Run Final Verification

**Files:**
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Optional modify: `docs/repo-reference/02-key-flows-and-living-tests.md`

**Step 1: Document the local dispute contract**

Add a short section covering:
- structured dispute fields now stored on `Shipment`,
- meaning of open vs overdue vs unassigned list filters,
- tracking detail as the edit surface,
- list view as the prioritization surface.

**Step 2: Run the final targeted verification**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_tracking_dispute -v 2
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2
```

If the touched contract leaks into API or flow tests, also run:

```bash
./.venv/bin/python manage.py test wms.tests.core.tests_flow api.tests.tests_ui_e2e_workflows -v 2
```

**Step 3: Review the diff against the W2.1 exit criteria**

Checklist:
- structured open dispute
- mandatory resolution notes
- tracking detail dispute panel
- tracking list filters
- repo-reference updated

**Step 4: Commit**

```bash
git add wms/models_domain/shipment.py wms/migrations/0100_shipment_structured_dispute_fields.py wms/shipment_tracking_handlers.py wms/views_scan_shipments.py wms/views_scan_shipments_support.py wms/shipment_view_helpers.py templates/scan/shipment_tracking.html templates/scan/shipments_tracking.html wms/tests/views/tests_views_tracking_dispute.py wms/tests/views/tests_views_scan_shipments.py docs/repo-reference/04-shared-contracts.md docs/plans/2026-03-31-w21-centre-litiges-design.md docs/plans/2026-03-31-w21-centre-litiges-implementation-plan.md
git commit -m "feat: add local shipment dispute center"
```
