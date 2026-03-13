# Operations Runbook

This runbook is for day-to-day operations, releases, and incident handling.

## 0) Quality gate (mandatory)

Before any production deployment, run the full gate:

```bash
uv sync --frozen
make pre-commit
make ci
```

Emergency fallback if `uv sync --frozen` is blocked on the machine:

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
make pre-commit
make ci
```

Tooling roles:

- `make typecheck` is the blocking type gate.
- `make typecheck-pyright` is an informational shadow signal.
- `make export-requirements` regenerates `requirements.txt` and `requirements-dev.txt` from `uv.lock`.
- `SKIP=<hook-id> git commit ...` is acceptable only as a temporary local escape hatch while fixing a false positive; do not remove the hook from CI without investigation.
- Keep `mypy` as the release gate even if `pyright` becomes noisy.

Reference audit: `docs/audit_2026-02-19.md`.

Current priority from the audit:

- stabilize regression suite (tests must be green before release)
- avoid shipping with uncommitted migrations/static assets
- keep production environment variables aligned with `.env.example`
- run contact destination scope audit before release:
  - `python manage.py audit_contact_destinations`
  - `python manage.py audit_contact_destinations --apply` (if inconsistencies detected)
- keep importing models through `wms.models` (facade), model sources live in `wms/models_domain/`
- scan shipment page helpers are in `wms/views_scan_shipments_support.py` (public view endpoints remain in `wms/views_scan_shipments.py`)
- part of Django admin registrations is now hosted in `wms/admin_misc.py`
- legacy shipment tracking by reference can be disabled with `ENABLE_SHIPMENT_TRACK_LEGACY=false`

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
- `TRUSTED_PROXY_IPS` (comma-separated proxy IPs allowed to provide `X-Forwarded-For`)
- `DOCUMENT_SCAN_BACKEND=clamav` (or `noop` for local/dev only)
- `DOCUMENT_SCAN_CLAMAV_COMMAND=clamscan`
- `DOCUMENT_SCAN_TIMEOUT_SECONDS=30`
- `DOCUMENT_SCAN_QUEUE_PROCESSING_TIMEOUT_SECONDS=900`
- `CSRF_TRUSTED_ORIGINS=https://your-domain`
- `SECURE_HSTS_SECONDS=31536000`
- `SECURE_HSTS_INCLUDE_SUBDOMAINS=true`
- `SECURE_HSTS_PRELOAD=true`

Mail and queue values:

- `DEFAULT_FROM_EMAIL`
- `EMAIL_BACKEND` (console backend is default/fallback)
- `EMAIL_DELIVERY_MODE` (default `direct_or_queue`; set `direct_only` on PythonAnywhere if no scheduler is available)
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
uv sync --frozen
pre-commit install
make pre-commit
make ci
```

Fallback when `uv` is unavailable or native `mysqlclient` prerequisites are missing:

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
make pre-commit
make ci
```

`make ci` is the global verification gate for local release readiness.
`make typecheck` is intentionally scoped to selected core modules defined in `mypy.ini` and remains blocking.
`make typecheck-pyright` mirrors this critical-module scope through `pyrightconfig.json` and remains informational until a longer green period proves it is stable.
`make coverage` is the source of truth for the coverage gate (`COVERAGE_FAIL_UNDER`, default `93`) and excludes paused Next/frontend tags by default.
`make deploy-check-prod-like` sources `.env.deploy.example` (or `DEPLOY_ENV_FILE=...`) to run a reproducible local deploy check profile.

Notes:

- `make audit-soft` always writes `pip-audit-report.json`; if `pypi.org` is unreachable, the report contains an explicit skip reason.
- `make audit` remains the strict command (network required) for a full local vulnerability run.
- After editing dependencies, run `make lock` then `make export-requirements` to avoid drift between `uv.lock` and exported requirements files.

### 2.1) Smoke scope policy

Do not try to cover every user journey with smoke tests.

Use smoke checks only for nominal, cross-layer chains that prove the app is still wired correctly after a change. In this repo, the reference CI smoke guards are:

