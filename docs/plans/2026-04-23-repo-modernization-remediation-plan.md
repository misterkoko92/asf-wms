# Legacy Repo Modernization Remediation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce accidental complexity on the active legacy Django stack by tightening HTML/API boundaries, removing duplicated runtime helpers, finishing the first frontend modularization wave, and simplifying the highest-friction portal flows without touching paused Next/React or translation scope.

**Architecture:** Keep `scan/`, `portal/`, `planning/`, `benevole/`, `wms/`, and `api/v1/` as the active delivery surface. Push shared business mutations and read models down into `wms/application/*` and `wms/parties/*`, extract shared frontend/runtime helpers instead of cloning them per surface, and only promote UI contracts that are already reused by multiple legacy pages.

**Tech Stack:** Django legacy templates, DRF, Bootstrap 5, local vanilla JS, existing `wms/application/*` and `wms/parties/*` layers, Django test runner, optional Playwright browser smoke tests.

---

## Program Order

1. PR1: Portal HTML/API shared mutations and recipient resolution boundary
2. PR2: Print and pack artifact runtime consolidation
3. PR3: Frontend table tools extraction and `scan.js` modularization
4. PR4: Shared secondary shell cleanup for portal, benevole, planning
5. PR5: Portal order-create UX simplification and browser smoke coverage

## Global Constraints

- Stay on legacy Django only. Do not touch `frontend-next/`, `wms/views_next_frontend.py`, or Next migration docs.
- Keep translation scope paused. Do not modify `locale/` or language-switch behavior.
- Favor additive extractions with compatibility adapters instead of risky rewrites.
- Keep each PR reviewable in isolation and shippable without the following PRs.
- Assume a local Django test key is already exported in the shell before running the commands below.
- Re-run the smoke subset after every PR:

```bash
make test-smoke
```

## Preflight Baseline

Run once before PR1 and attach the outputs to the PR series kickoff note:

```bash
make check
make lint
make typecheck
make bandit
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py check --deploy --fail-level WARNING
```

Expected:
- `check`, `lint`, `typecheck`, `bandit`, `makemigrations --check` green
- `check --deploy` may still warn on runtime env like `ALLOWED_HOSTS`; record but do not block this modernization track

### Task 1: PR1 Portal Shared Mutations And Read Boundaries

**Owner:** application boundary cleanup on portal/account/order/recipient flows

**Why first:** this is the most expensive maintenance hotspot and the place where HTML and API are currently the most entangled.

**Files:**
- Create: `wms/application/portal/account_use_cases.py`
- Create: `wms/application/portal/order_use_cases.py`
- Create: `wms/application/portal/recipient_resolution.py`
- Modify: `wms/views_portal_account.py`
- Modify: `wms/views_portal_orders.py`
- Modify: `api/v1/ui_views.py`
- Modify: `wms/application/portal/__init__.py`
- Test: `api/tests/tests_ui_endpoints.py`
- Test: `api/tests/tests_ui_e2e_workflows.py`
- Test: `wms/tests/portal/tests_portal_order_handlers.py`
- Test: `wms/tests/portal/tests_portal_order_inbound_flow.py`
- Test: `wms/tests/portal/tests_portal_shipment_parties.py`
- Test: `wms/tests/portal/tests_portal_role_review_gate.py`

**Current evidence:**
- API imports a private view helper in `api/v1/ui_views.py:115`
- API account mutation calls `_save_profile_updates()` in `api/v1/ui_views.py:2777`
- API recipient resolution triggers `sync_association_recipient_to_contact()` in `api/v1/ui_views.py:680`
- HTML portal order flow resolves through `resolve_portal_recipient_party_contact()` in `wms/views_portal_orders.py:546`
- Account update currently deletes and recreates all contact rows in `wms/views_portal_account.py:1175`

**Step 1: Write failing parity tests for shared portal behavior**

Run:

```bash
.venv/bin/python manage.py test \
  api.tests.tests_ui_endpoints \
  api.tests.tests_ui_e2e_workflows \
  wms.tests.portal.tests_portal_order_handlers \
  wms.tests.portal.tests_portal_order_inbound_flow \
  wms.tests.portal.tests_portal_shipment_parties \
  -v 2
```

Expected:
- baseline green before refactor
- add new failing tests that assert HTML and API both call the same portal mutation and recipient-resolution layer

**Step 2: Extract account mutation use case**

Implement:
- move `_save_profile_updates()` responsibility into `wms/application/portal/account_use_cases.py`
- keep `wms/views_portal_account.py` as adapter only
- replace the private import from `api/v1/ui_views.py`

Expected:
- no more `from wms.views_portal_account import _save_profile_updates`

**Step 3: Extract order creation and recipient resolution use cases**

Implement:
- move recipient resolution into `wms/application/portal/recipient_resolution.py`
- move order creation orchestration into `wms/application/portal/order_use_cases.py`
- make both HTML and API call the same functions

