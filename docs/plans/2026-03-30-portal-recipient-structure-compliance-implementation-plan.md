# Portal Recipient Structure Compliance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add required recipient-structure compliance fields and creation-time documents to the legacy portal recipient flow, then surface the same canonical structure data in `scan/contacts`.

**Architecture:** Keep the portal recipient page on its current manual view/template flow, but promote canonical structure metadata onto the synchronized organization contact and attach recipient-structure documents to that canonical contact. Share one country-choice source between portal and scan, and keep the portal switch orientation change scoped to the recipient page.

**Tech Stack:** Django models/views/templates, `contacts.Contact`, legacy portal views in `wms/views_portal_account.py`, recipient sync in `wms/portal_recipient_sync.py`, scan admin CRUD/forms/templates, Django test suite via `./.venv/bin/python manage.py test`

---

### Task 1: Save the approved design and plan artifacts

**Files:**
- Create: `docs/plans/2026-03-30-portal-recipient-structure-compliance-design.md`
- Create: `docs/plans/2026-03-30-portal-recipient-structure-compliance-implementation-plan.md`

**Step 1: Verify the design document exists**

Run:

```bash
test -f docs/plans/2026-03-30-portal-recipient-structure-compliance-design.md
```

Expected:
- exit code `0`

**Step 2: Verify the implementation plan exists**

Run:

```bash
test -f docs/plans/2026-03-30-portal-recipient-structure-compliance-implementation-plan.md
```

Expected:
- exit code `0`

### Task 2: Lock down the portal UI contract with failing tests

**Files:**
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_portal.py`
- Reference: `templates/portal/recipients.html`
- Reference: `templates/portal/includes/recipient_flags.html`
- Reference: `templates/wms/components/switch.html`

**Step 1: Write the failing portal UI tests**

Add assertions that:
- the structure row renders `Nom de la structure`, `Forme juridique`, and `Nombre de beneficiaires` together
- the country field is a `<select>` rather than a text input
- the portal switch rows render the control before the text for:
  - `reuse_existing_structure`
  - `notify_deliveries`
  - `is_delivery_contact`

Example assertions:

```python
def test_portal_recipients_renders_structure_compliance_fields(self):
    response = self.client.get(reverse("portal:recipients"))
    self.assertContains(response, 'name="legal_form"')
    self.assertContains(response, 'name="beneficiary_count"')
    self.assertContains(response, 'name="country"')
    self.assertContains(response, 'id="recipient-structure-row"')


def test_portal_recipients_uses_country_select_and_leading_switch_controls(self):
    response = self.client.get(reverse("portal:recipients"))
    content = response.content.decode()
    self.assertIn('name="country"', content)
    self.assertIn("<select", content)
    self.assertIn('portal-switch-leading', content)
```

**Step 2: Run the portal UI tests to confirm failure**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_portal.PortalRecipientsViewTests -v 2
```

Expected:
- FAIL because the current portal form does not expose the new fields or switch layout

### Task 3: Add failing portal validation tests for the new required fields and documents

**Files:**
- Modify: `wms/tests/views/tests_views_portal.py`
- Reference: `wms/views_portal_account.py`

**Step 1: Write create-path validation tests**

Cover:
- missing `legal_form` fails
- missing `beneficiary_count` fails
- missing `doc_registration_proof` fails on create
- missing `doc_statutes` fails on create
- invalid country choice fails

**Step 2: Write edit-path validation tests**

Cover:
- update succeeds without re-upload when the recipient already exists
- existing values stay bound back into the form after validation errors

**Step 3: Write reuse-path validation tests**

Cover:
- when the portal resolves to a reused canonical structure with existing documents, creation does not require fresh uploads

**Step 4: Run the targeted tests to confirm failure**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalRecipientsViewTests -v 2
```

Expected:
- FAIL on the new required-field and required-document assertions

### Task 4: Add shared country choices and wire them into scan contact forms

**Files:**
- Create: `wms/country_choices.py`
- Modify: `wms/forms_admin_contacts_contact.py`
- Modify: `wms/tests/views/tests_views_scan_admin.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Write the failing scan/admin form tests**

Add tests that assert:
- `ContactCrudForm.fields["country"]` is a `ChoiceField`
- the choices include `France` and a non-trivial sample such as `Benin`, `Togo`, `Canada`
- the scan contact form renders a select for country

