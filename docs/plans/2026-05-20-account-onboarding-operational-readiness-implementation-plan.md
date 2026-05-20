# Account Onboarding Operational Readiness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align shipper and recipient account onboarding with ASF operational readiness: validated structures, usable contacts, served stopovers only, and explicit new-stopover study requests.

**Architecture:** Keep the legacy Django portal/scan stack as the delivery surface. Add small shared services for onboarding contact validation, destination options, stopover study requests, and shipper readiness so public forms, portal HTML views, scan review, and UI API endpoints enforce the same contracts. Prefer compatibility-preserving model additions over replacing existing `AssociationRecipient`, `AssociationPortalContact`, and `PublicAccountRequest` flows.

**Tech Stack:** Django models/views/templates, Django email queue helpers, legacy portal/scan templates, DRF UI API endpoints, Django test suite.

---

## Functional Contract

### Recipient Signup / Recipient Creation

- `Escale de livraison` is the first field.
- The standard list contains only active destinations whose `correspondent_contact` is active.
- Selecting a served stopover defaults `Pays` from the selected destination.
- Selecting `Autre escale` opens a separate study-request form and does not create a recipient/account.
- Recipient structure data required:
  - `Nom de la structure`
  - `Forme juridique`
  - `Nombre de bénéficiaires`
  - full address: street, city, country required; complement and postal code optional
- Recipient reception contact required:
  - structure attachment displayed and locked on edit
  - title, last name, first name
  - at least one valid email
  - at least one phone

### Shipper Signup / Account Profile

- Shipper structure data remains required for ASF eligibility.
- Shipper operational contacts required:
  - administrative contact
  - preparation/logistics contact
  - a single contact row may satisfy both via `Utiliser les mêmes informations que le contact administratif`
  - each required contact needs title, last name, first name, email, phone, full address with postal code/complement optional
- Existing `AssociationPortalContact.is_shipping` should be presented as `Préparation / logistique`.

### New Stopover Study Request

- Available from both shipper and recipient account creation, and from shipper-side recipient creation.
- Does not create a portal account, recipient, shipper, grant, or destination.
- Stores a traceable request and sends an internal email with subject `Demande nouvelle escale`.
- Required fields:
  - requester type: shipper or recipient
  - requested stopover(s) text
  - structure name
  - legal form
  - beneficiary count
  - contact title, last name, first name, email, phone
  - address line 1, city, country
  - address line 2 and postal code optional
  - context/message optional

### Nominal Usage Gates

- A shipper can create a portal order only when:
  - shipper is active and validated
  - account has at least one complete admin contact
  - account has at least one complete preparation/logistics contact
  - there is at least one active shipper-linked recipient organization with `validation_status=validated`
- Recipient product preferences require an active recipient organization and complete reception contact data.
- API endpoints must enforce the same readiness checks as HTML views.

---

## Current Behavior Impact Summary

| Surface | Current behavior | Planned behavior | Operational impact |
| --- | --- | --- | --- |
| Django data model | Account requests, portal contacts, and recipient records store partial operational contact data. | Add compatibility-preserving fields and one new `StopoverFeasibilityRequest` model. | Requires migrations. Existing records remain readable; incomplete existing portal accounts may need data completion before new orders. |
| Public account creation | Recipient signup requires only a limited structure dataset; shipper contact requirements are light. | Recipient/shipper signup collects the minimum operational contacts up front; unsupported stopovers become study requests. | More friction at signup, but fewer unusable validated accounts and less manual review work. |
| Scan account review | Operators can compensate for missing public signup data during review. | Review displays submitted operational contacts and remains tolerant of legacy incomplete requests. | Scan review gains context; existing pending requests must remain reviewable. |
| Portal recipients | Shippers can create recipients with incomplete contact data as long as core structure/doc rules pass. | Served stopover first, country defaulted, complete reception contact required, `Autre escale` does not create a recipient. | Fewer incomplete recipient records; portal recipient forms become stricter. |
| Portal account | Contact rows are usable for notifications but do not fully represent admin/preparation readiness. | Admin and preparation/logistics contacts become explicit readiness requirements; one row can satisfy both. | Existing shippers may be blocked from new orders until contacts are completed. |
| Portal order creation | A validated shipper mostly needs an active delivery contact/recipient selection path. | A validated linked recipient organization is required before creating orders. | Main intentional block: validated shipper accounts without a validated linked recipient cannot create orders. |
| UI API | API recipient/order mutation rules are looser than the proposed HTML contract. | API applies the same destination, contact, and readiness rules as HTML. | Prevents HTML/API divergence; may break clients relying on partial recipient payloads. |
| Emails | Account request emails exist; unsupported stopovers are not a first-class tracked flow. | `Autre escale` sends `Demande nouvelle escale` and stores a traceable request. | Adds an internal triage flow without creating operational records prematurely. |
| Warehouse scan operations | Packing, stock, shipment status, and preparation flows do not directly depend on signup forms. | No intended behavior change in warehouse execution flows. | Risk should stay low if tests confirm order/shipment selectors still receive only valid party data. |

