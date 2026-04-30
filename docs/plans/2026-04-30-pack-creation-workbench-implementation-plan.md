# Pack Creation Workbench Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current linear `/scan/pack/` creation form with a carton workbench that lets operators compose, duplicate, batch-edit, review, and then create exact cartons.

**Architecture:** Keep the legacy Django scan surface. The browser owns the transient draft carton plan; the server receives an exact carton plan only on confirmation and revalidates all stock, assignment, output, and format rules before writing cartons.

**Tech Stack:** Django templates/views/handlers, existing pack/carton models and services, vanilla scan JavaScript, Bootstrap scan CSS, Django tests.

---

### Task 1: Add Exact Carton Plan Parsing Tests

**Files:**
- Modify: `wms/tests/orders/tests_pack_handlers.py`
- Modify: `wms/pack_handlers.py`

**Step 1: Write failing tests**

Add tests that post an exact draft plan with:

- two mono-product available cartons;
- one multi-product available carton;
- one documentary carton;
- per-carton destination/shipment/output values;
- one selected shipment and one selected destination.

Expected behavior:

- stock quantities are consumed from the exact product lines;
- created cartons match row content and assignments;
- output mode is respected per row;
- no auto bin-packing runs when exact plan mode is used.

**Step 2: Run tests to verify failure**

Run:

```bash
env DJANGO_SECRET_KEY=codex-local-coverage-key-not-production-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ./.venv/bin/python manage.py test wms.tests.orders.tests_pack_handlers -v 2
```

Expected: new tests fail because exact carton plan parsing does not exist yet.

**Step 3: Implement parser skeleton**

In `wms/pack_handlers.py`, add a private parser for POST keys such as:

- `carton_plan_mode=exact`;
- `carton_plan_count`;
- `carton_1_output_mode`;
- `carton_1_preassigned_destination`;
- `carton_1_shipment_reference`;
- `carton_1_current_location`;
- `carton_1_carton_format_id`;
- `carton_1_line_count`;
- `carton_1_line_1_product_code`;
- `carton_1_line_1_quantity`;
- `carton_1_line_1_expires_on`;
- `carton_1_line_1_pack_family_override`.

Return a normalized list of draft cartons and validation errors.

**Step 4: Run targeted tests**

Run the same `wms.tests.orders.tests_pack_handlers` command and iterate until parser-focused tests pass.

**Step 5: Commit**

```bash
git add wms/pack_handlers.py wms/tests/orders/tests_pack_handlers.py
git commit -m "feat: parse exact pack carton plans"
```

### Task 2: Create Cartons From Exact Plans

**Files:**
- Modify: `wms/pack_handlers.py`
- Modify: `wms/tests/orders/tests_pack_handlers.py`

**Step 1: Write failing creation tests**

Cover:

- exact mono-product carton creation;
- exact multi-product carton creation;
- mixed `available` and `without_conditioning` output modes;
- invalid stock quantity rejection;
- invalid shipment/destination mismatch handling using existing rules where available.

**Step 2: Implement exact creation path**

In `handle_pack_post`, when `carton_plan_mode=exact` and confirmation is present:

- bypass forced carton count/bin packing;
- build bins directly from exact rows;
- reuse existing carton creation helpers where possible;
- keep stock errors non-destructive;
- keep deprecated `prepare_available_batch` rejection in place.

**Step 3: Preserve existing non-exact behavior**

Existing auto/manual modes must still work until the UI fully switches. Keep their tests passing.

**Step 4: Run tests**

Run:

```bash
env DJANGO_SECRET_KEY=codex-local-coverage-key-not-production-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ./.venv/bin/python manage.py test wms.tests.orders.tests_pack_handlers wms.tests.scan.tests_scan_pack_helpers -v 2
```

Expected: pass.

**Step 5: Commit**

```bash
git add wms/pack_handlers.py wms/tests/orders/tests_pack_handlers.py
git commit -m "feat: create exact pack carton plans"
```

### Task 3: Build Workbench Template Shell

**Files:**
- Modify: `templates/scan/pack.html`
- Modify: `templates/scan/includes/pack_shipping_section.html`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write failing view tests**

Assert `/scan/pack/` renders:

- quick generator section;
- `Plan des colis à créer`;
- selection action toolbar;
- final confirmation modal;
- no separate guided sections as the primary creation flow.

**Step 2: Replace creation form shell**

Keep editing existing carton behavior intact. For new carton creation, render:

- quick generator;
- draft plan table;
- batch toolbar;
- row editor container;
- final confirmation modal;
- hidden form fields for exact plan submission.

**Step 3: Run template tests**

Run:

