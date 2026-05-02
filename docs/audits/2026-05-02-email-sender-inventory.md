# Email Sender Configuration Audit For PR 3

Date: 2026-05-02

Branch: `audit/pr3-email-sender-inventory`

Classification: B. generic reusable capability and C. organization configuration. This audit prepares a narrow white-label/configuration step without changing runtime behavior.

## 1. Executive Summary

PR 3 should externalize only the Brevo sender display name as `installation.notifications.email_sender_name`.

Current code resolves Brevo sender identity inside `wms/emailing.py` at send time. Business email producers do not pass sender fields. Queued email payloads do not serialize sender name, sender email, or reply-to email; they serialize subject, message, recipient, optional HTML, optional tags, and queue retry metadata only.

The safest PR 3 implementation point is the Brevo transport branch, specifically the sender-name resolution used by `_send_with_brevo()`. This is not identical to PR 2 subject formatting: subjects are shared by Brevo and SMTP, while sender display names are represented differently by each transport.

Sender email and reply-to email must remain out of scope. `sender_email` changes affect SPF, DKIM, DMARC alignment, and Brevo sender/domain authentication. `reply_to_email` has lower delivery-authentication risk than `sender_email`, but it still affects trust, response routing, and potential personal-data leakage.

## 2. Search Method

Reproducible searches run:

- `rg -n "BREVO_SENDER" .`
- `rg -n "REPLY_TO" .`
- `rg -n "sender_name|sender_email|reply_to" .`
- `rg -n "send_email_safe|send_or_enqueue_email_safe|enqueue_email_safe|send_mail|EmailMessage|EmailMultiAlternatives|From|brevo|Brevo" wms asf_wms api docs .env.example deploy templates --glob '*.py' --glob '*.md' --glob '*.txt' --glob '*.template' --glob '.env.example'`
- `rg -n "from_email|DEFAULT_FROM_EMAIL|EmailMessage|EmailMultiAlternatives|send_mail\\(|mail_admins|mail_managers|get_connection|reply_to|replyTo|From:" wms asf_wms api templates docs deploy .env.example --glob '*.py' --glob '*.html' --glob '*.txt' --glob '*.md' --glob '*.template' --glob '.env.example'`
- `rg -n "EMAIL_PAYLOAD_|_build_enqueue_payload|_send_event_payload|process_email_queue|IntegrationEvent|enqueue_integration_event|payload=" wms/emailing.py wms/events/outbox.py wms/jobs/email_queue.py wms/management/commands/process_email_queue.py wms/tests/emailing --glob '*.py'`
- `rg -n "send_email_safe\\(|send_or_enqueue_email_safe\\(|enqueue_email_safe\\(" wms api --glob '*.py'`
- `rg -n "enqueue_email=|send_email=|send_or_enqueue_email_safe|enqueue_email_safe|send_email_safe" wms api --glob '*.py'`
- `rg -n "sender\\]|sender\\.|sender_name|BREVO_SENDER_NAME|replyTo|reply_to|DEFAULT_FROM_EMAIL|send_mail\\.assert_called|from_email" wms/tests --glob '*.py'`

## 3. Current Sender Configuration Flow

Settings and environment:

- `asf_wms/settings.py:378-392` defines `EMAIL_BACKEND`, `DEFAULT_FROM_EMAIL`, SMTP settings, `EMAIL_DELIVERY_MODE`, `BREVO_API_KEY`, `BREVO_SENDER_EMAIL`, `BREVO_SENDER_NAME`, and `BREVO_REPLY_TO_EMAIL`.
- `.env.example:57-70` documents `DEFAULT_FROM_EMAIL`, SMTP settings, `BREVO_API_KEY`, `BREVO_SENDER_EMAIL`, `BREVO_SENDER_NAME`, and `BREVO_REPLY_TO_EMAIL`.
- `deploy/pythonanywhere/asf-wms.env.template:31-47` sets `DEFAULT_FROM_EMAIL`, SMTP Brevo fallback settings, `BREVO_SENDER_EMAIL`, `BREVO_SENDER_NAME='ASF WMS'`, and `BREVO_REPLY_TO_EMAIL`.
- `deploy/pythonanywhere/asf-wms.messmed.env.template:22-37` sets the MessMed defaults, keeps `BREVO_API_KEY=''` for SMTP-only, and still declares `BREVO_SENDER_NAME='ASF WMS'`.

