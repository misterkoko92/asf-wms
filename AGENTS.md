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
