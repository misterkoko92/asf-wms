# Bugfix Prompt (ASF-WMS)

You are working on ASF-WMS.
Goal: diagnose and fix the reported bug with the smallest reliable patch.

For background on universal task discipline, see `docs/agent/playbooks.md` § Universal Execution Loop.
For task classification and mandatory risk checks, see `docs/agent/prompts.md`.

## Branch policy
- Work on a dedicated branch named `codex/fix-<short-slug>`
- If the branch does not exist, create it from `main` and switch to it
- Never modify `main` directly

## Source priority (in case of conflict)
1. `AGENTS.md`
2. `docs/repo-reference/`
3. actual codebase reality
4. secondary documentation

## Migration policy
A bugfix must not introduce schema migrations.
If the bug appears to require a schema change, this is no longer a bugfix.
Stop, escalate, and request a feature-prompt session instead.

## Mandatory approach
Do not start coding immediately.

## Workflow
1. Restate bug clearly.
2. Identify likely reproduction path.
3. Identify probable root causes.
4. Inspect only relevant files first.
5. Choose minimal fix.
6. Add a regression test that fails on the buggy version and passes after the fix.
   If the code is not testable in current state, explain why and propose manual reproduction steps.
7. Avoid unrelated cleanup.

## Required output before coding
### Diagnosis
- probable cause
- confidence level (high / medium / low)
- files involved

### Fix plan
Short numbered steps.

## Stop point
After producing diagnosis and fix plan:
- If confidence is high and fix is < 20 lines: proceed to implementation.
- If confidence is medium or fix is larger: stop and wait for explicit go-ahead.
- If confidence is low: do not patch. Surface the uncertainty and ask.

## Periphery limits
- If the minimal fix exceeds 50 lines or touches more than 5 files, stop and reassess.
  A large fix usually signals a misdiagnosed root cause.

## After implementation
Run validations:
- regression test passes
- existing tests in impacted area still pass
- lint if relevant

If a validation fails: do not commit, do not push.
Surface the error, explain probable cause, propose minimal fix, wait for validation.
Never retry blindly.

Commit with format: `fix(<scope>): <short imperative description>`
Optional second commit for the failing regression test before the fix:
`test(<scope>): add failing test reproducing <bug>`

Push the branch when validations pass.

## Boundary with other prompts
This prompt ends at `git push`.
Do not open a PR.
PR review is handled by `pr-review-prompt.md`.

## Final report
### Root cause
What caused the bug.

### Fix applied
Exact behavior corrected.

### Files changed
Touched files only.

### Validation
- reproduction no longer occurs
- tests run
- side effects checked

### Residual risk
Anything uncertain.

### Ready status
READY / NEEDS REVIEW / BLOCKED

## Rules
- Minimal diff wins.
- Preserve existing behavior outside bug scope.
- If unable to reproduce, say so clearly.
- If multiple causes possible, rank them.
- No opportunistic refactor in touched files.
- No PR opened automatically.

## Reported bug
[PASTE BUG HERE]
