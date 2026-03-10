# Planning Communications Cockpit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transformer les communications planning en flux operateur version-centrique, avec un draft agrege par destinataire/canal, un statut de changement lisible et une priorisation claire des messages a rediffuser.

**Architecture:** Ajouter une couche de service `communication plan` dans `wms/planning/` pour comparer une version a son parent et produire des items agreges `new/changed/cancelled/unchanged`. Faire ensuite de `wms/planning/communications.py` le materializer de drafts persistants par destinataire/canal, puis enrichir `wms/planning/version_dashboard.py` et les templates du cockpit pour exposer les statuts, les resumes de diff et l'ordre d'affichage operateur. Garder `CommunicationDraft` et le workflow d'edition existants, sans migration de schema dans ce lot.

**Tech Stack:** Django legacy views/templates/forms, services Python dans `wms/planning/`, tests `manage.py test`, lint `ruff`.

---

### Task 1: Poser le service de plan de communication agrege

**Files:**
- Create: `wms/planning/communication_plan.py`
- Test: `wms/tests/planning/tests_communication_plan.py`

**Step 1: Write the failing tests**

```python
def test_build_version_communication_plan_marks_first_publication_as_new():
    version = make_published_version_with_assignments()

    plan = build_version_communication_plan(version)

    assert len(plan.items) == 1
    assert plan.items[0].change_status == "new"
```

```python
def test_build_version_communication_plan_marks_removed_recipient_as_cancelled():
    version_1, version_2 = make_published_version_pair_with_removed_assignment()

    plan = build_version_communication_plan(version_2)

    cancelled = [item for item in plan.items if item.change_status == "cancelled"]
    assert cancelled
```

```python
def test_build_version_communication_plan_marks_unchanged_recipient():
    version_1, version_2 = make_published_version_pair_with_same_assignment()

    plan = build_version_communication_plan(version_2)

    assert plan.items[0].change_status == "unchanged"
```

**Step 2: Run tests to verify they fail**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_communication_plan -v 2
```

Expected: FAIL because `build_version_communication_plan(...)` and the aggregated comparison layer do not exist.

**Step 3: Write the minimal implementation**

- Create `wms/planning/communication_plan.py`.
- Introduce service-layer objects or dicts for:
  - normalized assignment payload
  - aggregated plan item per `(recipient_label, channel)`
  - ordered plan result
- Compare `version` against `version.based_on` using canonical assignment payloads, not rendered text.
- Support all four statuses:
  - `new`
  - `changed`
  - `cancelled`
  - `unchanged`
- Return operator-facing summaries that can later feed both draft generation and dashboard rendering.

**Step 4: Run tests to verify they pass**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_communication_plan -v 2
```

Expected: PASS with deterministic aggregated plan items.

**Step 5: Commit**

```bash
git add wms/planning/communication_plan.py wms/tests/planning/tests_communication_plan.py
git commit -m "feat(planning): add aggregated communication plan"
```

### Task 2: Refactor draft generation to materialize one draft per recipient/channel

**Files:**
- Modify: `wms/planning/communications.py`
- Modify: `wms/tests/planning/tests_outputs.py`
- Test: `wms/tests/planning/tests_communication_plan.py`

**Step 1: Write the failing tests**

```python
def test_generate_version_drafts_aggregates_multiple_assignments_for_same_recipient():
    version = make_published_version_with_two_assignments_same_volunteer()

    drafts = generate_version_drafts(version)

    assert len(drafts) == 1
    assert "AF123" in drafts[0].body
    assert "AF456" in drafts[0].body
```

```python
def test_generate_version_drafts_creates_cancellation_message_for_removed_recipient():
    version_1, version_2 = make_published_version_pair_with_removed_assignment()

    drafts = generate_version_drafts(version_2)

    assert drafts[0].recipient_label == "Alice"
    assert "annulation" in drafts[0].body.lower()
```

**Step 2: Run tests to verify they fail**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_outputs wms.tests.planning.tests_communication_plan -v 2
```

Expected: FAIL because generation still produces one draft per assignment and no cancellation draft.

**Step 3: Write the minimal implementation**

- Update `generate_version_drafts(version)` to:
  - call `build_version_communication_plan(version)`
  - delete only the current version's drafts
  - create one `CommunicationDraft` per plan item and template/channel combination
- Extend template context with aggregated values:
  - `change_status`
  - `change_summary`
  - `current_assignments`
  - `previous_assignments`
  - `assignment_count`
- Keep fallback text generation when no template is active.
- Preserve version isolation: regenerating `v2` must not affect drafts stored for `v1`.

**Step 4: Run tests to verify they pass**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_outputs wms.tests.planning.tests_communication_plan -v 2
```

Expected: PASS with aggregated drafts and cancellation support.

**Step 5: Commit**

```bash
git add wms/planning/communications.py wms/tests/planning/tests_outputs.py wms/tests/planning/tests_communication_plan.py
git commit -m "feat(planning): aggregate communication drafts by recipient"
```

### Task 3: Exposer le plan de communication dans le cockpit

