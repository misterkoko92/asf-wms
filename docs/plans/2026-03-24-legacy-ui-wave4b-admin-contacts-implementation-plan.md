# Legacy UI Wave 4B Admin Contacts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Simplify the legacy scan admin contacts page by decomposing the remaining large inline sections into workflow-local partials while preserving current CRUD actions, cockpit behavior, inline directory actions, and shipment recipient scripts.

**Architecture:** Keep `templates/scan/admin_contacts.html` as the route entry point and asset host. Extract only workflow-local sections under `templates/scan/includes/`, preserve the existing form includes and JS hooks, and lock the resulting section boundaries with targeted Django view tests. This wave stays `En convergence`: no new shared `wms_ui` abstraction and no promotion to `UI Lab`.

**Tech Stack:** Django templates, Django TestCase, legacy scan admin views, Bootstrap bridge classes, existing `scan.js` behaviors, inline shipment-recipient sync script

---

### Task 1: Lock the wave 4B admin contacts section contracts with failing tests

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `templates/scan/admin_contacts.html`
- Verify: `wms/tests/views/tests_views_scan_admin.py`

**Step 1: Write the failing test**

Add a UI-structure test that requires explicit section markers for the page shell:

```python
def test_scan_admin_contacts_breaks_into_named_workflow_sections(self):
    self.client.force_login(self.superuser)

    response = self.client.get(reverse("scan:scan_admin_contacts"))

    self.assertContains(response, 'id="scan-admin-contacts-intro"')
    self.assertContains(response, 'id="scan-admin-contacts-create-destination"')
    self.assertContains(response, 'id="scan-admin-contacts-create-contact"')
    self.assertContains(response, 'id="scan-admin-contacts-filters"')
    self.assertContains(response, 'id="scan-admin-contacts-cockpit"')
    self.assertContains(response, 'id="scan-admin-contacts-directory-card"')
    self.assertContains(response, 'id="scan-admin-contacts-correspondents-card"')
```

Add a second assertion set that proves the split keeps the current behaviors and wrappers:

```python
self.assertContains(response, "ui-comp-card", count=7)
self.assertContains(response, 'data-admin-contacts-crud="1"')
self.assertContains(response, 'data-table-tools="1"', count=6)
self.assertContains(response, 'id="scan-admin-contact-action-panel"')
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_admin_contacts_breaks_into_named_workflow_sections -v 2`

Expected: FAIL on the new section IDs because the page still renders most cards inline without named workflow boundaries.

**Step 3: Write minimal implementation**

No production implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Re-run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_admin_contacts_breaks_into_named_workflow_sections -v 2`

Expected: FAIL only on the newly introduced section markers.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "test: lock legacy ui wave 4b admin contacts contracts"
```

### Task 2: Extract the intro and filter cards into explicit local includes

**Files:**
- Modify: `templates/scan/admin_contacts.html`
- Create: `templates/scan/includes/admin_contacts_intro_card.html`
- Create: `templates/scan/includes/admin_contacts_filters_card.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Extend the red test to require two explicit top-level cards:

```python
self.assertContains(response, 'id="scan-admin-contacts-intro"')
self.assertContains(response, 'id="scan-admin-contacts-filters"')
```

Keep the existing search and filter expectations intact:

```python
self.assertContains(response, 'id="scan-admin-contacts-q"')
self.assertContains(response, 'name="contact_type"')
self.assertContains(response, 'name="destination_id"')
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_admin_contacts_breaks_into_named_workflow_sections -v 2`

Expected: FAIL because the intro and filters wrappers do not yet exist.

**Step 3: Write minimal implementation**

Move the summary card and the search/filter card into workflow-local includes:

```django
{% include "scan/includes/admin_contacts_intro_card.html" %}
{% include "scan/includes/admin_contacts_filters_card.html" %}
```

Inside the new includes:
- keep `ui-comp-card`, `ui-comp-title`, and `ui-comp-form`,
- preserve `scan-admin-contacts-q`, `contact_type`, and `destination_id`,
- keep the reset link and filter submit button unchanged.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_admin_contacts_breaks_into_named_workflow_sections -v 2`

Expected: PASS for the intro and filters section markers.

**Step 5: Commit**

```bash
git add templates/scan/admin_contacts.html templates/scan/includes/admin_contacts_intro_card.html templates/scan/includes/admin_contacts_filters_card.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "refactor: extract admin contacts intro and filters cards"
```

### Task 3: Extract the shipment cockpit into a workflow-local include without changing actions

