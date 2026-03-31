# ASF WMS V2 Phase 1 Local Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** deliver the first local-only phase of ASF WMS V2 by turning the existing legacy Django surfaces into an actionable cockpit across `scan`, `portal`, and queue health, without opening production rollout work yet.

**Architecture:** keep the legacy Django stack as the visible surface and use the existing `api/v1/ui` layer as the shared data contract. Phase 1 should enrich the current dashboard and portal views by reusing existing models, queue snapshots, and workflow indicators rather than introducing a new workflow engine. Treat this phase as local-only: optimize UX, thresholds, and local seed data first; defer production rollout polish until the behavior stabilizes.

**Tech Stack:** Django 4.2 templates, DRF UI endpoints, `wms/views_scan_dashboard.py`, `wms/views_portal_orders.py`, `api/v1/ui_views.py`, `IntegrationEvent` queue models, local exhaustive seed, Django test suites under `wms/tests/views` and `api/tests`.

---

### Task 1: Stabilize The Shared V2 Phase 1 Dashboard Contract

**Files:**
- Modify: `api/v1/ui_views.py`
- Modify: `api/tests/tests_ui_endpoints.py`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Optional inspect-only reference: `docs/plans/2026-03-31-pilotage-flux-roadmap.md`

**Step 1: Write the failing API tests for the new local V2 action contract**

Add focused tests in `api/tests/tests_ui_endpoints.py` covering:

```python
def test_ui_dashboard_exposes_pending_actions_with_age_owner_priority_and_url(self):
    response = self.staff_client.get("/api/v1/ui/dashboard/")
    self.assertEqual(response.status_code, 200)
    payload = response.json()
    self.assertIn("pending_actions", payload)
    item = payload["pending_actions"][0]
    self.assertIn("type", item)
    self.assertIn("reference", item)
    self.assertIn("label", item)
    self.assertIn("priority", item)
    self.assertIn("owner", item)
    self.assertIn("url", item)
    self.assertIn("age_hours", item)
```

```python
def test_ui_dashboard_exposes_document_scan_cards_alongside_email_cards(self):
    response = self.staff_client.get("/api/v1/ui/dashboard/")
    payload = response.json()
    self.assertIn("document_scan_cards", payload)
    cards = {card["label"]: card for card in payload["document_scan_cards"]}
    self.assertIn("Queue scan doc en attente", cards)
    self.assertIn("Queue scan doc en echec", cards)
```

```python
def test_ui_dashboard_pending_actions_use_stable_owner_and_priority_vocab(self):
    response = self.staff_client.get("/api/v1/ui/dashboard/")
    payload = response.json()
    allowed_owners = {"magasin", "qualite", "admin", "portal"}
    allowed_priorities = {"high", "medium", "low"}
    for item in payload["pending_actions"]:
        self.assertIn(item["owner"], allowed_owners)
        self.assertIn(item["priority"], allowed_priorities)
```

