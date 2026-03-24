# Legacy UI Stabilization Phase Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Run a short, governance-driven stabilization phase for legacy UI waves 4A to 6 so review feedback can be handled without reopening the refactor or expanding the shared library prematurely.

**Architecture:** Treat stabilization as a gate plus a short post-merge window. Every accepted change must be classified against the stabilization design, reproduced with the smallest relevant failing regression test or verifier, fixed with the smallest local patch, and revalidated with the exact suites for the touched surface. No new wave, no `UI Lab` promotion, and no new shared component is allowed during this plan unless a separate design explicitly reopens that scope.

**Tech Stack:** GitHub PR review flow, Django templates, Django TestCase, legacy scan/portal Bootstrap UI tests, governance docs

---

### Task 1: Triage PR feedback against the stabilization rules

**Files:**
- Review: `docs/plans/2026-03-24-legacy-ui-stabilization-design.md`
- Review: `docs/checklists/legacy-ui-component-governance.md`
- Review: `docs/plans/2026-03-24-legacy-ui-next-waves-design.md`
- Review: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Review: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Review PR: `https://github.com/misterkoko92/asf-wms/pull/82`

**Step 1: Pull the latest PR review state**

Run: `gh pr view 82 --comments --json comments,reviews,files`

Expected: the current review corpus for the stabilization branch.

**Step 2: Classify every finding**

For each review item, assign exactly one class:
- `Blocker before merge`
- `Allowed stabilization fix`
- `Defer after merge`
- `Reject as overshoot`

Use `docs/plans/2026-03-24-legacy-ui-stabilization-design.md` as the decision source of truth.

**Step 3: Record the execution target**

For every accepted item, record:
- touched screen or test suite,
- exact file path(s),
- smallest test command that should fail first,
- broader verification command that must pass after the fix.

**Step 4: Stop if no accepted item exists**

If no finding is classified as `Blocker before merge` or `Allowed stabilization fix`, move directly to Task 4.

**Step 5: Commit**

No commit in this task unless the stabilization docs themselves need clarification.

### Task 2: Apply accepted scan-side stabilization fixes with TDD

**Files:**
- Modify if needed: `templates/scan/imports.html`
- Modify if needed: `templates/scan/admin_contacts.html`
- Modify if needed: `templates/scan/receive_pallet.html`
- Modify if needed: `templates/scan/receive.html`
- Modify if needed: `templates/scan/receive_association.html`
- Modify if needed: `templates/scan/includes/imports_intro_card.html`
- Modify if needed: `templates/scan/includes/imports_categories_card.html`
- Modify if needed: `templates/scan/includes/imports_contacts_card.html`
- Modify if needed: `templates/scan/includes/imports_locations_card.html`
- Modify if needed: `templates/scan/includes/imports_product_match_review.html`
- Modify if needed: `templates/scan/includes/imports_products_card.html`
- Modify if needed: `templates/scan/includes/imports_users_card.html`
- Modify if needed: `templates/scan/includes/imports_warehouses_card.html`
- Modify if needed: `templates/scan/includes/admin_contacts_intro_card.html`
- Modify if needed: `templates/scan/includes/admin_contacts_filters_card.html`
- Modify if needed: `templates/scan/includes/admin_contacts_shipment_cockpit.html`
- Modify if needed: `templates/scan/includes/admin_contacts_directory_card.html`
- Modify if needed: `templates/scan/includes/admin_contacts_correspondents_card.html`
- Modify if needed: `templates/scan/includes/receive_select_card.html`
- Modify if needed: `templates/scan/includes/receive_create_card.html`
- Modify if needed: `templates/scan/includes/receive_active_summary_card.html`
- Modify if needed: `templates/scan/includes/receive_add_line_card.html`
- Modify if needed: `templates/scan/includes/receive_lines_card.html`
- Modify if needed: `templates/scan/includes/receive_empty_card.html`
- Modify if needed: `templates/scan/includes/receive_association_create_card.html`
- Modify if needed: `templates/scan/includes/receive_association_allocations_card.html`
- Modify if needed: `templates/scan/includes/receive_pallet_create_card.html`
- Modify if needed: `templates/scan/includes/receive_pallet_listing_upload_card.html`
- Modify if needed: `templates/scan/includes/receive_pallet_mapping_card.html`
- Modify if needed: `templates/scan/includes/receive_pallet_review_card.html`
- Modify if needed: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify if needed: `wms/tests/views/tests_views_scan_admin.py`
- Modify if needed: `wms/tests/views/tests_views_scan_admin_contacts_crud.py`
- Modify if needed: `wms/tests/views/tests_views_scan_receipts.py`
- Modify if needed: `wms/tests/scan/tests_scan_import_handlers.py`
- Modify if needed: `wms/tests/scan/tests_admin_contacts_crud.py`
- Modify if needed: `wms/tests/scan/tests_scan_admin_contacts_cockpit_helpers.py`
- Modify if needed: `wms/tests/views/tests_views.py`

**Step 1: Write the failing regression test first**

Pick the smallest suite that proves the reported issue:
- import structure/contract issue: `wms/tests/views/tests_scan_bootstrap_ui.py`
- import workflow issue: `wms/tests/scan/tests_scan_import_handlers.py`
- admin contacts structure/contract issue: `wms/tests/views/tests_scan_bootstrap_ui.py`
- admin contacts behavior issue: `wms/tests/views/tests_views_scan_admin.py`, `wms/tests/views/tests_views_scan_admin_contacts_crud.py`, or `wms/tests/scan/tests_admin_contacts_crud.py`
- receiving structure/contract issue: `wms/tests/views/tests_scan_bootstrap_ui.py`
- receiving behavior issue: `wms/tests/views/tests_views_scan_receipts.py` or `wms/tests/views/tests_views.py`

