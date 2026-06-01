# Release Checklist

Use this checklist for each production release.

## A) Before merge

- [ ] `uv sync --frozen`
- [ ] `pre-commit install`
- [ ] `make pre-commit`
- [ ] `make ci`
- [ ] Keep the CI smoke subset small and deterministic. `make test-smoke` runs the current cross-domain smoke guards: `api.tests.tests_ui_e2e_workflows`, `wms.tests.emailing.tests_notifications_queue`, `wms.tests.emailing.tests_order_status_notifications`, and `wms.tests.planning.tests_smoke_planning_flow`.
- [ ] `make typecheck` is green and remains the blocking type gate.
- [ ] If V3 structural layers changed, `make typecheck-structural` is green.
- [ ] If V3 structural layers changed, `make ruff-structural` is green.
- [ ] `make typecheck-pyright` reviewed as informational only and interpreted as the public structural-facade signal, not full ORM coverage.
- [ ] `make export-requirements` re-run after any dependency change.
- [ ] For any dependency change, `make deps-check` and `make audit` are green, or the accepted risk is documented as described in `docs/security-dependencies.md`.
- [ ] The latest `Dependency Audit` workflow run on `main` is green or has an explicit triage note before release.

Fallback if `uv` is blocked locally:

- [ ] `python -m pip install -r requirements.txt`
- [ ] `python -m pip install -r requirements-dev.txt`
- [ ] `make pre-commit`
- [ ] `make ci`

## B) Before deploy

