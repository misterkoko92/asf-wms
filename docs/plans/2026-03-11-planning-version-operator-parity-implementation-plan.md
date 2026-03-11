# Planning Version Operator Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn `/planning/versions/<id>/` into the primary operator cockpit for weekly planning, with editable planning rows, actionnable unassigned shipments, and communication families aligned with legacy `asf-planning`.

**Architecture:** Keep the legacy Django cockpit page and extend it incrementally. Rework the presenter in `wms/planning/version_dashboard.py`, add dedicated POST flows in `wms/views_planning.py`, and port communication formatting from `asf-planning` into versioned WMS draft generation. Published versions remain immutable; every post-publication edit goes through a cloned draft version.

**Tech Stack:** Django legacy views/forms/templates, WMS planning models/snapshots, legacy `asf-planning` communication handlers as formatting oracle, Django tests.

---

### Task 1: Baseline the cockpit surface and add a focused branch-local safety net

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/tests/views/tests_views_planning.py`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/tests/planning/tests_version_dashboard.py`

**Step 1: Write failing expectations for the new header contract**

Add tests asserting that the dashboard header exposes:
- week label text
- KPI values needed by the summary table
- status badge label

**Step 2: Run targeted tests to confirm failure**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2
```

Expected:
- failures on missing header fields / old text contract

**Step 3: Commit the failing red phase checkpoint if helpful**

```bash
git add wms/tests/planning/tests_version_dashboard.py wms/tests/views/tests_views_planning.py
git commit -m "test(planning): define operator parity header expectations"
```

Only commit if the repo workflow tolerates red-phase commits on this branch.

### Task 2: Rebuild the header presenter and template

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/planning/version_dashboard.py`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/planning/stats.py`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/templates/planning/_version_header.html`

**Step 1: Implement the new header payload**

Expose:
- `week_label`
- `week_range_label`
- `status_badge`
- `summary_metrics`

Reuse run/version data and stats data rather than recomputing in template code.

**Step 2: Update the template**

Render:
- `Planning Semaine XX (du DD/MM/YY au DD/MM/YY)`
- metadata row (`Cree par / Creation / Publication / Periode`)
- summary table with six KPI columns

**Step 3: Run focused tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2
```

Expected:
- header tests green

**Step 4: Commit**

```bash
git add wms/planning/version_dashboard.py wms/planning/stats.py templates/planning/_version_header.html wms/tests/planning/tests_version_dashboard.py wms/tests/views/tests_views_planning.py
git commit -m "feat(planning): upgrade version header summary"
```

### Task 3: Replace grouped planning cards with detailed planning rows

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/planning/version_dashboard.py`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/templates/planning/_version_planning_block.html`
- Test: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/tests/planning/tests_version_dashboard.py`

**Step 1: Write failing presenter tests for the detailed planning row shape**

Cover these columns:
- date_vol
- heure_vol
- numero_vol
- destination
- routing
- be_numero
- be_nb_colis
- be_nb_equiv
- benevole
- be_type
- be_expediteur
- be_destinataire

**Step 2: Run tests to confirm failure**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard -v 2
```

**Step 3: Implement row-building helpers**

Build one presenter row per `PlanningAssignment`, sourcing missing values from snapshot payloads where needed.

**Step 4: Replace the template table**

Render a single operator table instead of per-flight cards.

**Step 5: Re-run tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2
```

**Step 6: Commit**

```bash
git add wms/planning/version_dashboard.py templates/planning/_version_planning_block.html wms/tests/planning/tests_version_dashboard.py
git commit -m "feat(planning): render detailed planning rows"
```

### Task 4: Add selector classification service for volunteers and flights

**Files:**
- Create: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/planning/operator_options.py`
- Test: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/tests/planning/tests_operator_options.py`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/planning/version_dashboard.py`

**Step 1: Write failing unit tests for volunteer option coloring**

Cover:
- green available/no conflict
- orange available but time-conflicted within 2h30
- red unavailable
- neutral unknown availability

**Step 2: Write failing unit tests for date/flight option coloring**

Cover:
- date list only when a flight exists for the shipment destination
- green / orange / red semantics for capacity

**Step 3: Run the new tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.planning.tests_operator_options -v 2
```

**Step 4: Implement the classification service**

Return normalized option payloads:
- `label`
- `value`
- `color`
- `reason`
- availability/capacity metadata

**Step 5: Hook the presenter to expose editable options per row**