Runtime flow:

- `wms/emailing.py:387-400` reads Brevo API key, sender email, sender name, and reply-to email in `_brevo_settings()`.
- `wms/emailing.py:389-392` resolves `sender_email` from `settings.BREVO_SENDER_EMAIL`, then `os.environ["BREVO_SENDER_EMAIL"]`, then `settings.DEFAULT_FROM_EMAIL`.
- `wms/emailing.py:394-398` resolves `sender_name` and `reply_to` from `settings` or `os.environ`, with no hard-coded sender-name default in the transport helper.
- `wms/emailing.py:403-418` constructs the Brevo API payload. `sender.name` is `sender_name or sender_email`; `replyTo` is present only when `reply_to` is configured.
- `wms/emailing.py:460-467` constructs the SMTP fallback send via Django `send_mail(...)`, passing `settings.DEFAULT_FROM_EMAIL` as `from_email`. No display name or reply-to is passed on this path.
- `wms/config/installation.py:84-87` currently exposes only `InstallationNotifications.email_subject_prefix`.
- `wms/config/installation.py:131-136` uses `BREVO_REPLY_TO_EMAIL`, `BREVO_SENDER_EMAIL`, and `DEFAULT_FROM_EMAIL` only as identity contact-email candidates. It does not expose sender display name.

Business producers:

- `wms/emailing.py:440-501` exposes helper signatures with only `subject`, `message`, `recipient`, `html_message`, and `tags`.
- Producer searches show calls to `send_email_safe`, `send_or_enqueue_email_safe`, or `enqueue_email_safe` at `wms/account_request_handlers.py:430`, `wms/account_request_handlers.py:435`, `wms/public_order_handlers.py:94`, `wms/public_order_handlers.py:100`, `wms/order_notifications.py:62`, `wms/order_notifications.py:68`, `wms/signals.py:156`, `wms/signals.py:266`, `wms/signals.py:329`, `wms/signals.py:470`, `wms/events/handlers_notifications.py:48`, `wms/events/handlers_notifications.py:102`, `wms/views_portal_auth.py:197`, `wms/views_volunteer_auth.py:167`, `wms/views_shipment_tracking_access.py:349`, `wms/views_scan_shipments.py:1066`, `wms/pack_handlers.py:192`, `wms/views_volunteer_account_request.py:89`, and `wms/views_volunteer_account_request.py:103`.
- No producer call accepts or passes sender name, sender email, reply-to email, `from_email`, or custom headers.

## 4. Inventory Table