- [ ] Confirm production env vars are set (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS`, `SITE_BASE_URL`, security flags).
- [ ] Validate env values against `.env.example` baseline.
- [ ] Review `docs/policies/rgpd.md` for any release touching personal data, documents, exports, portal/public forms, emails, logs, or third-party services.
- [ ] If visible legal text changed, review `docs/policies/confidentialite.md`, `docs/policies/cgu-portail.md`, `docs/policies/mentions-legales.md`, and `docs/policies/mentions-information-formulaires.md`.
- [ ] Confirm every new personal-data flow has a documented finality, legal-basis assumption, retention rule, processor/transfer impact, and suppression/anonymization path.
- [ ] Confirm visible legal texts are validated or explicitly risk-accepted when portal, public account creation, public orders, auth pages, or recipient/correspondent access changed.
- [ ] Confirm the release does not add production personal data, real documents, secrets, or non-anonymized dumps to the repository, CI artifacts, or local audit artifacts intended for sharing.
- [ ] Confirm mail provider env vars (`EMAIL_*` and/or `BREVO_*`).
- [ ] Confirm document scan env vars (`DOCUMENT_SCAN_BACKEND=clamav`, `DOCUMENT_SCAN_CLAMAV_COMMAND`, queue timeout settings).
- [ ] Confirm CSP report-only is enabled or explicitly risk-accepted for the environment, including the local helper `connect-src` origin when helper workflows are in scope.
- [ ] Ensure ClamAV binary is available on host (`clamscan --version`).
- [ ] Confirm `INTEGRATION_API_KEY` for integration endpoints.
- [ ] Confirm API throttle rates (`DRF_USER_THROTTLE_RATE`, `DRF_ANON_THROTTLE_RATE`) and QR access throttles/TTL (`SHIPMENT_TRACKING_ACCESS_*`) are acceptable for the release.
- [ ] Run `python manage.py check_planning_pdf_runtime` and confirm `backend=excel_desktop`, `status=ready`.
- [ ] Confirm backup available (SQLite file or MySQL dump) and record the backup timestamp/path.
- [ ] Confirm media backup available for `MEDIA_ROOT` and record the backup timestamp/path.
- [ ] Confirm latest restore drill date/result, or record an explicit release risk if no successful drill exists yet.
- [ ] Confirm RPO/RTO targets from `docs/operations.md` are still acceptable for this release.
- [ ] Confirm monitoring path for this release: Sentry if `SENTRY_DSN` is configured, otherwise platform logs plus `/scan/dashboard/` and queue health checks.
- [ ] Run `python manage.py check_sentry_runtime --allow-missing`.
- [ ] If `SENTRY_DSN` was added or changed, run `python manage.py check_sentry_runtime --send-test` and confirm the event appears in Sentry.
- [ ] Run `python manage.py check_referential_integrity` after migrations on the target data, or explicitly document any accepted anomaly before release.
- [ ] If portal/contact/shipment-party scope changed, run `python manage.py rebuild_recipient_party_graph --dry-run` and review the reported grant/projection repair summary before deploy.
- [ ] If scan frontend assets changed (`wms/static/scan/scan.js`, `wms/static/scan/scan.css`, `wms/static/scan/scan-bootstrap.css`, `wms/static/scan/modules/core.js`, manifest/icon), bump both `SCAN_SERVICE_WORKER_VERSION` in `wms/views_scan_misc.py` (`wms-scan-vNN`) and the registration query string in `templates/scan/base.html`.
- [ ] If templates/frontend supply-chain scope changed, confirm `_blank` uses `rel`, CDN assets have SRI or are self-hosted, and dynamic HTML sinks are covered by tests.

## C) Deploy

- [ ] `git pull origin main`
- [ ] `python -m pip install -r requirements.txt`
- [ ] `python manage.py migrate --noinput`
- [ ] `python manage.py compilemessages -v 1`
- [ ] `python manage.py collectstatic --noinput`
- [ ] `python manage.py check --deploy --fail-level WARNING`
- [ ] Restart app service/process

Notes:

- [ ] If `locale/en/LC_MESSAGES/django.po` or `locale/fr/LC_MESSAGES/django.po` changed, `compilemessages` is mandatory on the deploy host before app reload. Django uses compiled `.mo` catalogs at runtime, not raw `.po` files.

## D) After deploy

- [ ] Always-on smoke: `GET /`, `/admin/login/`, `/scan/`, `/scan/shipments-ready/`, `/scan/shipments-tracking/`, `/api/v1/products/`
- [ ] Always-on smoke: validate shipment create sequencing (destination -> expéditeur -> destinataire/correspondant -> détails).
- [ ] Always-on smoke: validate document-first shipment creation in `Préparer sans colis` mode so destination + 3 contacts + planned count creates a shipment with a final reference and no attached cartons.
- [ ] Always-on smoke: validate `/scan/shipment/batch/` creates multiple independent prepared shipments and summary print links open paper/preparatory-label bundles.
- [ ] Always-on smoke: if carton batch scope changed, validate Vue Colis batch assignment plus grouped picking / packing-list outputs.
- [ ] Always-on smoke: validate one shipment tracking or close action on an existing shipment.
- [ ] Conditional smoke: if QR shipment tracking access changed, validate an anonymous QR tracking open, identifier entry, login-required redirect, lost-code email, pending-account creation, and one authenticated correspondent/recipient proof scan.
- [ ] Conditional smoke: if dashboard scope changed, validate one `Blocages workflow` row opens the expected dossier and claim/release works once.
- [ ] Conditional smoke: if pilotage/settings scope changed, validate `/scan/settings/`, `/scan/dashboard/`, and `/scan/pilotage/` all expose `Seuils actifs`, the expected active preset label, and coherent planning thresholds.
- [ ] Conditional smoke: if portal scope changed, validate portal login plus one nominal shipper flow; if a `recipient_admin` grant is enabled in the target environment, also validate `/portal/` in recipient scope plus one recipient shared-data update.
- [ ] Conditional smoke: if portal onboarding/readiness changed, validate public shipper signup, public recipient signup, `Autre escale` request, scan account validation detail, portal account contact update, portal recipient create served-stopover path, portal recipient `Autre escale`, order create blocked with missing readiness, and order create allowed with complete readiness.
- [ ] Conditional smoke: if planning scope changed, validate run-list attention cards, one run input preparation path (`api`/`hybrid`) with either retained flights or an explicit `flight_import_failed` issue, cockpit access on an existing run/version, `Runtime PDF`, and strict `Planning.pdf` / `Planning.xlsx` artifact visibility, regeneration, or download if applicable.
- [ ] Conditional smoke: if planning scope changed, validate one internal planning helper payload is blocked when no ready PDF exists and unblocked after a successful PDF export.
- [ ] Conditional smoke: if billing scope changed, validate one nominal billing preview/export or payment/correction flow.
- [ ] Run `python manage.py process_email_queue --limit=100`
- [ ] Run `python manage.py refresh_ops_pilotage`
- [ ] If runtime/jobs scope changed, inspect recent `OperationalJobRun` rows for `email_queue`, `document_scan_queue`, `workflow_projection_rebuild`, `ops_pilotage_refresh`, and `print_artifact_queue`.
- [ ] If print artifact sync changed, verify `print_artifact_queue.result_summary.proof_sync_preview` exposes coherent artifact ids, outcomes, and OneDrive paths for the latest run.
- [ ] Check queue health (pending/failed counts)
- [ ] Run `python manage.py process_document_scan_queue --limit=100`
- [ ] Check document scan queue health (pending/failed/stale processing counts)
- [ ] Run `python manage.py check_document_scan_runtime --max-failed=0 --max-stale-processing=0`
- [ ] Verify no spike in app errors/log warnings or external monitoring events.

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
- [ ] No untriaged critical or high dependency advisory remains open beyond the targets in `docs/security-dependencies.md`.
- [ ] Four consecutive weeks of green CI before any discussion of replacing `mypy`.
