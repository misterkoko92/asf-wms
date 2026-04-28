# ASF-WMS — Prompt Runtime

Always read `AGENTS.md` first.

For task-specific execution patterns and stop-thresholds by task type, see `docs/agent/playbooks.md`.

For repo work, also read:

- `docs/policies/agent-guardrails.md`
- `docs/repo-reference/README.md`

---

## Standard Workflow

1. Understand the request
2. Classify the task
3. Evaluate impact and risk
4. Inspect relevant code and docs
5. Choose the smallest safe path
6. Present a short plan
7. Implement carefully
8. Validate with appropriate checks
9. Update docs if needed
10. Recommend next best move

---

## Task Classification

### Low Risk

- copy updates
- local UI cleanup
- isolated bug fix
- tests only
- documentation only

### Medium Risk

- shared templates
- shared assets
- business rules
- forms
- permissions
- queries
- non-trivial refactors

### High Risk

- migrations
- authentication
- portal scopes
- shipment-party logic
- notifications
- shared contracts
- production configuration
- destructive changes

Increase caution with each level.

---

## Mandatory Risk Checks

Always consider:

- production impact
- migration impact
- permission regressions
- user workflow regressions
- hosting compatibility
- maintenance burden
- rollback path

---

## ASF-WMS Productization Lens

Ask before implementing:

- useful beyond ASF?
- configurable?
- clearly ASF-specific?
- adds support burden?
- improves demo readiness?
- creates reusable capability?

Prefer reusable core + ASF-specific configuration when practical.

---

## Change Strategy

Prefer:

- reversible steps
- backward compatibility
- small PRs
- explicit contracts
- tests near changed behavior
- simple maintainable solutions

Avoid:

- broad rewrites
- speculative abstractions
- parallel systems without sunset plan
- hidden coupling
- unnecessary complexity

---

## Completion Rule

Before declaring done:

- verify requested outcome
- verify no obvious regressions
- verify docs/tests updated when needed
- state residual risks honestly

---

## Final Rule

If unsure, choose the safer smaller reversible path.