| Area | Evidence | Finding |
|---|---|---|
| Settings source | `asf_wms/settings.py:378-392` | Email backend, SMTP, Brevo API, sender email/name, and reply-to are environment-backed settings. |
| Example env | `.env.example:57-70` | Generic env docs include `DEFAULT_FROM_EMAIL`, SMTP settings, and empty `BREVO_*` sender fields. |
| PythonAnywhere template | `deploy/pythonanywhere/asf-wms.env.template:31-47` | Generic deployment template uses SMTP Brevo fallback and declares `BREVO_SENDER_NAME='ASF WMS'`. |
| MessMed template | `deploy/pythonanywhere/asf-wms.messmed.env.template:22-37` | Current MessMed template is SMTP-only by default but still declares `BREVO_SENDER_NAME='ASF WMS'`. |
| Diagnostic script | `deploy/pythonanywhere/test_email_setup.sh:19-33` | Prints backend, host, API key presence, sender email, and default from email; does not print sender name or reply-to. |
| Installation config | `wms/config/installation.py:84-87` | `InstallationNotifications` currently has only `email_subject_prefix`. |
| Installation identity contact | `wms/config/installation.py:131-136` | Reply-to/sender/default-from emails feed identity contact email only; no notification sender-name field exists. |
| Brevo settings helper | `wms/emailing.py:387-400` | `_brevo_settings()` resolves API key, sender email, sender name, and reply-to at send time. |
| Brevo sender payload | `wms/emailing.py:407-418` | Brevo payload uses `sender: {"email": ..., "name": ...}` and optional `replyTo: {"email": ...}`. |
| SMTP fallback | `wms/emailing.py:460-467` | SMTP uses Django `send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients, ...)`. |
| From header construction | `wms/emailing.py:460-467` | The app does not manually build a `From` header; Django builds it from `from_email`. |
| Reply-to header construction | `wms/emailing.py:415-416` | Reply-to is only constructed for Brevo API as `payload["replyTo"]`. No SMTP reply-to path exists. |
| Subject transport boundary | `wms/emailing.py:128-145`, `wms/emailing.py:450` | PR 2 subject formatting is applied once inside `send_email_safe()` before Brevo/SMTP selection. |
| Queue payload keys | `wms/emailing.py:41-45` | Queue payload keys are `subject`, `message`, `recipient`, `html_message`, and `tags`. |
| Queue payload builder | `wms/emailing.py:367-384` | `_build_enqueue_payload()` serializes subject/message/recipient and optional HTML/tags only. |
| Queue enqueue | `wms/emailing.py:513-528` | `enqueue_email_safe()` persists the payload through the outbox without sender fields. |
| Outbox serialization | `wms/events/outbox.py:16-23` | `enqueue_integration_event()` stores `payload=dict(payload or {})` in `IntegrationEvent`. |
| Queue event model | `wms/models_domain/integration.py:48-59` | `IntegrationEvent.payload` is a JSONField; no sender-specific columns exist. |
| Queue send-time consumer | `wms/emailing.py:313-320` | `_send_event_payload()` reads only subject/message/recipient/html/tags and calls `send_email_safe()`. |
| Queue processing save | `wms/emailing.py:602-613` | Processing mutates queue metadata and status, not sender fields. |
| Job wrapper args | `wms/jobs/email_queue.py:14-31` | Job context stores queue-processing options only, not email sender fields. |
| Management command | `wms/management/commands/process_email_queue.py:47-54` | Command passes processing options to `run_email_queue_job()`, not sender fields. |
| Brevo settings tests | `wms/tests/emailing/tests_emailing_extra.py:142-179` | Tests cover env/settings resolution and fallback sender email; sender name is asserted only as a returned helper value. |
| Brevo payload tests | `wms/tests/emailing/tests_emailing_extra.py:199-241` | Tests assert sender email, subject, content, replyTo, and tags; they currently do not assert `payload["sender"]["name"]`. |
| SMTP tests | `wms/tests/emailing/tests_emailing_extra.py:309-333` | SMTP tests assert `send_mail` receives formatted subject, message, `DEFAULT_FROM_EMAIL`, recipients, and HTML. |
| Queue creation tests | `wms/tests/emailing/tests_emailing.py:19-35` | Queue tests assert recipient and `_queue` metadata; no sender fields. |
| Queue fixture tests | `wms/tests/emailing/tests_emailing.py:177-190`, `wms/tests/emailing/tests_emailing.py:275-288`, `wms/tests/emailing/tests_emailing.py:314-324` | Existing queue fixtures contain subject/message/recipient/_queue only. |
| PR 2 queue compatibility test | `wms/tests/emailing/tests_email_subject_formatting.py:90-111` | Existing queued payloads are processed through `send_email_safe()`, proving send-time subject formatting. |
| Operations docs | `docs/operations.md:89-95`, `docs/operations.md:356-374` | Operations docs list mail env vars and email queue processing; they do not define sender-name semantics. |
| Release checklist | `docs/release_checklist.md:36`, `docs/release_checklist.md:84-89` | Release checks require mail provider env review and queue processing checks. |

Negative findings:

- No runtime usage of `EmailMessage`, `EmailMultiAlternatives`, `mail_admins`, `mail_managers`, or `get_connection` was found.
- No app-level manual `From` header construction was found.
- No SMTP reply-to construction was found.
- No queued email payload, job context, fixture, or test serializes sender name, sender email, or reply-to email.