Implementation should block only action execution, not recovery pages. Users must always be able to access `/portal/account/` and `/portal/recipients/` to complete missing data.

---

## Cross-Repo Impact Analysis

### Django Models And Migrations

Impacted files:

- `wms/models_domain/portal.py`
- `wms/models.py`
- new migration under `wms/migrations/`
- `wms/admin.py` or `wms/admin_misc.py`
- `wms/reset_operational_data.py`

Expected changes:

- Add `StopoverFeasibilityRequest` for traceability of `Autre escale` submissions.
- Extend `PublicAccountRequest` with structured contact payload storage for shipper admin/preparation and recipient reception data.
- Extend `AssociationPortalContact` to support contact-level address and multi-value email/phone while preserving existing `email` and `phone` primary fields for compatibility.
- Avoid changing `contacts.Contact` globally in the first pass; that model is used by scan, shipments, print, planning, and imports.

Risk:

- `AssociationPortalContact.get_notification_emails()` currently reads `email`; new multi-email fields must keep `email` as first email.
- Reset/seed commands may need to include new model and new fields.

### Public Account Creation

Impacted files:

- `wms/account_request_handlers.py`
- `templates/scan/public_account_request.html`
- `templates/scan/includes/public_account_request_association_fields.html`
- `templates/scan/includes/public_account_request_documents.html`
- `templates/emails/account_request_admin_notification.txt`
- `templates/emails/account_request_received.txt`
- `wms/tests/admin/tests_account_request_handlers.py`
- `wms/tests/views/tests_views_public_account.py`
- `wms/tests/views/tests_scan_bootstrap_ui.py`

Expected changes:

- Reorder recipient signup around destination first.
- Add served-stopover destination options and `Autre escale` branch.
- Require recipient legal form, beneficiary count, reception contact name/title/email/phone/address at signup.
- Require shipper admin/preparation contact payload at signup.
- Add reuse-admin-for-preparation behavior in the template and backend validation.
- Keep upload validation behavior unchanged.

Risk:

- Public account form is shared by public order links and portal account request route.
- Throttling and pending-email checks must still apply to real account requests, but not incorrectly block new-stopover study requests unless intentionally designed.

### Account Review / Scan

Impacted files:

- `wms/forms_scan_account_validations.py`
- `wms/views_scan_account_validations.py`
- `templates/scan/includes/account_validation_request_summary.html`
- `templates/scan/includes/account_validation_review_form.html`
- `wms/admin_account_request_approval.py`
- `wms/account_request_review_service.py`
- `wms/tests/views/tests_views_scan_account_validations.py`
- `wms/tests/portal/tests_portal_role_review_gate.py`

Expected changes:

- Scan review should display submitted admin/preparation/reception contacts.
- Recipient review should no longer rely on operator manually filling first/last/legal form/beneficiary count when the public request already supplied them.
- Shipper approval should create/update required `AssociationPortalContact` rows.
- Recipient approval should provision the reception contact with email and phone.

Risk:

- Existing pending requests without new payloads may still exist. Review form must remain tolerant and allow operator completion.

### Portal Recipient Management

Impacted files:

- `wms/views_portal_account.py`
- `templates/portal/recipients.html`
- `templates/portal/recipient_profile.html`
- `templates/portal/includes/recipient_contact_fields.html`
- `templates/portal/includes/recipient_flags.html`
- `api/v1/serializers.py`
- `api/v1/ui_views.py`
- `wms/application/parties/use_cases.py`
- `wms/tests/views/tests_views_portal.py`
- `api/tests/tests_ui_endpoints.py`
- `api/tests/tests_ui_e2e_workflows.py`

