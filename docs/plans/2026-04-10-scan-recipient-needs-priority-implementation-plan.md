# Scan Recipient Needs Priority View Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a new scan `Stocks` recap page that synthesizes recipient product needs by destination/recipient/category, shows linked shippers, and prioritizes rows from shipment urgency with hoverable threshold explanations.

**Architecture:** Build a dedicated read-side query helper under `wms/application/scan/` that composes explicit recipient preferences, category-derived product rows, coverage metrics, linked shipper labels, and SLA-aligned urgency into deterministic page rows. Keep the delivery surface in legacy Django scan, wire the new route through the existing stock view module/facades/sidebar, and render local Bootstrap tooltips so the priority logic stays explainable without adding a new edit flow or an API mirror.

**Tech Stack:** Django views/templates, Django ORM, runtime settings, Bootstrap tooltips, Django test runner.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:verification-before-completion`, `@repo-reference-governance`.

### Task 1: Add failing tests for the read-side query contract

**Files:**
- Create: `wms/tests/core/tests_scan_recipient_needs_queries.py`
- Review: `wms/tests/core/tests_recipient_product_preference_coverage.py`

**Step 1: Write the failing tests**

Add tests that prove:
- the query only materializes explicit product rules and products covered by explicit category rules
- the query does not emit a full recipient x catalog `unspecified` cross-join
- destination, recipient, category, need-status, and priority filters all narrow the row set
- linked shipper labels are included and stable for recipients with one or more active links
- priority levels classify rows as `critical`, `high`, `normal`, `covered`, or `out_of_scope`
- each actionable row exposes a tooltip/help string describing the applied thresholds and source values

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.core.tests_scan_recipient_needs_queries \
  -v 2
```

Expected: failures because the query helper and row contract do not exist yet.

### Task 2: Implement the recipient-needs query helper

**Files:**
- Create: `wms/application/scan/recipient_needs_queries.py`
- Review: `wms/recipient_product_preferences.py`
- Review: `wms/runtime_settings.py`
- Review: `wms/policies/sla.py`

**Step 1: Write minimal implementation**

Implement a helper API that:
- parses the page filters
- expands explicit product preferences directly
- expands explicit category preferences into active products in the selected subtree
- reuses `list_recipient_product_coverages(...)` for delivered/pipeline/remaining metrics
- aggregates active linked shipper names from `ShipmentShipperRecipientLink`
- uses `get_runtime_config().tracking_alert_hours` for delay classification
- computes:
  - summary cards
  - row priority
  - period/deadline labels
  - hover/tooltip text

Keep the helper read-only and deterministic. Do not add an API endpoint or mutation path in this task.

**Step 2: Run the targeted tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.core.tests_scan_recipient_needs_queries \
  -v 2
```

Expected: the new query-contract tests pass.

**Step 3: Commit**

```bash
git add wms/application/scan/recipient_needs_queries.py wms/tests/core/tests_scan_recipient_needs_queries.py
git commit -m "feat: add scan recipient needs query helper"
```

### Task 3: Add failing tests for the scan route and view context

**Files:**
- Modify: `wms/tests/views/tests_views_scan_stock.py`

**Step 1: Write the failing tests**

Add tests that prove:
- a staff user can reach the new route
- the view sets the correct `active` key for the `Stocks` sidebar group
- the default ordering is priority-first
- destination and recipient filters are preserved in the rendered context
- row actions point at the existing recipient admin detail page

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_stock \
  -v 2
```

Expected: failures because the route and context do not exist yet.

### Task 4: Wire the scan route, view, and façade exports

**Files:**
- Modify: `wms/scan_urls.py`
- Modify: `wms/views_scan_stock.py`
- Modify: `wms/views_scan.py`
- Modify: `wms/views.py`

**Step 1: Write minimal implementation**

Add a new legacy scan route and view:
- route: `scan/recipient-needs/`
- view name: `scan_recipient_needs`

Implementation details:
- keep the page in `wms/views_scan_stock.py` because it belongs to the `Stocks` navigation cluster
- call the read-side helper from Task 2
- pass the page `active` value needed by the shared sidebar
- keep permissions staff-only and read-only

**Step 2: Run the targeted tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_stock \
  -v 2
```

Expected: the new route/context tests pass.

**Step 3: Commit**

```bash
git add wms/scan_urls.py wms/views_scan_stock.py wms/views_scan.py wms/views.py wms/tests/views/tests_views_scan_stock.py
git commit -m "feat: add scan recipient needs route"
```

### Task 5: Add failing UI contract tests for sidebar, filters, and tooltips

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing tests**

Add bootstrap/UI tests that prove:
- the `Stocks` sidebar shows the new `Vue Besoins` entry
- the page renders the destination filter alongside recipient/category controls
- the table renders the expected priority, shipper, and quantity columns
- priority badges or help controls expose tooltip markup for threshold explanations

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  -v 2
```

Expected: failures because the new page markup and sidebar entry do not exist yet.

### Task 6: Render the new scan page and tooltip help

**Files:**
- Create: `templates/scan/recipient_needs_view.html`
- Modify: `templates/scan/includes/scan_sidebar_navigation.html`

**Step 1: Write minimal implementation**

Render the page with:
- summary cards
- destination/recipient/category/status/priority filters
- a priority-first table
- linked shipper labels
- an action to open `scan_admin_recipient_organization_detail`
- Bootstrap tooltip markup for threshold explanations

Implementation detail:
- initialize `bootstrap.Tooltip` locally in the page `extra_scripts` block
- do not introduce a shared tooltip primitive; keep this local unless a second surface needs the same pattern

**Step 2: Run the UI tests to verify they pass**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_views_scan_stock \
  -v 2
```

Expected: the sidebar/page contract tests pass.

**Step 3: Commit**

```bash
git add templates/scan/recipient_needs_view.html templates/scan/includes/scan_sidebar_navigation.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: render scan recipient needs priority page"
```

### Task 7: Update repo-reference and flow documentation

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Review: `docs/mvp_spec.md`
- Review: `docs/repo-reference/03-impact-map.md`

**Step 1: Update the docs**

Document:
- the new scan read surface in the scan flow reference
- the new sidebar entry and `active` contract in the shared contracts reference
- whether `docs/mvp_spec.md` needs wording updates for this new official operator recap page

**Step 2: Run final verification**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.core.tests_scan_recipient_needs_queries \
  wms.tests.core.tests_recipient_product_preference_coverage \
  wms.tests.views.tests_views_scan_stock \
  wms.tests.views.tests_scan_bootstrap_ui \
  -v 2
```

Expected: all targeted tests pass and the existing coverage contract remains intact.

**Step 3: Commit**

```bash
git add docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/04-shared-contracts.md docs/mvp_spec.md
git commit -m "docs: add scan recipient needs cockpit references"
```