**Step 2: Run the API tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiEndpointsTests.test_ui_dashboard_exposes_pending_actions_with_age_owner_priority_and_url -v 2
./.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiEndpointsTests.test_ui_dashboard_exposes_document_scan_cards_alongside_email_cards -v 2
./.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiEndpointsTests.test_ui_dashboard_pending_actions_use_stable_owner_and_priority_vocab -v 2
```

Expected:

- FAIL because `pending_actions` items do not yet expose all required fields
- FAIL because `document_scan_cards` is not yet part of the payload

**Step 3: Implement the minimal API contract**

Update `api/v1/ui_views.py` so that `UiDashboardView.get()`:

```python
pending_actions.append(
    {
        "type": "shipment_dispute",
        "reference": shipment.reference or f"EXP-{shipment.id}",
        "label": "Resoudre litige",
        "priority": "high",
        "owner": "qualite",
        "url": reverse("scan:scan_shipments_tracking"),
        "age_hours": _age_hours(shipment.created_at),
        "context": {
            "shipment_id": shipment.id,
            "destination_id": shipment.destination_id,
        },
    }
)
```

Add a dedicated document-scan snapshot built from `IntegrationEvent`:

```python
document_scan_cards = [
    {
        "label": "Queue scan doc en attente",
        "value": snapshot["pending_count"],
        "tone": "warn" if snapshot["pending_count"] else "success",
        "url": reverse("scan:scan_dashboard"),
    },
    {
        "label": "Queue scan doc en echec",
        "value": snapshot["failed_count"],
        "tone": "danger" if snapshot["failed_count"] else "success",
        "url": reverse("scan:scan_dashboard"),
    },
]
```

Keep the owner taxonomy intentionally short and local to phase 1:

```python
ALLOWED_DASHBOARD_ACTION_OWNERS = ("magasin", "qualite", "admin", "portal")
ALLOWED_DASHBOARD_ACTION_PRIORITIES = ("high", "medium", "low")
```

**Step 4: Run the API tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiEndpointsTests.test_ui_dashboard_exposes_pending_actions_with_age_owner_priority_and_url -v 2
./.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiEndpointsTests.test_ui_dashboard_exposes_document_scan_cards_alongside_email_cards -v 2
./.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiEndpointsTests.test_ui_dashboard_pending_actions_use_stable_owner_and_priority_vocab -v 2
```

Expected:

- PASS on all three tests

**Step 5: Document the shared contract**

Update `docs/repo-reference/04-shared-contracts.md` with a short section covering:

- dashboard action item schema
- allowed `owner` and `priority` values
- local-only status for the phase 1 contract

**Step 6: Commit**

```bash
git add api/v1/ui_views.py api/tests/tests_ui_endpoints.py docs/repo-reference/04-shared-contracts.md
git commit -m "feat: define local v2 dashboard action contract"
```

### Task 2: Render The Action Queue And Queue Health In The Legacy Scan Dashboard

**Files:**
- Modify: `wms/views_scan_dashboard.py`
- Modify: `templates/scan/dashboard.html`
- Modify: `wms/tests/views/tests_views_scan_dashboard.py`
- Optional inspect-only reference: `api/v1/ui_views.py`

**Step 1: Write the failing HTML dashboard tests**

Extend `wms/tests/views/tests_views_scan_dashboard.py` with focused behavior checks:

```python
def test_scan_dashboard_renders_action_queue_panel(self):
    response = self.client.get(reverse("scan:scan_dashboard"))
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, 'id="scan-dashboard-action-queue"')
    self.assertContains(response, "A traiter maintenant")
```

```python
def test_scan_dashboard_renders_document_scan_health_cards(self):
    response = self.client.get(reverse("scan:scan_dashboard"))
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "Queue scan doc en attente")
    self.assertContains(response, "Queue scan doc en echec")
```

```python
def test_scan_dashboard_action_queue_rows_expose_owner_priority_and_cta(self):
    response = self.client.get(reverse("scan:scan_dashboard"))
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "magasin")
    self.assertContains(response, "qualite")
    self.assertContains(response, "Voir le detail")
```

**Step 2: Run the failing dashboard tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests.test_scan_dashboard_renders_action_queue_panel -v 2
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests.test_scan_dashboard_renders_document_scan_health_cards -v 2
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests.test_scan_dashboard_action_queue_rows_expose_owner_priority_and_cta -v 2
```

Expected:

- FAIL because the template has no action queue panel and no document scan section

**Step 3: Implement the minimal legacy dashboard rendering**

In `wms/views_scan_dashboard.py`, build context entries that mirror the API contract:

```python
action_queue_rows = [
    {
        "label": "Resoudre litige",
        "reference": shipment.reference,
        "owner": "qualite",
        "priority": "high",
        "age_hours": _age_hours(shipment.created_at),
        "url": reverse("scan:scan_shipments_tracking"),
    },
]
```

Add a dedicated document-scan snapshot and section:

```python
system_health_sections.append(
    _build_dashboard_section(
        section_id="scan-dashboard-document-scan",
        title=_("Technique / Scan documentaire"),
        description=_("Etat de la file antivirus et du traitement."),
        cards=document_scan_cards,
    )
)
```

In `templates/scan/dashboard.html`, add a concrete action panel:

```django
<section id="scan-dashboard-action-queue" class="scan-dashboard-section">
  <div class="scan-card card border-0 ui-comp-card scan-dashboard-section-card">
    <div class="scan-dashboard-section-header">
      <h2 class="ui-comp-title mb-1">A traiter maintenant</h2>
    </div>
    <div class="scan-table-wrap table-responsive">
      <table class="scan-table table table-sm table-hover">
        <thead>
          <tr>
            <th>Action</th>
            <th>Reference</th>
            <th>Owner</th>
            <th>Priorite</th>
            <th>Age</th>
            <th></th>
          </tr>
        </thead>
      </table>
    </div>
  </div>