Expected changes:

- Served-stopover filtering must be shared between HTML and API.
- Country defaults from destination in HTML and API mutation paths.
- Recipient create/update requires title, first name, last name, at least one email, and at least one phone.
- Recipient create documents remain required where currently required.
- `Autre escale` submission is available from shipper-side recipient creation but does not create `AssociationRecipient`.
- Recipient-scope profile edits use the same contact completeness validation.

Risk:

- API tests currently allow optional legal form/beneficiary/contact fields; update serializers and tests in the same task.
- Existing recipient records may be incomplete; do not break read-only list/detail pages.

### Portal Account Contacts

Impacted files:

- `wms/views_portal_account.py`
- `wms/application/portal/account_use_cases.py`
- `templates/portal/account.html`
- `api/v1/serializers.py`
- `api/v1/ui_views.py`
- `wms/tests/views/tests_views_portal.py`
- `api/tests/tests_ui_endpoints.py`

Expected changes:

- Contact rows need full identity/address and at least one role.
- Admin and preparation/logistics roles must both be represented before order creation.
- A row may satisfy both roles.
- Existing notification behavior continues to use first email from each active contact row.

Risk:

- Existing accounts with minimal contacts should still reach `/portal/account/` to complete data.
- Avoid changing billing contact behavior unless the same row fields naturally apply.

### Portal Order Creation

Impacted files:

- `wms/view_permissions.py`
- `wms/views_portal_orders.py`
- `wms/application/portal/recipient_resolution.py`
- new `wms/application/portal/readiness.py`
- `api/v1/ui_views.py`
- `templates/portal/dashboard.html`
- `templates/portal/account.html`
- `templates/portal/recipients.html`
- `wms/tests/views/tests_views_portal.py`
- `wms/tests/portal/tests_portal_role_review_gate.py`
- `api/tests/tests_ui_endpoints.py`

Expected changes:

- Replace the current "active delivery contact exists" gate with a richer readiness checker.
- Order creation requires a validated linked recipient organization, not only an active `AssociationRecipient`.
- HTML and API order creation both call the same readiness checker.
- Dashboard/account pages should show actionable missing requirements instead of a confusing generic block.

Risk:

- This changes user-visible behavior. Add FAQ changelog entry when implementing.
- Current dashboard redirect tests must be updated to match the new checklist or redirect behavior.

### Email / Notifications

Impacted files:

- new `templates/emails/stopover_feasibility_request_admin.txt`
- new service file such as `wms/stopover_request_handlers.py`
- `wms/emailing.py` usage only, no queue refactor
- `wms/tests/emailing/`
- `wms/tests/admin/tests_account_request_handlers.py` or new tests

Expected changes:

- New stopover requests send one internal email after transaction commit.
- Recipients should be account validation/admin group recipients, consistent with account request emails.
- Subject must be exactly `Demande nouvelle escale`.

Risk:

- Avoid sending email before the request row is persisted.
- Avoid duplicate sends on validation failure/re-render.

### Shared UI / Assets

Impacted files:

- `templates/scan/public_account_request.html`
- `templates/scan/includes/public_account_request_association_fields.html`
- `templates/portal/recipients.html`
- `templates/portal/account.html`
- possibly shared include: `templates/includes/contact_form_fields.html`
- possibly `wms/static/scan/scan-bootstrap.css`
- possibly `wms/static/scan/scan.js`

Expected changes:

- Prefer server-rendered form sections with small page-local JS for:
  - destination country defaulting
  - `Autre escale` branch display
  - reuse admin contact for preparation
  - add/remove email/phone controls if implemented dynamically
- If shared scan assets change, bump service worker version in:
  - `wms/views_scan_misc.py`
  - `templates/scan/base.html`

Risk:

- Public account request is a scan-styled public page, not inside portal base.
- Keep JS progressive: server validation must remain source of truth.

### Documentation

Impacted docs:

