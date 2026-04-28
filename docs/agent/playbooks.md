# Agent Playbooks

Purpose: task-specific execution patterns for coding agents working on ASF-WMS.

Use with:

- `AGENTS.md`
- `docs/policies/agent-guardrails.md`
- `docs/agent/prompts.md`
- `docs/repo-reference/README.md`

For sensitive zones, completion rules, and repository-reference update policy, see:

- `AGENTS.md`
- `docs/policies/agent-guardrails.md`

For the three most common task types, use the dedicated templates instead of this file:

- Add a feature → `docs/agent/feature-prompt.md`
- Fix a bug → `docs/agent/bugfix-prompt.md`
- Review a PR → `docs/agent/pr-review-prompt.md`

For documentation drift audits, use the prompts in `docs/agent/prompts.md` § Documentation Drift Prompts.

---

# Universal Execution Loop

For nearly every task:

1. Clarify the objective in one sentence.
2. Identify impacted surface(s): scan / portal / planning / benevole / api / shared core.
3. Read relevant docs first.
4. Read runtime files before editing.
5. Choose the smallest viable change.
6. Add or update tests.
7. Run targeted proof.
8. Check whether docs must change.
9. Summarize impact, risk, and next steps.

If the task expands unexpectedly, stop and re-scope.

---

# Task Type: UI Polish

Goal:

- improve usability without breaking shared shells

Read first:

- relevant template
- shared contracts if applicable
- shared assets when touched

Execution pattern:

1. Prefer local template change first.
2. Reuse existing primitives.
3. Validate mobile width / overflow.
4. Preserve labels, actions, accessibility.

Proof:

- related UI tests
- quick responsive review

Avoid:

- new primitive for a one-page need
- broad shared CSS changes for a local issue

Stop and ask human if:

- UX direction is unclear
- shared component semantics would change

---

# Task Type: Refactor

Goal:

- improve structure while preserving behavior

Read first:

- impacted runtime files
- architecture docs
- existing tests

Execution pattern:

1. Preserve interfaces first.
2. Move logic toward existing boundaries.
3. Keep adapters thin.
4. Refactor in slices.

Proof:

- existing tests stay green
- add tests if hidden logic is moved

Avoid:

- refactor + feature + migration in one step

Stop and ask human if:

- hidden coupling appears across domains

---

# Task Type: Migration / Data Shape Change

Goal:

- evolve schema safely

Read first:

- models
- dependent queries / forms / views
- production docs

Execution pattern:

1. Prefer additive migration.
2. Keep backward compatibility when possible.
3. Consider legacy rows and null states.
4. Add integrity checks.

Proof:

- migration runs cleanly
- impacted tests pass

Avoid:

- destructive rename / drop without plan
- silent data rewrites

Stop and ask human if:

- data loss risk exists
- production uncertainty is high

---

# Task Type: Production Incident

Goal:

- stabilize first, improve later

Execution pattern:

1. Contain blast radius.
2. Restore service.
3. Use the smallest reversible patch.
4. Capture likely root cause.
5. Add regression proof afterward.

Prefer:

- guarded fallback
- queue pause / retry control when safer

Avoid:

- broad cleanup during outage

Stop and ask human if:

- security issue
- data corruption
- privacy or legal impact

---

# Task Type: Test Repair

Goal:

- restore trust in signal, not hide failure

Execution pattern:

1. Understand why the test fails.
2. Fix product code if regression is real.
3. Update test only if intended behavior changed.
4. Remove brittleness.

Avoid:

- weakening assertions blindly
- snapshot churn without review

Stop and ask human if:

- expected behavior is disputed
- failing tests expose deeper instability
