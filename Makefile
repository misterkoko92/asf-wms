PYTHON ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
PIP ?= $(PYTHON) -m pip
UV ?= $(shell [ -x .venv/bin/uv ] && echo .venv/bin/uv || echo uv)
RUFF ?= $(shell [ -x .venv/bin/ruff ] && echo .venv/bin/ruff || echo ruff)
BANDIT ?= $(shell [ -x .venv/bin/bandit ] && echo .venv/bin/bandit || echo bandit)
MYPY ?= $(shell [ -x .venv/bin/mypy ] && echo .venv/bin/mypy || echo mypy)
PYRIGHT ?= $(shell [ -x .venv/bin/pyright ] && echo .venv/bin/pyright || echo pyright)
PYRIGHT_CONFIG ?= pyrightconfig.json
PIP_AUDIT ?= $(shell [ -x .venv/bin/pip-audit ] && echo .venv/bin/pip-audit || echo pip-audit)
PIP_AUDIT_SOFT_ARGS ?= --disable-pip --no-deps
PIP_AUDIT_REPORT ?= pip-audit-report.json
PRE_COMMIT ?= $(shell [ -x .venv/bin/pre-commit ] && echo .venv/bin/pre-commit || echo pre-commit)
COVERAGE ?= $(shell [ -x .venv/bin/coverage ] && echo .venv/bin/coverage || echo coverage)
COVERAGE_FAIL_UNDER ?= 93
COVERAGE_TEST_ARGS ?= --exclude-tag=next_frontend --exclude-tag=next_ui
TEST_PARALLEL ?= 4
TEST_PARALLEL_ARGS ?= --parallel $(TEST_PARALLEL)
COMPILEMESSAGES_IGNORE ?= --ignore='.venv' --ignore='.venv/*' --ignore='.worktrees' --ignore='.worktrees/*' --ignore='frontend-next' --ignore='frontend-next/*'
UV_EXPORT_ARGS ?= --frozen --no-header --no-annotate --no-hashes
DEPLOY_ENV_FILE ?= .env.deploy.example
FORMAT_SCOPE ?= asf_wms api contacts wms manage.py
FORMAT_EXCLUDES ?= --exclude frontend-next --exclude wms/views_next_frontend.py --exclude wms/ui_mode.py --exclude wms/tests/views/tests_views_next_frontend.py

BANDIT_EXCLUDES := wms/migrations,contacts/migrations,wms/tests,api/tests,contacts/tests

.PHONY: install install-dev sync sync-no-dev lock export-requirements deps-check install-uv install-dev-uv check deploy-check deploy-check-prod-like migrate-check compilemessages fmt fmt-check lint typecheck typecheck-pyright bandit audit audit-soft security test test-next-ui scan-queue scan-queue-retry scan-queue-health scan-queue-stale scan-queue-runtime-check coverage pre-commit ci

install:
	$(PIP) install -r requirements.txt

install-dev: install
	$(PIP) install -r requirements-dev.txt

sync-no-dev:
	@command -v $(UV) >/dev/null 2>&1 || (echo "Missing uv. Install it first with: python -m pip install uv" >&2; exit 1)
	$(UV) sync --frozen --no-dev

sync:
	@command -v $(UV) >/dev/null 2>&1 || (echo "Missing uv. Install it first with: python -m pip install uv" >&2; exit 1)
	$(UV) sync --frozen

lock:
	@command -v $(UV) >/dev/null 2>&1 || (echo "Missing uv. Install it first with: python -m pip install uv" >&2; exit 1)
	$(UV) lock

export-requirements: lock
	$(UV) export $(UV_EXPORT_ARGS) --no-dev --no-emit-project --format requirements.txt -o requirements.txt
	$(UV) export $(UV_EXPORT_ARGS) --only-group dev --no-emit-project --format requirements.txt -o requirements-dev.txt

deps-check:
	@command -v $(UV) >/dev/null 2>&1 || (echo "Missing uv. Install it first with: python -m pip install uv" >&2; exit 1)
	$(UV) lock --check
	@runtime_tmp=$$(mktemp); \
	$(UV) export $(UV_EXPORT_ARGS) --no-dev --no-emit-project --format requirements.txt -o "$$runtime_tmp"; \
	diff -u requirements.txt "$$runtime_tmp"; \
	rm -f "$$runtime_tmp"
	@dev_tmp=$$(mktemp); \
	$(UV) export $(UV_EXPORT_ARGS) --only-group dev --no-emit-project --format requirements.txt -o "$$dev_tmp"; \
	diff -u requirements-dev.txt "$$dev_tmp"; \
	rm -f "$$dev_tmp"

install-uv: sync-no-dev

install-dev-uv: sync

check:
	@if $(PYTHON) -c "import pip" >/dev/null 2>&1; then \
		$(PYTHON) -m pip check; \
	else \
		$(UV) pip check --python $(PYTHON); \
	fi

