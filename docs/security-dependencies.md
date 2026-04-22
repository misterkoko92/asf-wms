# Dependency Security Policy

This repo treats vulnerable runtime dependencies as release blockers unless there
is an explicit, dated accepted-risk note in the pull request or release notes.

## Signals

- Dependabot monitors the `uv` lockfile daily and GitHub Actions weekly.
- The CI workflow runs a blocking `pip-audit` check on `requirements.txt`.
- The `Dependency Audit` workflow runs daily on `main`, can be started manually,
  and also checks dependency-related pull requests.
- `make deps-check` remains the local drift check between `uv.lock` and exported
  requirement files.

## Severity Targets

- Critical: open a fix pull request or record an accepted-risk note within
  24 hours. Do not release with an untriaged critical finding.
- High: patch within 7 days, or record why the affected package is not reachable
  at runtime.
- Medium: batch into the next planned dependency maintenance window.
- Low: batch when already touching dependencies, unless the package is exposed
  on an internet-facing or file-parsing path.

Runtime dependencies take priority over development-only dependencies. When a
development-only dependency is flagged, first confirm that it is not shipped or
loaded in production.

## Local Triage

Run these commands before merging dependency changes:

```sh
make export-requirements
make deps-check
make audit
```

For an isolated audit without using the local virtualenv:

```sh
uv tool run --from pip-audit==2.10.0 pip-audit -r requirements.txt --disable-pip --no-deps
```

## Accepted Risk

Accepted risk must name the package, advisory id, severity, runtime reachability,
temporary mitigation, owner, and review date. Do not silence or remove the audit
gate to pass a release.
