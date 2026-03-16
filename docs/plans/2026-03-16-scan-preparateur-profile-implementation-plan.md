# Scan Preparateur Profile Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a locked-down `Preparateur` scan profile that lands on legacy pack creation, can only prepare cartons, and auto-routes finished cartons into `MM` or `CN` ready locations with a clear success popup.

**Architecture:** Keep the legacy Django scan stack and reuse the existing `scan_pack` workflow. Introduce a dedicated scan role helper for `Preparateur`, guard the scan entrypoints and navigation at the backend/template level, then extend the legacy pack handler with `MM/CN` grouping, manual type override for unresolved products, automatic ready-location assignment, and success recap state for the pack page.

**Tech Stack:** Django views/templates/forms, legacy scan JavaScript, Django TestCase view tests, handler unit tests

---

### Task 0: Create the isolated worktree and verify the baseline

**Files:**
- Reference: `.worktrees/`
- Reference: `docs/plans/2026-03-16-scan-preparateur-profile-design.md`

**Step 1: Create the feature branch in the existing worktree directory**

Run:

```bash
git worktree add .worktrees/preparateur-profile -b codex/preparateur-profile
```

Expected: git creates `.worktrees/preparateur-profile` on branch `codex/preparateur-profile`.

**Step 2: Move into the worktree**

Run:

```bash
cd /Users/EdouardGonnu/asf-wms/.worktrees/preparateur-profile
```

Expected: all following edits happen outside `main`.

**Step 3: Run a narrow scan baseline**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views.ScanViewTests.test_scan_pack_creates_carton \
  wms.tests.views.tests_views.ScanViewTests.test_scan_internal_routes_require_staff \
  wms.tests.orders.tests_pack_handlers.PackHandlersTests.test_handle_pack_post_success_with_warnings_sets_pack_results \
  -v 2
```

Expected: PASS on the current baseline before feature work starts.

**Step 4: Commit**

No commit in the baseline task.

### Task 1: Add failing tests for the preparateur access model

**Files:**
- Create: `wms/tests/scan/tests_scan_permissions.py`
- Modify: `wms/tests/views/tests_views.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Reference: `wms/scan_urls.py`
- Reference: `wms/view_permissions.py`
- Reference: `templates/scan/base.html`

**Step 1: Write the failing tests for role detection**

Add tests that cover:
- `user_is_preparateur(user)` returns `True` only for users in the `Preparateur` group;
- normal staff users are not treated as `Preparateur`.

**Step 2: Write the failing view tests**

Add view assertions for a logged-in `Preparateur`:
- `GET /scan/` redirects to `scan:scan_pack`;
- `GET /scan/pack/` returns `200`;
- `GET /scan/dashboard/`, `GET /scan/stock/`, `GET /scan/shipments-ready/` return `403`;
- `GET /scan/sync/` still returns `200`.

Also add template assertions that the pack page menu shows only the allowed preparateur entries and hides dashboard/admin/stock links.

**Step 3: Run the focused tests to verify they fail**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.scan.tests_scan_permissions \
  wms.tests.views.tests_views.ScanViewTests \
  wms.tests.views.tests_views_scan_shipments.ScanShipmentsViewsTests \
  -v 2
```

Expected: FAIL because the role helper, route redirect, backend whitelist, and menu gating do not exist yet.

**Step 4: Commit**

No commit in the red phase.

### Task 2: Implement the preparateur role helper, root redirect, and scan whitelist

**Files:**
- Create: `wms/scan_permissions.py`
- Modify: `wms/view_permissions.py`
- Modify: `wms/views_scan.py`
- Modify: `wms/views.py`
- Modify: `wms/scan_urls.py`
- Modify: `wms/context_processors.py`
- Modify: `templates/scan/base.html`
- Test: `wms/tests/scan/tests_scan_permissions.py`
- Test: `wms/tests/views/tests_views.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the minimal implementation**