**Step 2: Run the targeted scan/admin tests to confirm failure**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin wms.tests.views.tests_portal_bootstrap_ui -v 2
```

Expected:
- FAIL because `country` is currently a free-text field

**Step 3: Write the minimal implementation**

In `wms/country_choices.py`:
- add a stable tuple of world-country choices
- export `DEFAULT_COUNTRY = "France"` or reuse the existing portal constant carefully

In `wms/forms_admin_contacts_contact.py`:
- replace the `country` `CharField` with a `ChoiceField`
- default to `France`

**Step 4: Run the same tests to verify they pass**

Expected:
- PASS with a shared country-choice source available for scan/admin

### Task 5: Add canonical structure fields and recipient-structure document models

**Files:**
- Modify: `contacts/models.py`
- Modify: `wms/models_domain/portal.py`
- Modify: `wms/models.py`
- Create: `contacts/migrations/<next>_contact_recipient_structure_fields.py`
- Create: `wms/migrations/<next>_recipient_structure_documents.py`
- Modify: `wms/tests/portal/tests_portal_recipient_sync.py`
- Modify: `wms/tests/views/tests_views_portal.py`

**Step 1: Write the failing model and sync tests**

Cover:
- organization contacts persist `legal_form`
- organization contacts persist `beneficiary_count`
- recipient-structure documents can be created for the synchronized organization
- duplicate document types are constrained per contact where appropriate

**Step 2: Run the targeted tests to confirm failure**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.portal.tests_portal_recipient_sync wms.tests.views.tests_views_portal.PortalRecipientsViewTests -v 2
```

Expected:
- FAIL because the fields and document model do not exist

**Step 3: Write the minimal implementation**

In `contacts/models.py`:
- add a `RecipientLegalForm` `TextChoices`
- add `legal_form = models.CharField(..., blank=True)`
- add `beneficiary_count = models.PositiveIntegerField(null=True, blank=True)`

In `wms/models_domain/portal.py`:
- add a `RecipientStructureDocumentType` enum with:
  - `REGISTRATION_PROOF`
  - `STATUTES`
- add a `RecipientStructureDocument` model linked to `contacts.Contact`
- mirror the existing document fields:
  - `status`
  - `file`
  - `scan_status`
  - `scan_message`
  - `scan_updated_at`
  - `uploaded_by`
  - `uploaded_at`

In `wms/models.py`:
- export the new enum and model

**Step 4: Run the same tests to verify they pass**

Expected:
- PASS with the schema available to the rest of the flow

### Task 6: Extend portal recipient extraction, validation, and payload building

**Files:**
- Modify: `wms/views_portal_account.py`
- Modify: `templates/portal/recipients.html`
- Modify: `templates/portal/includes/recipient_flags.html`
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Implement form-data extraction and binding**

Extend:
- `_build_default_recipient_form_data`
- `_extract_recipient_form_data`
- `_build_recipient_form_data_from_instance`
- `_validate_recipient_form_data`
- `_build_recipient_payload`

Add fields:
- `legal_form`
- `beneficiary_count`
- `country` from shared choices

**Step 2: Implement create-only document validation**

Add a small helper that validates:
- `doc_registration_proof`
- `doc_statutes`

Rules:
- required for `create_recipient`
- optional for `update_recipient`
- optional when create resolves to an already reused canonical structure that already has both required docs

**Step 3: Reshape the portal template**

Update `templates/portal/recipients.html` to:
- render the three-field structure row
- render the country select
- add the two file inputs in the creation flow area

Update `templates/portal/includes/recipient_flags.html` and page-local classes so the switch control appears before the text without changing scan/admin switches globally.

**Step 4: Run the targeted portal tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalRecipientsViewTests wms.tests.views.tests_portal_bootstrap_ui -v 2
```

Expected:
- PASS with the new portal UI and validation contract

### Task 7: Persist recipient-structure documents during recipient creation

**Files:**
- Modify: `wms/views_portal_account.py`
- Modify: `wms/portal_recipient_sync.py`
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/portal/tests_portal_recipient_sync.py`

**Step 1: Write the failing creation-path tests**

Cover:
- successful portal recipient creation creates both required recipient-structure documents
- uploaded files go through `validate_upload`
- created documents are queued for antivirus scan
- creating against a reused structure does not duplicate existing required docs

**Step 2: Run the targeted tests to confirm failure**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalRecipientsViewTests wms.tests.portal.tests_portal_recipient_sync -v 2
```

Expected:
- FAIL because recipient creation currently stores no recipient-structure documents

**Step 3: Write the minimal implementation**

Add a helper in `wms/views_portal_account.py` or a nearby service that:
- resolves the canonical synchronized organization after create
- creates the two required `RecipientStructureDocument` rows only when missing
- queues antivirus scan events using the existing document-scan queue helper

Keep the helper idempotent for retries.

**Step 4: Run the same tests to verify they pass**

Expected:
- PASS with document creation and queueing wired in

### Task 8: Synchronize canonical structure metadata into the operational contact

**Files:**
- Modify: `wms/portal_recipient_sync.py`
- Modify: `wms/tests/portal/tests_portal_recipient_sync.py`
- Modify: `wms/tests/portal/tests_portal_shipment_parties.py`

**Step 1: Write the failing sync tests**

Cover:
- new canonical organization gets `legal_form` and `beneficiary_count`
- reused canonical organization updates those fields from the latest portal recipient edit
- shipment-party links remain unchanged

**Step 2: Run the targeted sync tests to confirm failure**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.portal.tests_portal_recipient_sync wms.tests.portal.tests_portal_shipment_parties -v 2
```

Expected:
- FAIL because sync currently ignores the new metadata

