# Legacy Global Navigation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Validate and roll out the recommended three-layer legacy navigation model through `UI Lab` first, then `scan`, then lighter adaptations in `portal` and `benevole`.

**Architecture:** Keep the work on the legacy Django stack. Use `UI Lab` as the proving ground for the navigation contract, then refactor shell templates and existing Bootstrap bridge styles without inventing a second navigation library. Preserve the `Core stable` / `En convergence` governance split by treating global navigation as a documented contract first and only then as local shell markup.

**Tech Stack:** Django templates, legacy Bootstrap 5 shell markup, `scan-bootstrap.css`, `portal-bootstrap.css`, `UI Lab`, Django view tests.

---

### Task 1: Add failing UI Lab navigation demo coverage

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Reference: `templates/scan/ui_lab.html`

**Step 1: Write the failing test**

Add a test like:

```python
def test_scan_ui_lab_exposes_recommended_global_navigation_demo_contract(self):
    response = self.client.get(reverse("scan:scan_ui_lab"))

    self.assertContains(response, 'id="ui-lab-demo-global-navigation"')
    self.assertContains(response, "Navigation globale recommandee")
    self.assertContains(response, "scan-nav-demo-primary")
    self.assertContains(response, "scan-nav-demo-utility")
    self.assertContains(response, "Tableau de bord")
    self.assertContains(response, "Gestion")
```

**Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_ui_lab_exposes_recommended_global_navigation_demo_contract -v 2
```

Expected:
- FAIL because the new demo block does not exist yet.

**Step 3: Commit the failing test**

```bash
git add wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "test: add ui lab global navigation demo contract"
```

### Task 2: Implement the UI Lab navigation demo markup

**Files:**
- Modify: `templates/scan/ui_lab.html`
- Optional Modify: `wms/views_scan_misc.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Add one dedicated article to UI Lab**

Add a new article with:
- `id="ui-lab-demo-global-navigation"`
- a compact utility row
- a recommended primary `scan` section rail
- a lightweight mobile-toggle representation if needed
- optional lighter `portal` and `benevole` mini variants if they strengthen the comparison without bloating the page

**Step 2: Keep it demo-only**

Use inert links or safe placeholder anchors. Do not bind runtime business actions or real navigation side effects.

**Step 3: Re-run the targeted test**

Run:

```bash
.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_ui_lab_exposes_recommended_global_navigation_demo_contract -v 2
```

Expected:
- PASS

**Step 4: Commit**

```bash
git add templates/scan/ui_lab.html wms/views_scan_misc.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add ui lab global navigation demo"
```

### Task 3: Style the UI Lab navigation demo and verify the shell page

**Files:**
- Modify: `wms/static/scan/ui-lab.css`
- Optional Modify: `wms/static/scan/ui-lab.js`
- Test: `wms/tests/views/tests_views_scan_misc.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Add demo-local CSS**

Add styles for:
- utility row
- primary section rail
- active item treatment
- demo-only mobile menu block or collapsed state
- clear separation of navigation versus CTA

Keep all selectors local to the demo block.

**Step 2: Prefer zero custom JS**

If a mobile reveal interaction is needed, use Bootstrap-native collapse first. Add demo JS only if markup alone cannot express the contract.

**Step 3: Run UI Lab regression coverage**

Run:

```bash
.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc wms.tests.views.tests_scan_bootstrap_ui -v 1
```

Expected:
- PASS for the `UI Lab` page and existing contract coverage.

**Step 4: Commit**

```bash
git add wms/static/scan/ui-lab.css wms/static/scan/ui-lab.js templates/scan/ui_lab.html wms/tests/views/tests_views_scan_misc.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: style ui lab global navigation demo"
```

### Task 4: Add failing scan-shell navigation tests

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Reference: `templates/scan/base.html`
- Reference: `wms/static/scan/scan-bootstrap.css`

**Step 1: Update scan navigation expectations**

Add or replace tests so they assert the new shell contract, for example:

```python
def test_scan_nav_uses_primary_sections_and_utility_account_menu(self):
    response = self.client.get(reverse("scan:scan_stock"))
    nav_html = self._scan_nav_html(response)

    self.assertIn("Tableau de bord", nav_html)
    self.assertIn("Stocks", nav_html)
    self.assertIn("Reception", nav_html)
    self.assertIn("Preparation", nav_html)
    self.assertIn("Expeditions", nav_html)
    self.assertIn("Gestion", nav_html)
    self.assertNotIn("Voir Les Etats", nav_html)