Expected:
- no portal order mutation logic duplicated between `wms/views_portal_orders.py` and `api/v1/ui_views.py`

**Step 4: Replace destructive contact-row rewrite with upsert semantics**

Implement:
- preserve `AssociationPortalContact` row identity when unchanged
- only create, update, disable, or reorder rows as needed
- keep notification-email synchronization behavior unchanged

Expected:
- no blanket `profile.portal_contacts.all().delete()`

**Step 5: Run focused regressions**

Run:

```bash
.venv/bin/python manage.py test \
  api.tests.tests_ui_endpoints \
  api.tests.tests_ui_e2e_workflows \
  wms.tests.portal.tests_portal_order_handlers \
  wms.tests.portal.tests_portal_order_inbound_flow \
  wms.tests.portal.tests_portal_shipment_parties \
  wms.tests.portal.tests_portal_role_review_gate \
  -v 2
```

Expected: PASS

**Step 6: Commit**

```bash
git add wms/application/portal/__init__.py \
  wms/application/portal/account_use_cases.py \
  wms/application/portal/order_use_cases.py \
  wms/application/portal/recipient_resolution.py \
  wms/views_portal_account.py \
  wms/views_portal_orders.py \
  api/v1/ui_views.py \
  api/tests/tests_ui_endpoints.py \
  api/tests/tests_ui_e2e_workflows.py \
  wms/tests/portal/tests_portal_order_handlers.py \
  wms/tests/portal/tests_portal_order_inbound_flow.py \
  wms/tests/portal/tests_portal_shipment_parties.py \
  wms/tests/portal/tests_portal_role_review_gate.py
git commit -m "refactor: share portal mutations across html and api"
```

**Rollback:** revert to the previous HTML/API adapters only; no schema change should be required in this PR.

### Task 2: PR2 Print And Pack Artifact Runtime Consolidation

**Owner:** shared print/pack delivery runtime

**Why second:** this is low-risk technical debt with immediate maintainability payoff and limited UX exposure.

**Files:**
- Create: `wms/print_artifact_delivery.py`
- Modify: `wms/admin.py`
- Modify: `wms/views_print_docs.py`
- Modify: `wms/views_print_labels.py`
- Test: `wms/tests/views/tests_views_print_docs.py`
- Test: `wms/tests/admin/tests_admin_extra.py`
- Test: `wms/tests/admin/tests_admin_print_pack.py`
- Test: `api/tests/tests_ui_endpoints.py`

**Current evidence:**
- duplicated `_artifact_pdf_response()` and XLSX fallback helpers in `wms/admin.py:85`
- same helpers duplicated again in `wms/views_print_docs.py:161`
- same helpers duplicated again in `wms/views_print_labels.py:105`

**Step 1: Write failing coverage for shared fallback behavior**

Run:

```bash
.venv/bin/python manage.py test \
  wms.tests.views.tests_views_print_docs \
  wms.tests.admin.tests_admin_extra \
  wms.tests.admin.tests_admin_print_pack \
  api.tests.tests_ui_endpoints \
  -v 2
```

Expected:
- add explicit tests for PDF response naming and XLSX fallback consistency

**Step 2: Extract shared delivery helpers**

Implement:
- move PDF response creation and XLSX fallback routing into `wms/print_artifact_delivery.py`
- keep views/admin as thin callers

**Step 3: Replace local clones**

Implement:
- import the shared helpers from admin, print docs, and print labels
- remove duplicated local functions

**Step 4: Run focused regressions**

Run:

```bash
.venv/bin/python manage.py test \
  wms.tests.views.tests_views_print_docs \
  wms.tests.admin.tests_admin_extra \
  wms.tests.admin.tests_admin_print_pack \
  api.tests.tests_ui_endpoints \
  api.tests.tests_ui_e2e_workflows \
  -v 2
```

Expected: PASS

**Step 5: Commit**

```bash
git add wms/print_artifact_delivery.py \
  wms/admin.py \
  wms/views_print_docs.py \
  wms/views_print_labels.py \
  wms/tests/views/tests_views_print_docs.py \
  wms/tests/admin/tests_admin_extra.py \
  wms/tests/admin/tests_admin_print_pack.py \
  api/tests/tests_ui_endpoints.py
git commit -m "refactor: share print artifact delivery helpers"
```

**Rollback:** restore the duplicated local helpers; the extraction should remain behavior-preserving.

### Task 3: PR3 Frontend Table Tools Extraction And `scan.js` Modularization

**Owner:** legacy frontend modularization without changing route structure

**Why third:** this reduces future refactor cost before any shell or UX changes land.

