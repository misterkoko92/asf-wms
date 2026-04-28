# Core Facades And Structural Boundaries

Read this file when touching import facades, extracted runtime layers, package roots, or type-check boundaries.

---

## View Facade Contract

### Primary runtime sources

- `wms/views.py`

### Current contract

- `wms/views.py` is mostly a compatibility and re-export layer for routing and many tests.
- Business logic usually lives in `wms/views_*`, handlers, services, application modules, or domain modules.
- Do not assume core logic lives in `wms/views.py`.

### Maintenance rule

- If a scan, portal, public, volunteer, or planning view is moved or renamed, check `wms/views.py`.
- Keep route imports and tests aligned.
- Do not add new business logic to the facade unless explicitly justified.

---

## Model Facade Contract

### Primary runtime sources

- `wms/models.py`
- `wms/models_domain/*`

### Current contract

- `wms/models.py` is the compatibility import facade above extracted domain modules.
- Normal runtime imports may continue using the facade unless the task explicitly targets the extracted source module.

### Maintenance rule

- If a model-level contract changes, verify both the extracted domain module and compatibility imports.
- Avoid breaking legacy imports while the repo remains in progressive modular extraction.

---

## Structural Facade Contract

### Primary runtime sources

- `wms/application/__init__.py`
- `wms/application/parties/__init__.py`
- `wms/application/planning_artifacts/__init__.py`
- `wms/events/__init__.py`
- `wms/jobs/__init__.py`
- `wms/parties/__init__.py`
- `wms/artifacts/__init__.py`
- `mypy.ini`
- `pyrightconfig.json`
- `Makefile`

### Current contract

- Package-root `__init__` modules are stable public import facades for structural layers.
- `mypy.ini` is the broad structural type gate.
- `pyrightconfig.json` intentionally validates public facades rather than full Django ORM-heavy internals.
- `make typecheck-structural` proves the structural type gate.
- `make ruff-structural` proves structural linting.
- `wms/tests/core/tests_v33_contracts.py` proves runtime facade contract.

### Maintenance rule

- If a structural package adds, removes, or renames a public entry point, update package `__init__`, contract tests, structural typecheck config, and architecture docs together.
- Do not point pyright at ORM-heavy internals unless the repo adopts the stubs/typing discipline needed to keep that signal green.

### Reference tests

- `wms/tests/core/tests_v33_contracts.py`
