# Agent Guardrails (ASF-WMS)

This file defines operational execution constraints for agents working on ASF-WMS.

Strategic priorities, decision principles, architecture mindset, and change philosophy are defined in `AGENTS.md`.

Use this file for runtime guardrails and repo-specific operational rules.

---

## GitHub Network Access Policy

- Do not assume GitHub network access outside the sandbox is authorized.
- At the start of a new thread involving repo work, explicitly ask whether GitHub-related commands are allowed.
- Also ask whether approval applies only to the current request or remains active until revoked.
- Until confirmed, avoid work that depends on external GitHub access.

### Covered commands

- `git push`
- `git pull`
- `git fetch`
- `git ls-remote`
- `gh pr create`
- `gh pr view`
- `gh pr checks`
- any similar GitHub API/network command

### Default after approval

- If approved only for the request, limit usage to that task.
- If approved until revoked, treat it as active for the thread.
- Tooling approval prompts may still appear depending on command prefix or sandbox policy.

---

## Scope Policy: Translation Paused

Translation work is paused by default.

Exclude translation scope from analysis, planning, implementation, tests, and verification unless explicitly requested in the current prompt.

### Paused scope

- `locale/`
- language switch templates
- translation parity work
- translation-focused tests
- FR/EN wording harmonization tasks

### Default behavior

- Prefer default language behavior.
- Ignore translation regressions unless translation scope is reopened.

---

## Scope Policy: Next / React Migration Paused

The repository currently prioritizes the legacy Django stack.

Do not include Next / React migration scope unless explicitly requested.

### Paused scope

- `frontend-next/`
- `wms/views_next_frontend.py`
- `wms/ui_mode.py`
- Next migration tests
- migration execution plans

### Default behavior

- Prefer legacy Django routes, templates, views, handlers, and shared assets.
- If both stacks could solve the task, choose legacy Django.

---

## Repository Reference Policy

Before substantial repo work:

- Read `docs/repo-reference/README.md`
- Read relevant linked sections
- Use `03-impact-map.md` to evaluate propagation risk

Before declaring work complete:

- Recheck relevant shared contracts
- Update repo-reference docs if the change affects:

  - critical routes / entrypoints → `01-architecture-and-entrypoints.md`
  - business flows → `03-impact-map.md`
  - shared UI contracts → `04-shared-contracts/`
  - shipment-party logic → `04-portal-parties.md`
  - runtime jobs / notifications / smoke checks → `04-shared-contracts/07-runtime-events-jobs-ops.md`
  - operational procedures → `docs/operations.md`
  - release verification → `docs/release_checklist.md`
  - named reference tests → relevant source section

---

## FAQ Change Log Policy

For every PR changing user-visible behavior or workflow:

- Add one entry to `wms/faq_changelog.py`
- Include:
  - date
  - PR number
  - short business summary

If PR number is unknown during implementation, fill it before merge.

---

## Scan Service Worker Bump Policy

If a shared scan frontend asset changes and stale browser cache could break behavior, bump the service worker version in the same work.

Update both:

- `wms/views_scan_misc.py`
- `templates/scan/base.html`

### Default bump candidates

- `wms/static/scan/scan.css`
- `wms/static/scan/scan-bootstrap.css`
- `wms/static/scan/scan.js`
- `wms/static/scan/modules/core.js`
- `wms/static/scan/manifest.json`
- `wms/static/scan/icon.png`

Shared frontend changes should be considered bump-required unless clearly harmless.

---

## Conflict Rule

If this file and `AGENTS.md` overlap:

- `AGENTS.md` governs strategy and priorities
- `agent-guardrails.md` governs operational execution constraints
