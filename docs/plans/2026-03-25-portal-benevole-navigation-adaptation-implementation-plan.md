# Portal And Benevole Navigation Adaptation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Adapt `portal/` and `benevole/` to the validated legacy navigation language from `scan/`, while keeping both shells lighter than the `scan` desktop sidebar model.

**Architecture:** Stay on the legacy Django stack. Reuse the shell split validated on `scan/`: utility controls in the masthead, primary navigation separated from local actions, and mobile offcanvas for compact navigation. Do not introduce a second navigation library and do not port the `scan` sidebar to these surfaces.

**Tech Stack:** Django templates, Bootstrap 5 shell markup, `scan-bootstrap.css`, `portal-bootstrap.css`, Django view tests.

---

### Task 1: Add failing portal shell navigation tests

**Files:**
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Reference: `templates/portal/base.html`

**Step 1: Add assertions for the new portal contract**

Cover:
- masthead utility area
- primary navigation items
- separate `Nouvelle commande` CTA
- absence of logout in the primary navigation rail

**Step 2: Run the targeted failing test**

```bash
.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui -v 1
```

**Step 3: Commit the failing test**

```bash
git add wms/tests/views/tests_portal_bootstrap_ui.py
git commit -m "test: add portal navigation shell contract"
```

### Task 2: Implement the portal shell adaptation

**Files:**
- Modify: `templates/portal/base.html`
- Modify: `wms/static/portal/portal-bootstrap.css`
- Optional Modify: `wms/static/scan/scan-bootstrap.css`

**Step 1: Replace the button-strip shell**

Implement:
- logo + identity in masthead
- utility controls on the right
- primary navigation rail
- separate `Nouvelle commande` CTA

**Step 2: Keep the shell light**

Do not add:
- sidebar desktop
- scan operator-density layout
- workflow-local controls in the masthead

**Step 3: Add mobile offcanvas if needed**

Use Bootstrap-native offcanvas/collapse only.

**Step 4: Re-run portal shell coverage**

```bash
.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal -v 1
```

**Step 5: Commit**

```bash
git add templates/portal/base.html wms/static/portal/portal-bootstrap.css wms/static/scan/scan-bootstrap.css wms/tests/views/tests_portal_bootstrap_ui.py
git commit -m "feat: adapt portal navigation shell"
```

### Task 3: Add failing benevole shell navigation tests

**Files:**
- Modify: `wms/tests/views/tests_views_volunteer.py`
- Optional Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Reference: `templates/benevole/base.html`

**Step 1: Add assertions for the new benevole shell**

Cover:
- masthead utility controls
- primary section rail
- absence of logout in peer navigation
- lighter shell than `portal`

**Step 2: Run the targeted failing test**

```bash
.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer -v 1
```

**Step 3: Commit the failing test**

```bash
git add wms/tests/views/tests_views_volunteer.py
git commit -m "test: add benevole navigation shell contract"
```

### Task 4: Implement the benevole shell adaptation

**Files:**
- Modify: `templates/benevole/base.html`
- Modify: `wms/static/portal/portal-bootstrap.css`
- Optional Modify: `wms/static/scan/scan-bootstrap.css`

**Step 1: Apply the lighter authenticated shell**

Implement:
- masthead with utility controls
- primary section rail
- utility-only logout
- no CTA cluster

**Step 2: Reuse the same navigation language**

Keep:
- the same active-state grammar
- the same calm separation between navigation and utility

Do not add:
- sidebar desktop
- stronger CTA emphasis than needed

**Step 3: Re-run benevole shell coverage**

```bash
.venv/bin/python manage.py test wms.tests.views.tests_views_volunteer -v 1
```

**Step 4: Commit**

```bash
git add templates/benevole/base.html wms/static/portal/portal-bootstrap.css wms/static/scan/scan-bootstrap.css wms/tests/views/tests_views_volunteer.py
git commit -m "feat: adapt benevole navigation shell"
```

### Task 5: Run the combined navigation verification

**Files:**
- No new files

**Step 1: Run the focused combined suite**

```bash
.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal wms.tests.views.tests_views_volunteer -v 1
```

**Step 2: Run diff hygiene**

```bash
git diff --check
```

**Step 3: Commit the final verification state**

```bash
git add templates/portal/base.html templates/benevole/base.html wms/static/portal/portal-bootstrap.css wms/static/scan/scan-bootstrap.css wms/tests/views/tests_portal_bootstrap_ui.py wms/tests/views/tests_views_portal.py wms/tests/views/tests_views_volunteer.py
git commit -m "chore: finalize portal and benevole navigation adaptation"
```