**Files:**
- Create: `wms/static/scan/modules/table-tools.js`
- Create: `wms/static/scan/modules/pack.js`
- Create: `wms/static/scan/modules/shipment-builder.js`
- Modify: `wms/static/scan/scan.js`
- Modify: `wms/static/portal/portal_tables.js`
- Modify: `templates/scan/base.html`
- Modify: `templates/portal/base.html`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Test: `wms/tests/core/tests_ui.py`

**Current evidence:**
- `scan.js` still carries pack flow, shipment builder, and table tools in `wms/static/scan/scan.js:1114`, `:1899`, and `:3604`
- table sorting/filtering is duplicated in `wms/static/scan/scan.js:3604` and `wms/static/portal/portal_tables.js:135`

**Step 1: Freeze current behavior with regression tests**

Run:

```bash
.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_portal_bootstrap_ui \
  -v 2
```

Optional browser checks:

```bash
RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui -v 2
```

Expected:
- baseline green before JS extraction

**Step 2: Extract shared table tools module**

Implement:
- move shared sort/filter logic to `wms/static/scan/modules/table-tools.js`
- load the same script from scan and portal
- keep grouped-row support for scan tables
- keep flat-row support for portal tables

**Step 3: Extract pack and shipment-builder modules**

Implement:
- move `setupPackLines()` into `wms/static/scan/modules/pack.js`
- move `setupShipmentBuilder()` into `wms/static/scan/modules/shipment-builder.js`
- keep `scan.js` only as stable bootstrap shell plus legacy leftovers not yet extracted

**Step 4: Replace inline/duplicate loaders**

Implement:
- stop using a separate `portal_tables.js` clone once the shared module is loaded
- keep `templates/scan/base.html` and `templates/portal/base.html` aligned on the stable module entrypoints

**Step 5: Run regressions**

Run:

```bash
.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_portal_bootstrap_ui \
  api.tests.tests_ui_e2e_workflows \
  -v 2
```

Optional browser checks:

```bash
RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui -v 2
```

Expected: PASS

**Step 6: Commit**

```bash
git add wms/static/scan/modules/table-tools.js \
  wms/static/scan/modules/pack.js \
  wms/static/scan/modules/shipment-builder.js \
  wms/static/scan/scan.js \
  wms/static/portal/portal_tables.js \
  templates/scan/base.html \
  templates/portal/base.html \
  wms/tests/views/tests_scan_bootstrap_ui.py \
  wms/tests/views/tests_portal_bootstrap_ui.py \
  wms/tests/core/tests_ui.py
git commit -m "refactor: extract shared legacy frontend modules"
```

**Rollback:** keep the new modules unused and re-enable the original local script entrypoints.

### Task 4: PR4 Shared Secondary Shell Cleanup For Portal, Benevole, Planning

**Owner:** shell-level UI contract cleanup

**Why fourth:** once the JS contract is cleaner, the shell extraction is mostly template work and shared-contract hardening.

**Files:**
- Create: `templates/includes/secondary_shell_masthead.html`
- Create: `templates/includes/secondary_shell_offcanvas.html`
- Modify: `templates/portal/base.html`
- Modify: `templates/benevole/base.html`
- Modify: `templates/planning/base.html`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Test: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Test: `wms/tests/views/tests_views_volunteer.py`
- Test: `wms/tests/views/tests_views_planning.py`

**Current evidence:**
- portal and benevole shells are nearly parallel in `templates/portal/base.html:23` and `templates/benevole/base.html:23`
- planning still uses a scan shell hybrid in `templates/planning/base.html:25`

**Step 1: Add regression checks for shell contracts**

Run:

```bash
.venv/bin/python manage.py test \
  wms.tests.views.tests_portal_bootstrap_ui \
  wms.tests.views.tests_views_volunteer \
  wms.tests.views.tests_views_planning \
  -v 2
```

Expected:
- baseline green
- add focused assertions for shared masthead/offcanvas markup where useful

**Step 2: Extract common secondary-shell includes**

Implement:
- centralize repeated masthead and mobile-nav markup
- parameterize label set and active links per surface

**Step 3: Realign planning on the secondary-shell contract**

Implement:
- keep planning as legacy Django
- stop treating it as a one-off scan shell clone where possible
- preserve current route behavior and `scan_sidebar_navigation` inclusion

**Step 4: Update shared contract docs**

Implement:
- update `docs/repo-reference/04-shared-contracts.md` with the stabilized shell contract

**Step 5: Run regressions**

Run:

```bash
.venv/bin/python manage.py test \
  wms.tests.views.tests_portal_bootstrap_ui \
  wms.tests.views.tests_views_volunteer \
  wms.tests.views.tests_views_planning \
  wms.tests.views.tests_scan_bootstrap_ui \
  -v 2
```

Expected: PASS

**Step 6: Commit**

