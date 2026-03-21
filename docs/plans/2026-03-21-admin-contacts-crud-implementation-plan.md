# Admin Contacts CRUD Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add destination/contact creation plus contact edit, deactivate, and merge flows directly to the legacy admin contacts page with duplicate review and shipment-safe relation updates.

**Architecture:** Keep `scan_admin_contacts` as a thin page controller. Split destination workflows, contact workflows, duplicate detection, and merge logic into separate modules so the admin page does not become another monolith. Reuse canonical `Contact`, `ContactCapability`, `Destination`, and `Shipment*` tables only.

**Tech Stack:** Django views/templates/forms, existing scan Bootstrap UI, Django ORM transactions, Django test suite.

---

### Task 1: Write failing view tests for the new admin page structure

**Files:**
- Modify: `wms/tests/views/tests_views_scan_admin.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing tests**

- Assert `scan/admin/contacts/` renders `Creation de destination` before `Recherche et filtres`
- Assert `scan/admin/contacts/` renders `Creation de contact` before `Recherche et filtres`
- Assert both cards are `<details>` blocks closed by default
- Assert `Repertoire des contacts` exposes an `Actions` column with `Voir les choix`

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_admin \
  wms.tests.views.tests_scan_bootstrap_ui -v 2
```

**Step 3: Write minimal implementation**

- Update the admin contacts template structure only

**Step 4: Run test to verify it passes**

Run the same command and expect green.

### Task 2: Write failing form tests for destination and contact CRUD

**Files:**
- Create: `wms/tests/forms/tests_forms_admin_contacts_destination.py`
- Create: `wms/tests/forms/tests_forms_admin_contacts_contact.py`

**Step 1: Write the failing tests**

- Destination form requires `city`, `iata_code`, and `country`
- Contact form toggles required fields by requested business type
- `Benevole` requires a person
- `Destinataire` requires destination and at least one allowed shipper
- Duplicate-resolution forms require an explicit decision when suggestions are present

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.forms.tests_forms_admin_contacts_destination \
  wms.tests.forms.tests_forms_admin_contacts_contact -v 2
```

**Step 3: Write minimal implementation**

- Add dedicated form modules:
  - `wms/forms_admin_contacts_destination.py`
  - `wms/forms_admin_contacts_contact.py`

**Step 4: Run test to verify it passes**

Run the same command and expect green.

### Task 3: Write failing duplicate-detection tests before implementing matching helpers

**Files:**
- Create: `wms/tests/scan/tests_admin_contacts_duplicate_detection.py`

**Step 1: Write the failing tests**

- Exact destination duplicate by `iata_code`
- Exact destination duplicate by normalized `city + country`
- Fuzzy destination suggestion with case/accent tolerance
- Exact contact duplicate by `asf_id`
- Fuzzy organization suggestion by normalized structure name
- Fuzzy person suggestion by normalized identity plus organization context
- Edit mode excludes the currently edited record from suggestions

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.scan.tests_admin_contacts_duplicate_detection -v 2
```

**Step 3: Write minimal implementation**

- Create `wms/admin_contacts_duplicate_detection.py`
- Move reusable normalization and fuzzy-match helpers there instead of growing `scan_admin_contacts_cockpit.py`

**Step 4: Run test to verify it passes**

Run the same command and expect green.

### Task 4: Write failing destination workflow tests

**Files:**
- Create: `wms/tests/scan/tests_admin_contacts_destination_service.py`

**Step 1: Write the failing tests**

- Create a new destination with correspondent
- Replace an existing destination after duplicate review
- Merge into an existing destination without overwriting populated fields
- Reject `Dupliquer` when an exact unique conflict still exists

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.scan.tests_admin_contacts_destination_service -v 2
```

**Step 3: Write minimal implementation**

- Create `wms/admin_contacts_destination_service.py`
- Keep all destination create/edit/replace/merge behavior there

**Step 4: Run test to verify it passes**

Run the same command and expect green.

### Task 5: Write failing contact workflow tests

**Files:**
- Create: `wms/tests/scan/tests_admin_contacts_contact_service.py`

**Step 1: Write the failing tests**

- Create donor, transporter, and volunteer contacts with capabilities
- Create shipper with organization + default contact + scope
- Create recipient with organization + destination + referent + allowed shipper links
- Create correspondent and make it the active stopover correspondent
- Replace an existing contact on duplicate review
- Merge into an existing contact by filling missing fields only
- Deactivate a contact instead of hard deleting it

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.scan.tests_admin_contacts_contact_service -v 2
```

**Step 3: Write minimal implementation**

- Create `wms/admin_contacts_contact_service.py`
- Keep type-specific orchestration in small helpers per business type
- Do not place this logic in the view

**Step 4: Run test to verify it passes**

Run the same command and expect green.

### Task 6: Write failing merge-service tests for contact reassignment

