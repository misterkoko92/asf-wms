# Planning Operator Cockpit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transformer `/planning/versions/<id>/` en cockpit operateur central pour le planning, afin que `asf-wms` devienne l'outil principal de travail et que `Planning.xlsx` reste un export transitoire.

**Architecture:** Garder le stack Django legacy et enrichir la vue de version planning autour d'un presenter dedie dans `wms/planning/` qui compose un en-tete operateur, un bloc planning par vol, un bloc non-affectes, un bloc communications, un bloc stats, un bloc exports et un bloc historique/diff. La vue HTTP reste legere; les calculs d'agregation et de presentation vont dans des services testables. L'export Excel reste rattache a `PlanningVersion`, mais devient plus exploitable pour la transition.

**Tech Stack:** Django views/templates/forms, services Python dans `wms/planning/`, `openpyxl` pour l'export Excel, tests `manage.py test`, lint `ruff`.

---

### Task 1: Poser le presenter du cockpit de version

**Files:**
- Create: `wms/planning/version_dashboard.py`
- Modify: `wms/views_planning.py`
- Test: `wms/tests/planning/tests_version_dashboard.py`
- Test: `wms/tests/views/tests_views_planning.py`

**Step 1: Write the failing presenter tests**

```python
def test_build_version_dashboard_groups_assignments_by_flight():
    version = make_planning_version_with_two_flights()

    dashboard = build_version_dashboard(version)

    assert len(dashboard["flight_groups"]) == 2
    assert dashboard["header"]["version_number"] == version.number
```

```python
def test_build_version_dashboard_exposes_parent_diff_summary():
    version = make_cloned_planning_version()

    dashboard = build_version_dashboard(version)

    assert dashboard["history"]["has_parent"] is True
    assert "assignment_changes" in dashboard["history"]
```

**Step 2: Run tests to verify they fail**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2
```

Expected: FAIL because `build_version_dashboard(...)` and the cockpit context do not exist.

**Step 3: Write the minimal presenter implementation**

- Create `wms/planning/version_dashboard.py` with a `build_version_dashboard(version)` entry point.
- Return a structure with at least:
  - `header`
  - `flight_groups`
  - `unassigned_shipments`
  - `communications`
  - `stats`
  - `exports`
  - `history`
- Update `planning_version_detail(...)` in `wms/views_planning.py` to pass this dashboard into the template context.

**Step 4: Run tests to verify they pass**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2
```

Expected: PASS with dashboard data exposed to the view.

**Step 5: Commit**

```bash
git add wms/planning/version_dashboard.py wms/views_planning.py wms/tests/planning/tests_version_dashboard.py wms/tests/views/tests_views_planning.py
git commit -m "feat(planning): add version cockpit presenter"
```

### Task 2: Refondre le bloc Planning autour d'une lecture par vol

**Files:**
- Modify: `templates/planning/version_detail.html`
- Create: `templates/planning/_version_header.html`
- Create: `templates/planning/_version_planning_block.html`
- Modify: `wms/forms_planning.py`
- Test: `wms/tests/views/tests_views_planning.py`

**Step 1: Write the failing view test**

```python
def test_version_detail_renders_assignments_grouped_by_flight(self):
    version = make_published_version_with_assignments()

    response = self.client.get(reverse("planning:version_detail", args=[version.pk]))

    self.assertContains(response, "AF652")
    self.assertContains(response, "Charge utilisee")
    self.assertContains(response, "Benevole affecte")
```

**Step 2: Run test to verify it fails**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_planning.PlanningVersionDetailTests -v 2
```

Expected: FAIL because the current template is still a flat assignment table.

**Step 3: Write minimal implementation**

- Split the template into reusable partials.
- Replace the flat assignment-centric table with flight groups rendered from the dashboard presenter.
- Keep manual editing within this block for draft versions only.
- Extend `PlanningAssignmentForm` labels or widgets only if needed to support the grouped presentation.

**Step 4: Run tests to verify they pass**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_planning -v 2
```

Expected: PASS with the planning block rendered by flight.

**Step 5: Commit**

```bash
git add templates/planning/version_detail.html templates/planning/_version_header.html templates/planning/_version_planning_block.html wms/forms_planning.py wms/tests/views/tests_views_planning.py
git commit -m "feat(planning): render planning cockpit by flight"
```

### Task 3: Ajouter le bloc Non affectes et les motifs operateurs

**Files:**
- Modify: `wms/planning/version_dashboard.py`
- Modify: `templates/planning/version_detail.html`
- Create: `templates/planning/_version_unassigned_block.html`
- Test: `wms/tests/planning/tests_version_dashboard.py`
- Test: `wms/tests/views/tests_views_planning.py`

**Step 1: Write the failing tests**

```python
def test_build_version_dashboard_lists_unassigned_shipments_with_reason():
    version = make_version_with_unassigned_shipments()

    dashboard = build_version_dashboard(version)

    assert dashboard["unassigned_shipments"][0]["reason"]
```

```python
def test_version_detail_renders_unassigned_block(self):
    version = make_version_with_unassigned_shipments()

    response = self.client.get(reverse("planning:version_detail", args=[version.pk]))

    self.assertContains(response, "Non affectes")
    self.assertContains(response, "capacite insuffisante")
```

**Step 2: Run tests to verify they fail**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2
```

Expected: FAIL because the dashboard does not yet compute or render unassigned reasons.

**Step 3: Write minimal implementation**

- Build the unassigned shipment list from:
  - `run.shipment_snapshots`
  - `version.assignments`
  - `run.solver_result["unassigned_reasons"]` when available
- Map raw reason codes to operator-friendly labels.
- Render a dedicated `Non affectes` block in the version cockpit.

**Step 4: Run tests to verify they pass**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2
```

