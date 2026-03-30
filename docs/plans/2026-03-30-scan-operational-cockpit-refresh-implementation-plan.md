# Scan Operational Cockpit Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the low-value dashboard chart and refactor `/scan/shipments-tracking/` plus `/scan/orders-view/` into clearer action-oriented scan cockpits that match the newer `Vue Colis` and `Dossiers` patterns.

**Architecture:** Keep the legacy Django routes and business logic intact, but expose tighter presenter data from the existing scan helpers and reshape the templates around summary cards plus action-first tables. Limit styling changes to local scan CSS so the refresh remains a page-local composition instead of a new shared UI primitive.

**Tech Stack:** Django views/templates, `wms/views_scan_dashboard.py`, `wms/views_scan_shipments.py`, `wms/views_scan_orders.py`, `wms/shipment_view_helpers.py`, `wms/order_view_helpers.py`, `templates/scan/*.html`, `wms/static/scan/scan-bootstrap.css`, Django test suite via `./.venv/bin/python manage.py test`

---

### Task 1: Lock Down Dashboard Simplification With Failing Tests

**Files:**
- Modify: `wms/tests/views/tests_views_scan_dashboard.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Reference: `wms/views_scan_dashboard.py`
- Reference: `templates/scan/dashboard.html`

**Step 1: Write the failing tests**

Add tests that assert the chart shell and chart-only controls are gone while KPI pilotage remains:

```python
def test_scan_dashboard_does_not_expose_chart_specific_controls(self):
    response = self.client.get(reverse("scan:scan_dashboard"))
    self.assertNotIn("chart_start", response.context)
    self.assertNotIn("chart_end", response.context)
    self.assertNotIn("shipment_status", response.context)
    self.assertNotContains(response, 'id="id_chart_start"')
    self.assertNotContains(response, 'id="id_chart_end"')
    self.assertNotContains(response, 'name="shipment_status"')


def test_scan_dashboard_renders_pilotage_without_chart_panel(self):
    response = self.client.get(reverse("scan:scan_dashboard"))
    content = response.content.decode()
    self.assertIn('id="scan-dashboard-kpi-panel"', content)
    self.assertNotIn('id="scan-dashboard-chart-panel"', content)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests.test_scan_dashboard_does_not_expose_chart_specific_controls wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests.test_scan_dashboard_renders_pilotage_without_chart_panel -v 2
```

Expected:
- FAIL because the current dashboard still computes chart context and renders chart controls/panel

**Step 3: Write minimal implementation**

In `wms/views_scan_dashboard.py`:
- remove chart-specific GET parsing
- stop building `shipment_chart_rows`, `shipments_total`, and `shipment_equivalent_total`
- stop exposing chart-specific context keys

In `templates/scan/dashboard.html`:
- remove the advanced chart toolbar block
- remove the chart panel from `Pilotage`
- keep KPI cards intact

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS with a simplified dashboard contract

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_scan_dashboard.py wms/tests/views/tests_scan_bootstrap_ui.py wms/views_scan_dashboard.py templates/scan/dashboard.html
git commit -m "feat: simplify scan dashboard pilotage"
```

### Task 2: Define Shipment Tracking Summary And Row Presenter Contract

**Files:**
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/shipment_view_helpers.py`
- Modify: `wms/views_scan_shipments.py`

**Step 1: Write the failing tests**

Add tests for the new presenter fields and summary cards:

```python
def test_scan_shipments_tracking_exposes_summary_cards(self):
    response = self.client.get(reverse("scan:scan_shipments_tracking"))
    self.assertEqual(
        [card["id"] for card in response.context["summary_cards"]],
        [
            "open-disputes",
            "closable-cases",
            "waiting-stopover",
            "waiting-delivery",
        ],
    )


def test_build_shipments_tracking_rows_marks_dispute_and_next_action(self):
    rows = build_shipments_tracking_rows([shipment])
    self.assertEqual(rows[0]["next_action_label"], "Traiter le litige")
    self.assertTrue(rows[0]["is_disputed"])
    self.assertEqual(rows[0]["row_tone"], "danger")