**Step 6: Re-run tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.planning.tests_operator_options wms.tests.planning.tests_version_dashboard -v 2
```

**Step 7: Commit**

```bash
git add wms/planning/operator_options.py wms/planning/version_dashboard.py wms/tests/planning/tests_operator_options.py wms/tests/planning/tests_version_dashboard.py
git commit -m "feat(planning): classify operator options for edits"
```

### Task 5: Replace the assignment formset with row-level edit and delete flows

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/forms_planning.py`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/views_planning.py`
- Create: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/planning/operator_mutations.py`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/templates/planning/_version_planning_block.html`
- Test: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/tests/views/tests_views_planning.py`

**Step 1: Write failing view tests for line deletion**

Assert:
- draft version can delete an assignment
- published version rejects direct deletion

**Step 2: Write failing view tests for inline line update**

Assert:
- row update can change volunteer/date/flight
- updates mark assignment source as manual

**Step 3: Run the failing tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_planning -v 2
```

**Step 4: Implement dedicated forms and mutation service**

Add row-level POST actions:
- `planning_row_action=delete`
- `planning_row_action=update`

**Step 5: Update template actions**

Render:
- `Supprimer`
- `Modifier`
- inline expansion UI backed by Django forms

**Step 6: Re-run tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_planning wms.tests.planning.tests_operator_options -v 2
```

**Step 7: Commit**

```bash
git add wms/forms_planning.py wms/views_planning.py wms/planning/operator_mutations.py templates/planning/_version_planning_block.html wms/tests/views/tests_views_planning.py
git commit -m "feat(planning): add row edit and delete flows"
```

### Task 6: Make published versions create a working draft before edits

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/views_planning.py`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/templates/planning/_version_header.html`
- Test: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/tests/views/tests_views_planning.py`

**Step 1: Write failing test for published-version edit CTA**

Assert:
- published version does not expose inline edit actions
- it exposes `Creer une nouvelle version de travail`

**Step 2: Write failing test for clone-and-redirect behavior**

Assert:
- POST on the CTA clones a new draft version and redirects to it

**Step 3: Implement**

Use existing `clone_version(...)` flow and keep published versions immutable.

**Step 4: Re-run tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_planning -v 2
```

**Step 5: Commit**

```bash
git add wms/views_planning.py templates/planning/_version_header.html wms/tests/views/tests_views_planning.py
git commit -m "feat(planning): route published edits through cloned drafts"
```

### Task 7: Turn `Non affectes` into an actionnable add-to-planning table

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/planning/version_dashboard.py`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/forms_planning.py`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/views_planning.py`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/templates/planning/_version_unassigned_block.html`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/planning/operator_mutations.py`
- Test: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/tests/views/tests_views_planning.py`

**Step 1: Write failing tests for the new unassigned row schema**

Cover required columns and action visibility.

**Step 2: Write failing tests for add-from-unassigned POST**

Assert:
- manual assignment is created on draft version
- dashboard refresh shows it as assigned

**Step 3: Implement presenter + form + mutation**

Use:
- volunteer options from `operator_options`
- direct flight selector filtered by destination

**Step 4: Update template**

Render the requested columns and inline expansion UI.

**Step 5: Re-run tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_planning wms.tests.planning.tests_version_dashboard -v 2
```

**Step 6: Commit**

```bash
git add wms/planning/version_dashboard.py wms/forms_planning.py wms/views_planning.py templates/planning/_version_unassigned_block.html wms/planning/operator_mutations.py wms/tests/views/tests_views_planning.py
git commit -m "feat(planning): add actionnable unassigned shipments"
```

### Task 8: Introduce communication families in WMS

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/models_domain/planning.py`
- Create: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/migrations/<next>_communication_draft_family.py`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/planning/communication_plan.py`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/planning/communications.py`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/planning/version_dashboard.py`
- Test: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/tests/planning/tests_communication_plan.py`
- Test: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/tests/planning/tests_outputs.py`

**Step 1: Write failing tests for family-aware communication plan items**

Families:
- whatsapp_benevoles
- email_asf
- email_airfrance
- email_correspondants
- email_expediteurs
- email_destinataires

**Step 2: Add the persistence field**

Add a family discriminator on `CommunicationDraft`.

**Step 3: Implement family-aware plan generation**

Keep version-centric draft storage, but separate plan items per family.

