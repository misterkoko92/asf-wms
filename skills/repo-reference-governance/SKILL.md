---
name: repo-reference-governance
description: Use when a repository needs a canonical maintenance reference, or when recurring work requires tracking architecture, key flows, propagation impacts, and shared contracts across the repo
---

# Repo Reference Governance

## Overview

Create and maintain a small repository reference that helps future work start faster and miss fewer cross-cutting impacts.

This skill governs the maintenance reference itself. It does not replace runtime code, tests, or operational docs.

## When to Use

Use this skill when:

- a repo has useful docs but no canonical maintenance entry point
- repeated work keeps re-discovering the same architecture or propagation rules
- changes often forget sibling screens, APIs, smoke checks, or shared contracts
- named reference tests or critical flows keep drifting away from docs
- onboarding a new repo for recurring maintenance work

Do not use this skill as a generic development best-practices skill. For implementation discipline, use the dedicated skills for TDD, debugging, planning, verification, and review.

## Deliverable

Default output structure:

- `docs/repo-reference/README.md`
- `docs/repo-reference/01-architecture-and-entrypoints.md`
- `docs/repo-reference/02-key-flows-and-living-tests.md`
- `docs/repo-reference/03-impact-map.md`
- `docs/repo-reference/04-shared-contracts.md`

Adapt names only if the repo already has a stronger local convention.

See `references/layout-and-template.md` for the default layout.

## Core Rules

1. Keep the repository reference small and segmented.
2. Treat runtime code and living tests as source of truth. The reference is a synthesis layer.
3. Wire the repository reference into the repo entry points so it is actually used:
   - `README.md`
   - `docs/README.md` when present
   - `AGENTS.md` or equivalent agent guardrail file when present
4. Update the repository reference in the same work when a critical route, flow, shared contract, smoke rule, or named reference test changes.
5. Verify that every referenced path or test still exists before claiming the reference is current.

## Workflow

### 1. Audit the repo surface

Start from the real entry points:

- root routing or app entry files
- view/controller/handler/service layers
- model or domain modules
- templates or UI surfaces
- test tree
- operations and release docs

Build the reference from runtime reality, not from old plans alone.

### 2. Create or refresh the reference files

Capture only the information future maintenance work repeatedly needs:

- where the app starts
- which files define the critical flows
- which tests are the quickest living references
- where shared contracts live
- which changes usually propagate across surfaces

Do not dump every file in the repo into the reference.

### 3. Add propagation logic

The impact map should force the same questions every time:

- does the same rule exist on another screen or API?
- is there already a shared helper, service, signal, or contract?
- does a release smoke, runbook, or matrix need an update too?
- did a named reference test move or disappear?

### 4. Add maintainability heuristics

Include only heuristics that improve repository reference quality and cross-cutting maintenance decisions.

See `references/maintainability-heuristics.md`.

### 5. Wire it into the repo

Make the reference discoverable from the start of future tickets:

- link it from `README.md`
- link it from `docs/README.md` when relevant
- add a short guardrail in `AGENTS.md` or equivalent so the reference is read before substantial work and re-checked before completion

### 6. Verify before completion

Before claiming the repository reference is ready:

- confirm referenced files exist
- confirm cited living tests exist
- confirm entry-point docs link to the new reference
- confirm the repo instructions require reading and updating it when relevant

## Maintainability Boundaries

Apply these heuristics carefully:

- Do not create a monolithic maintenance document.
- Do not extract a shared helper or shared contract at first sight. Prefer local implementation first, then extract after repeated real use.
- Do not invent abstractions just to make the reference look clean.
- Document shared contracts only when they truly span several surfaces.
- If the repo already has a strong local pattern, preserve it and document it instead of replacing it.

## Related Skills

- Use `test-driven-development` for feature or bugfix implementation.
- Use `systematic-debugging` for failures and unexpected behavior.
- Use `writing-plans` for multi-step implementation work.
- Use `verification-before-completion` before claiming anything is done.
