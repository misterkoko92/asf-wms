# Maintainability Heuristics

These heuristics are intentionally narrow. They exist to improve repository-reference quality and change propagation decisions, not to replace dedicated engineering-discipline skills.

## Keep

- Prefer a segmented repository reference over one monolithic document.
- Keep source of truth explicit: runtime code and living tests first, synthesized docs second.
- Reuse an existing shared contract if it is already real and stable.
- Promote local logic to a helper or shared contract only after repeated real use across surfaces.
- Update the repository reference in the same work when critical routes, flows, shared contracts, smoke rules, or named reference tests change.
- Verify cited paths and tests exist before calling the reference current.

## Avoid

- Giant "architecture" docs that become stale immediately.
- Abstractions created only for aesthetic consistency.
- Declaring something "shared" before it has multiple real consumers.
- Copying old doc references without checking whether the current files still exist.
- Using the repository reference as a substitute for reading runtime code.

## Good Prompts The Skill Should Encourage

- "We changed page `X`. Does the same rule exist on another screen, API, or admin surface?"
- "Is there already a shared helper, signal, service, or contract for this behavior?"
- "Did this change alter a smoke check, runbook step, or named reference test?"
- "If this contract moved, which repository-reference file now needs an update?"