Implement:
- `PREPARATEUR_GROUP_NAME = "Preparateur"` in `wms/scan_permissions.py`;
- helpers such as `user_is_preparateur(user)` and `user_can_access_scan_view(user, view_name)`;
- a dedicated scan root view that redirects `Preparateur` to `scan:scan_pack` and other staff to `scan:scan_dashboard`;
- preparateur-aware decorators or guard logic in `wms/view_permissions.py` so `scan_pack` and `scan_sync` remain allowed while other scan views return `403`;
- a context flag used by `templates/scan/base.html` to collapse the nav for `Preparateur`.

Keep `scan_service_worker` public and unchanged.

**Step 2: Run the focused tests to verify they pass**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.scan.tests_scan_permissions \
  wms.tests.views.tests_views.ScanViewTests \
  wms.tests.views.tests_views_scan_shipments.ScanShipmentsViewsTests \
  -v 2
```

Expected: PASS for the new access-model assertions.

**Step 3: Commit**

```bash
git add \
  wms/scan_permissions.py \
  wms/view_permissions.py \
  wms/views_scan.py \
  wms/views.py \
  wms/scan_urls.py \
  wms/context_processors.py \
  templates/scan/base.html \
  wms/tests/scan/tests_scan_permissions.py \
  wms/tests/views/tests_views.py \
  wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat(scan): lock scan access for preparateurs"
```

### Task 3: Add failing tests for MM/CN grouping, manual override, and auto locations

**Files:**
- Modify: `wms/tests/orders/tests_pack_handlers.py`
- Modify: `wms/tests/views/tests_views.py`
- Reference: `wms/pack_handlers.py`
- Reference: `wms/domain/stock.py`
- Reference: `wms/models_domain/inventory.py`

**Step 1: Write handler tests for MM/CN resolution**

Add unit tests that cover:
- root category `MM` routes lines into an `MM` packing group;
- root category `CN` routes lines into a `CN` packing group;
- a submission with both groups creates separate carton calls;
- a product without root `MM/CN` adds a blocking non-field error when no manual override is provided;
- a line-level manual override `MM` or `CN` clears that error.

Use the existing `handle_pack_post` test style with mocked products, mocked packing bins, mocked locations, and mocked `pack_carton`.

**Step 2: Write an integration-style view test**

Add one view test that posts through `scan:scan_pack` as a `Preparateur` and asserts:
- created cartons end in `CartonStatus.PACKED`;
- `current_location` is the expected ready location;
- no carton mixes `MM` and `CN`.

**Step 3: Run the targeted tests to verify they fail**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.orders.tests_pack_handlers.PackHandlersTests \
  wms.tests.views.tests_views.ScanViewTests \
  -v 2
```

Expected: FAIL because `scan_pack` still treats all lines as one undifferentiated packing flow and does not auto-resolve ready locations or manual type overrides.

**Step 4: Commit**

No commit in the red phase.

### Task 4: Implement the preparateur packing rules in the legacy pack handler

**Files:**
- Modify: `wms/pack_handlers.py`
- Modify: `wms/views_scan_shipments.py`
- Reference: `wms/scan_helpers.py`
- Test: `wms/tests/orders/tests_pack_handlers.py`
- Test: `wms/tests/views/tests_views.py`

**Step 1: Write the minimal implementation**

Extend the pack flow with dedicated helpers inside `wms/pack_handlers.py` for:
- deriving the root category type from each product;
- reading line-level manual overrides from `POST`;
- validating unresolved lines and surfacing a blocking message that asks the operator to choose `MM` or `CN` manually;
- resolving the two ready locations used by the preparateur flow;
- partitioning valid lines into `MM` and `CN` groups before calling `build_packing_bins`;
- calling `pack_carton(...)` with the resolved ready location;
- promoting each created carton from `PICKING` to `PACKED` when the request user is a `Preparateur`;
- storing a richer `pack_results` session payload for the success popup.

Do not change the non-preparateur pack behavior beyond the shared helper extraction that is necessary to keep one handler.

**Step 2: Run the targeted tests to verify they pass**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.orders.tests_pack_handlers.PackHandlersTests \
  wms.tests.views.tests_views.ScanViewTests \
  -v 2