</section>
```

Do not remove the existing priority cards; phase 1 adds a deeper action layer under them.

**Step 4: Run the targeted dashboard tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard -v 2
```

Expected:

- PASS on the new dashboard action queue and document scan assertions
- PASS on existing section-order assertions after any necessary expectation updates

**Step 5: Run the related UI API regression slice**

Run:

```bash
./.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiEndpointsTests -v 2
```

Expected:

- PASS, confirming HTML and API contracts stay aligned

**Step 6: Commit**

```bash
git add wms/views_scan_dashboard.py templates/scan/dashboard.html wms/tests/views/tests_views_scan_dashboard.py
git commit -m "feat: add local v2 action queue to scan dashboard"
```

### Task 3: Convert The Portal Dashboard Into A Local V2 Dossier Cockpit

**Files:**
- Modify: `wms/views_portal_orders.py`
- Modify: `templates/portal/dashboard.html`
- Modify: `api/v1/ui_views.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Modify: `api/tests/tests_ui_endpoints.py`

**Step 1: Write the failing portal cockpit tests**

Add HTML tests in `wms/tests/views/tests_portal_bootstrap_ui.py`:

```python
def test_portal_dashboard_renders_kpi_cards(self):
    response = self.client.get(reverse("portal:portal_dashboard"))
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "Commandes en attente")
    self.assertContains(response, "Corrections demandees")
```

```python
def test_portal_dashboard_renders_next_step_guidance_per_order(self):
    response = self.client.get(reverse("portal:portal_dashboard"))
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "Etape suivante")
```

Extend API tests in `api/tests/tests_ui_endpoints.py`:

```python
def test_ui_portal_dashboard_exposes_step_guidance_and_summary_counts(self):
    response = self.portal_client.get("/api/v1/ui/portal/dashboard/")
    self.assertEqual(response.status_code, 200)
    payload = response.json()
    self.assertIn("kpis", payload)
    self.assertIn("orders", payload)
    self.assertIn("next_step_label", payload["orders"][0])
```

**Step 2: Run the targeted portal tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui -v 2
./.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiEndpointsTests.test_ui_portal_dashboard_exposes_step_guidance_and_summary_counts -v 2
```

Expected:

- FAIL because the HTML template only renders an order table
- FAIL because the API rows do not yet expose next-step guidance

**Step 3: Implement the minimal local portal cockpit**

In `wms/views_portal_orders.py`, build a richer dashboard context:

```python
dashboard_kpis = {
    "orders_total": len(orders),
    "orders_pending_review": sum(1 for order in orders if order.review_status == OrderReviewStatus.PENDING),
    "orders_changes_requested": sum(1 for order in orders if order.review_status == OrderReviewStatus.CHANGES_REQUESTED),
    "orders_with_shipment": sum(1 for order in orders if order.shipment_id),
}
```

Decorate each order with a next-step helper:

```python
order.next_step_label = _portal_order_next_step_label(order)
order.next_step_tone = _portal_order_next_step_tone(order)
```

In `api/v1/ui_views.py`, extend each portal order payload:

```python
{
    "id": order.id,
    "reference": order.reference or f"CMD-{order.id}",
    "review_status_label": order.get_review_status_display(),
    "shipment_reference": order.shipment.reference if order.shipment_id else "",
    "next_step_label": _portal_order_next_step_label(order),
    "next_step_tone": _portal_order_next_step_tone(order),
}
```

