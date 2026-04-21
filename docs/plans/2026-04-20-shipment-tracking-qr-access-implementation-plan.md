# Shipment Tracking QR Access Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert `/scan/shipment/track/<tracking_token>/` into an authenticated QR gateway that reuses the existing role identifiers, supports lost-code recovery and pending identity creation, and requires proof capture for correspondent / recipient receipt scans.

**Architecture:** Keep the legacy Django scan route and `ShipmentTrackingEvent` history, but add a narrow QR access layer, enrich tracking events with actor snapshot and proof metadata, and split the page into an access gateway plus the authenticated update form. Reuse the existing portal / volunteer auth paths when they already match, and fall back to a new QR-restricted access flow for correspondents and pending identities.

**Tech Stack:** Django models / views / forms / templates, legacy scan page JS, email templates via `send_or_enqueue_email_safe`, Django test suite via `./.venv/bin/python manage.py test`

---

### Task 1: Lock The QR Access And Event Snapshot Model Contracts

**Files:**
- Create: `wms/tests/shipment/tests_shipment_tracking_access.py`
- Modify: `wms/models_domain/shipment.py`
- Modify: `wms/models.py`
- Create: `wms/shipment_tracking_access.py`
- Create: `wms/migrations/0120_shipment_tracking_access_and_event_snapshot.py`

**Step 1: Write the failing tests**

Add model / helper coverage for:

- creating a QR access grant tied to a `Contact`
- creating a QR access grant tied to a `VolunteerProfile`
- resolving a snapshot payload from a restricted grant
- storing the new shipment-tracking event metadata defaults

Example:

```python
grant = ShipmentTrackingAccessGrant.objects.create(
    user=user,
    role=ShipmentTrackingAccessRole.CORRESPONDENT,
    contact=contact,
    identity_status=ShipmentTrackingIdentityStatus.PENDING,
)

snapshot = build_tracking_actor_snapshot_from_grant(grant)

self.assertEqual(snapshot["role"], "correspondent")
self.assertEqual(snapshot["identifier"], contact.asf_id)
self.assertEqual(snapshot["identity_status"], "pending")
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.shipment.tests_shipment_tracking_access -v 2
```

Expected:
- FAIL because the grant model, helper module, and event snapshot fields do not exist yet

**Step 3: Write minimal implementation**

Implement:

- `ShipmentTrackingAccessGrant` and its enum choices in `wms/models_domain/shipment.py`
- the new `ShipmentTrackingEvent` fields for role / identifier / email / auth source / escale / proof / actor snapshot
- the `wms/models.py` facade exports
- `wms/shipment_tracking_access.py` helpers for snapshot resolution and grant lookup
- the migration `wms/migrations/0120_shipment_tracking_access_and_event_snapshot.py`

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

**Step 5: Commit**

```bash
git add wms/tests/shipment/tests_shipment_tracking_access.py wms/models_domain/shipment.py wms/models.py wms/shipment_tracking_access.py wms/migrations/0120_shipment_tracking_access_and_event_snapshot.py
git commit -m "feat: add qr shipment tracking access model"
```

### Task 2: Add The Gateway And Proof Form Contracts

**Files:**
- Create: `wms/tests/forms/tests_forms_shipment_tracking.py`
- Modify: `wms/forms.py`
- Modify: `wms/shipment_tracking_access.py`

**Step 1: Write the failing tests**

Add form coverage for:

- role-specific identifier labels
- `Code perdu ?` defaulting escale to `CDG` before `boarding_ok`
- defaulting escale to destination IATA after `boarding_ok`
- `Reçu correspondant` requiring photo or manual carton number
- `Reçu destinataire` requiring photo or manual carton number
- pending creation requiring structure fields for the non-volunteer roles and not showing them for volunteers

Example:

```python
form = ShipmentTrackingUpdateForm(
    data={
        "status": ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
        "proof_mode": "manual",
        "proof_carton_reference": "",
    },
    shipment=shipment,
    actor_role="correspondent",
)

self.assertFalse(form.is_valid())
self.assertIn("proof_carton_reference", form.errors)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.forms.tests_forms_shipment_tracking -v 2
```

Expected:
- FAIL because the gateway forms and proof validation do not exist yet

**Step 3: Write minimal implementation**