```bash
env DJANGO_SECRET_KEY=codex-local-coverage-key-not-production-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected: pass.

**Step 4: Commit**

```bash
git add templates/scan/pack.html templates/scan/includes/pack_shipping_section.html wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add pack workbench shell"
```

### Task 4: Implement Workbench JavaScript

**Files:**
- Modify: `wms/static/scan/scan.js`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Add static contract tests**

Assert JS contains stable hooks/functions for:

- draft carton state;
- quick generator;
- row duplication by target total count;
- selected-row batch update;
- exact plan hidden field serialization;
- final confirmation summary.

**Step 2: Implement draft state**

Maintain an array of draft cartons with stable client IDs. Each draft carton owns content lines, assignment, output, location, and format.

**Step 3: Implement quick generator**

For the primary case:

- product scanned/searched;
- total quantity;
- quantity per carton;
- generated count;
- default output/assignment.

Generate one draft row per carton. Handle remainder explicitly if total quantity is not divisible by quantity per carton.

**Step 4: Implement duplication**

The duplication modal asks:

```text
Dupliquer ce colis pour obtenir [N] colis identiques au total
```

If the source row already counts as one, add `N - 1` copies. Reject `N < 2`.

**Step 5: Implement cumulative batch actions**

Batch actions update only the target field:

- destination;
- shipment;
- output mode;
- location;
- format;
- delete;
- duplicate.

**Step 6: Serialize exact plan**

Before confirmation submit, write exact hidden inputs matching the server parser contract.

**Step 7: Run checks**

Run:

```bash
node --check wms/static/scan/scan.js
env DJANGO_SECRET_KEY=codex-local-coverage-key-not-production-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected: pass.

**Step 8: Commit**

```bash
git add wms/static/scan/scan.js wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add pack workbench interactions"
```

### Task 5: Style The Workbench

**Files:**
- Modify: `wms/static/scan/scan-bootstrap.css`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Add CSS contract tests**

Assert CSS includes stable classes for:

- workbench grid;
- draft plan table/cards;
- selection toolbar;
- expanded carton editor;
- compact mobile rows.

**Step 2: Implement CSS**

Use dense operational layout:

- no nested cards;
- stable table/card dimensions;
- compact action toolbar;
- mobile rows that preserve product, assignment, and output readability.

**Step 3: Run checks**

Run:

```bash
env DJANGO_SECRET_KEY=codex-local-coverage-key-not-production-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2
git diff --check
```

Expected: pass.

**Step 4: Commit**

```bash
git add wms/static/scan/scan-bootstrap.css wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: style pack workbench"
```

### Task 6: Update Docs, Cache, And Regression Coverage

**Files:**
- Modify: `templates/scan/faq.html`
- Modify: `wms/faq_changelog.py`
- Modify: `docs/repo-reference/04-shared-contracts/03-scan-operations.md`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/release_checklist.md`
- Modify: `wms/views_scan_misc.py`
- Modify: `templates/scan/base.html`

**Step 1: Update docs**

Document:

- pack workbench replaces linear guided flow;
- exact draft cartons can be edited individually or in batch;
- Vue Colis remains available for later assignment;
- final confirmation is mandatory.

**Step 2: Add FAQ changelog entry**

Use PR number when known. If unknown during local work, write `PR TBD` and replace before merge.

**Step 3: Bump scan service worker version**

Update both `wms/views_scan_misc.py` and `templates/scan/base.html`.

**Step 4: Run focused tests**

Run:

```bash
node --check wms/static/scan/scan.js
uv run ruff check wms/pack_handlers.py wms/scan_pack_helpers.py wms/views_scan_shipments.py wms/views_scan_misc.py wms/faq_changelog.py wms/tests/orders/tests_pack_handlers.py wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/scan/tests_scan_pack_helpers.py
git diff --check
env DJANGO_SECRET_KEY=codex-local-coverage-key-not-production-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ./.venv/bin/python manage.py test wms.tests.scan.tests_scan_pack_helpers wms.tests.orders.tests_pack_handlers wms.tests.views.tests_views_scan_shipments wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_orders wms.tests.carton.tests_carton_handlers -v 2
```

Expected: pass.

**Step 5: Commit**

```bash
git add templates/scan/faq.html wms/faq_changelog.py docs/repo-reference/04-shared-contracts/03-scan-operations.md docs/repo-reference/02-key-flows-and-living-tests.md docs/release_checklist.md wms/views_scan_misc.py templates/scan/base.html
git commit -m "docs: document pack workbench flow"
```

### Task 7: PR Verification

**Files:**
- No code changes unless CI fails.

**Step 1: Run final local checks**

Run the focused checks from Task 6.

**Step 2: Push and update PR**

Push the branch and create or update the PR. Do not merge without user approval.

**Step 3: Check CI after 3.5 minutes**

Run:

```bash
gh pr checks <PR_NUMBER>
```

If a job fails, inspect logs, fix the actual cause, push, and repeat the 3.5-minute check loop.

**Step 4: Launch seeded local instance**

Run:

```bash
pkill -f "manage.py runserver"
env DJANGO_SECRET_KEY=codex-local-dev-key-not-production-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ./.venv/bin/python manage.py seed_local_exhaustive_data --scenario=pack-workbench --fresh --with-demo-documents --with-queue-backlog --with-planning-solve --with-e2e-baseline
env DJANGO_SECRET_KEY=codex-local-dev-key-not-production-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ DJANGO_DEBUG=true DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost ./.venv/bin/python manage.py runserver 127.0.0.1:8000 --noreload
```

**Step 5: Report manual test flows**

List:

- quick generator creates identical mono-product cartons;
- duplication by target total count;
- mixed mono/multi-product draft rows;
- individual destination/shipment/output edits;
- cumulative batch actions;
- final confirmation summary;
- Vue Colis later assignment for free available cartons;
- preparateur flow remains usable.
