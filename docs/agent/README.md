# `docs/agent/` — Index

This folder contains everything an agent (or a human delegating to one) needs to work on ASF-WMS.

## Where to start

1. Always read `AGENTS.md` first (repo root).
2. Then read this folder in this order:
   - `prompts.md` — runtime conventions, task classification, mandatory checks, drift audit prompts
   - `playbooks.md` — task-specific execution patterns for cases without a dedicated template
   - `feature-prompt.md` / `bugfix-prompt.md` / `pr-review-prompt.md` — copy-paste templates for the three most common tasks

## File roles

| File | What it is | When to use |
|---|---|---|
| `prompts.md` | Runtime guide. Workflow, risk classification, mandatory checks, productization lens, drift audit prompts. | Always loaded as background. Copy-paste the drift audit blocks when running an audit. |
| `playbooks.md` | Execution patterns for task types that don't have a dedicated template (UI polish, refactor, migration, production incident, test repair). | Read when working on one of those task types. |
| `feature-prompt.md` | Copy-paste template for adding a feature. | Copy, fill the request section, send to the agent. |
| `bugfix-prompt.md` | Copy-paste template for fixing a bug. | Copy, fill the bug section, send to the agent. |
| `pr-review-prompt.md` | Copy-paste template for reviewing a PR. | Copy, paste the PR context, send to the agent. |

## Typical workflow

```
new feature      → copy feature-prompt.md   → agent works → push → manual PR open → pr-review-prompt.md
bug report       → copy bugfix-prompt.md    → agent works → push → manual PR open → pr-review-prompt.md
UI polish        → playbooks.md § UI Polish (no template)
refactor         → playbooks.md § Refactor (no template)
migration        → playbooks.md § Migration (no template)
incident         → playbooks.md § Production Incident (no template)
test repair      → playbooks.md § Test Repair (no template)
drift audit      → prompts.md § Documentation Drift Prompts
```

## Conventions shared across all files

- **Branch naming**: `codex/<type>-<short-slug>` (e.g. `codex/feat-rangement-button`, `codex/fix-scan-scroll`)
- **Never modify `main` directly**
- **Source priority in case of conflict**:
  1. `AGENTS.md`
  2. `docs/repo-reference/`
  3. actual codebase reality
  4. secondary documentation
- **Migration discipline**: features may introduce migrations only if explicitly requested; bugfixes never introduce migrations.
- **No PR opened automatically**: templates end at `git push`. PR opening is manual.

## Maintenance

If you change a convention (branch naming, source priority, commit format), update it in:

- `AGENTS.md`
- This README
- The 3 templates (`feature-prompt.md`, `bugfix-prompt.md`, `pr-review-prompt.md`)
- Relevant sections of `prompts.md` and `playbooks.md`

Drift between these files is the most common source of agent confusion. Audit periodically using the drift audit prompts in `prompts.md`.