- `docs/repo-reference/04-shared-contracts/04-portal-parties.md`
- `docs/repo-reference/02-key-flows-and-living-tests.md`
- `docs/repo-reference/03b-impact-portal.md`
- `docs/repo-reference/03d-impact-parties.md`
- `docs/email_flows_target_matrix_2026-02-20.md` if email matrix is still maintained
- `docs/release_checklist.md`
- `wms/faq_changelog.py`

Reason:

- This changes user-visible onboarding, portal order eligibility, portal recipient data contracts, and an email flow.

---

## Implementation Tasks

### Task 1: Add Destination Option And Readiness Helpers

**Files:**

- Create: `wms/application/portal/destination_options.py`
- Create: `wms/application/portal/readiness.py`
- Test: `wms/tests/portal/tests_portal_onboarding_readiness.py`

**Step 1: Write failing tests**

Add tests proving:

- served destination options include only `Destination(is_active=True, correspondent_contact__is_active=True)`.
- each option includes `id`, `label`, `country`, and `iata_code`.
- inactive destination and inactive correspondent are excluded.
- shipper readiness fails without complete admin contact.
- shipper readiness fails without complete preparation contact.
- shipper readiness fails without a validated linked delivery recipient.
- shipper readiness passes when all three are present.

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.portal.tests_portal_onboarding_readiness -v 2
```

Expected: FAIL because helper modules do not exist.

**Step 3: Implement minimal helpers**

Implement:

- `list_served_destination_options()`
- `served_destination_queryset()`
- `build_shipper_readiness(profile)`
- contact completeness helpers that initially read current `AssociationPortalContact.email` and `.phone`.
- validated recipient link lookup using `ShipmentShipper`, `ShipmentShipperRecipientLink`, and `ShipmentRecipientOrganization.validation_status`.

**Step 4: Run tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.portal.tests_portal_onboarding_readiness -v 2
```

Expected: PASS.

**Step 5: Checkpoint**

Suggested commit after user approval:

```bash
git add wms/application/portal/destination_options.py wms/application/portal/readiness.py wms/tests/portal/tests_portal_onboarding_readiness.py
git commit -m "feat: add portal onboarding readiness helpers"
```

### Task 2: Add Stopover Feasibility Request Model And Email

**Files:**

- Modify: `wms/models_domain/portal.py`
- Modify: `wms/models.py`
- Create: `wms/migrations/013x_stopover_feasibility_request.py`
- Create: `wms/stopover_request_handlers.py`
- Create: `templates/emails/stopover_feasibility_request_admin.txt`
- Modify: `wms/admin.py` or `wms/admin_misc.py`
- Test: `wms/tests/portal/tests_stopover_feasibility_requests.py`
- Test: `wms/tests/emailing/tests_stopover_feasibility_requests.py`

**Step 1: Write failing tests**

Cover:

- valid request creates a `StopoverFeasibilityRequest`.
- missing requested stopover, structure name, legal form, beneficiary count, contact email, contact phone, address line 1, city, or country is rejected.
- invalid email is rejected.
- valid save enqueues/sends one admin email after commit with subject `Demande nouvelle escale`.
- request does not create `PublicAccountRequest`, `AssociationRecipient`, `ShipmentRecipientOrganization`, or `PortalAccessGrant`.

**Step 2: Run tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.portal.tests_stopover_feasibility_requests wms.tests.emailing.tests_stopover_feasibility_requests -v 2
```

Expected: FAIL because model/service do not exist.

**Step 3: Implement model and service**

Add fields:

- `requester_type`
- `requested_stopovers`
- `structure_name`
- `legal_form`
- `beneficiary_count`
- `contact_title`
- `contact_last_name`
- `contact_first_name`
- `contact_email`
- `contact_phone`
- `address_line1`
- `address_line2`
- `postal_code`
- `city`
- `country`
- `message`
- `source`
- `created_at`

Use `send_or_enqueue_email_safe` with `get_admin_emails()` and validation group recipients, inside `transaction.on_commit`.

**Step 4: Run tests**

Run the same command. Expected: PASS.

**Step 5: Checkpoint**

Suggested commit after user approval:

```bash
git add wms/models_domain/portal.py wms/models.py wms/migrations templates/emails/stopover_feasibility_request_admin.txt wms/stopover_request_handlers.py wms/tests/portal/tests_stopover_feasibility_requests.py wms/tests/emailing/tests_stopover_feasibility_requests.py
git commit -m "feat: track new stopover study requests"
```

### Task 3: Refactor Public Account Request Form Validation

**Files:**

- Modify: `wms/account_request_handlers.py`
- Modify: `templates/scan/public_account_request.html`
- Modify: `templates/scan/includes/public_account_request_association_fields.html`
- Possibly create: `templates/includes/operational_contact_fields.html`
- Test: `wms/tests/admin/tests_account_request_handlers.py`
- Test: `wms/tests/views/tests_views_public_account.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write failing tests**