```bash
git add templates/includes/secondary_shell_masthead.html \
  templates/includes/secondary_shell_offcanvas.html \
  templates/portal/base.html \
  templates/benevole/base.html \
  templates/planning/base.html \
  docs/repo-reference/04-shared-contracts.md \
  wms/tests/views/tests_portal_bootstrap_ui.py \
  wms/tests/views/tests_views_volunteer.py \
  wms/tests/views/tests_views_planning.py
git commit -m "refactor: share legacy secondary shell contract"
```

**Rollback:** restore the per-surface base templates and drop the includes.

### Task 5: PR5 Portal Order-Create UX Simplification And Browser Smokes

**Owner:** highest-friction operator UX flow on portal

**Why last:** this builds on the safer technical boundaries from PR1 to PR4.

**Files:**
- Modify: `wms/views_portal_orders.py`
- Modify: `templates/portal/order_create.html`
- Modify: `templates/portal/includes/order_create_routing_card.html`
- Modify: `templates/portal/includes/order_create_shipper_inbound_card.html`
- Modify: `templates/portal/includes/order_create_ready_cartons_card.html`
- Modify: `templates/portal/includes/order_create_ready_kits_card.html`
- Modify: `templates/portal/includes/order_create_unit_products_card.html`
- Create: `wms/tests/core/tests_ui_portal.py`
- Test: `wms/tests/portal/tests_portal_order_inbound_flow.py`
- Test: `wms/tests/portal/tests_portal_shipment_parties.py`
- Test: `wms/tests/views/tests_views_portal.py`

**Current evidence:**
- one screen currently mixes routing, self-packed inbound, pickup capture, ready cartons, ready kits, unit products, and submit in `templates/portal/order_create.html:9`
- the pickup subsection alone is already a full subflow in `templates/portal/includes/order_create_shipper_inbound_card.html:19`
- unit products still show explicitly fictive stock in `templates/portal/includes/order_create_unit_products_card.html:5`

**Target outcome:**
- Step 1: route recipient and destination
- Step 2: choose source of goods
- Step 3: only reveal the relevant fulfillment block
- Step 4: final review/submit

**Step 1: Lock current flow with server-side tests**

Run:

```bash
.venv/bin/python manage.py test \
  wms.tests.portal.tests_portal_order_inbound_flow \
  wms.tests.portal.tests_portal_shipment_parties \
  wms.tests.views.tests_views_portal \
  -v 2
```

Expected:
- baseline green
- add failing assertions for progressive disclosure and preserved validation state

**Step 2: Simplify the UI structure without changing the business contract**

Implement:
- convert the page into explicit sections/steps
- hide irrelevant blocks until prerequisite choices are made
- demote or hide fictive stock messaging from the main decision path

**Step 3: Add browser smoke coverage for non-scan legacy UI**

Implement:
- create `wms/tests/core/tests_ui_portal.py`
- cover at least one portal order-create path
- cover one recipient scope edit path
- cover one planning navigation smoke if the shell changed materially

Run:

```bash
RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui_portal -v 2
```

Expected: PASS when Playwright is available

**Step 4: Run full focused regressions**

Run:

```bash
.venv/bin/python manage.py test \
  wms.tests.portal.tests_portal_order_inbound_flow \
  wms.tests.portal.tests_portal_shipment_parties \
  wms.tests.views.tests_views_portal \
  api.tests.tests_ui_endpoints \
  api.tests.tests_ui_e2e_workflows \
  -v 2
```

Expected: PASS

**Step 5: Commit**

```bash
git add wms/views_portal_orders.py \
  templates/portal/order_create.html \
  templates/portal/includes/order_create_routing_card.html \
  templates/portal/includes/order_create_shipper_inbound_card.html \
  templates/portal/includes/order_create_ready_cartons_card.html \
  templates/portal/includes/order_create_ready_kits_card.html \
  templates/portal/includes/order_create_unit_products_card.html \
  wms/tests/core/tests_ui_portal.py \
  wms/tests/portal/tests_portal_order_inbound_flow.py \
  wms/tests/portal/tests_portal_shipment_parties.py \
  wms/tests/views/tests_views_portal.py
git commit -m "refactor: simplify portal order create flow"
```

**Rollback:** revert the template/layout layer only and keep the prior server-side contract.

## Closure Checklist

- `make check`
- `make lint`
- `make typecheck`
- `make bandit`
- `.venv/bin/python manage.py makemigrations --check --dry-run`
- `make test-smoke`
- relevant focused suites from each PR all green
- `docs/repo-reference/04-shared-contracts.md` updated if shell/UI shared contracts changed
- no changes in paused translation or Next/React scope

## Residual Risks

- `check --deploy` will still depend on local env parity; treat runtime configuration separately from this refactor track.
- Optional Playwright coverage may remain skipped on machines without the browser dependency; keep at least one non-optional server-side regression per changed flow.
- Portal recipient resolution is business-sensitive; do not merge PR1 without both HTML and API path coverage.