**Step 4: Re-run tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.planning.tests_communication_plan wms.tests.planning.tests_outputs -v 2
```

**Step 5: Commit**

```bash
git add wms/models_domain/planning.py wms/migrations wms/planning/communication_plan.py wms/planning/communications.py wms/planning/version_dashboard.py wms/tests/planning/tests_communication_plan.py wms/tests/planning/tests_outputs.py
git commit -m "feat(planning): add communication families"
```

### Task 9: Port legacy formatting for the five existing communication families

**Files:**
- Create: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/planning/legacy_comm_bridge.py`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/planning/communications.py`
- Test: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/tests/planning/tests_outputs.py`
- Reference only:
  - `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_communication/whatsapp_handler.py`
  - `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_communication/email_asf_handler.py`
  - `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_communication/email_airfrance_handler.py`
  - `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_communication/email_destinations_handler.py`
  - `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_communication/email_expediteurs_handler.py`

**Step 1: Write failing tests for formatting parity snapshots**

Cover one golden example per legacy family.

**Step 2: Implement the bridge layer**

Do not import Streamlit UI code into WMS. Port the formatting logic and grouping rules only.

**Step 3: Re-run tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.planning.tests_outputs -v 2
```

**Step 4: Commit**

```bash
git add wms/planning/legacy_comm_bridge.py wms/planning/communications.py wms/tests/planning/tests_outputs.py
git commit -m "feat(planning): port legacy communication formatting"
```

### Task 10: Add the new `Destinataires` family as an `Expediteurs` mirror

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/planning/communications.py`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/planning/communication_plan.py`
- Test: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/tests/planning/tests_outputs.py`

**Step 1: Write failing tests for destinataire grouping and formatting**

Assert:
- same formatting shape as expediteurs
- recipient source comes from destinataire contacts instead of shipper contacts

**Step 2: Implement the new family**

Mirror expediteur behavior as agreed during design.

**Step 3: Re-run tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.planning.tests_outputs -v 2
```

**Step 4: Commit**

```bash
git add wms/planning/communications.py wms/planning/communication_plan.py wms/tests/planning/tests_outputs.py
git commit -m "feat(planning): add destinataire communications"
```

### Task 11: Rework the communications card UI around families

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/templates/planning/_version_communications_block.html`
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/planning/version_dashboard.py`
- Test: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/tests/planning/tests_version_dashboard.py`
- Test: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/wms/tests/views/tests_views_planning.py`

**Step 1: Write failing tests for family sections and counts**

Assert that the dashboard exposes the six families and draft counts per family.

**Step 2: Update template**

Render:
- family summary table
- family detail blocks
- existing edit controls on drafts

**Step 3: Re-run tests**

Run:
```bash
./.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2
```

**Step 4: Commit**

```bash
git add templates/planning/_version_communications_block.html wms/planning/version_dashboard.py wms/tests/planning/tests_version_dashboard.py wms/tests/views/tests_views_planning.py
git commit -m "feat(planning): redesign communication cockpit families"
```

### Task 12: Run the planning smoke and regression suite

**Files:**
- No code change required unless regressions are found

**Step 1: Run the focused operator parity suite**

Run:
```bash
./.venv/bin/python manage.py test \
  wms.tests.planning.tests_operator_options \
  wms.tests.planning.tests_version_dashboard \
  wms.tests.planning.tests_communication_plan \
  wms.tests.planning.tests_outputs \
  wms.tests.views.tests_views_planning -v 2
```

Expected:
- all green

**Step 2: Run the broader planning safety net**

Run:
```bash
./.venv/bin/python manage.py test \
  wms.tests.planning \
  wms.tests.management.tests_management_seed_planning_demo_data \
  wms.tests.management.tests_management_planning_recipe_data \
  wms.tests.management.tests_management_makemigrations_check -v 1
```

Expected:
- planning suite green

**Step 3: Run Ruff on touched planning files**

Run:
```bash
./.venv/bin/ruff check wms/planning wms/tests/planning wms/views_planning.py templates/planning
```

**Step 4: Commit any final regression fix**

```bash
git add -A
git commit -m "test(planning): validate operator parity cockpit"
```

### Task 13: Document operator recipe deltas and prepare review

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/docs/plans/2026-03-10-planning-phase3-recipe-runbook.md`
- Create or modify: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-version-operator-parity/docs/plans/2026-03-11-planning-version-operator-parity-validation.md`

**Step 1: Update the recipe runbook**

Describe the new UI actions:
- row edit/delete
- add from unassigned
- communication families

**Step 2: Capture validation notes**

Document:
- which legacy communication families reached parity
- known deltas, if any

**Step 3: Commit docs**

```bash
git add docs/plans/2026-03-10-planning-phase3-recipe-runbook.md docs/plans/2026-03-11-planning-version-operator-parity-validation.md
git commit -m "docs(planning): document operator parity cockpit"
```
