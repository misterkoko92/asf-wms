# Portal Impact Map

Use this file when touching any external `/portal/` surface used by partner organizations, shippers, recipients, or self-service users.

Read this file for changes involving:

- portal authentication
- account/profile management
- portal dashboard
- order creation / submission
- recipient management
- billing visibility
- portal permissions
- shipper / recipient scope switching
- external file uploads
- portal search / lists / filters
- portal notifications triggered by user actions
- portal UI flows
- portal API-backed pages

Portal changes directly affect partner trust, support load, and data quality entering operations.

---

## Also Read

Depending on the change, also read:

- `03d-impact-parties.md` — recipients / contacts / actor graph
- `03c-impact-shipments.md` — orders becoming shipments / downstream lifecycle
- `03a-impact-scan.md` — internal follow-up after portal submissions
- `03g-impact-shared-ui-api.md` — mirrored UI/API contracts
- `03h-impact-email-events.md` — confirmations / notifications
- `04-shared-contracts.md` — shared filters / selectors / pagination

If unsure, read more than one file.

---

## Critical Invariants

These rules must remain true unless explicitly redesigned.

### Access Integrity

Users must only see data within their granted scope.

### Identity Integrity

Correct organization / recipient context must remain explicit.

### Submission Integrity

Orders created in portal must reach operations accurately.

### Sync Integrity

Portal-visible recipient/contact truth must stay aligned with internal canonical data.

### Trust Integrity

External users must understand status, next actions, and ownership clearly.

---

## Always Check

### Runtime Sources

- `wms/portal_urls.py`
- `wms/views_portal_auth.py`
- `wms/views_portal_account.py`
- `wms/views_portal_orders.py`
- `wms/views_portal_billing.py`

### Shared Application Sources

- `wms/application/portal/account_use_cases.py`
- `wms/application/portal/order_use_cases.py`
- `wms/application/portal/recipient_resolution.py`
- `wms/application/portal/dashboard_queries.py`

### Access / Scope

- `wms/portal_access.py`
- `wms/view_permissions.py`

### Templates / Assets

- `templates/portal/`
- `wms/static/portal/`

### Tests

- `wms/tests/portal/`
- portal UI tests under `wms/tests/views/`

---

## Ask Yourself

### Permission Questions

- can users access another organization’s data?
- did scope switching remain correct?
- can stale sessions see forbidden data?

### Submission Questions

- does order creation still validate properly?
- does downstream data remain complete?
- can duplicate submissions occur?

### Recipient Questions

- can users maintain recipients correctly?
- did selector defaults change unexpectedly?
- is internal sync still coherent?

### UX Questions

- is next action obvious?
- do statuses make sense to non-expert users?
- did support burden likely increase?

### Trust Questions

- would a partner understand what happened after submit?
- are confirmations clear?
- are errors actionable?

---

## Precision Checks

### If Editing Access Scope Logic

Also verify:

- `wms/portal_access.py`
- active grant switching
- shipper vs recipient contexts
- historical users with multiple scopes

### If Editing Order Submission

Also verify:

- `wms/application/portal/order_use_cases.py`
- downstream shipment creation assumptions
- confirmation messages
- duplicate submit protection

### If Editing Recipient Resolution

Also verify:

- `wms/application/portal/recipient_resolution.py`
- `wms/portal_recipient_sync.py`
- actor labels in forms
- shipment selectors downstream

### If Editing Dashboard

Also verify:

- `wms/application/portal/dashboard_queries.py`
- empty states
- counts/status truth
- performance on real user accounts

### If Editing Billing Visibility

Also verify:

- organization scoping
- downloadable docs
- historical visibility
- labels / wording clarity

---

## Run First

Choose nearest tests.

### High Value

- nearest tests under `wms/tests/portal/`

### UI / Views

- portal bootstrap UI tests
- nearest portal page tests

### Cross Flow

- shipment/order E2E tests
- recipient sync tests

### Manual Verification Often Needed

- login flow
- submit sample order
- edit recipient
- switch scope if multi-grant user

---

## Known Traps

### Permission Leak Trap

User sees another organization’s data.

### Duplicate Submit Trap

Slow request causes repeated order creation.

### Silent Validation Trap

Bad data accepted and breaks downstream operations.

### Scope Confusion Trap

User no longer knows which organization context is active.

### Internal Drift Trap

Portal recipient truth diverges from internal records.

### Support Load Trap

Minor UX confusion creates many emails/messages.

---

## Docs To Update

If behavior changed, review:

- `docs/mvp_spec.md`
- `docs/operations.md`
- `docs/repo-reference/02-key-flows-and-living-tests.md`
- `docs/repo-reference/04-shared-contracts.md`

---

## Final Rule

If changing `/portal/`, optimize for trust, clarity, low support burden, and clean downstream operational data.
