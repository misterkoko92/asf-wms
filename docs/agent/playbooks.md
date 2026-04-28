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

# Task Type: Documentation Drift Audit

Goal:

- verify that repository documentation still matches recent code, governance, and workflow reality

This playbook is user-triggered or event-triggered only. It does not imply automatic recurrence, persistent agent memory, or background monitoring.

Triggers:

- after a series of commits
- after a major feature or workflow change
- after changes to roles, permissions, shared contracts, or architecture
- before release
- after large documentation refactors
- whenever the user requests a drift audit

Modes:

- lightweight audit: compare recent commits against affected docs and report missing or stale updates
- full audit: review `AGENTS.md`, `docs/agent/*`, `docs/repo-reference/**`, `docs/policies/**`, README files, and docs indexes

Execution pattern:

1. Identify the commit range or documentation scope.
2. Read the relevant governance rules first.
3. Compare changed behavior, contracts, or workflows against affected docs.
4. Check for broken links, missing referenced files, stale names, and conflicting rules.
5. Report findings by severity with exact files.
6. Do not apply fixes unless the user explicitly requests remediation.

Proof:

- `git diff` or `git log` for the selected range
- targeted link/path checks for referenced docs
- direct review of relevant docs

---

# Task Type: Bug Fix

Goal:

- restore expected behavior with minimal blast radius

Read first:

- failing traceback or failing test
- relevant route / view / service
- related shared contract if one exists

Execution pattern:

1. Reproduce.
2. Locate root cause, not only symptom.
3. Patch minimally.
4. Add regression test.
5. Verify no adjacent breakage.

Proof:

- targeted tests
- optional route smoke test

Avoid:

- opportunistic refactor during urgent fixes
- changing unrelated behavior

Stop and ask human if:

- expected behavior is ambiguous
- bug reveals a business-rule conflict

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

# Task Type: Add Feature

Goal:

- ship the smallest useful version safely

Read first:

- related workflow docs
- nearest existing implementation
- adjacent tests

Execution pattern:

1. Define user-visible outcome.
2. Reuse existing models and flows when possible.
3. Add minimal UI.
4. Add happy-path and guardrail tests.
5. Update docs if behavior changed.

Proof:

- targeted tests
- smoke journey

Avoid:

- speculative abstraction
- parallel second system

Stop and ask human if:

- feature changes business semantics
- touches several sensitive zones at once

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