In `templates/portal/dashboard.html`, add:

- a KPI card row above the table
- an "Etape suivante" column
- lightweight dossier guidance text

Example snippet:

```django
<div class="scan-kpi-grid mb-3">
  <div class="scan-kpi-card">
    <span class="scan-kpi-label">Commandes en attente</span>
    <span class="scan-kpi-value">{{ dashboard_kpis.orders_pending_review }}</span>
  </div>
</div>
```

**Step 4: Run the portal regression slice**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal -v 2
./.venv/bin/python manage.py test api.tests.tests_ui_endpoints.UiEndpointsTests.test_ui_portal_dashboard_requires_association_profile api.tests.tests_ui_endpoints.UiEndpointsTests.test_ui_portal_dashboard_exposes_step_guidance_and_summary_counts -v 2
```

Expected:

- PASS on new HTML and API expectations
- PASS on existing portal dashboard auth contract

**Step 5: Commit**

```bash
git add wms/views_portal_orders.py templates/portal/dashboard.html api/v1/ui_views.py wms/tests/views/tests_portal_bootstrap_ui.py api/tests/tests_ui_endpoints.py
git commit -m "feat: add local v2 cockpit signals to portal dashboard"
```

### Task 4: Lock The Local-Only Feedback Loop

**Files:**
- Modify: `docs/plans/2026-03-31-pilotage-flux-roadmap.md`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/deferred-follow-ups.md` (only if an explicit deferral appears during implementation)
- Optional modify: `wms/tests/management/tests_management_seed_local_exhaustive_data.py`

**Step 1: Write the failing local validation note or seed assertion**

If the existing exhaustive seed does not cover the new dashboard/portal cases, add one targeted failing seed test:

```python
def test_local_exhaustive_seed_lights_up_phase1_v2_dashboard_and_portal_cockpits(self):
    response = self.client.get(reverse("scan:scan_dashboard"))
    self.assertContains(response, "A traiter maintenant")
```

**Step 2: Run the failing local validation**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.management.tests_management_seed_local_exhaustive_data -v 2
```

Expected:

- FAIL if the local exhaustive dataset does not exercise the new signals

**Step 3: Update local verification docs and seed assumptions**

Document in `docs/plans/2026-03-31-pilotage-flux-roadmap.md` and `docs/repo-reference/02-key-flows-and-living-tests.md` that phase 1 V2 local validation now includes:

- scan dashboard action queue
- email + document scan queue health
- portal dossier cockpit

If needed, extend local seed/test fixtures so those screens are visibly populated during local runs.

**Step 4: Run the local regression slice**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard wms.tests.views.tests_portal_bootstrap_ui api.tests.tests_ui_endpoints -v 2
```

Expected:

- PASS on the phase 1 local-only cockpit contract

**Step 5: Commit**

```bash
git add docs/plans/2026-03-31-pilotage-flux-roadmap.md docs/repo-reference/02-key-flows-and-living-tests.md wms/tests/management/tests_management_seed_local_exhaustive_data.py
git commit -m "docs: lock local validation loop for v2 phase 1"
```

## Final Verification Pass

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_dashboard \
  wms.tests.views.tests_portal_bootstrap_ui \
  wms.tests.views.tests_views_portal \
  api.tests.tests_ui_endpoints \
  -v 2
```

Expected:

- PASS across the full local phase 1 cockpit slice

Run:

```bash
./.venv/bin/python manage.py seed_local_exhaustive_data \
  --scenario=local-exhaustive \
  --with-queue-backlog \
  --with-e2e-baseline
```

Expected:

- local dataset contains enough queue, shipment, and order states to visually test the new cockpits

## Notes

- Keep this phase local-only. Do not update `docs/operations.md` or `docs/release_checklist.md` for rollout wording until the local cockpit behavior stabilizes.
- If implementation reveals a new cross-surface contract, update `docs/repo-reference/04-shared-contracts.md` in the same branch.
- If a meaningful item is explicitly deferred during implementation, record it in `docs/deferred-follow-ups.md` instead of hiding it in commit messages.
