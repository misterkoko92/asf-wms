# UI Library Governance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Operationalize the approved UI library governance so upcoming legacy Django UI waves reuse a frozen core, expose the official contracts in the UI Lab, and classify new patterns consistently.

**Architecture:** Keep the existing Bootstrap-only hybrid approach. Shared leaf primitives continue to live in `wms_ui` and `templates/wms/components/*`, while wrapper/layout patterns stay as explicit HTML/CSS contracts documented in `scan/ui-lab/`. Governance is enforced through tests, the UI Lab catalog, and a lightweight checklist for future waves.

**Tech Stack:** Django templates, Django inclusion tags, Django TestCase, Bootstrap bridge CSS, docs in `docs/plans` and `docs/checklists`

---

### Task 1: Lock the current core stable contracts with failing tests

**Files:**
- Modify: `wms/tests/templatetags/tests_wms_ui.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `wms/templatetags/wms_ui.py`
- Verify: `templates/wms/components/button.html`
- Verify: `templates/wms/components/field.html`
- Verify: `templates/wms/components/alert.html`
- Verify: `templates/wms/components/status_badge.html`
- Verify: `templates/wms/components/switch.html`
- Verify: `templates/scan/ui_lab.html`

**Step 1: Write the failing test**

Add assertions that describe the governed stable core:
- `ui_button`, `ui_field`, `ui_alert`, `ui_status_badge`, and `ui_switch` keep their approved shared classes and escaping behavior.
- the `UI Lab` explicitly exposes these stable contracts instead of relying on incidental examples only.
- shared wrapper contracts for `ui-comp-card`, `ui-comp-panel`, and `ui-comp-actions` appear in the catalog as first-class reference material.

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.templatetags.tests_wms_ui wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL because the governance-oriented `UI Lab` assertions are not yet implemented.

**Step 3: Write minimal implementation**

No production implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.templatetags.tests_wms_ui wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL only on the new governance assertions.

**Step 5: Commit**

```bash
git add wms/tests/templatetags/tests_wms_ui.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "test: lock ui library governance contracts"
```

### Task 2: Surface the governance tiers in the UI Lab

**Files:**
- Modify: `templates/scan/ui_lab.html`
- Modify: `wms/static/scan/ui-lab.css`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `wms/static/scan/scan-bootstrap.css`

**Step 1: Write the failing test**

Use the red tests from Task 1 and add assertions that:
- the `UI Lab` contains a clearly labeled `Core stable` section,
- the page distinguishes `Core stable` from `En convergence`,
- every stable primitive has at least one canonical example in the catalog,
- the wrapper contracts are documented without inventing new generic template tags.

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL because the `UI Lab` does not yet expose the governance tiers explicitly.

**Step 3: Write minimal implementation**

- add a read-only governance section near the top of `scan/ui-lab/`,
- show which primitives are frozen now,
- show which patterns remain in convergence,
- keep the catalog concrete and avoid turning the page into a generic design-system shell,
- add only the CSS needed to present these governance blocks clearly.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS for the `UI Lab` governance assertions.

**Step 5: Commit**

```bash
git add templates/scan/ui_lab.html wms/static/scan/ui-lab.css wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "docs: expose ui governance tiers in the ui lab"
```

### Task 3: Create the component intake checklist used by future waves

**Files:**
- Create: `docs/checklists/legacy-ui-component-governance.md`
- Verify: `docs/plans/2026-03-22-ui-library-governance-design.md`

**Step 1: Write the failing test**

Use a simple file-existence and content check as the red gate:
- verify that `docs/checklists/legacy-ui-component-governance.md` does not yet exist,
- define the required checklist headings before writing the file.

Run: `test -f /Users/EdouardGonnu/asf-wms/docs/checklists/legacy-ui-component-governance.md`

Expected: FAIL because the governance checklist file does not exist yet.

**Step 2: Run test to verify it fails**

Run: `test -f /Users/EdouardGonnu/asf-wms/docs/checklists/legacy-ui-component-governance.md`

Expected: FAIL.

**Step 3: Write minimal implementation**

Create a concise checklist that future UI work must answer:
- change classification: `Core stable`, `En convergence`, or `Local au workflow`,
- reused stable primitives,
- reason for any new component or new option,
- `UI Lab` impact,
- test impact,
- promotion criteria if the pattern is intended to become shared.

**Step 4: Run test to verify it passes**

Run: `rg -n "Core stable|En convergence|Local au workflow|UI Lab|promotion" /Users/EdouardGonnu/asf-wms/docs/checklists/legacy-ui-component-governance.md`

Expected: PASS with matches for each required section.

**Step 5: Commit**

```bash
git add docs/checklists/legacy-ui-component-governance.md
git commit -m "docs: add legacy ui component governance checklist"
```

### Task 4: Classify the remaining major legacy surfaces before wave 4

**Files:**
- Create: `docs/plans/2026-03-22-legacy-ui-wave4-design.md`
- Verify: `templates/scan/admin_contacts.html`
- Verify: `templates/scan/imports.html`
- Verify: `templates/scan/shipment_create.html`
- Verify: `templates/scan/public_account_request.html`
- Verify: `templates/scan/pack.html`

**Step 1: Write the failing test**

Use a red documentation gate:
- confirm that `docs/plans/2026-03-22-legacy-ui-wave4-design.md` does not exist yet,
- define the required sections: target screens, governance classification, core stable reuse, convergence candidates, deferred items, and targeted tests.

Run: `test -f /Users/EdouardGonnu/asf-wms/docs/plans/2026-03-22-legacy-ui-wave4-design.md`

Expected: FAIL because the wave 4 design handoff does not exist yet.

**Step 2: Run test to verify it fails**

Run: `test -f /Users/EdouardGonnu/asf-wms/docs/plans/2026-03-22-legacy-ui-wave4-design.md`

Expected: FAIL.

**Step 3: Write minimal implementation**

Create the wave 4 design handoff that:
- names the next highest-value legacy surfaces,
- classifies each one using the governance tiers,
- states which stable primitives must be reused,
- identifies which patterns should stay in convergence,
- lists the view and template test suites that must lock the contracts.

**Step 4: Run test to verify it passes**

Run: `rg -n "Core stable|En convergence|Local au workflow|Tests|Differe" /Users/EdouardGonnu/asf-wms/docs/plans/2026-03-22-legacy-ui-wave4-design.md`

Expected: PASS with all required sections present.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-22-legacy-ui-wave4-design.md
git commit -m "docs: prepare legacy ui wave 4 governance handoff"
```

