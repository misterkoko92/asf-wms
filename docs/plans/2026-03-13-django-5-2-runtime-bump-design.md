# Django 5.2 Runtime Bump Design

Date: 2026-03-13
Branch: `codex/django-5-2-upgrade-spike`
Scope: legacy Django stack only

## Goal

Turn the validated Django 5.2 spike into the real project runtime baseline by updating the pinned framework dependencies and re-running the legacy Django validation matrix on the actual dependency set used by the repository.

## Context

The repository still pins Django 4.2.11 and djangorestframework 3.15.2 in both `pyproject.toml` and exported requirements files, even though the spike branch now contains the compatibility fixes needed to run cleanly on Django 5.2.

The spike already proved three technical points:

- planning workbook exports needed explicit closure
- generated PDF artifact responses needed early file-handle closure
- `CheckConstraint` declarations needed a compatibility shim so the same code works on Django 4.2 and Django 5.1+

That means the remaining work is not product design. It is dependency rollout, regression control, and project-level verification.

## Options considered

### Option A: Minimal bump with compatibility shim retained

- Update `Django` to `5.2.x`
- Update `djangorestframework` to `3.16.x`
- Keep the `CheckConstraint` compatibility helper already merged in the spike
- Regenerate exported requirement files

Pros:

- lowest rollout risk
- consistent with the spike proof already obtained
- preserves a downgrade path during rollout if needed

Cons:

- leaves temporary compatibility code in place longer

### Option B: Direct bump plus cleanup to 5.2-only APIs

- Same as Option A
- Remove the compatibility helper and switch all code to `condition=...`

Pros:

- cleaner end state

Cons:

- higher regression risk
- no benefit for the immediate bump
- would mix two changesets in one branch

### Option C: Broader dependency refresh

- Same as Option A
- opportunistically update related packages if anything looks stale

Pros:

- fewer follow-up dependency PRs

Cons:

- harder attribution if regressions appear
- larger test surface than necessary

## Chosen approach

Use Option A.

This branch should only do the runtime bump that the spike already validated:

- `Django==5.2.x`
- `djangorestframework==3.16.x`

The compatibility helper stays in place for now because it is the mechanism that keeps the code compatible with both the old and new framework APIs during rollout and review.

## Implementation outline

### Dependency sources

`pyproject.toml` remains the source of truth for pins. `requirements.txt` and `requirements-dev.txt` must be regenerated via the repo workflow (`make export-requirements`) so CI, local pip installs, and audit tooling stay aligned.

### Verification strategy

Use a narrow-to-wide verification flow:

1. Add or update a regression guard for the expected Django/DRF runtime versions.
2. Run the targeted suites that were sensitive during the spike:
   - `makemigrations --check --dry-run`
   - planning export tests
   - portal tests
   - print/admin tests
3. Run the full Django test suite on the actual bumped environment.

### Rollback safety

Because the compatibility helper stays in place, reverting the dependency bump later remains straightforward if deployment reality uncovers an infrastructure issue such as an unsupported database server version.

## Non-goals

- No Next/React work
- No removal of the compatibility helper in this branch
- No unrelated dependency refresh
- No production deployment changes

## Expected deliverables

- updated pins in `pyproject.toml`
- regenerated `requirements.txt`
- regenerated `requirements-dev.txt`
- any minimal regression guard needed for version expectations
- fresh verification evidence on the real bumped dependency set