**Step 3: Write the minimal implementation**

In `_upsert_recipient_structure_contact`:
- set `contact.legal_form`
- set `contact.beneficiary_count`
- include those fields in `update_fields`

Do not change destination validation or shipper-link logic.

**Step 4: Run the same tests to verify they pass**

Expected:
- PASS with canonical metadata synchronized

### Task 9: Surface the canonical fields and documents in `scan/contacts`

**Files:**
- Modify: `wms/forms_admin_contacts_contact.py`
- Modify: `wms/admin_contacts_crud.py`
- Modify: `templates/scan/includes/admin_contacts_contact_form.html`
- Modify: `wms/views_scan_admin.py`
- Modify: `wms/tests/views/tests_views_scan_admin.py`

**Step 1: Write the failing scan/admin tests**

Cover:
- edit form initial data includes `legal_form` and `beneficiary_count`
- contact form renders both fields for organization recipients
- contact form renders recipient-structure documents when present
- country renders through the shared select

**Step 2: Run the targeted scan/admin tests to confirm failure**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin -v 2
```

Expected:
- FAIL because scan/admin does not yet expose those fields or documents

**Step 3: Write the minimal implementation**

In `wms/forms_admin_contacts_contact.py`:
- add fields for `legal_form` and `beneficiary_count`

In `wms/admin_contacts_crud.py`:
- include those values in `_contact_initial_from_instance`

In `templates/scan/includes/admin_contacts_contact_form.html`:
- render the two new fields in the organization/recipient structure area
- add a read-only document panel for recipient organizations

If needed in `wms/views_scan_admin.py`:
- preload the related document queryset for efficient rendering

**Step 4: Run the same tests to verify they pass**

Expected:
- PASS with scan/admin visibility aligned to portal requirements

### Task 10: Preserve the data through contact merge flows

**Files:**
- Modify: `wms/admin_contacts_merge_service.py`
- Modify: `wms/tests/views/tests_views_scan_admin.py`
- Modify: `wms/tests/admin/tests_admin_extra.py`

**Step 1: Write the failing merge tests**

Cover:
- merging recipient organizations preserves `legal_form`
- merging recipient organizations preserves `beneficiary_count`
- recipient-structure documents move or merge onto the surviving contact

**Step 2: Run the targeted merge tests to confirm failure**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin wms.tests.admin.tests_admin_extra -v 2
```

Expected:
- FAIL because merge logic currently ignores the new fields and documents

**Step 3: Write the minimal implementation**

In `wms/admin_contacts_merge_service.py`:
- merge scalar structure fields conservatively
- reassign or deduplicate recipient-structure documents on the target contact

Keep the existing same-destination merge guard intact.

**Step 4: Run the same tests to verify they pass**

Expected:
- PASS with merge safety preserved

### Task 11: Run end-to-end targeted verification and impact re-check

**Files:**
- Review: `docs/repo-reference/03-impact-map.md`
- Review: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Run the targeted verification suite**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.views.tests_portal_bootstrap_ui wms.tests.portal.tests_portal_recipient_sync wms.tests.portal.tests_portal_shipment_parties wms.tests.views.tests_views_scan_admin wms.tests.admin.tests_admin_extra -v 2
```

Expected:
- PASS

**Step 2: Re-check propagation**

Confirm the implementation did not miss:
- portal recipient sync contracts
- scan/admin recipient visibility
- merge behavior
- shipment-party recipient eligibility

**Step 3: Inspect the final diff**

Run:

```bash
git diff -- contacts wms templates docs/plans
```

Expected:
- only the intended portal-recipient compliance changes and planning docs

### Task 12: Commit in focused slices

**Files:**
- Review: staged files from Tasks 4 through 10

**Step 1: Commit the shared country-choice and form groundwork**

```bash
git add wms/country_choices.py wms/forms_admin_contacts_contact.py wms/tests/views/tests_views_scan_admin.py wms/tests/views/tests_portal_bootstrap_ui.py
git commit -m "feat: add shared country choices for portal and scan contacts"
```

**Step 2: Commit the portal recipient compliance flow**

```bash
git add contacts/models.py contacts/migrations wms/models_domain/portal.py wms/models.py wms/views_portal_account.py wms/portal_recipient_sync.py templates/portal/recipients.html templates/portal/includes/recipient_flags.html wms/tests/views/tests_views_portal.py wms/tests/portal/tests_portal_recipient_sync.py wms/tests/portal/tests_portal_shipment_parties.py
git commit -m "feat: require recipient structure compliance in portal"
```

**Step 3: Commit the scan/admin visibility and merge preservation**

```bash
git add wms/admin_contacts_crud.py wms/forms_admin_contacts_contact.py wms/admin_contacts_merge_service.py templates/scan/includes/admin_contacts_contact_form.html wms/views_scan_admin.py wms/tests/views/tests_views_scan_admin.py wms/tests/admin/tests_admin_extra.py
git commit -m "feat: expose recipient structure compliance in scan contacts"
```