**Files:**
- Create: `wms/tests/scan/tests_admin_contacts_merge_service.py`

**Step 1: Write the failing tests**

- Merge two organization contacts and preserve shipment shipper references
- Merge two person contacts and preserve recipient-contact / authorized-contact wiring
- Merge capabilities and addresses without duplicating identical records
- Reject incompatible merges across person vs organization

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.scan.tests_admin_contacts_merge_service -v 2
```

**Step 3: Write minimal implementation**

- Create `wms/admin_contacts_merge_service.py`
- Reassign canonical `Shipment*` relations transactionally
- Deactivate the source contact at the end

**Step 4: Run test to verify it passes**

Run the same command and expect green.

### Task 7: Wire the admin page controller without growing a monolith

**Files:**
- Modify: `wms/views_scan_admin.py`
- Modify: `templates/scan/admin_contacts.html`

**Step 1: Add failing integration tests**

- POST create destination succeeds and redirects back with success message
- POST create contact succeeds and redirects back with success message
- POST duplicate-triggering forms reopen the correct card with review choices
- POST edit/deactivate/merge from the directory table routes to the correct workflow

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_admin -v 2
```

**Step 3: Write minimal implementation**

- Keep `scan_admin_contacts` as a dispatcher only
- Parse POST action
- Delegate to destination/contact/merge services
- Rebuild template context
- Preserve filters and edit state through redirects

**Step 4: Run test to verify it passes**

Run the same command and expect green.

### Task 8: Add progressive UI behavior for dynamic forms and inline actions

**Files:**
- Modify: `templates/scan/admin_contacts.html`
- Modify: `wms/static/scan/scan.js`
- Modify: `wms/static/scan/scan.css`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing tests**

- Contact-type selector reveals only the relevant fields
- Duplicate review selector appears only when the server provides candidate matches
- Inline `Voir les choix` actions reveal the correct form controls
- New cards keep the page consistent with existing scan Bootstrap styling

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui -v 2
```

**Step 3: Write minimal implementation**

- Add only progressive UI behavior
- Keep validation and duplicate decisions server authoritative

**Step 4: Run test to verify it passes**

Run the same command and expect green.

### Task 9: Run focused regression and verify no monolith creep

**Files:**
- Review:
  - `wms/views_scan_admin.py`
  - `wms/forms_admin_contacts_destination.py`
  - `wms/forms_admin_contacts_contact.py`
  - `wms/admin_contacts_duplicate_detection.py`
  - `wms/admin_contacts_destination_service.py`
  - `wms/admin_contacts_contact_service.py`
  - `wms/admin_contacts_merge_service.py`
  - `templates/scan/admin_contacts.html`
  - `wms/static/scan/scan.js`
  - `wms/static/scan/scan.css`

**Step 1: Run focused regression suite**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.forms.tests_forms_admin_contacts_destination \
  wms.tests.forms.tests_forms_admin_contacts_contact \
  wms.tests.scan.tests_admin_contacts_duplicate_detection \
  wms.tests.scan.tests_admin_contacts_destination_service \
  wms.tests.scan.tests_admin_contacts_contact_service \
  wms.tests.scan.tests_admin_contacts_merge_service \
  wms.tests.views.tests_views_scan_admin \
  wms.tests.views.tests_scan_bootstrap_ui -v 2
```

**Step 2: Run broader admin/shipment safety suite**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_admin_shipment_parties \
  wms.tests.shipment.tests_shipment_party_registry \
  wms.tests.shipment.tests_shipment_party_models \
  wms.tests.shipment.tests_shipment_helpers -v 2
```

**Step 3: Review module sizes before commit**

- Confirm `wms/views_scan_admin.py` remains orchestration-only
- Confirm duplicate logic is not copied across services
- Confirm contact and destination workflows stay in separate modules

**Step 4: Commit**

```bash
git add docs/plans \
  wms/forms_admin_contacts_destination.py \
  wms/forms_admin_contacts_contact.py \
  wms/admin_contacts_duplicate_detection.py \
  wms/admin_contacts_destination_service.py \
  wms/admin_contacts_contact_service.py \
  wms/admin_contacts_merge_service.py \
  wms/views_scan_admin.py \
  templates/scan/admin_contacts.html \
  wms/static/scan/scan.js \
  wms/static/scan/scan.css \
  wms/tests/forms/tests_forms_admin_contacts_destination.py \
  wms/tests/forms/tests_forms_admin_contacts_contact.py \
  wms/tests/scan/tests_admin_contacts_duplicate_detection.py \
  wms/tests/scan/tests_admin_contacts_destination_service.py \
  wms/tests/scan/tests_admin_contacts_contact_service.py \
  wms/tests/scan/tests_admin_contacts_merge_service.py \
  wms/tests/views/tests_views_scan_admin.py \
  wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat(scan): add admin contacts CRUD workflows"
```