```

Expected: PASS for the new handler and integration assertions.

**Step 3: Commit**

```bash
git add wms/pack_handlers.py wms/views_scan_shipments.py wms/tests/orders/tests_pack_handlers.py wms/tests/views/tests_views.py
git commit -m "feat(scan): auto-route preparateur cartons by type"
```

### Task 5: Add failing tests for the preparateur pack UI and success popup

**Files:**
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/tests/views/tests_views.py`
- Reference: `templates/scan/pack.html`
- Reference: `wms/static/scan/scan.js`

**Step 1: Write the failing template tests**

Add assertions for a `Preparateur` response on `scan:scan_pack`:
- the shipment reference field is absent;
- the manual location field is absent;
- helper print/download links are absent;
- a line with unresolved type renders a manual `MM/CN` selector;
- a successful response with one result renders the single-carton popup copy;
- a successful response with multiple results renders each `zone / numero` pair in the popup.

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments.ScanShipmentsViewsTests \
  wms.tests.views.tests_views.ScanViewTests \
  -v 2
```

Expected: FAIL because the pack template and dynamic pack-line JavaScript do not yet expose preparateur-specific controls or the success modal.

**Step 3: Commit**

No commit in the red phase.

### Task 6: Implement the preparateur-specific pack page rendering

**Files:**
- Modify: `templates/scan/pack.html`
- Modify: `wms/static/scan/scan.js`
- Modify: `wms/views_scan_shipments.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`
- Test: `wms/tests/views/tests_views.py`

**Step 1: Write the minimal implementation**

Implement:
- preparateur-only conditional rendering in `templates/scan/pack.html`;
- removal of shipment/location/helper controls for that profile;
- conditional Bootstrap modal markup for success recap using the richer `pack_results` payload;
- pack-line JSON/bootstrap state that includes manual type values and unresolved-line hints;
- `setupPackLines()` updates in `wms/static/scan/scan.js` so dynamic lines keep and submit the manual `MM/CN` selector when needed.

Prefer a server-rendered Bootstrap modal opened on load over new custom modal plumbing.

**Step 2: Run the targeted tests to verify they pass**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments.ScanShipmentsViewsTests \
  wms.tests.views.tests_views.ScanViewTests \
  -v 2
```

Expected: PASS for the preparateur pack page assertions and popup rendering.

**Step 3: Commit**

```bash
git add templates/scan/pack.html wms/static/scan/scan.js wms/views_scan_shipments.py wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_views.py
git commit -m "feat(scan): tailor pack UI for preparateurs"
```

### Task 7: Run verification and record handoff notes

**Files:**
- Modify: `docs/plans/2026-03-16-scan-preparateur-profile-design.md` only if implementation drift requires an explicit note

**Step 1: Run the full focused verification set**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.scan.tests_scan_permissions \
  wms.tests.orders.tests_pack_handlers \
  wms.tests.views.tests_views \
  wms.tests.views.tests_views_scan_shipments \
  -v 2
```

Expected: PASS for the feature scope.

**Step 2: Run lint on touched Python files**

Run:

```bash
uv run ruff check \
  wms/scan_permissions.py \
  wms/view_permissions.py \
  wms/pack_handlers.py \
  wms/views_scan.py \
  wms/views.py \
  wms/views_scan_shipments.py \
  wms/context_processors.py \
  wms/tests/scan/tests_scan_permissions.py \
  wms/tests/orders/tests_pack_handlers.py \
  wms/tests/views/tests_views.py \
  wms/tests/views/tests_views_scan_shipments.py
```

Expected: `All checks passed!`

**Step 3: Run diff sanity checks**

Run:

```bash
git diff --check
git status --short
```

Expected:
- no whitespace issues;
- only the intended preparateur feature files are modified or staged.

**Step 4: Commit any final documentation drift**

If the implementation required design clarifications:

```bash
git add docs/plans/2026-03-16-scan-preparateur-profile-design.md
git commit -m "docs: align preparateur scan design notes"
```

Otherwise, no extra commit is needed in this task.