In `wms/forms.py`:

- add a role-selection / identifier form for the QR gateway
- add a `Code perdu ?` recovery form
- add a pending-creation form with role-aware field groups
- extend `ShipmentTrackingForm` into a shipment-aware authenticated update form with:
  - actor role
  - proof mode
  - proof upload
  - manual carton reference
  - escale defaulting helpers

In `wms/shipment_tracking_access.py`:

- add the escale-default helper and role requirement helpers used by the forms

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

**Step 5: Commit**

```bash
git add wms/tests/forms/tests_forms_shipment_tracking.py wms/forms.py wms/shipment_tracking_access.py
git commit -m "feat: add qr shipment tracking gateway forms"
```

### Task 3: Build The Restricted QR Auth And Recovery Views

**Files:**
- Create: `wms/tests/views/tests_views_shipment_tracking_access.py`
- Create: `wms/views_shipment_tracking_access.py`
- Modify: `wms/scan_urls.py`
- Modify: `wms/views_scan.py`
- Modify: `wms/views.py`
- Create: `templates/scan/shipment_tracking_login.html`
- Create: `templates/scan/shipment_tracking_set_password.html`
- Create: `templates/scan/shipment_tracking_access_recovery.html`

**Step 1: Write the failing tests**

Add view coverage for:

- QR access login GET rendering
- QR access login POST authenticating a restricted grant user
- recovery POST keeping a generic success message for unknown emails
- recovery POST sending an email for a matching restricted grant user
- set-password flow redirecting back to the shipment tracking route through `next`

Example:

```python
response = self.client.post(
    reverse("scan:scan_shipment_tracking_access_login"),
    {"identifier": "actor@example.com", "password": "TEST_PASSWORD", "next": next_url},  # pragma: allowlist secret
)

self.assertRedirects(response, next_url)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_shipment_tracking_access -v 2
```

Expected:
- FAIL because the restricted QR auth routes and templates do not exist yet

**Step 3: Write minimal implementation**

Create `wms/views_shipment_tracking_access.py` modeled on the portal / volunteer auth flows, but restricted to QR access grants only.

Add routes under `wms/scan_urls.py` for:

- QR login
- QR recovery
- QR set-password
- QR logout if needed for the flow

Re-export the new views through `wms/views_scan.py` and `wms/views.py`.

Create the three scan templates with the existing scan bootstrap shell.

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_shipment_tracking_access.py wms/views_shipment_tracking_access.py wms/scan_urls.py wms/views_scan.py wms/views.py templates/scan/shipment_tracking_login.html templates/scan/shipment_tracking_set_password.html templates/scan/shipment_tracking_access_recovery.html
git commit -m "feat: add restricted qr tracking auth flow"
```

### Task 4: Turn The Tracking QR Page Into An Authenticated Gateway

**Files:**
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/shipment_tracking_handlers.py`
- Modify: `templates/scan/shipment_tracking.html`
- Create: `wms/static/scan/modules/shipment-tracking.js`

**Step 1: Write the failing tests**

Add view / handler coverage for:

- unauthenticated QR GET showing the access gateway instead of the update form
- unauthenticated POST refusing to create a tracking event
- authenticated staff still seeing the update form directly
- authenticated restricted grant user seeing the update form only when role + identifier match
- role-to-step authorization (`correspondant -> Reçu correspondant`, `destinataire -> Reçu destinataire`)
- stored actor snapshot / proof fields on a successful POST

Example:

```python
response = self.client.post(
    reverse("scan:scan_shipment_track", args=[shipment.tracking_token]),
    {
        "status": ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
        "proof_mode": "manual",
        "proof_carton_reference": "COL-001",
    },
)

self.assertEqual(response.status_code, 302)
self.assertEqual(ShipmentTrackingEvent.objects.count(), 0)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2
```

Expected:
- FAIL because the QR page still behaves like a public direct mutation form

**Step 3: Write minimal implementation**

In `wms/views_scan_shipments.py`:

- split the page context into `gateway mode` and `tracking form mode`
- resolve the current actor context from staff / volunteer / portal / restricted QR access
- keep the current document / history rendering intact

In `wms/shipment_tracking_handlers.py`:

