# Email & Events Impact Map

Use this file when touching notifications, outbound emails, queued side effects, signals, integrations, or operational jobs triggered by business events.

Read this file for changes involving:

- transactional emails
- account approval emails
- shipment notifications
- tracking emails
- portal confirmations
- planning publication notifications
- async queues
- retry logic
- event logging
- integration calls
- management commands processing side effects
- signal-triggered actions
- webhooks / outbound integrations
- email templates
- idempotent event processing

Email/event bugs are often silent until users complain. Precision matters.

---

## Also Read

Depending on the change, also read:

- `03b-impact-portal.md` — user confirmations / external notifications
- `03c-impact-shipments.md` — shipment lifecycle triggers
- `03d-impact-parties.md` — recipients / contacts / permissions
- `03f-impact-planning.md` — publication / coordination outputs
- `03g-impact-shared-ui-api.md` — endpoints triggering side effects
- `04-shared-contracts.md` — naming / state contracts used by events

If unsure, read more than one file.

---

## Critical Invariants

These rules must remain true unless explicitly redesigned.

### Delivery Integrity

Intended recipients must receive the intended message.

### Trigger Integrity

Events should fire exactly when business rules intend.

### Idempotency Integrity

Retries or repeated actions must not create duplicate harmful side effects.

### Audit Integrity

Important outbound actions should remain traceable.

### Environment Safety

Non-production environments must not accidentally notify real users.

---

## Always Check

### Runtime Sources

- `wms/emailing.py`
- `wms/signals.py`
- `wms/events/outbox.py`

### Producers / Triggers

- `wms/account_request_handlers.py`
- `wms/admin_account_request_approval.py`
- `wms/public_order_handlers.py`
- `wms/order_notifications.py`

### Domain / Audit Sources

- `wms/models_domain/integration.py`

### Jobs / Commands

- `wms/management/commands/process_email_queue.py`
- related management commands

### Templates

- email templates under `templates/`

### Tests

- `wms/tests/emailing/`

---

## Ask Yourself

### Recipient Questions

- who receives this message now?
- could the wrong recipient receive it?
- are CC/BCC semantics affected if any?

### Trigger Questions

- what exact event causes send now?
- did timing change?
- can one user action trigger two sends?

### Retry Questions

- if provider/API fails, what happens?
- can retries duplicate side effects?
- is partial success handled?

### Environment Questions

- could staging/dev send real emails?
- are env vars still safe?
- are test recipients isolated?

### UX Questions

- is the email understandable?
- does it tell user next action?
- does subject line remain clear?

### Operational Questions

- will support volume rise?
- is there enough logging to debug failures?
- can staff manually recover?

---

## Precision Checks

### If Editing Queue Processing

Also verify:

- `wms/management/commands/process_email_queue.py`
- retry policy
- lock/concurrency assumptions
- poison message handling
- observability logs

### If Editing Signals

Also verify:

- `wms/signals.py`
- duplicate registration risks
- import-time side effects
- transaction timing issues

### If Editing Durable Enqueue Logic

Prefer durable routing through:

`wms/events/outbox.py`

Check that direct ad-hoc event creation does not reappear.

### If Editing Templates

Also verify:

- subject lines
- localization if applicable
- variable placeholders
- mobile readability
- accidental sensitive data exposure

### If Editing Shipment Notifications

Also verify:

- status truth
- tracking links
- recipient permissions
- duplicate sends after repeated updates

---

## Run First

Choose nearest tests.

### High Value

- nearest tests under `wms/tests/emailing/`

### Producer Tests

- account approval tests
- portal/order tests
- shipment trigger tests

### Manual Verification Often Needed

- send to sandbox mailbox
- inspect rendered HTML/text
- simulate retry path
- inspect logs after processing

---

## Known Traps

### Duplicate Send Trap

One action emits two notifications.

### Silent Failure Trap

Queue fails quietly and nobody knows.

### Wrong Recipient Trap

Email sent to stale or unauthorized contact.

### Timing Trap

Notification sent before transaction commit or before truth is final.

### Environment Leak Trap

Staging/dev sends real production emails.

### Template Trap

Rendered email missing variables or unreadable on mobile.

### Retry Storm Trap

Transient provider issue causes repeated spam.

---

## Docs To Update

If behavior changed, review:

- `docs/operations.md`
- `docs/release_checklist.md`
- `docs/email_flows_target_matrix_2026-02-20.md`
- `docs/repo-reference/02-key-flows-and-living-tests.md`

---

## Final Rule

If changing email/events logic, optimize for correctness, traceability, idempotency, and user trust.
