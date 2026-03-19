# Bootstrap-Only UI Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove dormant Next/theme UI layers so the product keeps a single Django-rendered Bootstrap UI, while preserving the runtime Design editor for direct UI parameter tuning.

**Architecture:** Drive the cleanup from tests that lock the Bootstrap-only target, then remove `/app/*` and `ui_mode`, simplify context/templates so Bootstrap is always active, and finally strip theme presets and theme-specific CSS while keeping the Design token editor. Keep the scope on the Django UI and avoid paused Next migration work outside the explicit cleanup requested here.

**Tech Stack:** Django templates, Django URL routing, Django TestCase, Bootstrap 5, local CSS bridges, runtime design tokens

---

### Task 1: Lock the Bootstrap-only target with failing tests

**Files:**
- Modify: `wms/tests/core/tests_ui_mode.py`
- Modify: `wms/tests/views/tests_views_scan_admin.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_home.py`
- Modify: `wms/tests/admin/tests_admin_bootstrap_ui.py`
- Verify: `asf_wms/urls.py`
- Verify: `templates/scan/base.html`
- Verify: `templates/portal/base.html`
- Verify: `templates/benevole/base.html`
- Verify: `templates/home.html`
- Verify: `templates/password_help.html`
- Verify: `wms/views_scan_design.py`

**Step 1: Write the failing test**

Add assertions that prove the new target:
- reverse or resolve no longer exposes `ui_mode_set`, `ui_mode_set_mode`, `next_frontend_root`, `next_frontend`
- scan/portal/home/admin templates keep Bootstrap assets and shell classes without any `SCAN_BOOTSTRAP_ENABLED=False` fallback branch
- design admin no longer renders built-in style presets or preset actions

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.core.tests_ui_mode wms.tests.views.tests_views_scan_admin wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_home wms.tests.admin.tests_admin_bootstrap_ui -v 2`

Expected: FAIL because routes, preset UI, and Bootstrap-disable compatibility still exist.

**Step 3: Write minimal implementation**

No production implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run the same command and confirm failures point only to the targeted Bootstrap-only assertions.

**Step 5: Commit**

```bash
git add wms/tests/core/tests_ui_mode.py wms/tests/views/tests_views_scan_admin.py wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_portal_bootstrap_ui.py wms/tests/views/tests_views_home.py wms/tests/admin/tests_admin_bootstrap_ui.py
git commit -m "test: lock bootstrap-only ui target"
```

### Task 2: Remove dormant Next and ui_mode entry points

**Files:**
- Modify: `asf_wms/urls.py`
- Delete: `wms/views_next_frontend.py`
- Delete: `wms/ui_mode.py`
- Delete: `wms/tests/views/tests_views_next_frontend.py`
- Modify: `wms/context_processors.py`
- Modify: `wms/models.py` or integration exports if `UiMode` / `UserUiPreference` imports need pruning
- Delete: `templates/app/next_build_missing.html`
- Delete: `frontend-next/README.md`
- Delete: `frontend-next/app/layout.tsx`
- Delete: `frontend-next/app/page.tsx`

**Step 1: Write the failing test**

Use the red tests from Task 1 that assert the routes and mode helpers are gone.

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.core.tests_ui_mode wms.tests.views.tests_views_scan_admin wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_home wms.tests.admin.tests_admin_bootstrap_ui -v 2`

Expected: FAIL because the URL patterns and helper modules are still present.

**Step 3: Write minimal implementation**

- remove `/app/*`, `/ui/mode/*`, and `frontend_log_event` from `asf_wms/urls.py`
- delete `wms/views_next_frontend.py`
- delete `wms/ui_mode.py`
- remove `wms_ui_mode` and `wms_ui_mode_is_next` from the context processor
- delete dormant Next placeholder template and static Next app files

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.core.tests_ui_mode wms.tests.views.tests_views_scan_admin wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_home wms.tests.admin.tests_admin_bootstrap_ui -v 2`

Expected: PASS for route/mode removal checks, with any remaining failures limited to Bootstrap-only/template/preset cleanup.

**Step 5: Commit**

```bash
git add asf_wms/urls.py wms/context_processors.py wms/models.py templates/app/next_build_missing.html frontend-next wms/views_next_frontend.py wms/ui_mode.py wms/tests/views/tests_views_next_frontend.py
git commit -m "chore: remove dormant next ui entry points"
```

### Task 3: Make Bootstrap unconditional across Django templates

**Files:**
- Modify: `templates/scan/base.html`
- Modify: `templates/portal/base.html`
- Modify: `templates/portal/login.html`
- Modify: `templates/portal/access_recovery.html`
- Modify: `templates/portal/set_password.html`
- Modify: `templates/benevole/base.html`
- Modify: `templates/benevole/login.html`
- Modify: `templates/benevole/access_recovery.html`
- Modify: `templates/home.html`
- Modify: `templates/password_help.html`
- Modify: `templates/scan/public_account_request.html`
- Modify: `templates/scan/public_order.html`
- Modify: `templates/scan/shipment_tracking.html`
- Modify: `templates/print/order_summary.html`
- Modify: `templates/admin/wms/stockmovement/change_list.html`
- Modify: `templates/admin/wms/stockmovement/form.html`
- Modify: `templates/admin/wms/shipment/change_form.html`
- Modify: `wms/context_processors.py`

**Step 1: Write the failing test**

Use the red tests from Task 1 that assert:
- Bootstrap assets are always present
- Bootstrap body classes are always present
- no template branch depends on `scan_bootstrap_enabled`

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_home wms.tests.admin.tests_admin_bootstrap_ui -v 2`

