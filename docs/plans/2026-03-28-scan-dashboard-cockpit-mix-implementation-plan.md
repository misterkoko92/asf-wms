# Scan Dashboard Cockpit Mix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rework `/scan/dashboard/` into a mixed cockpit with a compact page header, one visible dashboard toolbar, an explicit priority strip, a grouped `Pilotage` block, and calmer lower `Flux` / `Santé système` sections.

**Architecture:** Keep the legacy Django `scan_dashboard` route and most existing metric calculations, but regroup the current dashboard cards in `wms/views_scan_dashboard.py` into explicit page actions, anchors, priority cards, flow sections, and system-health sections. Then reshape `templates/scan/dashboard.html` and local dashboard CSS in `wms/static/scan/scan-bootstrap.css` around those new context groups without changing metric semantics or reopening shared UI governance.

**Tech Stack:** Django views/templates, `wms/views_scan_dashboard.py`, `templates/scan/dashboard.html`, `wms/static/scan/scan-bootstrap.css`, Django test suite via `./.venv/bin/python manage.py test`

---

### Task 1: Lock Down The Presenter Contract With Failing View Tests

**Files:**
- Modify: `wms/tests/views/tests_views_scan_dashboard.py`
- Reference: `wms/views_scan_dashboard.py`

**Step 1: Write the failing tests**

Add view tests that describe the new dashboard context contract:

```python
def test_scan_dashboard_exposes_actions_anchors_and_grouped_sections(self):
    response = self.client.get(reverse("scan:scan_dashboard"))

    self.assertEqual(
        [item["id"] for item in response.context["dashboard_anchors"]],
        [
            "scan-dashboard-priorities",
            "scan-dashboard-pilotage",
            "scan-dashboard-flow",
            "scan-dashboard-health",
        ],
    )
    self.assertEqual(response.context["page_actions"][0]["url"], reverse("scan:scan_shipment_create"))
    self.assertEqual(len(response.context["priority_cards"]), 6)
    self.assertEqual(response.context["flow_sections"][0]["id"], "scan-dashboard-stock")
    self.assertEqual(response.context["system_health_sections"][0]["id"], "scan-dashboard-technical")


def test_scan_dashboard_priority_cards_include_explicit_cta_labels(self):
    response = self.client.get(reverse("scan:scan_dashboard"))
    self.assertEqual(
        [card["cta_label"] for card in response.context["priority_cards"]],
        [
            "Voir les expéditions prêtes",
            "Traiter les blocages workflow",
            "Ouvrir le suivi expédition",
            "Traiter les litiges",
            "Contrôler le stock",
            "Investiguer la queue email",
        ],
    )
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests.test_scan_dashboard_exposes_actions_anchors_and_grouped_sections wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests.test_scan_dashboard_priority_cards_include_explicit_cta_labels -v 2
```

Expected:
- FAIL because the current view context does not expose page actions, anchors, grouped flow/system sections, or CTA-labelled priority cards

**Step 3: Write minimal implementation**

Do not touch the template yet. Only add the new presenter-level context shape in `wms/views_scan_dashboard.py`:

```python
page_actions = [
    {"label": _("Nouvelle expédition"), "url": reverse("scan:scan_shipment_create"), "tone": "primary"},
    {"label": _("Suivi expéditions"), "url": reverse("scan:scan_shipments_tracking"), "tone": "tertiary"},
    {"label": _("Vue stock"), "url": reverse("scan:scan_stock"), "tone": "tertiary"},
]

dashboard_anchors = [
    {"id": "scan-dashboard-priorities", "label": _("Priorités")},
    {"id": "scan-dashboard-pilotage", "label": _("Pilotage")},
    {"id": "scan-dashboard-flow", "label": _("Flux")},
    {"id": "scan-dashboard-health", "label": _("Santé")},
]
```

Also add local helper(s) that decorate existing cards with:
- `cta_label`
- `section_id`
- optional `section_tone`

Build:
- `priority_cards`
- `flow_sections`
- `system_health_sections`

from the existing `shipment_cards`, `workflow_blockage_cards`, `tracking_cards`, `stock_cards`, `technical_cards`, `sla_cards`, `carton_cards`, and `flow_cards`.

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS with the new grouped dashboard context keys

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_scan_dashboard.py wms/views_scan_dashboard.py
git commit -m "feat: group scan dashboard context for cockpit layout"
```

### Task 2: Lock Down The Dashboard Shell Through Failing UI Tests

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_scan_dashboard.py`
- Reference: `templates/scan/dashboard.html`

**Step 1: Write the failing tests**

Add template/UI tests for the new dashboard shell and section order:

```python
def test_scan_dashboard_renders_cockpit_header_toolbar_and_sections(self):
    response = self.client.get(reverse("scan:scan_dashboard"))
    self.assertContains(response, 'id="scan-dashboard-page-header"')
    self.assertContains(response, 'id="scan-dashboard-toolbar"')
    self.assertContains(response, 'id="scan-dashboard-toolbar-advanced"')
    self.assertContains(response, 'id="scan-dashboard-section-nav"')
    self.assertContains(response, 'id="scan-dashboard-priorities"')
    self.assertContains(response, 'id="scan-dashboard-pilotage"')
    self.assertContains(response, 'id="scan-dashboard-flow"')
    self.assertContains(response, 'id="scan-dashboard-health"')


def test_scan_dashboard_orders_priority_pilotage_flow_and_health_sections(self):
    response = self.client.get(reverse("scan:scan_dashboard"))
    content = response.content.decode()
    self.assertLess(content.index('id="scan-dashboard-priorities"'), content.index('id="scan-dashboard-pilotage"'))
    self.assertLess(content.index('id="scan-dashboard-pilotage"'), content.index('id="scan-dashboard-flow"'))
    self.assertLess(content.index('id="scan-dashboard-flow"'), content.index('id="scan-dashboard-health"'))
```

Also extend bootstrap UI assertions so the dashboard still exposes the tested scan form-row classes while adding the new cockpit shell hooks.

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_dashboard_renders_cockpit_header_toolbar_and_sections wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests.test_scan_dashboard_orders_priority_pilotage_flow_and_health_sections -v 2
```

Expected:
- FAIL because the current template does not render the cockpit shell IDs or the new top-level section ordering

**Step 3: Write minimal implementation**

Do not style yet. Only reshape the template into the new semantic shell:
- add a header block with title, context sentence, and page actions
- add one main toolbar form with visible primary controls
- add an advanced chart-period wrapper for `chart_start` / `chart_end`
- add the anchor nav
- add top-level sections for `Priorités`, `Pilotage`, `Flux`, and `Santé système`

Use new structural IDs and class hooks consistently:

```html
<section id="scan-dashboard-page-header" class="scan-card card border-0 ui-comp-card">
...
</section>

<form id="scan-dashboard-toolbar" class="scan-filters row g-3 scan-dashboard-filter-row">
...
</form>

<nav id="scan-dashboard-section-nav" ...>
...
</nav>

<section id="scan-dashboard-priorities" ...>
...
</section>
```

Keep the existing scan dashboard filter-row class names alive where tests already depend on them.

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS with the new dashboard shell rendered in the correct order

**Step 5: Commit**

```bash
git add wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_dashboard.py templates/scan/dashboard.html
git commit -m "feat: add scan dashboard cockpit shell"
```

### Task 3: Implement The Priority Strip And Grouped `Pilotage` Block

**Files:**
- Modify: `templates/scan/dashboard.html`
- Modify: `wms/views_scan_dashboard.py`
- Test: `wms/tests/views/tests_views_scan_dashboard.py`

**Step 1: Write the failing tests**

Add view/template assertions for the actual content of the new middle page hierarchy:

```python
def test_scan_dashboard_renders_six_priority_cards_with_explicit_actions(self):
    response = self.client.get(reverse("scan:scan_dashboard"))
    self.assertContains(response, "Voir les expéditions prêtes")
    self.assertContains(response, "Traiter les blocages workflow")
    self.assertContains(response, "Contrôler le stock")
    self.assertContains(response, "Investiguer la queue email")


def test_scan_dashboard_groups_kpi_and_chart_inside_pilotage_block(self):
    response = self.client.get(reverse("scan:scan_dashboard"))
    content = response.content.decode()
    pilotage_start = content.index('id="scan-dashboard-pilotage"')
    self.assertIn('id="scan-dashboard-kpi-panel"', content[pilotage_start:])
    self.assertIn('id="scan-dashboard-chart-panel"', content[pilotage_start:])
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests.test_scan_dashboard_renders_six_priority_cards_with_explicit_actions wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests.test_scan_dashboard_groups_kpi_and_chart_inside_pilotage_block -v 2
```

Expected:
- FAIL because the template does not yet render the priority strip and `Pilotage` sub-panels from the new grouped context

**Step 3: Write minimal implementation**

In `templates/scan/dashboard.html`:
- render `priority_cards` as the first high-signal card grid
- add explicit CTA copy inside each priority card
- render one `Pilotage` section with:
  - `scan-dashboard-kpi-panel`
  - `scan-dashboard-chart-panel`
- keep the KPI and shipment-chart metrics unchanged semantically

Use local composition, not a new shared primitive:

```html
<section id="scan-dashboard-pilotage" class="scan-card card border-0 ui-comp-card">
  <div class="scan-dashboard-pilotage-grid">
    <div id="scan-dashboard-kpi-panel" class="ui-comp-panel">...</div>
    <div id="scan-dashboard-chart-panel" class="ui-comp-panel">...</div>
  </div>
