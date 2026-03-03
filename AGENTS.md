# Agent Guardrails (asf-wms)

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

For details, see `docs/policies/next-migration-paused.md`.
