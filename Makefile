PYTHON ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
PIP ?= $(PYTHON) -m pip
RUFF ?= $(shell [ -x .venv/bin/ruff ] && echo .venv/bin/ruff || echo ruff)
BANDIT ?= $(shell [ -x .venv/bin/bandit ] && echo .venv/bin/bandit || echo bandit)
MYPY ?= $(shell [ -x .venv/bin/mypy ] && echo .venv/bin/mypy || echo mypy)
PIP_AUDIT ?= $(shell [ -x .venv/bin/pip-audit ] && echo .venv/bin/pip-audit || echo pip-audit)
PRE_COMMIT ?= $(shell [ -x .venv/bin/pre-commit ] && echo .venv/bin/pre-commit || echo pre-commit)
COVERAGE ?= $(shell [ -x .venv/bin/coverage ] && echo .venv/bin/coverage || echo coverage)

BANDIT_EXCLUDES := wms/migrations,contacts/migrations,wms/tests,api/tests,contacts/tests

.PHONY: install install-dev check deploy-check migrate-check lint typecheck bandit audit audit-soft security test test-next-ui coverage pre-commit ci

install:
	$(PIP) install -r requirements.txt

install-dev: install
	$(PIP) install -r requirements-dev.txt

check:
	$(PYTHON) -m pip check

deploy-check:
	$(PYTHON) manage.py check --deploy --fail-level WARNING

migrate-check:
	$(PYTHON) manage.py makemigrations --check --dry-run

lint:
	$(RUFF) check .

typecheck:
	$(MYPY) --config-file mypy.ini

bandit:
	$(BANDIT) -r asf_wms api contacts wms -x "$(BANDIT_EXCLUDES)"

audit:
	$(PIP_AUDIT) -r requirements.txt

audit-soft:
	$(PIP_AUDIT) -r requirements.txt || true

security: bandit audit

test:
	$(PYTHON) manage.py test

test-next-ui:
	RUN_UI_TESTS=1 $(PYTHON) manage.py test wms.tests.core.tests_ui.NextUiTests

coverage:
	$(COVERAGE) run --rcfile=.coveragerc manage.py test
	$(COVERAGE) report -m --fail-under=95
	$(COVERAGE) xml

pre-commit:
	$(PRE_COMMIT) run --all-files

ci: check deploy-check migrate-check lint bandit coverage audit-soft
