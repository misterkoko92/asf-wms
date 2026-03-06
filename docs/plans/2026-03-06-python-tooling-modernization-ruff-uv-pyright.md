# Python Tooling Modernization Plan (Legacy Django)

Date: 2026-03-06
Scope: legacy Django only (`scan/`, `portal/`, `templates/`, `wms/`), excluding paused Next/React migration.
Status: Phase 1 completed in-repo; Phase 2 started with non-blocking `pyright` CI shadow step.

## Objectives

- Keep quality/security gates stable while modernizing developer tooling.
- Reduce local/CI drift for installs and type checking.
- Improve maintainability by converging on a single formatter (`ruff format`).

## Current baseline

- Lint: `ruff check .` (enforced).
- Formatter: no dedicated formatting gate yet.
- Type checking gate: `mypy` on 20 critical modules.
- Package install: `pip` in local/CI.

## Phase plan

1. Phase 1 (low risk, immediate)
- Add `make fmt` / `make fmt-check` using Ruff formatter.
- Keep formatter scope aligned with legacy policy (exclude paused Next/React paths).
- Add optional `uv` install path (`make install-uv`, `make install-dev-uv`).
- Add `pyright` dependency and baseline config (`pyrightconfig.json`) scoped to the same critical modules as `mypy`.
- Keep release gate unchanged (`mypy` remains authoritative).

2. Phase 2 (shadow signal, 1-2 weeks)
- Run `make typecheck-pyright` in local/CI as informational only.
- Track divergence `mypy` vs `pyright`:
  - true positives to fix
  - framework false positives to tune in config.

3. Phase 3 (gate switch decision)
- Switch type gate to `pyright` only if all criteria are met:
  - zero unresolved critical findings in scoped modules
  - at least 10 consecutive green runs on default branch
  - no increase in escaped type-related regressions.
- Keep `mypy` as fallback command for one release cycle.

4. Phase 4 (install path modernization)
- Introduce `uv` install in CI only after one dry-run period with unchanged artifacts.
- Keep `pip` fallback documented for emergency rollback.

## Acceptance criteria

- No regression on current mandatory gate (`make ci`).
- `make fmt-check` deterministic on clean branch.
- `make typecheck` remains green.
- `make typecheck-pyright` executable on dev envs with `requirements-dev.txt` installed.
- Release docs and operations runbook reflect the dual-run period clearly.

## Rollback strategy

- If pyright shadow produces unstable noise, keep it local only and postpone CI shadow.
- If uv path creates environment drift, revert to `pip` as default and keep uv optional.
- If formatter adoption causes large unrelated diffs, gate only on touched files until repository-wide reformat window is planned.