Cover:

- recipient account request requires served destination first.
- recipient request rejects inactive destination or inactive correspondent destination.
- recipient request defaults country to selected destination country when blank.
- recipient request requires legal form and beneficiary count.
- recipient request requires reception contact title, last name, first name, email, and phone.
- shipper request requires admin contact and preparation contact.
- `use_admin_for_preparation` satisfies both contact roles.
- selecting `Autre escale` with valid study fields creates a `StopoverFeasibilityRequest` and does not create `PublicAccountRequest`.

**Step 2: Run tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.admin.tests_account_request_handlers wms.tests.views.tests_views_public_account wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected: FAIL for new requirements.

**Step 3: Implement backend validation**

Add structured extraction helpers for:

- recipient reception contact payload
- shipper admin contact payload
- shipper preparation contact payload
- stopover study payload

Persist real account contact payloads on `PublicAccountRequest` via a new JSON field from Task 4 if not already added there. If Task 4 is not done yet, add the JSON field in this task and migrate.

**Step 4: Implement template changes**

Use destination options from `list_served_destination_options()`.

Add page-local JS for:

- country default from destination `data-country`
- `Autre escale` branch display
- reuse admin contact for preparation

Do not rely on JS for validation.

**Step 5: Run tests**

Run the same command. Expected: PASS.

**Step 6: Checkpoint**

Suggested commit after user approval:

```bash
git add wms/account_request_handlers.py templates/scan/public_account_request.html templates/scan/includes/public_account_request_association_fields.html templates/includes/operational_contact_fields.html wms/tests/admin/tests_account_request_handlers.py wms/tests/views/tests_views_public_account.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: require operational contacts during account signup"
```

### Task 4: Persist And Provision Shipper Operational Contacts

**Files:**

- Modify: `wms/models_domain/portal.py`
- Create migration under `wms/migrations/`
- Modify: `wms/application/portal/account_use_cases.py`
- Modify: `wms/admin_account_request_approval.py`
- Modify: `wms/views_portal_account.py`
- Modify: `templates/portal/account.html`
- Test: `wms/tests/views/tests_views_portal.py`
- Test: `wms/tests/portal/tests_portal_role_review_gate.py`

**Step 1: Write failing tests**

Cover:

- approving a shipper account request creates active admin and preparation `AssociationPortalContact` rows.
- one reused contact can be both administrative and preparation/logistics.
- portal account save rejects missing admin contact.
- portal account save rejects missing preparation contact.
- portal account save rejects contact rows missing title, last name, first name, email, phone, address line 1, city, or country.
- first email/phone remain mirrored to existing `email`/`phone` fields.

**Step 2: Run tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.portal.tests_portal_role_review_gate -v 2
```

Expected: FAIL for new requirements.

**Step 3: Extend `AssociationPortalContact` compatibly**

Add fields:

- `emails = models.TextField(blank=True)`
- `phones = models.TextField(blank=True)`
- `address_line1`, `address_line2`, `postal_code`, `city`, `country`

Keep `email` and `phone` as primary mirror fields.

**Step 4: Update account use case**

In `save_portal_account_profile(...)`, normalize contact rows:

- split email/phone values
- validate at least one of each
- mirror first values to `email`/`phone`
- persist full address
- require at least one active admin and one active shipping/preparation contact

**Step 5: Update approval provisioning**

When approving shipper requests, create or update portal contacts from `PublicAccountRequest.contact_payloads`.

**Step 6: Run tests**

Run the same command. Expected: PASS.

**Step 7: Checkpoint**

Suggested commit after user approval:

```bash
git add wms/models_domain/portal.py wms/migrations wms/application/portal/account_use_cases.py wms/admin_account_request_approval.py wms/views_portal_account.py templates/portal/account.html wms/tests/views/tests_views_portal.py wms/tests/portal/tests_portal_role_review_gate.py
git commit -m "feat: persist shipper operational contacts"
```

### Task 5: Tighten Recipient Creation And Profile Validation

**Files:**

- Modify: `wms/views_portal_account.py`
- Modify: `wms/application/parties/use_cases.py`
- Modify: `templates/portal/recipients.html`
- Modify: `templates/portal/recipient_profile.html`
- Modify: `templates/portal/includes/recipient_contact_fields.html`
- Modify: `api/v1/serializers.py`
- Modify: `api/v1/ui_views.py`
- Test: `wms/tests/views/tests_views_portal.py`
- Test: `api/tests/tests_ui_endpoints.py`

**Step 1: Write failing tests**

Cover:

- portal recipient create lists only served destinations.
- `Autre escale` creates stopover request and no recipient.
- country defaults from selected destination.
- recipient create rejects missing title, last name, first name, email, phone, city, country.
- recipient profile update rejects missing required contact fields.
- API recipient create/patch rejects the same missing fields.

**Step 2: Run tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal api.tests.tests_ui_endpoints -v 2
```