**Step 2: Run the targeted test to verify it fails**

Use the exact narrow command that matches the accepted finding, then confirm the failure is caused by the issue under review.

Examples:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 1
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.scan.tests_scan_import_handlers -v 1
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_receipts -v 1
```

Expected: FAIL only on the accepted regression.

**Step 3: Write the minimal local fix**

Rules:
- stay inside the already-touched scan screens and includes,
- do not introduce a new shared component,
- do not update `scan/ui-lab/`,
- do not broaden the change beyond the accepted finding.

**Step 4: Re-run the targeted test and the broader scan verification**

Run the smallest correct targeted suite first, then:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_receipts wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_scan_admin_contacts_crud wms.tests.scan.tests_scan_import_handlers wms.tests.scan.tests_admin_contacts_crud wms.tests.scan.tests_scan_admin_contacts_cockpit_helpers wms.tests.views.tests_views -v 1
```

Expected: PASS.

**Step 5: Commit**

```bash
git add <touched scan files>
git commit -m "fix: stabilize legacy scan ui review feedback"
```

### Task 3: Apply accepted portal-side stabilization fixes with TDD

**Files:**
- Modify if needed: `templates/portal/order_create.html`
- Modify if needed: `templates/portal/account.html`
- Modify if needed: `templates/portal/includes/order_create_intro_card.html`
- Modify if needed: `templates/portal/includes/order_create_unit_products_card.html`
- Modify if needed: `templates/portal/includes/order_create_ready_cartons_card.html`
- Modify if needed: `templates/portal/includes/order_create_ready_kits_card.html`
- Modify if needed: `templates/portal/includes/order_create_routing_card.html`
- Modify if needed: `templates/portal/includes/account_intro_card.html`
- Modify if needed: `templates/portal/includes/account_profile_card.html`
- Modify if needed: `templates/portal/includes/account_documents_card.html`
- Modify if needed: `templates/portal/includes/account_billing_card.html`
- Modify if needed: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Modify if needed: `wms/tests/views/tests_views_portal.py`

**Step 1: Write the failing regression test first**

Use:
- `wms/tests/views/tests_portal_bootstrap_ui.py` for section, button, and contract issues,
- `wms/tests/views/tests_views_portal.py` for workflow or context regressions.

**Step 2: Run the targeted test to verify it fails**

Run the exact narrow portal test or module first, then confirm the failure matches the accepted review item.

Examples:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui -v 1
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_portal -v 1
```

Expected: FAIL only on the accepted regression.

**Step 3: Write the minimal local fix**

Rules:
- stay inside the touched portal screens and includes,
- keep the current legacy Bootstrap contracts,
- do not generalize a portal pattern into a shared primitive during stabilization.

**Step 4: Re-run the targeted test and the broader portal verification**

Run the smallest correct targeted suite first, then:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal -v 1
```

Expected: PASS.

**Step 5: Commit**

```bash
git add <touched portal files>
git commit -m "fix: stabilize legacy portal ui review feedback"
```

### Task 4: Re-run the full wave verification and update the PR state

**Files:**
- Review: `docs/plans/2026-03-24-legacy-ui-stabilization-design.md`
- Update if needed: PR `https://github.com/misterkoko92/asf-wms/pull/82`

**Step 1: Run the full scan-side verification**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_receipts wms.tests.views.tests_views -v 1
```

Expected: PASS.

**Step 2: Run the full portal/import/admin verification**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_scan_admin_contacts_crud wms.tests.scan.tests_scan_import_handlers wms.tests.scan.tests_admin_contacts_crud wms.tests.scan.tests_scan_admin_contacts_cockpit_helpers -v 1
```

Expected: PASS.

**Step 3: Check Git hygiene**

Run:

```bash
git diff --check
git status --short --branch
```

Expected:
- no whitespace or patch hygiene issues,
- only intentional stabilization changes remain.

**Step 4: Update PR resolution**

Resolve review threads or leave an explicit defer/reject note for any non-blocking suggestion.

**Step 5: Commit**

No local commit unless additional doc clarification was required.

### Task 5: Close the stabilization window without opening a new wave

**Files:**
- Review: `docs/plans/2026-03-24-legacy-ui-stabilization-design.md`
- Review: `docs/checklists/legacy-ui-component-governance.md`
- Review: `docs/plans/2026-03-24-legacy-ui-next-waves-design.md`

**Step 1: Gather the final stabilization outcome**

Collect:
- blockers fixed before merge,
- accepted micro-fixes,
- explicitly deferred ideas,
- suggestions rejected as overshoot.

**Step 2: Decide whether any new sequence is justified**

A new design may be opened only if fresh evidence exists:
- a repeated cross-screen pattern,
- a genuine missing stable contract,
- or a new high-value monolith outside the current waves.

If those conditions are absent, explicitly stop and close the stabilization phase.

**Step 3: Record the decision**

Update the PR summary, merge notes, or follow-up planning docs with one of:
- `No new wave justified`
- `Future sequence justified by new evidence`

**Step 4: Verify there is no silent scope creep**

Check that no stabilization patch introduced:
- a new shared component,
- a `UI Lab` promotion,
- a refactor on untouched screens,
- a translation or Next scope leak.

**Step 5: Commit**

If a final doc clarification is needed:

```bash
git add docs/plans/2026-03-24-legacy-ui-stabilization-design.md docs/plans/2026-03-24-legacy-ui-stabilization-implementation-plan.md
git commit -m "docs: close legacy ui stabilization phase"
```