**Files:**
- Modify: `templates/scan/admin_contacts.html`
- Create: `templates/scan/includes/admin_contacts_shipment_cockpit.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `wms/tests/views/tests_views_scan_admin.py`

**Step 1: Write the failing test**

Add assertions that the cockpit becomes a named section and keeps its shipment controls:

```python
self.assertContains(response, 'id="scan-admin-contacts-cockpit"')
self.assertContains(response, 'name="action" value="set_default_authorized_recipient_contact"')
self.assertContains(response, 'name="action" value="set_stopover_correspondent_recipient_organization"')
self.assertContains(response, 'name="action" value="merge_shipment_recipient_organizations"')
self.assertContains(response, 'id="scan-shipment-link-id"')
self.assertContains(response, 'id="scan-merge-target-recipient-organization"')
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_admin_contacts_breaks_into_named_workflow_sections -v 2`

Expected: FAIL because the named cockpit wrapper does not exist yet.

**Step 3: Write minimal implementation**

Move the whole “Pilotage contacts expédition” block into one workflow-local include:

```django
{% include "scan/includes/admin_contacts_shipment_cockpit.html" %}
```

Inside the include:
- keep the four tables and their `data-table-tools="1"` markers,
- preserve all hidden filter inputs and POST action names,
- preserve `data-link-id` and `data-destination-id` attributes,
- do not move the inline shipment sync script out of `admin_contacts.html`.

**Step 4: Run test to verify it passes**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_admin_contacts_breaks_into_named_workflow_sections -v 2`

Expected: PASS for the cockpit section marker and action-contract assertions.

**Step 5: Commit**

```bash
git add templates/scan/admin_contacts.html templates/scan/includes/admin_contacts_shipment_cockpit.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "refactor: extract admin contacts shipment cockpit"
```

### Task 4: Extract the directory and correspondents cards, then run final wave 4B verification

**Files:**
- Modify: `templates/scan/admin_contacts.html`
- Create: `templates/scan/includes/admin_contacts_directory_card.html`
- Create: `templates/scan/includes/admin_contacts_correspondents_card.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify: `wms/tests/views/tests_views_scan_admin.py`

**Step 1: Write the failing test**

Add assertions that the remaining heavy tables are isolated and still keep the inline-action contract:

```python
self.assertContains(response, 'id="scan-admin-contacts-directory-card"')
self.assertContains(response, 'id="scan-admin-contacts-correspondents-card"')
self.assertContains(response, 'data-contact-action-select="1"')
self.assertContains(response, reverse("admin:contacts_contact_changelist"))
self.assertContains(response, reverse("admin:wms_destination_changelist"))
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_admin_contacts_breaks_into_named_workflow_sections -v 2`

Expected: FAIL because the dedicated directory and correspondents wrappers do not yet exist.

**Step 3: Write minimal implementation**

Move the remaining cards into local includes:

```django
{% include "scan/includes/admin_contacts_directory_card.html" %}
{% include "scan/includes/admin_contacts_correspondents_card.html" %}
```

Inside the new includes:
- keep the directory action select and the existing `admin_contacts_directory_action_panel.html`,
- preserve the hidden fallback admin links block,
- keep the correspondents table unchanged apart from the section wrapper,
- preserve all current table headers and empty states.

**Step 4: Run test to verify it passes**

Run the targeted suites:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_views_scan_admin \
  -v 2
```

Expected: PASS for the new structure test and the existing admin contacts behavior tests.

Run the broader admin contacts regressions:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.scan.tests_admin_contacts_contact_service \
  wms.tests.scan.tests_admin_contacts_destination_service \
  wms.tests.scan.tests_admin_contacts_crud \
  wms.tests.scan.tests_admin_contacts_merge_service \
  wms.tests.scan.tests_scan_admin_contacts_cockpit_helpers \
  wms.tests.scan.tests_admin_contacts_duplicate_detection \
  -v 2
git diff --check
```

Expected: PASS and no diff-check output.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-24-legacy-ui-wave4b-admin-contacts-implementation-plan.md templates/scan/admin_contacts.html templates/scan/includes/admin_contacts_intro_card.html templates/scan/includes/admin_contacts_filters_card.html templates/scan/includes/admin_contacts_shipment_cockpit.html templates/scan/includes/admin_contacts_directory_card.html templates/scan/includes/admin_contacts_correspondents_card.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "refactor: deliver legacy ui wave 4b admin contacts split"
```