### Task 5: Final governance verification and handoff

**Files:**
- Verify: `docs/plans/2026-03-22-ui-library-governance-design.md`
- Verify: `docs/plans/2026-03-22-ui-library-governance-implementation-plan.md`
- Verify: `docs/checklists/legacy-ui-component-governance.md`
- Verify: `templates/scan/ui_lab.html`
- Verify: `wms/tests/templatetags/tests_wms_ui.py`
- Verify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

No new tests in this task. Reuse the checks and test suites from the previous tasks.

**Step 2: Run test to verify the final branch state**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.templatetags.tests_wms_ui wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS.

Run: `rg -n "Core stable|En convergence|Local au workflow" /Users/EdouardGonnu/asf-wms/docs/plans/2026-03-22-ui-library-governance-design.md /Users/EdouardGonnu/asf-wms/docs/checklists/legacy-ui-component-governance.md /Users/EdouardGonnu/asf-wms/docs/plans/2026-03-22-legacy-ui-wave4-design.md`

Expected: PASS with matches in all three files.

**Step 3: Write minimal implementation**

No production implementation in this task.

**Step 4: Run test to verify it still passes**

Re-run the verification commands from Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-22-ui-library-governance-design.md docs/plans/2026-03-22-ui-library-governance-implementation-plan.md docs/checklists/legacy-ui-component-governance.md docs/plans/2026-03-22-legacy-ui-wave4-design.md templates/scan/ui_lab.html wms/static/scan/ui-lab.css wms/tests/templatetags/tests_wms_ui.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "docs: roll out ui library governance"
```