- reject POST updates without an authorized actor context
- enforce the role-to-step matrix
- persist the actor snapshot / proof / escale metadata on the event

In `templates/scan/shipment_tracking.html` and the new JS module:

- render the gateway forms
- hide / show the role-specific field groups
- toggle photo vs manual carton proof fields
- keep the existing unsaved-changes overlay only for the authenticated update form

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_scan_shipments.py wms/views_scan_shipments.py wms/shipment_tracking_handlers.py templates/scan/shipment_tracking.html wms/static/scan/modules/shipment-tracking.js
git commit -m "feat: gate shipment qr tracking behind auth"
```

### Task 5: Add Lost-Code And Pending-Creation Email Coverage

**Files:**
- Create: `wms/tests/emailing/tests_shipment_tracking_access.py`
- Modify: `wms/shipment_tracking_access.py`
- Create: `templates/emails/shipment_tracking_access_recovery.txt`
- Create: `templates/emails/shipment_tracking_pending_created.txt`

**Step 1: Write the failing tests**

Add focused email / helper coverage for:

- recovery emails including role, identifier, login path, and QR return link
- pending-creation emails including the newly assigned identifier and `pending` status wording
- generic UI success without sending when no matching identity exists
- correspondent pending creation notifying ASF through the helper

Example:

```python
message = render_recovery_email_context(...)

self.assertIn("ASF ID", message)
self.assertIn("correspondant", message)
self.assertIn(tracking_url, message)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.emailing.tests_shipment_tracking_access -v 2
```

Expected:
- FAIL because the templates and helper functions do not exist yet

**Step 3: Write minimal implementation**

In `wms/shipment_tracking_access.py`:

- add recovery email dispatch helpers
- add pending-creation email dispatch helpers
- normalize the role / identifier / tracking-return payload

Create the two outbound email templates under `templates/emails/`.

Reuse `send_or_enqueue_email_safe` to stay aligned with current email policy.

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

**Step 5: Commit**

```bash
git add wms/tests/emailing/tests_shipment_tracking_access.py wms/shipment_tracking_access.py templates/emails/shipment_tracking_access_recovery.txt templates/emails/shipment_tracking_pending_created.txt
git commit -m "feat: add qr tracking recovery emails"
```

### Task 6: Wire Pending Creation Into Existing Review Flows And Re-Check Docs

**Files:**
- Modify: `wms/tests/admin/tests_account_request_handlers.py`
- Modify: `wms/tests/views/tests_views_volunteer_account_request.py`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/03-impact-map.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Modify if needed: `docs/operations.md`
- Modify if needed: `docs/release_checklist.md`

**Step 1: Write the failing tests**

Add focused coverage proving:

- shipper / recipient QR pending creation still creates `PublicAccountRequest(status=pending)`
- volunteer QR pending creation still creates `VolunteerAccountRequest(status=pending)`
- any reuse of existing pending objects does not duplicate requests unnecessarily

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.admin.tests_account_request_handlers \
  wms.tests.views.tests_views_volunteer_account_request \
  -v 2
```

Expected:
- FAIL because the QR pending-creation adapters are not wired into the existing request flows yet

**Step 3: Write minimal implementation**

Implement the QR pending-creation adapters so they:

- create or reuse the right pending review object
- assign the generated identifier immediately
- avoid granting broad portal / volunteer access before approval
- keep the QR-restricted access grant as the only active route for pending identities

Update the repo-reference and ops docs for the new authenticated QR gateway contract.

**Step 4: Run focused verification**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.shipment.tests_shipment_tracking_access \
  wms.tests.forms.tests_forms_shipment_tracking \
  wms.tests.views.tests_views_shipment_tracking_access \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.emailing.tests_shipment_tracking_access \
  wms.tests.admin.tests_account_request_handlers \
  wms.tests.views.tests_views_volunteer_account_request \
  -v 2
```

Expected:
- PASS across the directly impacted model, form, view, email, and pending-creation flows

**Step 5: Commit**

```bash
git add wms/tests/admin/tests_account_request_handlers.py wms/tests/views/tests_views_volunteer_account_request.py docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/03-impact-map.md docs/repo-reference/04-shared-contracts.md docs/operations.md docs/release_checklist.md
git commit -m "docs: record qr shipment tracking gateway contract"
```
