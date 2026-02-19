# Operations Runbook

This runbook is for day-to-day operations, releases, and incident handling.

## 0) Quality gate (mandatory)

Before any production deployment, run the full gate:

```bash
python manage.py check
python manage.py check --deploy --fail-level WARNING
python manage.py makemigrations --check --dry-run
python manage.py test
ruff check .
bandit -r asf_wms api contacts wms -x "wms/migrations,contacts/migrations,wms/tests,api/tests,contacts/tests"
```

Reference audit: `docs/audit_2026-02-19.md`.

Current priority from the audit:

- stabilize regression suite (tests must be green before release)
- avoid shipping with uncommitted migrations/static assets
- keep production environment variables aligned with `.env.example`
- run contact destination scope audit before release:
  - `python manage.py audit_contact_destinations`
  - `python manage.py audit_contact_destinations --apply` (if inconsistencies detected)
- keep importing models through `wms.models` (facade), model sources live in `wms/models_domain/`

## 1) Environment baseline

Start from `.env.example` and adapt values for each environment.

Set at minimum:

- `DJANGO_SECRET_KEY` (strong random key)
- `DJANGO_DEBUG=false`
- `DJANGO_ALLOWED_HOSTS` (comma-separated)
- `SITE_BASE_URL` (absolute public base URL)
- `ENABLE_BASIC_AUTH=false` in production unless explicitly needed

Security-related values (recommended in production):

- `SECURE_SSL_REDIRECT=true`
- `SESSION_COOKIE_SECURE=true`
- `CSRF_COOKIE_SECURE=true`
- `USE_PROXY_SSL_HEADER=true` (if reverse proxy terminates TLS)
- `CSRF_TRUSTED_ORIGINS=https://your-domain`
- `SECURE_HSTS_SECONDS=31536000`
- `SECURE_HSTS_INCLUDE_SUBDOMAINS=true`
- `SECURE_HSTS_PRELOAD=true`

Mail and queue values:

- `DEFAULT_FROM_EMAIL`
- `EMAIL_BACKEND` (console backend is default/fallback)
- `BREVO_API_KEY` and related `BREVO_*` vars (optional)
- `EMAIL_QUEUE_MAX_ATTEMPTS` (default `5`)
- `EMAIL_QUEUE_RETRY_BASE_SECONDS` (default `60`)
- `EMAIL_QUEUE_RETRY_MAX_SECONDS` (default `3600`)
- `EMAIL_QUEUE_PROCESSING_TIMEOUT_SECONDS` (default `900`)

Integration/security values:

- `INTEGRATION_API_KEY` (required for API key-based integration access)
- `ACCOUNT_REQUEST_THROTTLE_SECONDS` (default `300`)
- `PUBLIC_ORDER_THROTTLE_SECONDS` (default `300`)

## 2) Pre-deploy checklist