Expected: FAIL for new requirements.

**Step 3: Implement shared validation**

Extract recipient contact validation into a helper in `wms/views_portal_account.py` or a small shared module if API reuse becomes awkward.

Use `served_destination_queryset()` for HTML and API paths.

**Step 4: Update templates**

Move destination to the first field and add `data-country` to options.

Display structure attachment as locked text when editing.

**Step 5: Run tests**

Run the same command. Expected: PASS.

**Step 6: Checkpoint**

Suggested commit after user approval:

```bash
git add wms/views_portal_account.py wms/application/parties/use_cases.py templates/portal/recipients.html templates/portal/recipient_profile.html templates/portal/includes/recipient_contact_fields.html api/v1/serializers.py api/v1/ui_views.py wms/tests/views/tests_views_portal.py api/tests/tests_ui_endpoints.py
git commit -m "feat: require complete recipient operational contacts"
```

### Task 6: Enforce Order Creation Readiness

**Files:**

- Modify: `wms/view_permissions.py`
- Modify: `wms/views_portal_orders.py`
- Modify: `api/v1/ui_views.py`
- Modify: `templates/portal/dashboard.html`
- Modify: `templates/portal/account.html`
- Test: `wms/tests/views/tests_views_portal.py`
- Test: `wms/tests/portal/tests_portal_role_review_gate.py`
- Test: `api/tests/tests_ui_endpoints.py`

**Step 1: Write failing tests**

Cover:

- order create redirects/blocks when no validated linked recipient exists.
- order create redirects/blocks when admin contact is incomplete.
- order create redirects/blocks when preparation contact is incomplete.
- order create succeeds when readiness is complete.
- API order create returns 403 or validation error with missing readiness details.
- recipient-scope order creation remains forbidden.

**Step 2: Run tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.portal.tests_portal_role_review_gate api.tests.tests_ui_endpoints -v 2
```

Expected: FAIL for new readiness gates.

**Step 3: Implement readiness gate**

Use `build_shipper_readiness(profile)` in:

- `portal_order_create`
- `UiPortalOrdersView.post`

Avoid blocking `/portal/account/` and `/portal/recipients/`, because users need those pages to resolve missing data.

**Step 4: Update dashboard/account UX**

Show a checklist with missing readiness items. Keep wording operational:

- `Contact administratif incomplet`
- `Contact préparation/logistique incomplet`
- `Aucun destinataire validé lié à votre structure`

**Step 5: Run tests**

Run the same command. Expected: PASS.

**Step 6: Checkpoint**

Suggested commit after user approval:

```bash
git add wms/view_permissions.py wms/views_portal_orders.py api/v1/ui_views.py templates/portal/dashboard.html templates/portal/account.html wms/tests/views/tests_views_portal.py wms/tests/portal/tests_portal_role_review_gate.py api/tests/tests_ui_endpoints.py
git commit -m "feat: gate portal orders on operational readiness"
```

### Task 7: Update Scan Review And Admin Visibility

**Files:**

- Modify: `templates/scan/includes/account_validation_request_summary.html`
- Modify: `templates/scan/includes/account_validation_review_form.html`
- Modify: `wms/forms_scan_account_validations.py`
- Modify: `wms/views_scan_account_validations.py`
- Modify: admin registration for `StopoverFeasibilityRequest`
- Test: `wms/tests/views/tests_views_scan_account_validations.py`
- Test: `wms/tests/admin/tests_account_request_handlers.py`

**Step 1: Write failing tests**

Cover:

- scan account validation detail displays shipper admin/preparation contact payloads.
- scan account validation detail displays recipient reception contact payload.
- legacy pending requests without contact payload still render and remain reviewable.
- stopover study requests appear in Django admin list/search.

**Step 2: Run tests**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_account_validations wms.tests.admin.tests_account_request_handlers -v 2
```