- `api.tests.tests_ui_e2e_workflows`
- `wms.tests.emailing.tests_email_flows_e2e`
- `wms.tests.planning.tests_smoke_planning_flow`

Add a new CI smoke only when a new critical chain spans multiple layers and existing unit, integration, and view tests would not catch a wiring regression. Keep user variants, error branches, and detailed business rules in the targeted test suites instead of duplicating them in smoke coverage.

## 3) Deploy sequence

```bash
git pull origin main
python -m pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py compilemessages -v 1
python manage.py collectstatic --noinput
python manage.py check --deploy --fail-level WARNING
```

Then restart the app process (systemd, supervisor, platform-specific service).

`compilemessages` is required whenever translation catalogs changed under `locale/`.
Django serves compiled `.mo` files at runtime, so deploying updated `.po` files without recompiling leaves the UI on old translations.

Run the document scan worker regularly (cron/systemd timer):

```bash
python manage.py process_document_scan_queue --limit=200
```

### 3.0) Tooling rollback

If the standardized Python tooling blocks a release or hotfix:

1. Fallback to `pip install -r requirements.txt && pip install -r requirements-dev.txt`.
2. Keep `make typecheck` as the blocking type gate; treat `make typecheck-pyright` as informational noise until tuned.
3. If a local `pre-commit` hook is a false positive, bypass it temporarily with `SKIP=<hook-id> git commit ...` and fix the hook or baseline immediately after.
4. If dependency artifacts drift, regenerate with `make export-requirements` from the committed `uv.lock`.

### 3.0) Scan Bootstrap progressive rollout (`SCAN_BOOTSTRAP_ENABLED`)

Goal: keep production usable while activating Bootstrap progressively on `/scan/*`.

1. Staging activation:
   - set `SCAN_BOOTSTRAP_ENABLED=true` in staging env
   - run `python manage.py collectstatic --noinput`
   - restart app
2. Staging smoke:
   - `/scan/stock/`
   - `/scan/shipment/create/`
   - verify no JS regression on dynamic sections (`shipment-form`, `shipment-lines`)
3. Production activation:
   - set `SCAN_BOOTSTRAP_ENABLED=true` in prod env
   - run `python manage.py collectstatic --noinput`
   - restart app
4. Immediate rollback:
   - set `SCAN_BOOTSTRAP_ENABLED=false`
   - restart app

Notes:
- Bootstrap assets are loaded from jsDelivr CDN only when the flag is enabled.
- Local bridge stylesheet remains `wms/static/scan/scan-bootstrap.css`.

### 3.1) Next static export (PythonAnywhere low-disk flow)

When `frontend-next` is hosted by Django under `/app/*`, deploy only `frontend-next/out`.

Preferred path (local build + sync):

```bash
PA_SSH_TARGET="youruser@ssh.pythonanywhere.com" \
PA_PROJECT_DIR="/home/youruser/asf-wms" \
deploy/pythonanywhere/push_next_export.sh
```

Fallback path (artifact build in GitHub Actions):

1. Run workflow `.github/workflows/frontend-next-export.yml` (`workflow_dispatch`).
2. Download `next-export-<sha>.tar.gz`.
3. Upload archive to PythonAnywhere.
4. Install:

```bash
PROJECT_DIR="/home/youruser/asf-wms" \
deploy/pythonanywhere/install_next_export.sh /home/youruser/next-export-<sha>.tar.gz
```

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
- Always-on authenticated smoke:
  - validate shipment create sequencing (`destination -> expéditeur -> destinataire/correspondant -> détails`)
  - validate "Enregistrer en brouillon" and confirm the `EXP-TEMP-XX` draft appears in Vue Expéditions
  - validate one tracking or close action on an existing shipment
- Conditional smoke based on release scope:
  - if `portal` changed, validate portal login plus one nominal order or recipient update flow
  - if `planning` changed, validate cockpit/version access on an existing run and artifact visibility/download when relevant
  - if `billing` changed, validate one nominal billing preview/export or payment/correction flow

## 5) Email queue operations