Expected: PASS with unassigned items and readable reasons.

**Step 5: Commit**

```bash
git add wms/planning/version_dashboard.py templates/planning/version_detail.html templates/planning/_version_unassigned_block.html wms/tests/planning/tests_version_dashboard.py wms/tests/views/tests_views_planning.py
git commit -m "feat(planning): surface unassigned shipments in cockpit"
```

### Task 4: Recomposer communications, stats et historique dans le cockpit

**Files:**
- Modify: `wms/planning/version_dashboard.py`
- Modify: `wms/planning/stats.py`
- Modify: `templates/planning/version_detail.html`
- Create: `templates/planning/_version_communications_block.html`
- Create: `templates/planning/_version_stats_block.html`
- Create: `templates/planning/_version_history_block.html`
- Test: `wms/tests/planning/tests_version_dashboard.py`
- Test: `wms/tests/views/tests_views_planning.py`

**Step 1: Write the failing tests**

```python
def test_build_version_dashboard_groups_drafts_by_channel_and_recipient():
    version = make_version_with_drafts()

    dashboard = build_version_dashboard(version)

    assert dashboard["communications"]["groups"]
```

```python
def test_build_version_dashboard_exposes_history_summary_for_parent_version():
    version = make_cloned_version_with_changes()

    dashboard = build_version_dashboard(version)

    assert dashboard["history"]["assignment_changes"]["moved"]
```

```python
def test_build_version_stats_exposes_unassigned_and_destination_breakdown():
    version = make_version_with_assignments()

    stats = build_version_stats(version)

    assert "unassigned_count" in stats
    assert "destination_breakdown" in stats
```

**Step 2: Run tests to verify they fail**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2
```

Expected: FAIL because communications, stats and history are still minimal.

**Step 3: Write minimal implementation**

- Extend `build_version_stats(...)` with operator-facing metrics:
  - `unassigned_count`
  - destination breakdown
  - volunteer load breakdown
- Group drafts by channel and recipient in the dashboard.
- Build a lightweight version history summary using `based_on`, `change_reason` and `diff_versions(...)`.
- Render dedicated cockpit blocks for communications, stats and history.

**Step 4: Run tests to verify they pass**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2
```

Expected: PASS with grouped drafts, richer stats and inline history summary.

**Step 5: Commit**

```bash
git add wms/planning/version_dashboard.py wms/planning/stats.py templates/planning/version_detail.html templates/planning/_version_communications_block.html templates/planning/_version_stats_block.html templates/planning/_version_history_block.html wms/tests/planning/tests_version_dashboard.py wms/tests/views/tests_views_planning.py
git commit -m "feat(planning): add operator communications stats and history blocks"
```

### Task 5: Rendre l'export Planning.xlsx plus utile pour la transition

**Files:**
- Modify: `wms/planning/exports.py`
- Modify: `wms/planning/version_dashboard.py`
- Create: `templates/planning/_version_exports_block.html`
- Test: `wms/tests/planning/tests_outputs.py`
- Test: `wms/tests/views/tests_views_planning.py`

**Step 1: Write the failing export test**

```python
def test_export_version_workbook_writes_operator_friendly_columns(tmp_path, settings):
    version = make_version_with_assignments()

    artifact = export_version_workbook(version)

    workbook = load_workbook(artifact.file_path)
    sheet = workbook["Planning"]
    assert sheet["A2"].value == "2026-03-10"
    assert sheet["B2"].value == "AF652"
```

**Step 2: Run test to verify it fails**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_outputs -v 2
```

Expected: FAIL because the workbook is still assignment-flat and minimal.

**Step 3: Write minimal implementation**

- Extend `export_version_workbook(...)` to produce a more operator-friendly `Planning` sheet, for example with:
  - date
  - flight
  - destination
  - departure time
  - volunteer
  - shipment reference
  - cartons
  - status
  - source
  - notes
- Expose artifact metadata through the dashboard and exports block.

**Step 4: Run tests to verify they pass**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_outputs wms.tests.views.tests_views_planning -v 2
```

Expected: PASS with richer export structure and artifact rendering intact.

**Step 5: Commit**

```bash
git add wms/planning/exports.py wms/planning/version_dashboard.py templates/planning/_version_exports_block.html wms/tests/planning/tests_outputs.py wms/tests/views/tests_views_planning.py
git commit -m "feat(planning): improve operator workbook export"
```

### Task 6: Verification finale et documentation operateur

**Files:**
- Modify: `docs/plans/2026-03-08-planning-module-verification.md`
- Modify: `docs/plans/2026-03-10-planning-operator-cockpit-design.md`
- Test: `wms/tests/planning/tests_version_dashboard.py`
- Test: `wms/tests/planning/tests_outputs.py`
- Test: `wms/tests/views/tests_views_planning.py`

**Step 1: Update operator verification notes**

- Document:
  - cockpit reading checklist
  - manual adjustment checklist
  - non-assigned review checklist
  - communication regeneration checklist
  - export verification checklist
  - version diff checklist

**Step 2: Run final verification**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning wms.tests.views.tests_views_planning wms.tests.management.tests_management_makemigrations_check wms.tests.management.tests_management_seed_planning_demo_data -v 1
```

Expected: PASS

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/ruff check wms/planning wms/tests/planning wms/views_planning.py
```

Expected: PASS

**Step 3: Commit**

```bash
git add docs/plans/2026-03-08-planning-module-verification.md docs/plans/2026-03-10-planning-operator-cockpit-design.md
git commit -m "docs(planning): add operator cockpit verification notes"
```