Expected: FAIL for new display expectations.

**Step 3: Implement display and fallback logic**

Render submitted payloads as read-only summary blocks.

Keep review form editable for operator correction and legacy records.

**Step 4: Run tests**

Run the same command. Expected: PASS.

**Step 5: Checkpoint**

Suggested commit after user approval:

```bash
git add templates/scan/includes/account_validation_request_summary.html templates/scan/includes/account_validation_review_form.html wms/forms_scan_account_validations.py wms/views_scan_account_validations.py wms/admin.py wms/tests/views/tests_views_scan_account_validations.py wms/tests/admin/tests_account_request_handlers.py
git commit -m "feat: show onboarding contact data in scan review"
```

### Task 8: Documentation And Release Safety

**Files:**

- Modify: `docs/repo-reference/04-shared-contracts/04-portal-parties.md`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/03b-impact-portal.md`
- Modify: `docs/repo-reference/03d-impact-parties.md`
- Modify: `docs/release_checklist.md`
- Modify: `wms/faq_changelog.py`

**Step 1: Update docs**

Document:

- served-stopover-only destination selection
- `Autre escale` study request
- required recipient reception contact
- required shipper admin/preparation contacts
- validated linked recipient requirement for order creation
- new tests acting as living references

**Step 2: Run targeted docs-related tests if any**

Run nearest full functional tests from prior tasks, plus:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected: PASS.

**Step 3: Checkpoint**

Suggested commit after user approval:

```bash
git add docs/repo-reference/04-shared-contracts/04-portal-parties.md docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/03b-impact-portal.md docs/repo-reference/03d-impact-parties.md docs/release_checklist.md wms/faq_changelog.py
git commit -m "docs: document onboarding readiness contracts"
```

### Task 9: Final Verification

**Files:**

- No direct file edits.

**Step 1: Run focused suite**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.admin.tests_account_request_handlers \
  wms.tests.views.tests_views_public_account \
  wms.tests.views.tests_views_scan_account_validations \
  wms.tests.views.tests_views_portal \
  wms.tests.portal.tests_portal_role_review_gate \
  wms.tests.portal.tests_portal_onboarding_readiness \
  wms.tests.portal.tests_stopover_feasibility_requests \
  wms.tests.emailing.tests_stopover_feasibility_requests \
  api.tests.tests_ui_endpoints \
  api.tests.tests_ui_e2e_workflows \
  -v 2
```

Expected: PASS.

**Step 2: Run broader safety gates**

Run, if time permits:

```bash
make test-next-ui
make typecheck
make pre-commit
```

Expected: PASS or documented unrelated failures.

**Step 3: Manual smoke checklist**

Verify in browser:

- public account request, shipper path
- public account request, recipient path
- public account request, other stopover path
- scan account validation detail for new shipper and recipient request
- portal account contact update
- portal recipient create served stopover path
- portal recipient create other stopover path
- portal order create blocked with missing readiness
- portal order create allowed with complete readiness

---

## Rollout Notes

- Existing accounts and recipients may be incomplete. Keep read access and completion pages available.
- Apply hard block only to action execution, especially order creation.
- Do not block users from `/portal/account/` or `/portal/recipients/`; those are recovery pages.
- Use clear status language: `Structure validée, données opérationnelles incomplètes`.
- Consider a short production data audit before deployment to estimate how many active portal accounts will be blocked from new order creation.

## Documentation Impact Check

Documentation is impacted because this changes user-visible onboarding, portal readiness gates, email behavior, and portal/party contracts. Update the docs listed in Task 8 during implementation.