From repo root:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
make check
make migrate-check
make deploy-check
make lint
make typecheck
make bandit
make coverage
make audit
```

`make typecheck` is intentionally scoped to selected core modules defined in `mypy.ini`.

Notes:

- `pip-audit` may fail in restricted/offline environments; this is informational in CI.
- If `pip-audit` fails locally due network, keep deployment gate on tests/lint/deploy-check and rerun audit when network is available.

## 3) Deploy sequence

```bash
git pull origin main
python -m pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy --fail-level WARNING
```

Then restart the app process (systemd, supervisor, platform-specific service).

## 4) Post-deploy smoke tests

Replace `BASE_URL`:

```bash
BASE_URL="https://your-domain"
curl -I "$BASE_URL/"
curl -I "$BASE_URL/admin/login/"
curl -I "$BASE_URL/scan/"
curl -I "$BASE_URL/scan/shipments-ready/"
curl -I "$BASE_URL/scan/shipments-tracking/"
curl -I "$BASE_URL/api/v1/products/"
```

Validate:

- No unexpected 500 responses.
- Admin login page loads.
- Scan and API routes answer (auth-protected routes may return `302/401/403`, which is acceptable).
- Shipment views load for staff users after authentication.

## 5) Email queue operations

Queue processor command:

```bash
python manage.py process_email_queue --limit=100
python manage.py process_email_queue --include-failed --limit=100
```

Suggested cron (every minute):

```cron
* * * * * cd /path/to/asf-wms && /path/to/asf-wms/.venv/bin/python manage.py process_email_queue --limit=100 >> /var/log/asf-wms-email-queue.log 2>&1
```

Queue health snapshot:

```bash
python manage.py shell -c "from wms.models import IntegrationEvent, IntegrationDirection; qs=IntegrationEvent.objects.filter(direction=IntegrationDirection.OUTBOUND, source='wms.email', event_type='send_email'); print({s: qs.filter(status=s).count() for s in ['pending','processing','processed','failed']})"
```

Recent failed events:

```bash
python manage.py shell -c "from wms.models import IntegrationEvent, IntegrationDirection, IntegrationStatus; qs=IntegrationEvent.objects.filter(direction=IntegrationDirection.OUTBOUND, source='wms.email', event_type='send_email', status=IntegrationStatus.FAILED).order_by('-created_at')[:20]; print(list(qs.values('id','created_at','processed_at','error_message')))"
```

## 6) Incident playbooks

### A) Queue backlog growing

1. Run `process_email_queue` manually with `--limit=500`.
2. Check failed-event errors (command above).
3. Validate SMTP/Brevo credentials and network egress.
4. Temporarily increase retry tuning (`EMAIL_QUEUE_*`) if provider latency is high.

### B) Many failed events after release

1. Verify env vars (`EMAIL_*`, `BREVO_*`, `DEFAULT_FROM_EMAIL`).
2. Replay failed events with `--include-failed`.
3. If still failing, rollback release and replay queue once stable.

### C) Deployment checks failing

1. `python manage.py check --deploy --fail-level WARNING`
2. Fix security/env mismatch before opening traffic.
3. Re-run smoke tests after fix.

## 7) Backup and restore basics

SQLite:

```bash
sqlite3 db.sqlite3 ".backup 'db-backup.sqlite3'"
```

MySQL:

```bash
mysqldump -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p "$DB_NAME" > asf_wms.sql
```

Restore MySQL:

```bash
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p "$DB_NAME" < asf_wms.sql
```

## 8) Recurring maintenance

Weekly:

- Run full test + coverage and security checks.
- Review open failed email events and oldest pending items.

Monthly:

- Refresh dependencies (`pip list --outdated`).
- Re-run `pip-audit` and review vulnerabilities.
- Run `python manage.py normalize_wms_text` if data normalization drift appears.

## 9) Shipment and carton status rules

### Carton statuses

- `draft` (Creation): carton created.
- `picking` (Preparation): filling in progress.
- `packed` (Pret): carton ready to be assigned.
- `assigned` (Affecte): linked to a shipment.
- `labeled` (Etiquette): explicit action, carton ready for departure.
- `shipped` (Expedie): shipment reached `boarding_ok`.

### Carton transition rules

- Assigning a `packed` carton to a shipment sets status to `assigned`.
- Packing directly with a shipment sets carton to `assigned`.
- Packing without shipment moves `draft` -> `picking`.
- Removing a carton from shipment:
  - if carton is `assigned` or `labeled`, it returns to `packed`.
  - if carton is `shipped`, removal is blocked.
- Manual status update (`draft`/`picking`/`packed`) is allowed only for cartons not assigned to a shipment.
- Labeling is explicit from Vue Colis (`mark_carton_labeled` action).
- "Remove label" (`mark_carton_assigned`) is available before shipment lock.

### Shipment statuses

- `draft` (Creation): initial state, including temporary drafts (`EXP-TEMP-XX`).
- `picking` (En cours): not all cartons are labeled yet.
- `packed` (Pret): all cartons are labeled.
- `planned` (Planifie): planning locked state.
- `shipped` (Expedie): boarding confirmed.
- `received_correspondent` (Recu escale): correspondent reception confirmed.
- `delivered` (Livre): final recipient reception confirmed.

### Shipment transition rules

- Automatic readiness sync:
  - if all cartons are labeled (or shipped), shipment becomes `packed`.
  - otherwise shipment stays/returns `picking`.
  - if no carton is linked, shipment is `draft`.
- Tracking steps drive advanced statuses:
  - `planning_ok` => shipment `packed`
  - `planned` and `moved_export` => shipment `planned`
  - `boarding_ok` => shipment `shipped`
  - `received_correspondent` => shipment `received_correspondent`
  - `received_recipient` => shipment `delivered`
- Once `planned`, carton modifications are locked.
- Temporary references (`EXP-TEMP-XX`) are automatically promoted to final references when shipment leaves `draft`.

### Dispute overlay (`is_disputed`)

- Dispute is a flag, not a separate status.
- It can be set from tracking screen at any time.
- While disputed, tracking progression is blocked.
- Resolving dispute resets shipment to `packed` ("Pret"), allowing replanning.
- If shipment had reached shipped/received stages, shipped cartons are reset back to `labeled`.

## 10) Shipment creation contact scoping rules

Rules implemented in the "Creer une expedition" form:

- Destination is mandatory to continue.
- Shipper list:
  - contacts tagged `Expediteur`
  - destination match (`contact.destinations` contains selected destination) OR global (`destinations` empty).
- Recipient list:
  - contacts tagged `Destinataire`
  - linked shipper match (`linked_shippers` contains selected shipper) OR global (`linked_shippers` empty).
- Correspondent list:
  - contacts tagged `Correspondant` with destination match/global
  - then restricted to destination correspondent when `Destination.correspondent_contact` is set.
  - if destination has no configured correspondent, the correspondent list is empty.

Additional contact governance:

- Recipient creation requires at least one linked shipper.
- Default shipper `AVIATION SANS FRONTIERES` is auto-added to recipients when available.

## 11) Tracking board and case closure

`/scan/shipments-tracking/` shows shipments in:

- `planned`
- `shipped`
- `received_correspondent`
- `delivered`

Board features:

- Week filter (`planned_week`) based on `planned` tracking timestamp.
- Closed-case filter (`exclude` by default, `all` optional).
- Columns: planned, boarding OK, shipped, received correspondent, delivered timestamps.

Case closure rules:

- "Clore le dossier" becomes active only when:
  - shipment status is `delivered`
  - all required tracking timestamps are present
  - `is_disputed` is false
  - shipment is not already closed
- Closure writes `closed_at` and `closed_by`.