Expected: FAIL because templates still contain compatibility branches and disabled-setting assertions.

**Step 3: Write minimal implementation**

- make `_resolve_scan_bootstrap_enabled()` disappear or inline `True`
- remove `{% if scan_bootstrap_enabled %}` branches from templates
- keep Bootstrap assets, Bootstrap bridge CSS, and shell classes unconditionally
- update tests that previously asserted the disabled-setting compatibility path

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_home wms.tests.admin.tests_admin_bootstrap_ui -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add templates/scan/base.html templates/portal/base.html templates/portal/login.html templates/portal/access_recovery.html templates/portal/set_password.html templates/benevole/base.html templates/benevole/login.html templates/benevole/access_recovery.html templates/home.html templates/password_help.html templates/scan/public_account_request.html templates/scan/public_order.html templates/scan/shipment_tracking.html templates/print/order_summary.html templates/admin/wms/stockmovement/change_list.html templates/admin/wms/stockmovement/form.html templates/admin/wms/shipment/change_form.html wms/context_processors.py wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_portal_bootstrap_ui.py wms/tests/views/tests_views_home.py wms/tests/admin/tests_admin_bootstrap_ui.py
git commit -m "refactor: make bootstrap the only django ui shell"
```

### Task 4: Simplify Design admin to direct Bootstrap token editing

**Files:**
- Modify: `wms/views_scan_design.py`
- Modify: `wms/forms_scan_design.py`
- Delete: `wms/design_style_presets.py`
- Modify: `templates/scan/admin_design.html`
- Modify: `wms/models_domain/integration.py`
- Modify: `wms/tests/views/tests_views_scan_admin.py`
- Verify: `templates/includes/design_vars_style.html`
- Verify: `wms/design_tokens.py`

**Step 1: Write the failing test**

Add assertions that:
- built-in preset labels no longer render
- preset action controls no longer render
- posting direct design-token values still persists and updates runtime settings

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin -v 2`

Expected: FAIL because preset labels/actions are still rendered.

**Step 3: Write minimal implementation**

- remove preset-building helpers and preset actions from `wms/views_scan_design.py`
- trim `ScanDesignSettingsForm` so it edits direct fields/tokens only
- delete `wms/design_style_presets.py`
- remove `design_selected_preset` and `design_custom_presets` usage from the request flow
- simplify the admin template so it only exposes direct controls and reset/save actions

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_scan_design.py wms/forms_scan_design.py templates/scan/admin_design.html wms/models_domain/integration.py wms/tests/views/tests_views_scan_admin.py wms/design_tokens.py templates/includes/design_vars_style.html
git commit -m "refactor: keep design admin as direct bootstrap token editor"
```

### Task 5: Remove dead theme CSS and run focused regressions

**Files:**
- Modify: `wms/static/scan/scan.css`
- Modify: `README.md`
- Modify: `.env.example`
- Verify: `wms/static/scan/scan-bootstrap.css`
- Verify: `wms/static/portal/portal-bootstrap.css`
- Verify: `wms/static/wms/admin-bootstrap.css`
- Verify: `docs/plans/2026-03-19-bootstrap-only-ui-design.md`

**Step 1: Write the failing test**

Add or update a CSS regression test that confirms `scan.css` no longer contains selectors like:
- `data-ui="studio"`
- `data-ui="benev"`
- `data-ui="timeline"`
- `data-ui="spreadsheet"`
- `data-theme="atelier"`

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL because the theme selectors still exist in `scan.css`.

**Step 3: Write minimal implementation**

- delete the dead theme selector blocks from `wms/static/scan/scan.css`
- remove README and env docs that still describe Bootstrap as a reversible toggle
- keep only documentation consistent with a single Bootstrap UI and Design runtime tuning

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_home wms.tests.admin.tests_admin_bootstrap_ui wms.tests.views.tests_views_scan_admin -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/static/scan/scan.css README.md .env.example wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_portal_bootstrap_ui.py wms/tests/views/tests_views_home.py wms/tests/admin/tests_admin_bootstrap_ui.py wms/tests/views/tests_views_scan_admin.py docs/plans/2026-03-19-bootstrap-only-ui-design.md docs/plans/2026-03-19-bootstrap-only-ui-implementation-plan.md
git commit -m "refactor: collapse ui onto bootstrap-only django shell"
```

### Task 6: Final focused verification

**Files:**
- Verify: `wms/tests/core/tests_ui_mode.py`
- Verify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Verify: `wms/tests/views/tests_views_home.py`
- Verify: `wms/tests/admin/tests_admin_bootstrap_ui.py`
- Verify: `wms/tests/views/tests_views_scan_admin.py`

**Step 1: Write the failing test**

No new test if Tasks 1-5 fully cover the target.

**Step 2: Run targeted regression suite**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.core.tests_ui_mode wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_home wms.tests.admin.tests_admin_bootstrap_ui wms.tests.views.tests_views_scan_admin -v 2`

Expected: PASS, or a report limited to pre-existing failures already observed before implementation.

**Step 3: Write minimal implementation**

Only if regressions remain. Fix the smallest route/template/design regression without broadening scope.

**Step 4: Run test to verify it passes**

Re-run the full command from Step 2 and confirm the final state.

**Step 5: Commit**

```bash
git add -A
git commit -m "test: verify bootstrap-only ui cleanup"
```