If `EMAIL_DELIVERY_MODE=direct_only`, the email queue is bypassed for application sends and these operations are only useful for historical backlog cleanup or non-production environments.

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

Processing events stuck beyond timeout:

```bash
python manage.py shell -c "from django.conf import settings; from django.utils import timezone; from datetime import timedelta; from wms.models import IntegrationEvent, IntegrationDirection, IntegrationStatus; timeout=max(1,int(getattr(settings,'EMAIL_QUEUE_PROCESSING_TIMEOUT_SECONDS',900))); cutoff=timezone.now()-timedelta(seconds=timeout); qs=IntegrationEvent.objects.filter(direction=IntegrationDirection.OUTBOUND, source='wms.email', event_type='send_email', status=IntegrationStatus.PROCESSING, processed_at__lte=cutoff); print({'timeout_seconds': timeout, 'stale_processing': qs.count()})"
```

## 6) Document scan queue operations

Queue processor command:

```bash
python manage.py process_document_scan_queue --limit=100
python manage.py process_document_scan_queue --include-failed --limit=100
# Runtime readiness check (strict production profile)
python manage.py check_document_scan_runtime --max-failed=0 --max-stale-processing=0
# Make shortcut
make scan-queue-runtime-check
# Dev-only (if ClamAV is intentionally unavailable locally)
DOCUMENT_SCAN_BACKEND=noop python manage.py check_document_scan_runtime --allow-noop
```

Suggested cron (every minute):

```cron
* * * * * cd /path/to/asf-wms && /path/to/asf-wms/.venv/bin/python manage.py process_document_scan_queue --limit=100 >> /var/log/asf-wms-document-scan-queue.log 2>&1
```

Queue health snapshot:

```bash
python manage.py shell -c "from wms.document_scan_queue import DOCUMENT_SCAN_QUEUE_EVENT_TYPE, DOCUMENT_SCAN_QUEUE_SOURCE; from wms.models import IntegrationDirection, IntegrationEvent; qs=IntegrationEvent.objects.filter(direction=IntegrationDirection.OUTBOUND, source=DOCUMENT_SCAN_QUEUE_SOURCE, event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE); print({s: qs.filter(status=s).count() for s in ['pending','processing','processed','failed']})"
```

Recent failed events:

```bash
python manage.py shell -c "from wms.document_scan_queue import DOCUMENT_SCAN_QUEUE_EVENT_TYPE, DOCUMENT_SCAN_QUEUE_SOURCE; from wms.models import IntegrationDirection, IntegrationEvent, IntegrationStatus; qs=IntegrationEvent.objects.filter(direction=IntegrationDirection.OUTBOUND, source=DOCUMENT_SCAN_QUEUE_SOURCE, event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE, status=IntegrationStatus.FAILED).order_by('-created_at')[:20]; print(list(qs.values('id','created_at','processed_at','error_message','payload')))"
```

Processing events stuck beyond timeout:

```bash
python manage.py shell -c "from datetime import timedelta; from django.conf import settings; from django.utils import timezone; from wms.document_scan_queue import DOCUMENT_SCAN_QUEUE_EVENT_TYPE, DOCUMENT_SCAN_QUEUE_SOURCE; from wms.models import IntegrationDirection, IntegrationEvent, IntegrationStatus; timeout=max(1,int(getattr(settings,'DOCUMENT_SCAN_QUEUE_PROCESSING_TIMEOUT_SECONDS',900))); cutoff=timezone.now()-timedelta(seconds=timeout); qs=IntegrationEvent.objects.filter(direction=IntegrationDirection.OUTBOUND, source=DOCUMENT_SCAN_QUEUE_SOURCE, event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE, status=IntegrationStatus.PROCESSING, processed_at__lte=cutoff); print({'timeout_seconds': timeout, 'stale_processing': qs.count()})"
```

PythonAnywhere helpers:

```bash
./deploy/pythonanywhere/process_document_scan_queue.sh
INCLUDE_FAILED=true ./deploy/pythonanywhere/process_document_scan_queue.sh
./deploy/pythonanywhere/flush_document_scan_queue.sh active
```

