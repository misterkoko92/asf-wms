# Agent Guardrails (asf-wms)

## GitHub network access policy

- By default, do not assume GitHub network access outside the sandbox is authorized for the current thread.
- At the beginning of each new thread, before any substantial work starts, explicitly ask whether GitHub-related commands should be allowed outside the sandbox for that thread.
- In the same question, explicitly ask whether the authorization applies only to the work directly related to the current request, or should remain in effect until explicit revocation.
- This per-thread question is mandatory at least once in every new thread, even if a broader or previously remembered authorization may already exist.
- Until the user answers for the current thread, avoid starting work that depends on GitHub network access outside the sandbox.

### Commands covered by this policy

- `git push`
- `git pull`
- `git fetch`
- `git ls-remote`
- `gh pr create`
- `gh pr view`
- `gh pr checks`
- Any similar `gh` command or GitHub API/network operation that requires access outside the sandbox

### Default behavior after the answer

- If the user authorizes only the current request, use escalated GitHub network access only for work directly tied to that request.
- If the user authorizes until explicit revocation, treat that as a standing preference, but still re-ask at least once at the start of each new thread before substantial work begins.
- If the user does not authorize GitHub network access for the current thread, continue with sandbox-safe work and stop before any blocked GitHub network step.

### Recommended persistent command prefixes

- Safe to keep broadly authorized for routine work:
  - `["git", "add"]`
  - `["git", "commit"]`
  - `["git", "push"]`
  - `["git", "pull"]`
  - `["git", "fetch"]`
  - `["git", "switch"]`
  - `["gh", "pr"]`
  - `["gh", "run"]`
  - `["gh", "workflow"]`
  - `["gh", "api"]`
  - `["gh", "auth", "status"]`
- Keep only if regularly needed, otherwise authorize case by case:
  - `["gh", "auth", "login"]`
  - `["gh", "pr", "merge"]`
  - `["git", "checkout", "-b"]`
  - `["git", "branch", "-d"]`
- Avoid broad persistent authorization for:
  - `["gh"]`
  - `["git"]`
  - `["git", "push", "--force"]`
  - `["git", "reset"]`
  - `["git", "rebase"]`
  - wide shell wrappers such as `["/bin/zsh", "-lc"]`

### Clarification on repeated approvals

- A user authorization for the thread and a sandbox/tool approval are separate layers.
- "Authorized until explicit revocation" means the repo policy question does not need to be re-negotiated again in the same thread.
- The desktop/tooling layer may still ask for approval when the exact command prefix is not already authorized, when a command is wrapped differently, or when the action falls outside existing sandbox allowances.

## Scope policy: Translation paused

- By default, exclude French / English translation scope from analysis, planning, code changes, tests, and verification.
- Keep the visible product language selector hidden unless the user explicitly asks to resume translation work.
- Treat translation pause as applying to legacy Django UI, public pages, auth pages, emails, print templates, docs, and translation-specific test coverage.

### Paused scope (do not touch by default)

- `templates/includes/language_switch.html`
- `templates/includes/language_switch_short.html`
- `locale/`
- `wms/tests/views/tests_i18n_language_switch.py`
- `wms/tests/management/tests_management_audit_i18n_strings.py`
- Any `docs/plans/*i18n*`, `docs/plans/*translation*`, or explicit FR/EN parity work items

### Default behavior for future requests

- Do not add or update FR/EN parity work unless the user explicitly asks for it.
- Do not add translation-focused tests or verification steps by default.
- Ignore English-copy regressions unless the current request explicitly re-opens translation scope.
- Prefer default-language legacy Django behavior for routine delivery work.

### Override rule

- Only include paused translation scope when the user explicitly asks in the current prompt.
- When override is used, limit changes strictly to the requested translation work.

## Scope policy: Next/React migration paused

- By default, all work must stay on the legacy Django stack (`scan/`, `portal/`, `templates/`, `wms/` legacy views/handlers).
- Exclude Next/React migration scope from analysis, planning, code changes, refactors, and tests unless the user explicitly asks for it.
- "Explicitly asks" means the request clearly mentions integrating Next/React or touching paused Next migration scope.

### Paused scope (do not touch by default)

- `frontend-next/`
- `wms/views_next_frontend.py`
- `wms/ui_mode.py`
- `wms/tests/views/tests_views_next_frontend.py`
- Any `docs/plans/*next*` migration execution items

### Default behavior for future requests

- Ignore paused Next scope even if it appears related.
- Prefer legacy routes and logic for equivalent functionality.
- If a task could be solved in both stacks, choose legacy Django implementation.

### Override rule

- Only include paused Next scope when the user explicitly requests it in the current prompt.
- When override is used, limit changes strictly to what was requested.

For details, see `docs/policies/translation-paused.md` and `docs/policies/next-migration-paused.md`.

## Repository reference policy

- Before substantial analysis, planning, or implementation work on the repo, read `docs/repo-reference/README.md` plus the relevant sections it points to.
- Treat `docs/repo-reference/README.md` as the canonical maintenance entry point for repo architecture, key flows, propagation checks, and shared contracts.
- When working on a ticket, use `docs/repo-reference/03-impact-map.md` to decide whether a change should propagate to other screens, APIs, docs, smoke checks, or shared contracts.
- Before declaring work complete, re-check the relevant impact-map and shared-contract sections to confirm whether any repo-reference docs also need an update.
- If a change modifies a critical route, flow, shared UI contract, shipment-party rule, smoke rule, or named reference test, update the relevant file(s) under `docs/repo-reference/` in the same work.

## FAQ Change Log policy

- For every PR that changes user-visible behavior or workflow, add one entry to `wms/faq_changelog.py`.
- Each entry must include the add date, the PR number, and a short business summary.
- If the PR number is not known during implementation, fill it before merge.

## Scan service worker bump policy

- If a change updates shared scan frontend assets that can remain stale in browser caches, bump the scan service worker version in both `wms/views_scan_misc.py` and `templates/scan/base.html` in the same work.
- Treat changes to `wms/static/scan/scan.css`, `wms/static/scan/scan-bootstrap.css`, `wms/static/scan/scan.js`, `wms/static/scan/modules/core.js`, `wms/static/scan/manifest.json`, or `wms/static/scan/icon.png` as bump candidates by default.
- Shared style changes should be considered bump-required unless the stale cached asset is demonstrably harmless.