deploy-check:
	$(PYTHON) manage.py check --deploy --fail-level WARNING

deploy-check-prod-like:
	@test -f "$(DEPLOY_ENV_FILE)" || (echo "Missing env file: $(DEPLOY_ENV_FILE)" >&2; exit 1)
	@set -a; . "$(DEPLOY_ENV_FILE)"; set +a; $(PYTHON) manage.py check --deploy --fail-level WARNING

migrate-check:
	$(PYTHON) manage.py makemigrations --check --dry-run

compilemessages:
	$(PYTHON) manage.py compilemessages -v 1 $(COMPILEMESSAGES_IGNORE)

fmt:
	$(RUFF) format $(FORMAT_EXCLUDES) $(FORMAT_SCOPE)

fmt-check:
	$(RUFF) format --check $(FORMAT_EXCLUDES) $(FORMAT_SCOPE)

lint:
	$(RUFF) check .

typecheck:
	$(MYPY) --config-file mypy.ini

typecheck-pyright:
	@command -v $(PYRIGHT) >/dev/null 2>&1 || (echo "Missing pyright. Install dev deps first with: uv sync --frozen or make install-dev" >&2; exit 1)
	$(PYRIGHT) -p $(PYRIGHT_CONFIG)

bandit:
	$(BANDIT) -r asf_wms api contacts wms -x "$(BANDIT_EXCLUDES)"

audit:
	$(PIP_AUDIT) -r requirements.txt

audit-soft:
	@set -e; \
	if ! $(PYTHON) -c "import socket; socket.getaddrinfo('pypi.org', 443)" >/dev/null 2>&1; then \
		echo '{"error":"pip-audit skipped: pypi.org is not reachable from this environment"}' > $(PIP_AUDIT_REPORT); \
		cat $(PIP_AUDIT_REPORT); \
	else \
		$(PIP_AUDIT) -r requirements.txt $(PIP_AUDIT_SOFT_ARGS) --format json --output $(PIP_AUDIT_REPORT) || true; \
		test -f $(PIP_AUDIT_REPORT) || echo '{"error":"pip-audit did not produce output"}' > $(PIP_AUDIT_REPORT); \
		cat $(PIP_AUDIT_REPORT); \
	fi

security: bandit audit

test:
	$(PYTHON) manage.py test $(TEST_PARALLEL_ARGS)

test-next-ui:
	RUN_UI_TESTS=1 $(PYTHON) manage.py test wms.tests.core.tests_ui.NextUiTests

scan-queue:
	$(PYTHON) manage.py process_document_scan_queue --limit=100

scan-queue-retry:
	$(PYTHON) manage.py process_document_scan_queue --include-failed --limit=100

scan-queue-health:
	$(PYTHON) manage.py shell -c "from wms.document_scan_queue import DOCUMENT_SCAN_QUEUE_EVENT_TYPE, DOCUMENT_SCAN_QUEUE_SOURCE; from wms.models import IntegrationDirection, IntegrationEvent; qs=IntegrationEvent.objects.filter(direction=IntegrationDirection.OUTBOUND, source=DOCUMENT_SCAN_QUEUE_SOURCE, event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE); print({s: qs.filter(status=s).count() for s in ['pending','processing','processed','failed']})"

scan-queue-stale:
	$(PYTHON) manage.py shell -c "from datetime import timedelta; from django.conf import settings; from django.utils import timezone; from wms.document_scan_queue import DOCUMENT_SCAN_QUEUE_EVENT_TYPE, DOCUMENT_SCAN_QUEUE_SOURCE; from wms.models import IntegrationDirection, IntegrationEvent, IntegrationStatus; timeout=max(1,int(getattr(settings,'DOCUMENT_SCAN_QUEUE_PROCESSING_TIMEOUT_SECONDS',900))); cutoff=timezone.now()-timedelta(seconds=timeout); qs=IntegrationEvent.objects.filter(direction=IntegrationDirection.OUTBOUND, source=DOCUMENT_SCAN_QUEUE_SOURCE, event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE, status=IntegrationStatus.PROCESSING, processed_at__lte=cutoff); print({'timeout_seconds': timeout, 'stale_processing': qs.count()})"

scan-queue-runtime-check:
	$(PYTHON) manage.py check_document_scan_runtime --max-failed=0 --max-stale-processing=0

coverage: compilemessages
	$(COVERAGE) erase
	$(COVERAGE) run --rcfile=.coveragerc manage.py test $(COVERAGE_TEST_ARGS) $(TEST_PARALLEL_ARGS)
	$(COVERAGE) combine
	$(COVERAGE) report -m --fail-under=$(COVERAGE_FAIL_UNDER)
	$(COVERAGE) xml

pre-commit:
	$(PRE_COMMIT) run --all-files

ci: check deploy-check-prod-like migrate-check lint bandit coverage audit-soft
