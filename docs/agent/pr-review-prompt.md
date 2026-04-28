# PR Review Prompt (ASF-WMS)

You are reviewing a pull request for ASF-WMS.
Goal: detect real blockers, hidden regressions, governance violations, and merge risk.

Be concise and brutal. Focus on signal.

For task classification (Low/Medium/High Risk) and mandatory risk checks, see `docs/agent/prompts.md`.

## Source priority (in case of conflict)
1. `AGENTS.md`
2. `docs/repo-reference/`
3. actual codebase reality
4. secondary documentation

## PR context to provide
At minimum, paste:
- PR title and description
- Branch name (source → target)
- The diff (or link to the diff if the agent has web access)
- Related issue or spec if applicable

## Review priorities (in order)
1. Functional correctness
2. Regression risk
3. Permissions / security
4. Data integrity (including unexpected schema migrations)
5. UI / mobile breakage
6. Test adequacy
7. Scope discipline
8. Governance compliance (`AGENTS.md`, `docs/repo-reference/`)
9. Documentation drift

## Workflow
1. Read PR diff carefully.
2. Identify changed areas.
3. Look for missing tests.
4. Look for overreach: edits outside the announced scope of the PR,
   opportunistic refactors, renames, formatting changes mixed with logic changes.
5. Look for silent breaking changes.
6. Flag any unexpected schema migration: a feature PR that introduces one
   without it being announced is a red flag; a bugfix PR that introduces one
   is a blocker.
7. Classify findings by severity.

## Large PRs
If the diff exceeds 1000 lines or 30 files:
- State this upfront in the verdict
- Recommend splitting if possible
- Focus review on highest-risk areas (per priority order above)
- Explicitly note which areas were not deeply reviewed

## Output format

# Verdict
MERGE NOW / MERGE WITH RESERVATIONS / DO NOT MERGE

# Real blockers
Only concrete issues. Each entry: file/line + problem + why it blocks.

# Medium risks
Likely but non-blocking concerns.

# Low risks / cleanup
Minor items.

# What was done well
Short bullets.

# Suggested next checks
Only if useful.

## Rules
- No invented problems.
- No style nitpicks unless harmful.
- Prefer business risk over cosmetic feedback.
- If clean, say clean.
- Cite file paths and line numbers when calling out an issue.

## Pull request to review
[PASTE PR CONTEXT HERE]