```

Also add a bootstrap/UI assertion that the page renders a summary strip and a dedicated next-action column.

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments.ScanShipmentsViewsTests wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_dashboard_and_tracking_views_use_design_component_classes -v 2
```

Expected:
- FAIL because the current tracking view context and row helper do not expose summary cards or next-action fields

**Step 3: Write minimal implementation**

In `wms/shipment_view_helpers.py`, extend tracking rows with:

```python
{
    "status_display": present_shipment_status(shipment),
    "badges": [...],
    "last_step_label": "...",
    "last_step_at": some_datetime,
    "next_action_label": "...",
    "row_tone": "danger",
}
```

In `wms/views_scan_shipments.py`, build `summary_cards` from the existing tracking query results:
- disputes
- closable
- waiting stopover
- waiting delivery

Keep closure and tracking-update business rules unchanged.

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS with the new tracking presenter contract available in context

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_scan_bootstrap_ui.py wms/shipment_view_helpers.py wms/views_scan_shipments.py
git commit -m "feat: add scan shipment tracking cockpit presenter"
```

### Task 3: Reshape Shipment Tracking Template Into An Action-First Table

**Files:**
- Modify: `templates/scan/shipments_tracking.html`
- Modify: `wms/static/scan/scan-bootstrap.css`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_views_tracking_dispute.py`

**Step 1: Write the failing tests**

Add template/UI tests for the new table shell:

```python
def test_scan_shipments_tracking_renders_summary_cards_and_next_action_column(self):
    response = self.client.get(reverse("scan:scan_shipments_tracking"))
    self.assertContains(response, 'id="scan-shipments-tracking-summary"')
    self.assertContains(response, "<th>À faire</th>", html=True)


def test_scan_shipments_tracking_surfaces_litige_badge_in_primary_cell(self):
    response = self.client.get(reverse("scan:scan_shipments_tracking"))
    self.assertContains(response, "Litige")
    self.assertContains(response, "Traiter le litige")
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_shipments_tracking_renders_summary_cards_and_next_action_column wms.tests.views.tests_views_tracking_dispute.ShipmentTrackingDisputeFlowTests -v 2
```

Expected:
- FAIL because the current template still renders the old date-heavy table

**Step 3: Write minimal implementation**

In `templates/scan/shipments_tracking.html`:
- keep the existing filter form
- add a summary-card strip below the filters
- replace the date-heavy table with the new five-column layout
- render dispute and closed badges in the first column
- render `next_action_label` in the dedicated action column

In `wms/static/scan/scan-bootstrap.css`:
- add local tracking page classes for the summary strip and row emphasis
- add stronger visual treatment for dispute rows
- preserve responsiveness by stacking cell metadata within the column

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS with disputes clearly surfaced and the new action-first table rendered

**Step 5: Commit**

```bash
git add templates/scan/shipments_tracking.html wms/static/scan/scan-bootstrap.css wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_tracking_dispute.py
git commit -m "feat: refresh scan shipment tracking cockpit"
```

### Task 4: Define Orders Summary And Action Presenter Contract

**Files:**
- Modify: `wms/tests/views/tests_views_scan_orders.py`
- Modify: `wms/order_view_helpers.py`
- Modify: `wms/views_scan_orders.py`
- Reference: `wms/order_view_handlers.py`

**Step 1: Write the failing tests**

Add tests for summary cards and next-action fields:

```python
def test_scan_orders_view_exposes_summary_cards(self):
    response = self.client.get(reverse("scan:scan_orders_view"))
    self.assertEqual(
        [card["id"] for card in response.context["summary_cards"]],
        [
            "pending-review",
            "changes-requested",
            "approved-without-shipment",
            "rejected-orders",
        ],
    )


def test_build_orders_view_rows_exposes_next_action_and_review_status_display(self):
    rows = build_orders_view_rows(Order.objects.all())
    self.assertEqual(rows[0]["next_action_label"], "Créer l'expédition")
    self.assertEqual(rows[0]["review_status_display"]["domain"], "order_review")
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_orders.ScanOrdersViewsTests -v 2
```

Expected:
- FAIL because the current orders view does not expose summary cards or next-action presenter fields

