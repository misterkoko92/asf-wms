# Contact Capability Categories Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** add persisted `Partenaire` and `Autre` contact categories with the same baseline behavior as `Transporteur`, and make manual creation easier to discover in scan.

**Architecture:** extend the existing `ContactCapability` enum and reuse the current scan admin contact CRUD pipeline. Keep the change local to legacy Django contact management: capability model, scan form/service/view JS, admin tests, and a small scan copy update.

**Tech Stack:** Django models/forms/admin/views, legacy scan templates/JS, Django test suite

---

### Task 1: Lock the new capability contract with failing tests

**Files:**
- Modify: `contacts/tests/tests_capabilities.py`
- Modify: `wms/tests/forms/tests_forms_admin_contacts_contact.py`
- Modify: `wms/tests/scan/tests_admin_contacts_contact_service.py`
- Modify: `wms/tests/scan/tests_admin_contacts_crud.py`
- Modify: `wms/tests/views/tests_views_scan_admin_contacts_crud.py`

**Step 1: Write the failing tests**

Add tests covering:
- `partner` and `other` in `ContactCapabilityType`
- scan form choices and validation parity with `transporter`
- capability persistence through `save_contact_from_form()`
- edit inference reopening existing contacts as `partner` or `other`
- scan page copy making manual creation explicit

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test contacts.tests.tests_capabilities wms.tests.forms.tests_forms_admin_contacts_contact wms.tests.scan.tests_admin_contacts_contact_service wms.tests.scan.tests_admin_contacts_crud wms.tests.views.tests_views_scan_admin_contacts_crud -v 1`
Expected: FAIL because the new capabilities and UI wiring do not exist yet.

### Task 2: Implement the persisted categories in the contact stack

**Files:**
- Modify: `contacts/models.py`
- Create: `contacts/migrations/0011_contactcapability_partner_other.py`
- Modify: `wms/forms_admin_contacts_contact.py`
- Modify: `wms/admin_contacts_contact_service.py`
- Modify: `wms/admin_contacts_crud.py`
- Modify: `wms/static/scan/scan.js`

**Step 1: Extend capability enum and migration**

Add `PARTNER` and `OTHER` to `ContactCapabilityType`, then add the matching schema migration for the `ContactCapability.capability` choices.

**Step 2: Wire the scan CRUD contract**

Update:
- business-type choices
- validation rules
- dynamic JS visibility/required-field logic
- capability persistence map
- edit inference for existing contacts

**Step 3: Keep behavior aligned with transporter**

Ensure `partner` and `other` follow the same non-runtime branch as `donor`/`transporter`, without creating shipment party rows.

### Task 3: Improve discoverability in the scan cockpit

**Files:**
- Modify: `templates/scan/admin_contacts.html`
- Modify: `templates/scan/includes/admin_contacts_intro_card.html`
- Modify: `wms/tests/views/tests_views_scan_admin.py`

**Step 1: Tighten the copy**

Update the intro and create-card helper text so operators can immediately identify:
- that manual creation is available in the `Création de contact` accordion in scan
- that the Django admin still exposes direct `Ajouter contact`

**Step 2: Cover the copy in view tests**

Add or update assertions in scan admin view tests for the new wording.

### Task 4: Verify focused regressions

**Files:**
- Test: `contacts/tests/tests_capabilities.py`
- Test: `wms/tests/forms/tests_forms_admin_contacts_contact.py`
- Test: `wms/tests/scan/tests_admin_contacts_contact_service.py`
- Test: `wms/tests/scan/tests_admin_contacts_crud.py`
- Test: `wms/tests/views/tests_views_scan_admin_contacts_crud.py`
- Test: `wms/tests/views/tests_views_scan_admin.py`

**Step 1: Run focused capability/contact tests**

Run: `./.venv/bin/python manage.py test contacts.tests.tests_capabilities wms.tests.forms.tests_forms_admin_contacts_contact wms.tests.scan.tests_admin_contacts_contact_service wms.tests.scan.tests_admin_contacts_crud wms.tests.views.tests_views_scan_admin_contacts_crud wms.tests.views.tests_views_scan_admin -v 1`
Expected: PASS

**Step 2: Re-check the nearest impact-map surface**

Confirm that the change stays local to the admin contacts maintenance surface and does not require additional repo-reference updates beyond the plan docs.
