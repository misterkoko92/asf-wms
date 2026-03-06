# Python Tooling Modernization Plan (Legacy Django)

Date: 2026-03-06
Scope: legacy Django only (`scan/`, `portal/`, `templates/`, `wms/`), excluding paused Next/React migration.
Status: Execution moved to `docs/plans/2026-03-06-python-tooling-standardization-implementation-plan.md`; the rollout below records the decision narrative and target end state.

## Objectives

- Keep quality/security gates stable while modernizing developer tooling.
- Reduce local/CI drift for installs and type checking.
- Improve maintainability by converging on a single formatter (`ruff format`).

## Current baseline

- Lint/format: `ruff check .` and `ruff format`.
- Local install default: `uv sync --frozen` (`pip` kept as documented fallback).
- Type checking gate: `mypy` on 20 critical modules.
- Secondary type signal: `pyright` in `standard` mode, still informational in CI.
- Local hygiene: `pre-commit`, `djlint`, `detect-secrets`, `bandit`.
- Dependency automation: weekly Dependabot updates for Python and GitHub Actions.

## Phase plan

1. Implemented wave
- `pyproject.toml` + `uv.lock` are the canonical dependency and tool config sources.
- `requirements.txt` and `requirements-dev.txt` are exported compatibility artifacts.
- `pyrightconfig.json` is cleaned up, promoted to `standard`, and kept informational in CI.
- `pre-commit` now covers JSON/YAML/TOML checks, large files, Ruff, `djlint`, `detect-secrets`, and `bandit`.
- CI now has a dedicated `pre-commit` job and a separate `uv`-based validation job.

2. Phase 2 (shadow signal, 4+ weeks)
- Keep `make typecheck-pyright` informational in local/CI.
- Track divergence `mypy` vs `pyright`:
  - true positives to fix
  - framework false positives to tune in config.

3. Phase 3 (gate switch decision, deferred)
- Switch type gate to `pyright` only if all criteria are met:
  - zero unresolved critical findings in scoped modules
  - at least 4 consecutive weeks of green CI on default branch
  - no increase in escaped type-related regressions.
- Keep `mypy` as fallback command for one release cycle.

## Acceptance criteria

- No regression on current mandatory gate (`make ci`).
- `make pre-commit` deterministic on a clean branch.
- `make typecheck` remains green.
- `make typecheck-pyright` executable on dev envs with `requirements-dev.txt` installed.
- No secret introduced in review or CI.
- No drift between `uv.lock` and exported `requirements*.txt`.
- Release docs and operations runbook reflect the dual-run period clearly.

## Rollback strategy

- If pyright shadow produces unstable noise, keep it local only and postpone CI shadow.
- If uv path creates environment drift, revert to `pip` as default and keep uv optional.
- If a local hook is noisy, bypass only the single hook temporarily with `SKIP=<hook-id> git commit ...` while fixing the rule or baseline.
- If formatter adoption causes large unrelated diffs, gate only on touched files until repository-wide reformat window is planned.
