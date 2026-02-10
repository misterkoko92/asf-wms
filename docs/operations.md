# Operations Runbook

This runbook is for day-to-day operations, releases, and incident handling.

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
curl -I "$BASE_URL/api/v1/products/"
```

Validate:

- No unexpected 500 responses.
- Admin login page loads.
- Scan and API routes answer (auth-protected routes may return `302/401/403`, which is acceptable).

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
