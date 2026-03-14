# FAQ Hub Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite the legacy FAQ page so it documents Scan, Planning, Portal, Volunteer, and admin/support workflows in a single mixed hub.

**Architecture:** Keep the existing `/scan/faq/` route, summary generator, and collapsible card pattern. Replace the old Scan-only copy in the Django template with a broader content structure, then lock the new sections down with view-level rendering tests in French and native English.

**Tech Stack:** Django templates, Django i18n tags, Django TestCase view tests

---

### Task 1: Add failing FAQ rendering expectations

**Files:**
- Modify: `wms/tests/views/tests_views_scan_misc.py`
- Modify: `wms/tests/views/tests_i18n_language_switch.py`

**Step 1: Write the failing test**

Add assertions for the new mixed FAQ structure:
- French sections for `Flux principaux`, `Planning`, `Portal association`, `Espace bénévole`, and `Administration & support`
- English sections for `Main workflows`, `Planning`, `Association portal`, `Volunteer area`, and `Admin & support`
- Key workflow snippets proving the FAQ now documents cross-area usage

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc wms.tests.views.tests_i18n_language_switch -v 2`

Expected: FAIL because the old FAQ template does not yet expose the new section titles and workflow text.

**Step 3: Write minimal implementation**

No implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run the same command and confirm the failures point to missing FAQ content, not unrelated rendering errors.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_scan_misc.py wms/tests/views/tests_i18n_language_switch.py
git commit -m "test: cover mixed FAQ hub content"
```

### Task 2: Rewrite the FAQ template content

**Files:**
- Modify: `templates/scan/faq.html`

**Step 1: Write the failing test**

Use the failing tests from Task 1 as the red state.

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc wms.tests.views.tests_i18n_language_switch -v 2`

Expected: FAIL on the new FAQ assertions.

**Step 3: Write minimal implementation**

Refactor the FAQ template into these sections while preserving summary/collapse hooks:
- Overview and access model
- Glossary and key statuses
- Main workflows
- Scan reference
- Planning reference
- Association portal reference
- Volunteer area reference
- Admin & support reference
- Cross-cutting business rules
- Troubleshooting

Keep all user-facing copy inside `{% trans %}` / `{% blocktrans %}`.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_views_scan_misc wms.tests.views.tests_i18n_language_switch -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add templates/scan/faq.html
git commit -m "feat: refresh mixed FAQ hub"
```

### Task 3: Run broader regression coverage for FAQ surfaces

**Files:**
- Verify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `wms/tests/views/tests_views_scan_misc.py`
- Verify: `wms/tests/views/tests_i18n_language_switch.py`

**Step 1: Write the failing test**

No new test required if Tasks 1-2 already cover behavior.

**Step 2: Run targeted regression suite**

Run: `.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_misc wms.tests.views.tests_i18n_language_switch -v 2`

Expected: PASS with the refreshed FAQ content.

**Step 3: Write minimal implementation**

Only if regressions appear. Fix copy or template structure without changing the agreed scope.

**Step 4: Run test to verify it passes**

Re-run the same command until clean.

**Step 5: Commit**

```bash
git add templates/scan/faq.html wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_misc.py wms/tests/views/tests_i18n_language_switch.py
git commit -m "test: verify FAQ hub regressions"
```