`flush_document_scan_queue.sh all` deletes all scan events and must be reserved for emergency cleanup.

## 7) Observability dashboard

Main view: `/scan/dashboard/`

Operational cards added for phase 3:

- Queue email: pending, processing, failed, stale-processing timeout.
- Blocages workflow (>72h): expéditions anciennes non sorties du flux, commandes validées sans expédition, dossiers livrés non clos, litiges ouverts.
- SLA suivi:
  - Planifié -> OK mise à bord
  - OK mise à bord -> Reçu escale
  - Reçu escale -> Livré
  - Planifié -> Livré
  - each card displays `breaches / completed segments`.

## 8) Structured workflow logs

Workflow transitions are emitted on logger `wms.workflow` as JSON messages:

- carton status transition
- shipment status transition
- shipment dispute set/resolved
- tracking event creation
- shipment case closure

If your platform supports log filtering, filter by logger name `wms.workflow` and parse JSON fields (`event_type`, `shipment.reference`, `previous_status`, `new_status`).

## 9) Incident playbooks

### A) Queue backlog growing

1. Run `process_email_queue` manually with `--limit=500`.
2. Check failed-event errors (command above).
3. Validate SMTP/Brevo credentials and network egress.
4. Temporarily increase retry tuning (`EMAIL_QUEUE_*`) if provider latency is high.

### B) Document scan queue backlog or failures

1. Verify env vars (`DOCUMENT_SCAN_*`) and ensure `DOCUMENT_SCAN_BACKEND=clamav` in production.
2. Run `python manage.py check_document_scan_runtime --max-failed=0 --max-stale-processing=0`.
3. Run `python manage.py process_document_scan_queue --include-failed --limit=500`.
4. Validate ClamAV availability (`clamscan --version`) and host PATH for the app process.
5. If failures persist, keep infected downloads blocked, switch to incident mode, and purge only active queue events once root cause is fixed.

### C) Many email failed events after release

1. Verify env vars (`EMAIL_*`, `BREVO_*`, `DEFAULT_FROM_EMAIL`).
2. Replay failed events with `--include-failed`.
3. If still failing, rollback release and replay queue once stable.

### D) Deployment checks failing

1. `python manage.py check --deploy --fail-level WARNING`
2. Fix security/env mismatch before opening traffic.
3. Re-run smoke tests after fix.

### E) Workflow blockages increasing (>72h)

1. Open `/scan/dashboard/` and review "Blocages workflow".
2. Resolve oldest "Cmd validées sans expédition >72h" from `/scan/orders/`.
3. Resolve stale shipment drafts/picking from `/scan/shipments-ready/`.
4. Review delivered-but-open cases in `/scan/shipments-tracking/` and close valid dossiers.

### F) SLA breaches rising

1. Open `/scan/dashboard/` and review "Suivi SLA" cards.
2. Cross-check delayed shipments in `/scan/shipments-tracking/` (planned/shipped/received statuses).
3. Prioritize shipments with no progression and open litiges.
4. Export weekly ops review with breach counts by segment.

## 10) Backup and restore basics

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

## 11) Recurring maintenance

Weekly:

- Run full test + coverage and security checks.
- Review open failed email events and oldest pending items.
- Review failed/stale document scan queue events and backlog size.

Monthly:

- Refresh dependencies (`pip list --outdated`).
- Re-run `pip-audit` and review vulnerabilities.
- Run `python manage.py normalize_wms_text` if data normalization drift appears.

## 12) Shipment and carton status rules

### Carton statuses

- `draft` (Creation): carton created.
- `picking` (Preparation): filling in progress.
- `packed` (Pret): carton ready to be assigned.
- `assigned` (Affecte): linked to a shipment.
- `labeled` (Étiquette): explicit action, carton ready for departure.
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

## 12) Shipment creation contact scoping rules

Rules implemented in the "Créer une expédition" form:

- Destination is mandatory to continue.
- Shipper list:
  - contacts tagged `Expéditeur`
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

## 13) Tracking board and case closure

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