## 5. Brevo vs SMTP `sender_name` Comparison

| Question | Brevo API path | SMTP/Django path |
|---|---|---|
| Where is it represented? | JSON payload `sender.name` inside the `sender` object. Evidence: `wms/emailing.py:407-408`. | In SMTP, display name would have to be encoded into the `From` header value passed as `from_email`. Current code does not do this. Evidence: `wms/emailing.py:460-467`. |
| Current source | `_brevo_settings()` reads `BREVO_SENDER_NAME` from Django settings or environment. Evidence: `wms/emailing.py:394-395`. | No sender-name source is read. `send_mail()` receives only `settings.DEFAULT_FROM_EMAIL`. Evidence: `wms/emailing.py:463`. |
| Current fallback | If `BREVO_SENDER_NAME` is blank, Brevo receives `sender.name = sender_email`. Evidence: `wms/emailing.py:408`. | If `DEFAULT_FROM_EMAIL` is a bare email, the app sends a bare email address as From. Current env templates use bare emails. Evidence: `.env.example:57`, `deploy/pythonanywhere/asf-wms.env.template:31`, `deploy/pythonanywhere/asf-wms.messmed.env.template:22`. |
| Reply-to | Brevo API receives optional `replyTo.email`. Evidence: `wms/emailing.py:415-416`. | No reply-to is passed to `send_mail()`. Evidence: `wms/emailing.py:460-467`. |
| Current ASF deployment shape | Generic template declares `BREVO_SENDER_NAME='ASF WMS'`; MessMed template declares the same but keeps Brevo API disabled by default. Evidence: `deploy/pythonanywhere/asf-wms.env.template:44-47`, `deploy/pythonanywhere/asf-wms.messmed.env.template:33-37`. | SMTP fallback is configured against `smtp-relay.brevo.com`, but the app passes bare `DEFAULT_FROM_EMAIL`; no display name is set by application code. Evidence: `deploy/pythonanywhere/asf-wms.messmed.env.template:24-31`, `wms/emailing.py:460-467`. |
| Single pre-transport injection feasible? | Not safely for PR 3. Brevo sender name is a JSON field. | Not safely for PR 3. SMTP sender name would require altering `from_email`/From header formatting, which is a visible behavior change and outside scope. |

Verdict: per-transport handling is required. PR 3 should inject/configure `email_sender_name` only where the Brevo `sender.name` payload is built or resolved. It should leave SMTP `from_email` behavior unchanged.

## 6. Queue Payload Analysis

Actual queue payload structure:

```json
{
  "subject": "...",
  "message": "...",
  "recipient": ["..."],
  "html_message": "... optional ...",
  "tags": ["... optional ..."],
  "_queue": {
    "attempts": 0,
    "next_attempt_at": null
  }
}
```

Evidence:

- `wms/emailing.py:41-45` defines the queue payload keys.
- `wms/emailing.py:367-384` builds the serialized payload.
- `wms/emailing.py:520-528` adds `_queue` metadata and stores the event.
- `wms/events/outbox.py:16-23` persists `payload=dict(payload or {})`.
- `wms/tests/emailing/tests_emailing.py:19-35` tests the persisted queue event.
- `wms/tests/emailing/tests_emailing.py:177-190`, `wms/tests/emailing/tests_emailing.py:275-288`, and `wms/tests/emailing/tests_emailing.py:314-324` are queued-event fixtures with no sender fields.
- `wms/tests/emailing/tests_emailing_extra.py:337-366` proves optional `html_message` and `tags` are the only optional email content fields currently serialized.

Queue producer and consumer behavior:

- `enqueue_email_safe()` captures subject/message/recipient/html/tags at enqueue time. Evidence: `wms/emailing.py:501-528`.
- `_send_event_payload()` resolves only those serialized fields and calls `send_email_safe()`. Evidence: `wms/emailing.py:313-320`.
- `send_email_safe()` resolves transport details at send time. Evidence: `wms/emailing.py:440-467`.
- Therefore sender name is currently resolved at send time, not enqueue time.
- Adding `installation.notifications.email_sender_name` does not require migration of queued payloads if PR 3 keeps sender-name resolution in the transport layer.
- Adding it does not require queue payload structure changes.

