# Contacts Validations Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a dedicated `Contacts` navigation group and move validation flows to a `hub -> queue -> dossier` structure without changing the underlying business rules.

**Architecture:** Keep legacy routes and business services stable wherever possible. Introduce a new validations hub and recipient-validation queue/detail pages, then reduce the contacts cockpit back to directory and shipment-role management.

**Tech Stack:** Django views, Django templates, Django URL routing, Bootstrap-based legacy Scan UI, Django test runner

---

### Task 1: Document the approved UX

**Files:**
- Create: `docs/plans/2026-04-12-contacts-validations-design.md`
- Create: `docs/plans/2026-04-12-contacts-validations-implementation-plan.md`

**Step 1: Write the approved design doc**

- Capture the approved navigation split:
  - `Contacts > Répertoire`
  - `Contacts > Rôles expédition`
  - `Contacts > Validations`
- Record the design choice to use cards and tables, not tabs.

**Step 2: Write the implementation plan**

- Break the work into navigation, queue screens, dossier screens, tests, and docs.

**Step 3: Verify docs exist**

Run: `ls docs/plans/2026-04-12-contacts-validations-*.md`
Expected: both files exist

### Task 2: Write failing navigation tests first

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_scan_admin.py`

**Step 1: Write a failing sidebar test**

- Add a test asserting the Scan sidebar exposes a dedicated `Contacts` group with:
  - `Répertoire`
  - `Rôles expédition`
  - `Validations`

**Step 2: Write a failing admin-contacts test**

- Add a test asserting pending recipient validations are no longer rendered on `scan_admin_contacts`.

**Step 3: Run only the new tests**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_admin -v 1`
Expected: FAIL on missing navigation / old contacts rendering

### Task 3: Implement the sidebar IA change

**Files:**
- Modify: `templates/scan/includes/scan_sidebar_navigation.html`

**Step 1: Add the `Contacts` group**

- Create a new collapsible sidebar group.
- Keep `Gestion` for planning and billing.
- Move validation visibility into `Contacts`.

**Step 2: Keep links stable where possible**

- `Répertoire` should point to `scan:scan_admin_contacts`.
- `Rôles expédition` should point to the same cockpit surface or a dedicated route if a lightweight split is required.
- `Validations` should point to the new hub.

**Step 3: Re-run navigation tests**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 1`
Expected: PASS for the new sidebar assertions

### Task 4: Write failing tests for the validations hub and recipient queue

**Files:**
- Modify: `wms/tests/views/tests_views_scan_account_validations.py`
- Create or modify: `wms/tests/views/tests_views_scan_contact_validations.py`

**Step 1: Add a failing test for the validations hub**

- Assert the page renders the two cards:
  - `Validation expéditeurs`
  - `Validation destinataires`

**Step 2: Add a failing test for the recipient queue**

- Assert pending recipient validations appear on their own page.
- Assert the contacts cockpit no longer shows them.

**Step 3: Add a failing test for the recipient dossier**

- Assert the page renders identity/context plus ASF decision actions.

**Step 4: Run only the new validation tests**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_account_validations wms.tests.views.tests_views_scan_contact_validations -v 1`
Expected: FAIL on missing routes/templates/context

### Task 5: Implement the validations hub and recipient queue/detail

**Files:**
- Modify: `wms/scan_urls.py`
- Modify: `wms/views.py`
- Modify: `wms/views_scan_account_validations.py`
- Modify: `wms/views_scan_admin.py`
- Create: `templates/scan/contact_validations_hub.html`
- Create: `templates/scan/recipient_validation_list.html`
- Create: `templates/scan/recipient_validation_detail.html`

**Step 1: Add routes**

- Add a hub route under Scan.
- Add recipient queue/detail routes.

**Step 2: Build minimal views**

- Reuse current account-validation queryset/count logic where helpful.
- Reuse current recipient-validation data already exposed on the contacts cockpit.

**Step 3: Build templates with established Scan patterns**

- Header card
- short explanatory text
- count badge
- queue table
- two-column dossier layout

**Step 4: Re-run the validation tests**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_account_validations wms.tests.views.tests_views_scan_contact_validations -v 1`
Expected: PASS

### Task 6: Reduce the contacts cockpit to management scope

**Files:**
- Modify: `templates/scan/admin_contacts.html`
- Modify: `wms/views_scan_admin.py`
- Modify: `wms/tests/views/tests_views_scan_admin.py`
- Modify: `wms/tests/views/tests_views_scan_admin_shipment_parties.py`

**Step 1: Remove the pending-recipient-validations alert/table from the contacts cockpit**

- Keep the directory, filters, and shipment-role management intact.

**Step 2: Add links out to the new validations area if useful**

- Keep the cockpit focused on manual correction and role management.

**Step 3: Re-run cockpit tests**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_scan_admin_shipment_parties -v 1`
Expected: PASS

### Task 7: Update shared docs and impacted contracts

**Files:**
- Modify: `docs/repo-reference/03-impact-map.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Modify any affected plan/doc references if tests reveal a named contract change

**Step 1: Re-check whether the navigation and validation entry points are documented shared contracts**

- Update repo-reference only if implementation changes the expected navigation/entry-point contract.

**Step 2: Add concise documentation updates**

- Keep them limited to the changed UI contract.

**Step 3: Diff-check docs**

Run: `git diff -- docs/repo-reference docs/plans`
Expected: only the intended navigation/validation notes

### Task 8: Final verification

**Files:**
- Verify the full touched set

**Step 1: Run the targeted full verification**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_account_validations wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_scan_admin_shipment_parties wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_contact_validations -v 1`
Expected: PASS

**Step 2: Run diff sanity**

Run: `git diff --check`
Expected: no whitespace or patch-format issues

**Step 3: Review impact against repo-reference**

- Confirm no further shared routes, smoke rules, or docs must be updated.

**Step 4: Commit**

```bash
git add docs/plans docs/repo-reference templates/scan wms/scan_urls.py wms/views.py wms/views_scan_account_validations.py wms/views_scan_admin.py wms/tests/views
git commit -m "feat: reorganize contacts validations workflow"
```
