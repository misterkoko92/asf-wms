# Feature Prompt (ASF-WMS)

You are working on ASF-WMS.
Goal: implement the feature described below with minimal, safe, production-grade changes.

For background on universal task discipline, see `docs/agent/playbooks.md` § Universal Execution Loop.
For task classification, mandatory risk checks, and the productization lens, see `docs/agent/prompts.md`.

## Branch policy
- Work on a dedicated branch named `codex/feat-<short-slug>`
- If the branch does not exist, create it from `main` and switch to it
- Never modify `main` directly

## Source priority (in case of conflict)
1. `AGENTS.md`
2. `docs/repo-reference/`
3. actual codebase reality
4. secondary documentation

## Mandatory context
Before changing code:
1. Read relevant repository governance docs (per source priority above).
2. Identify impacted files, views, templates, JS, CSS, tests.
3. Respect existing architecture and conventions.
4. Prefer smallest viable implementation.
5. Do not refactor unrelated code.
6. If requirement is ambiguous, state assumptions explicitly.

## Migration policy
- Do not introduce a schema migration unless the feature request explicitly mentions a schema change.
- If the implementation appears to need a migration that wasn't requested, stop and ask before generating it.
- Never run `makemigrations` or equivalent without explicit confirmation.
- If a migration is unavoidable: keep it minimal, additive (no destructive changes), and document the rollback path in the final report.

## Workflow
1. Restate requested feature briefly.
2. Produce short impact analysis:
   - files likely impacted
   - risks
   - permissions/auth concerns
   - mobile/UI concerns
   - tests needed
   - schema/migration impact (if any)
3. Produce implementation plan (short numbered list).
4. If the plan exceeds 10 files or 300 lines, stop and ask for confirmation before proceeding.
5. Implement changes on the dedicated branch.
6. Run targeted validations:
   - tests related to changed area
   - lint/checks if relevant
   - templates/pages load sanity

   If a validation fails: do not commit, do not push.
   Surface the error, explain probable cause, propose minimal fix, wait for validation.
   Never retry blindly.
7. Commit with format: `feat(<scope>): <short imperative description>`
   One commit per feature. Multiple commits only if the feature splits naturally into independent steps (e.g. model / API / UI).
8. Push the branch when validations pass.
9. Produce final report.

## Boundary with other prompts
This prompt ends at `git push`.
Do not open a PR.
PR review is handled by `pr-review-prompt.md`.

## Final report format
### Summary
What was implemented.

### Files changed
List only touched files.

### Validation
Tests/checks run and result.

### Risks / follow-up
Anything needing manual verification.

### Ready status
READY / NEEDS REVIEW / BLOCKED

## Rules
- No speculative rewrites.
- No broad refactor.
- No silent behavior changes.
- No new dependency without explicit justification.
- No PR opened automatically.
- Keep UX coherent with existing ASF-WMS flows.
- Prefer explicit error handling.

## Feature request
[PASTE REQUEST HERE]
