# Release Checklist

Use this checklist for each production release.

## A) Before merge

- [ ] `python -m pip install -r requirements.txt`
- [ ] `python -m pip install -r requirements-dev.txt`
- [ ] `make check`
- [ ] `make migrate-check`
- [ ] `make deploy-check`
- [ ] `make lint`
- [ ] `make typecheck`
- [ ] `make bandit`
- [ ] `make coverage`
- [ ] `make audit` (if network allows)

## B) Before deploy

- [ ] Confirm production env vars are set (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS`, `SITE_BASE_URL`, security flags).
- [ ] Validate env values against `.env.example` baseline.
- [ ] Confirm mail provider env vars (`EMAIL_*` and/or `BREVO_*`).
- [ ] Confirm `INTEGRATION_API_KEY` for integration endpoints.
- [ ] Confirm backup available (SQLite file or MySQL dump).

## C) Deploy

- [ ] `git pull origin main`
- [ ] `python -m pip install -r requirements.txt`
- [ ] `python manage.py migrate --noinput`
- [ ] `python manage.py collectstatic --noinput`
- [ ] `python manage.py check --deploy --fail-level WARNING`
- [ ] Restart app service/process

## D) After deploy

- [ ] Smoke test `GET /`, `/admin/login/`, `/scan/`, `/api/v1/products/`
- [ ] Run `python manage.py process_email_queue --limit=100`
- [ ] Check queue health (pending/failed counts)
- [ ] Verify no spike in app errors/log warnings

## E) Rollback criteria

Rollback immediately if one of these persists after a quick fix attempt:

- [ ] Repeated 500 errors on core routes.
- [ ] Authentication or admin access broken.
- [ ] Migrations applied but app is unstable.
- [ ] Email queue failures spike and cannot be replayed safely.

Rollback actions:

- [ ] Re-deploy previous known-good revision.
- [ ] Re-run `python manage.py migrate` if rollback includes schema-compatible migrations.
- [ ] Re-run smoke tests.
- [ ] Re-run `python manage.py process_email_queue --include-failed --limit=100` after stability is restored.
