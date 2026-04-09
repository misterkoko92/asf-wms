# Django Admin Recipient Canonical Models Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** expose canonical recipient and recipient-portal models in Django admin while locking legacy `AssociationRecipient` to inspection-only.

**Architecture:** keep the admin registrations in `wms/admin_misc.py`, where portal and miscellaneous operational models already live. Add focused `ModelAdmin` classes for canonical models and tighten the existing legacy projection admin with read-only permissions.

**Tech Stack:** Django admin, Django tests, legacy Django app structure

---

### Task 1: Lock the expected admin contract with tests

**Files:**
- Create: `wms/tests/admin/tests_admin_recipient_portal_models.py`

**Step 1: Write the failing test**

Add tests covering:
- canonical model registration in `admin.site._registry`
- admin changelist access for the new canonical models
- `AssociationRecipientAdmin` inspection-only behavior
- read-only field locking on existing canonical rows

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.admin.tests_admin_recipient_portal_models -v 1`
Expected: FAIL because the admin classes are not registered/configured yet.

### Task 2: Implement canonical recipient admin registrations

**Files:**
- Modify: `wms/admin_misc.py`

**Step 1: Add `ModelAdmin` classes**

Add:
- `PortalAccessGrantAdmin`
- `ShipmentRecipientOrganizationAdmin`
- `RecipientProductPreferenceAdmin`
- `RecipientStructureDocumentAdmin`

**Step 2: Harden legacy projection admin**

Update `AssociationRecipientAdmin` to:
- disable add/change/delete writes
- remain searchable/listable for inspection

**Step 3: Keep edit scope safe**

On existing canonical rows:
- lock structural identity fields
- leave only operational status/review fields editable

### Task 3: Verify the admin surface

**Files:**
- Test: `wms/tests/admin/tests_admin_recipient_portal_models.py`
- Test: `wms/tests/admin/tests_admin_volunteer.py`

**Step 1: Run focused admin tests**

Run: `./.venv/bin/python manage.py test wms.tests.admin.tests_admin_recipient_portal_models wms.tests.admin.tests_admin_volunteer -v 1`
Expected: PASS

**Step 2: Run recipient/portal regression tests**

Run: `./.venv/bin/python manage.py test wms.tests.portal.tests_portal_access_grants wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_scan_admin_shipment_parties -v 1`
Expected: PASS