```

Also add a utility-layer assertion for `Compte` and, for superusers, `Admin`.

**Step 2: Run the targeted scan nav tests**

Run:

```bash
.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_nav_uses_primary_sections_and_utility_account_menu -v 2
```

Expected:
- FAIL against the current shell.

**Step 3: Commit**

```bash
git add wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "test: update scan shell navigation expectations"
```

### Task 5: Implement the scan navigation refresh

**Files:**
- Modify: `templates/scan/base.html`
- Modify: `wms/static/scan/scan-bootstrap.css`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Split the shell into utility and primary layers**

Refactor the header so it contains:
- utility row with brand, language switch, account, and optional admin access
- primary section rail with the reduced first-level taxonomy

Keep workflow-local controls out of the shell.

**Step 2: Reduce the first-level taxonomy**

Map current pages under:
- `Tableau de bord`
- `Stocks`
- `Reception`
- `Preparation`
- `Expeditions`
- `Gestion`

Place `Planning` outside the core section rail if it must remain globally visible.

**Step 3: Update shell styling**

Adjust `scan-bootstrap.css` so:
- the header feels lighter,
- the nav stops looking like a wall of action buttons,
- the active state is more explicit,
- utility and primary layers are clearly separated,
- mobile gets a dedicated menu treatment rather than a long stacked dropdown list.

**Step 4: Run focused scan verification**

Run:

```bash
.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 1
```

Expected:
- PASS for shell and `UI Lab` coverage.

**Step 5: Commit**

```bash
git add templates/scan/base.html wms/static/scan/scan-bootstrap.css wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: refresh scan global navigation"
```

### Task 6: Add failing portal and benevole shell tests

**Files:**
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_volunteer.py`
- Reference: `templates/portal/base.html`
- Reference: `templates/benevole/base.html`

**Step 1: Add portal shell assertions**

Add a portal test that checks:
- a real navigation region exists
- `Nouvelle commande` is separated from the primary section list
- logout is not styled as a peer navigation item

**Step 2: Add benevole shell assertions**

Add a volunteer test that checks:
- the authenticated shell shows a primary navigation group
- the active section remains clear
- logout is separated from the main section group

**Step 3: Run the focused tests**

Run:

```bash
.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_volunteer -v 1
```

Expected:
- FAIL until the shells are updated.

**Step 4: Commit**

```bash
git add wms/tests/views/tests_portal_bootstrap_ui.py wms/tests/views/tests_views_volunteer.py
git commit -m "test: add portal and volunteer navigation shell coverage"
```

### Task 7: Implement the portal and benevole shell refresh

**Files:**
- Modify: `templates/portal/base.html`
- Modify: `templates/benevole/base.html`
- Modify: `wms/static/portal/portal-bootstrap.css`
- Test: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Test: `wms/tests/views/tests_views_volunteer.py`

**Step 1: Refactor portal shell**

Turn the header into:
- utility controls
- primary section navigation
- distinct CTA for `Nouvelle commande`

Move logout to the utility layer.

**Step 2: Refactor benevole shell**

Keep the authenticated shell light, but:
- use the same section-versus-utility separation
- keep the active section clear
- avoid the all-buttons-equal look

**Step 3: Extend portal bridge styling**

Update `portal-bootstrap.css` so both shells share:
- calmer section navigation treatment
- distinct CTA behavior
- cleaner wrap behavior on small screens

Do not add a separate new navigation library.

**Step 4: Run focused portal and volunteer verification**

Run:

```bash
.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_volunteer -v 1
```

Expected:
- PASS

**Step 5: Commit**

```bash
git add templates/portal/base.html templates/benevole/base.html wms/static/portal/portal-bootstrap.css wms/tests/views/tests_portal_bootstrap_ui.py wms/tests/views/tests_views_volunteer.py
git commit -m "feat: refresh portal and volunteer navigation"
```

### Task 8: Run final verification and prepare review

**Files:**
- Verify only

**Step 1: Run the full targeted navigation suite**

Run:

```bash
.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_volunteer -v 1
```

Expected:
- PASS

**Step 2: Run diff hygiene**

Run:

```bash
git diff --check
git status --short --branch
```

Expected:
- no diff-check errors
- only the intended branch changes present

**Step 3: Prepare review notes**

Summarize:
- `UI Lab` contract added
- `scan` shell simplified
- `portal` and `benevole` aligned with the same navigation language
- mobile handling adjusted without touching Django admin or translation scope

**Step 4: Commit if needed**

If any final doc or cleanup change remains:

```bash
git add -A
git commit -m "chore: finalize legacy navigation refresh"
```