</section>
```

In `wms/views_scan_dashboard.py`, remove or stop passing any now-unused dashboard groupings once the template fully consumes the new grouped structures.

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS with the new priority strip and grouped `Pilotage` block

**Step 5: Commit**

```bash
git add templates/scan/dashboard.html wms/views_scan_dashboard.py wms/tests/views/tests_views_scan_dashboard.py
git commit -m "feat: render scan dashboard priorities and pilotage block"
```

### Task 4: Implement `Flux` / `Santé système` Composition And Responsive Dashboard CSS

**Files:**
- Modify: `templates/scan/dashboard.html`
- Modify: `wms/static/scan/scan-bootstrap.css`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Reference: `docs/plans/2026-03-25-ui-lab-page-header-demo-design.md`

**Step 1: Write the failing tests**

Extend bootstrap UI coverage so the final dashboard class hooks are explicit:

```python
def test_scan_dashboard_exposes_cockpit_layout_class_hooks(self):
    response = self.client.get(reverse("scan:scan_dashboard"))
    self.assertContains(response, "scan-dashboard-page-header")
    self.assertContains(response, "scan-dashboard-toolbar")
    self.assertContains(response, "scan-dashboard-priority-grid")
    self.assertContains(response, "scan-dashboard-pilotage-grid")
    self.assertContains(response, "scan-dashboard-flow-grid")
    self.assertContains(response, "scan-dashboard-health-grid")
    self.assertContains(response, "scan-dashboard-section-nav")
```

Add a second assertion set that checks the stock low-stock table now lives inside the stock section wrapper.

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_dashboard_exposes_cockpit_layout_class_hooks -v 2
```

Expected:
- FAIL because the final layout class names and stock-section wrapper are not all present yet

**Step 3: Write minimal implementation**

Finish the lower-page section layout in `templates/scan/dashboard.html`:
- render `flow_sections` in the order `Stock`, `Colis`, `Réceptions / Commandes`
- keep `low_stock_rows` inside the stock section
- render `system_health_sections` after flow sections

Then add dashboard-local layout rules in `wms/static/scan/scan-bootstrap.css`:

```css
.scan-bootstrap-enabled .scan-dashboard-page-header { ... }
.scan-bootstrap-enabled .scan-dashboard-toolbar { ... }
.scan-bootstrap-enabled .scan-dashboard-section-nav { ... }
.scan-bootstrap-enabled .scan-dashboard-priority-grid { ... }
.scan-bootstrap-enabled .scan-dashboard-pilotage-grid { ... }
.scan-bootstrap-enabled .scan-dashboard-flow-grid { ... }
.scan-bootstrap-enabled .scan-dashboard-health-grid { ... }

@media (min-width: 992px) {
  .scan-bootstrap-enabled .scan-dashboard-pilotage-grid {
    grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
  }
}
```

Mobile rules must preserve the validated page order:
- header
- toolbar
- anchors
- priorities
- pilotage
- stock
- colis
- réceptions / commandes
- santé système

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS with the final dashboard layout hooks rendered

**Step 5: Commit**

```bash
git add templates/scan/dashboard.html wms/static/scan/scan-bootstrap.css wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add responsive cockpit layout for scan dashboard"
```

### Task 5: Run Targeted Regression And Recheck Propagation

**Files:**
- Reference: `docs/repo-reference/03-impact-map.md`
- Reference: `docs/repo-reference/04-shared-contracts.md`
- Test: `wms/tests/views/tests_views_scan_dashboard.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Run the targeted regression suite**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected:
- PASS for the dashboard presenter and bootstrap UI regressions

**Step 2: Recheck propagation**

Review:
- `docs/repo-reference/03-impact-map.md` section `Change On A Scan Page`
- `docs/repo-reference/04-shared-contracts.md` section `Shared UI Contract`

Confirm that the ticket only composes existing stable primitives locally.

If implementation drift has altered shared primitive semantics, update the relevant UI Lab or governance docs in the same task. If not, leave repo-reference and UI Lab docs unchanged.

**Step 3: Run whitespace / patch sanity verification**

Run:

```bash
git diff --check
```

Expected:
- no whitespace or patch-format errors

**Step 4: Review final diff**

Inspect the final diff to confirm:
- urgent signals are now first
- KPI and chart live together
- stock owns the low-stock table
- system health is last
- no Next/React or translation files were touched

**Step 5: Commit**

```bash
git add templates/scan/dashboard.html wms/views_scan_dashboard.py wms/static/scan/scan-bootstrap.css wms/tests/views/tests_views_scan_dashboard.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: reorganize scan dashboard as cockpit mix"
```