**Files:**
- Modify: `wms/planning/version_dashboard.py`
- Modify: `templates/planning/_version_communications_block.html`
- Modify: `templates/planning/version_detail.html`
- Modify: `wms/forms_planning.py`
- Modify: `wms/tests/planning/tests_version_dashboard.py`
- Modify: `wms/tests/views/tests_views_planning.py`

**Step 1: Write the failing tests**

```python
def test_build_version_dashboard_prioritizes_changed_communication_groups():
    version = make_published_version_pair_with_changed_assignment()[1]

    dashboard = build_version_dashboard(version)

    assert dashboard["communications"]["groups"][0]["change_status"] == "changed"
```

```python
def test_version_detail_renders_change_badges_and_collapses_unchanged_groups(self):
    version = make_version_with_changed_and_unchanged_drafts()

    response = self.client.get(reverse("planning:version_detail", args=[version.pk]))

    self.assertContains(response, "Modifie")
    self.assertContains(response, "Annule")
    self.assertContains(response, "Inchange")
```

**Step 2: Run tests to verify they fail**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2
```

Expected: FAIL because the dashboard only exposes `changed_since_parent` and the template renders a flat grouped table.

**Step 3: Write the minimal implementation**

- Make `build_version_dashboard(version)` consume the communication plan instead of a recipient impact boolean.
- Expose for each group:
  - `change_status`
  - `change_status_label`
  - `change_summary`
  - `is_priority`
  - `is_collapsed`
- Order groups as:
  - `new`
  - `changed`
  - `cancelled`
  - `unchanged`
- Update the communications block template with visible badges, summary text and default-collapsed unchanged groups.
- Keep draft forms attached to the aggregated groups through the existing formset mechanism.
- Adjust `build_communication_draft_formset(...)` ordering only if needed so forms stay aligned with the new grouped sequence.

**Step 4: Run tests to verify they pass**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2
```

Expected: PASS with prioritized communication groups rendered in the cockpit.

**Step 5: Commit**

```bash
git add wms/planning/version_dashboard.py templates/planning/_version_communications_block.html templates/planning/version_detail.html wms/forms_planning.py wms/tests/planning/tests_version_dashboard.py wms/tests/views/tests_views_planning.py
git commit -m "feat(planning): prioritize cockpit communication diffs"
```

### Task 4: Durcir la regeneration et documenter le workflow operateur

**Files:**
- Modify: `wms/views_planning.py`
- Modify: `docs/plans/2026-03-08-planning-module-verification.md`
- Modify: `docs/plans/2026-03-10-planning-communications-cockpit-design.md`
- Test: `wms/tests/views/tests_views_planning.py`

**Step 1: Write the failing regression test**

```python
def test_generating_drafts_from_version_detail_regenerates_aggregated_series(self):
    version = make_published_version_with_two_assignments_same_volunteer()
    self.client.force_login(self.staff_user)

    response = self.client.post(
        reverse("planning:version_detail", args=[version.pk]),
        {"draft_action": "generate"},
    )

    self.assertRedirects(response, reverse("planning:version_detail", args=[version.pk]))
    self.assertEqual(version.communication_drafts.count(), 1)
```

**Step 2: Run tests to verify they fail**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_planning -v 2
```

Expected: FAIL because the view still assumes the old per-assignment draft semantics somewhere in the workflow or displayed counts.

**Step 3: Write the minimal implementation**

- Keep `planning_version_detail(...)` workflow intact, but update success-path assumptions to the aggregated draft model.
- Ensure regenerate/save flows still work with:
  - one draft per recipient/channel
  - cancellation-only groups with no current assignment
- Update verification docs with:
  - expected operator behavior on first publication
  - expected operator behavior after `v2`
  - what should be regenerated vs ignored

**Step 4: Run tests to verify they pass**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_planning -v 2
```

Expected: PASS with stable regenerate/edit workflow from the cockpit.

**Step 5: Commit**

```bash
git add wms/views_planning.py docs/plans/2026-03-08-planning-module-verification.md docs/plans/2026-03-10-planning-communications-cockpit-design.md wms/tests/views/tests_views_planning.py
git commit -m "docs(planning): document communication cockpit workflow"
```

### Task 5: Run the full verification suite and prepare integration

**Files:**
- Modify: `docs/plans/2026-03-10-planning-communications-cockpit-implementation-plan.md`

**Step 1: Run the focused planning verification**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_communication_plan wms.tests.planning.tests_outputs wms.tests.planning.tests_version_dashboard wms.tests.views.tests_views_planning -v 2
```

Expected: PASS with the new communication plan, generation and cockpit behavior covered.

**Step 2: Run the broader planning regression suite**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning wms.tests.views.tests_views_planning wms.tests.management.tests_management_makemigrations_check wms.tests.management.tests_management_seed_planning_demo_data -v 1
```

Expected: PASS without regressions on solver, cockpit, exports or seed flows.

**Step 3: Run lint**

Run:
```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/ruff check wms/planning wms/tests/planning wms/views_planning.py
```

Expected: `All checks passed!`

**Step 4: Update plan status notes if needed**

- If command expectations changed during implementation, update this plan document and the verification notes.
- Keep the plan accurate for later replay or audit.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-10-planning-communications-cockpit-implementation-plan.md
git commit -m "docs(planning): finalize communication cockpit verification plan"
```