## 7. PR 2 Idempotence Rationale Applicability

PR 2 subject formatting rationale applies partially to `sender_name`.

Applies:

- Transport-side resolution protects already queued email payloads.
- No queue migration is required.
- Business producers can remain unchanged.
- Direct sends, queued sends, and `direct_only` sends continue to converge through `send_email_safe()`.

Does not apply:

- There is no sender-name string in producer payloads to double-prefix or double-apply.
- Sender name is a transport identity field, not a message content field.
- Idempotence logic like `format_email_subject()` is unnecessary.

Conclusion: keep the same transport-boundary discipline as PR 2, but do not model sender-name handling as idempotent formatting.

## 8. Risk Assessment

### `sender_name`

Risk: low to medium.

- Display-name-only change for the Brevo API path.
- No SPF, DKIM, or DMARC domain-alignment impact by itself.
- Main risk is user trust: a misleading display name can confuse recipients or partners.
- SMTP currently does not consume this value; changing SMTP display names would be a separate visible behavior change.
- For PR 3, default `ASF WMS` matches current ASF Brevo sender display-name intent in deployment templates.

### `sender_email`

Risk: high.

- Changes the message `From` identity and sender domain.
- SPF must authorize the sending provider for the sender domain.
- DKIM signing must be configured for the sender domain or an aligned subdomain.
- DMARC alignment can fail if the visible From domain does not align with DKIM/SPF authenticated domains.
- Brevo generally requires sender or domain authentication before reliable use.
- Arbitrary client-level sender domains could damage deliverability or cause spoofing-like failures.

### `reply_to_email`

Risk: medium.

- Reply-to does not usually define the authenticated From domain and has different SPF/DKIM/DMARC risk from sender email.
- It still controls where operational replies and potentially personal data are routed.
- A wrong reply-to can leak partner or recipient information, break support workflows, or reduce trust.
- Brevo API supports a separate `replyTo.email` today in this code path; SMTP does not currently set reply-to.

## 9. Future Prerequisites Checklist For `sender_email`

- Define allowed sender domains per installation.
- Prove the sender domain is owned or explicitly authorized by the client/organization.
- Authenticate the sender domain or exact sender in Brevo before use.
- Configure SPF so the provider used by ASF-WMS is authorized to send for the sender domain.
- Configure DKIM for the sender domain or an aligned subdomain.
- Configure and verify DMARC policy and alignment for the visible From domain.
- Verify behavior for both Brevo API and SMTP fallback paths before enabling.
- Decide whether `DEFAULT_FROM_EMAIL`, `BREVO_SENDER_EMAIL`, and installation config remain separate or become one canonical sender-email source.
- Add operational documentation for DNS setup, validation, rollback, and failure diagnostics.
- Add tests that prove unauthenticated or blank sender domains cannot silently become active.
- Add a sandbox/manual send checklist that inspects real headers for SPF, DKIM, and DMARC pass/alignment.

## 10. Future Prerequisites Checklist For `reply_to_email`

- Define the reply mailbox per installation.
- Confirm the mailbox exists, is monitored, and has an operational owner.
- Confirm the domain is owned or authorized by the client/organization.
- Document that reply-to can route personal or operational data outside ASF inboxes.
- Validate Brevo API acceptance of the configured `replyTo.email`.
- Decide how SMTP should represent reply-to, since current `send_mail()` usage does not set it.
- Add tests for Brevo `replyTo` payload construction and, if SMTP is added later, SMTP reply-to header construction.
- Keep reply-to configuration separate from sender email; do not use reply-to as a substitute for SPF/DKIM/DMARC sender authentication.
- Update privacy/RGPD operational docs if replies may route to a new organization mailbox.
- Add rollback guidance for misrouted replies.

## 11. Recommended PR 3 Implementation Shape

Likely files to change:

- `wms/config/installation.py`
- `wms/emailing.py`
- `wms/tests/config/tests_installation_config.py`
- `wms/tests/emailing/tests_emailing_extra.py` or a focused new sender-name test file under `wms/tests/emailing/`
- `docs/repo-reference/04-shared-contracts/08-installation-config.md`

Do not change:

- settings files
- queue payload formats
- business email producers
- SMTP sender behavior
- sender email behavior
- reply-to behavior

Recommended call site:

- Add `InstallationNotifications.email_sender_name`.
- Build it under `notifications.*`, not under a nested `notifications.email.*` object.
- Default to `ASF WMS`.
- Prefer deriving the config field from existing `BREVO_SENDER_NAME` when present, with `ASF WMS` as the ASF-compatible default.
- Read the value in `wms/emailing.py` at the Brevo sender-name resolution point, either in `_brevo_settings()` or immediately before the Brevo payload is constructed.
- Leave `send_mail(..., settings.DEFAULT_FROM_EMAIL, ...)` unchanged.

Recommended resolution model:

```python
def resolve_email_sender_name() -> str:
    return str(get_installation_config().notifications.email_sender_name or "").strip()
```

Then Brevo construction remains conceptually:

```python
sender_name = resolve_email_sender_name()
payload["sender"] = {
    "email": sender_email,
    "name": sender_name or sender_email,
}
```

Resolve separately inside the Brevo path. Do not resolve once and force it onto both Brevo and SMTP because SMTP would require From-header formatting and is out of scope.

## 12. Helper Decision

PR 3 should introduce a small helper, but not an idempotent formatter.

Recommended helper: `resolve_email_sender_name() -> str`.

Rationale:

- It mirrors PR 2's transport-boundary pattern without pretending sender-name idempotence exists.
- It keeps direct installation-config access out of payload construction details.
- It gives tests a narrow pure function to assert default and override behavior.
- It leaves `_send_with_brevo()` focused on provider payload construction.
- It avoids spreading direct `get_installation_config().notifications.email_sender_name` access.

Inline access would work because there is currently only one runtime consumer, but the helper is the smallest maintainable pattern if PR 3 is meant to establish the next controlled notification configuration field.

## 13. Proposed Test Plan

- Config default test: `get_installation_config().notifications.email_sender_name == "ASF WMS"`.
- Config override test: an override of existing sender-name input, likely `BREVO_SENDER_NAME`, is reflected in `installation.notifications.email_sender_name`.
- Helper test: `resolve_email_sender_name()` returns the installation value.
- Brevo payload test: `_send_with_brevo()` includes `payload["sender"]["name"] == "ASF WMS"` by default and a client value when overridden/mocked.
- Existing Brevo payload test should add an explicit assertion for `payload["sender"]["name"]`; current test asserts sender email and reply-to but not name.
- SMTP regression test: `send_mail()` still receives `settings.DEFAULT_FROM_EMAIL` as the third argument, with no display-name formatting.
- Queue compatibility test: an existing queued payload with only subject/message/recipient/_queue processes successfully and resolves sender name at send time.
- Direct-only regression test if using existing coverage: `EMAIL_DELIVERY_MODE=direct_only` still bypasses queue and does not serialize sender fields.

## 14. Explicit Non-Goals

- Do not implement `email_sender_email`.
- Do not implement `email_reply_to_email`.
- Do not alter sender email behavior.
- Do not alter reply-to behavior.
- Do not alter business email producers.
- Do not alter queued payload formats.
- Do not refactor the email layer.
- Do not change visible behavior for the default ASF installation.
- Do not introduce nested `notifications.email.*` configuration.

## 15. Open Questions

No blocking open questions.

Implementation PR should explicitly confirm one policy choice before coding: `installation.notifications.email_sender_name` should continue to honor existing `BREVO_SENDER_NAME` as the deployment override source, while moving runtime consumption through installation config.

## 16. Documentation Impact Check

This audit creates the requested report only. No runtime behavior, roles, permissions, core workflows, queue payload contracts, settings, or installation config were changed.

For the future implementation PR, `docs/repo-reference/04-shared-contracts/08-installation-config.md` should be updated because a new installation notification field and runtime consumer will be added.