**Step 3: Write minimal implementation**

In `wms/order_view_helpers.py`, extend each row with:

```python
{
    "review_status_display": present_order_review_status(order),
    "next_action_label": "...",
    "can_create_shipment": bool(...),
    "contact_lines": [...],
}
```

In `wms/views_scan_orders.py`, build `summary_cards` from the orders queryset:
- pending review
- changes requested
- approved without shipment
- rejected

Reuse existing review and shipment-creation business logic.

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS with the new orders presenter contract

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_scan_orders.py wms/order_view_helpers.py wms/views_scan_orders.py
git commit -m "feat: add scan orders cockpit presenter"
```

### Task 5: Reshape Orders Template Around Review Status And Next Action

**Files:**
- Modify: `templates/scan/orders_view.html`
- Modify: `wms/static/scan/scan-bootstrap.css`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Reference: `wms/tests/views/tests_views_portal.py`

**Step 1: Write the failing tests**

Add template/UI tests for the new shell:

```python
def test_scan_orders_view_renders_summary_cards_and_action_column(self):
    response = self.client.get(reverse("scan:scan_orders_view"))
    self.assertContains(response, 'id="scan-orders-summary"')
    self.assertContains(response, "<th>Action attendue</th>", html=True)


def test_scan_orders_view_does_not_render_follow_up_rows_below_main_row(self):
    response = self.client.get(reverse("scan:scan_orders_view"))
    self.assertNotContains(response, "Refus:")
    self.assertNotContains(response, "Modifier:")
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_orders_view_renders_summary_cards_and_action_column wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_orders_view_does_not_render_follow_up_rows_below_main_row -v 2
```

Expected:
- FAIL because the template still renders the old secondary follow-up rows and no summary strip

**Step 3: Write minimal implementation**

In `templates/scan/orders_view.html`:
- add a summary-card strip above the table
- replace the current columns with the new action-first layout
- keep the review-status update form in the review column
- move follow-up guidance into `Action attendue`
- remove the separate follow-up rows for rejected / changes requested

In `wms/static/scan/scan-bootstrap.css`:
- add local layout for order summary cards
- keep contact details compact
- make the primary shipment-creation action visually obvious only when valid

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS with the new cockpit shell and compact action guidance

**Step 5: Commit**

```bash
git add templates/scan/orders_view.html wms/static/scan/scan-bootstrap.css wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: refresh scan orders review cockpit"
```

### Task 6: Run Focused Verification And Close Repo-Reference Checks

**Files:**
- Re-check: `docs/repo-reference/03-impact-map.md`
- Re-check: `docs/repo-reference/04-shared-contracts.md`
- Optional Modify: `docs/repo-reference/*` only if an actual shared contract changed

**Step 1: Run focused tests**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_dashboard \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_views_scan_orders \
  wms.tests.views.tests_views_tracking_dispute \
  wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected:
- PASS for the refreshed dashboard, shipment-tracking, orders, dispute, and bootstrap UI coverage

**Step 2: Run one broader scan smoke subset if needed**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views wms.tests.core.tests_status_presenters -v 2
```

Expected:
- PASS with no regressions in shared status wording assumptions

**Step 3: Re-check propagation docs**

Confirm whether the change remained page-local:
- `docs/repo-reference/03-impact-map.md` scan-page checklist
- `docs/repo-reference/04-shared-contracts.md` shared UI contract

Expected:
- no repo-reference update needed unless a shared primitive semantic changed

**Step 4: Commit verification-safe changes**

```bash
git add wms/tests/views/tests_views_scan_dashboard.py wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_views_scan_orders.py wms/tests/views/tests_views_tracking_dispute.py wms/tests/views/tests_scan_bootstrap_ui.py wms/views_scan_dashboard.py wms/views_scan_shipments.py wms/views_scan_orders.py wms/shipment_view_helpers.py wms/order_view_helpers.py templates/scan/dashboard.html templates/scan/shipments_tracking.html templates/scan/orders_view.html wms/static/scan/scan-bootstrap.css
git commit -m "feat: refresh scan operational cockpits"
```
