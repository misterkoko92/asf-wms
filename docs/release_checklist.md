# Release Checklist

Use this checklist for each production release.

## A) Before merge

- [ ] `uv sync --frozen`
- [ ] `pre-commit install`
- [ ] `make pre-commit`
- [ ] `make ci`
- [ ] `make typecheck` is green and remains the blocking type gate.
- [ ] `make typecheck-pyright` reviewed as informational only.
- [ ] `make export-requirements` re-run after any dependency change.

Fallback if `uv` is blocked locally:

- [ ] `python -m pip install -r requirements.txt`
- [ ] `python -m pip install -r requirements-dev.txt`
- [ ] `make pre-commit`
- [ ] `make ci`

## B) Before deploy

- [ ] Confirm production env vars are set (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS`, `SITE_BASE_URL`, security flags).
- [ ] Validate env values against `.env.example` baseline.
- [ ] Confirm mail provider env vars (`EMAIL_*` and/or `BREVO_*`).
- [ ] Confirm document scan env vars (`DOCUMENT_SCAN_BACKEND=clamav`, `DOCUMENT_SCAN_CLAMAV_COMMAND`, queue timeout settings).
- [ ] Ensure ClamAV binary is available on host (`clamscan --version`).
- [ ] Confirm `INTEGRATION_API_KEY` for integration endpoints.
- [ ] Confirm backup available (SQLite file or MySQL dump).
- [ ] If scan frontend assets changed (`wms/static/scan/scan.js`, `wms/static/scan/scan.css`, manifest/icon), bump `CACHE_NAME` in `wms/views_scan_misc.py` (`wms-scan-vNN`).

## C) Deploy

- [ ] `git pull origin main`
- [ ] `python -m pip install -r requirements.txt`
- [ ] `python manage.py migrate --noinput`
- [ ] `python manage.py compilemessages -v 1`
- [ ] `python manage.py collectstatic --noinput`
- [ ] If `/app/*` changed, push updated `frontend-next/out` (see `deploy/pythonanywhere/push_next_export.sh`).
- [ ] `python manage.py check --deploy --fail-level WARNING`
- [ ] Restart app service/process

Notes:

- [ ] If `locale/en/LC_MESSAGES/django.po` or `locale/fr/LC_MESSAGES/django.po` changed, `compilemessages` is mandatory on the deploy host before app reload. Django uses compiled `.mo` catalogs at runtime, not raw `.po` files.

## D) After deploy

- [ ] Smoke test `GET /`, `/admin/login/`, `/scan/`, `/scan/shipments-ready/`, `/scan/shipments-tracking/`, `/api/v1/products/`
- [ ] Validate shipment create sequencing (destination -> expéditeur -> destinataire/correspondant -> détails).
- [ ] Validate draft flow: "Enregistrer en brouillon" creates `EXP-TEMP-XX` and is visible in Vue Expéditions.
- [ ] Run `python manage.py process_email_queue --limit=100`
- [ ] Check queue health (pending/failed counts)
- [ ] Run `python manage.py process_document_scan_queue --limit=100`
- [ ] Check document scan queue health (pending/failed/stale processing counts)
- [ ] Run `python manage.py check_document_scan_runtime --max-failed=0 --max-stale-processing=0`
- [ ] Verify no spike in app errors/log warnings

## E) Rollback criteria

Rollback immediately if one of these persists after a quick fix attempt:

- [ ] Repeated 500 errors on core routes.
- [ ] Authentication or admin access broken.
- [ ] Migrations applied but app is unstable.
- [ ] Email queue failures spike and cannot be replayed safely.
- [ ] Document scan queue failures spike or ClamAV is unavailable.

Rollback actions:

- [ ] Re-deploy previous known-good revision.
- [ ] Re-run `python manage.py migrate` if rollback includes schema-compatible migrations.
- [ ] Re-run smoke tests.
- [ ] Re-run `python manage.py process_email_queue --include-failed --limit=100` after stability is restored.
- [ ] Re-run `python manage.py process_document_scan_queue --include-failed --limit=100` after stability is restored.
- [ ] If local tooling blocks the hotfix path, fallback to `pip install -r requirements*.txt`.
- [ ] If exported dependency files drift, regenerate them from `uv.lock` with `make export-requirements`.
- [ ] If a local hook is a false positive, bypass only that hook temporarily with `SKIP=<hook-id> git commit ...`.
- [ ] Do not remove `mypy` from the blocking gate because `pyright` is noisy.

## F) Tooling success metrics

- [ ] No new secret detected in review or CI.
- [ ] No forgotten formatting diff detected by `pre-commit` or CI.
- [ ] No drift between `uv.lock` and exported `requirements*.txt`.
- [ ] Four consecutive weeks of green CI before any discussion of replacing `mypy`.
