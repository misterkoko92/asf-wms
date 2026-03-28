# Repo Reference Governance Skill Design

Date: 2026-03-28

## Goal

Create a reusable skill that helps future repositories establish and maintain a canonical repository reference for architecture, key flows, impact propagation, and shared contracts.

## Scope

The skill should help an agent:

- detect whether a repo already has a usable maintenance reference
- create or update a `docs/repo-reference/` structure when needed
- wire that reference into the repo entry points such as `README.md`, `docs/README.md`, and `AGENTS.md`
- keep the reference aligned when routes, flows, shared contracts, smoke checks, or named reference tests change

## Non-goals

The skill should not become a generic "all development best practices" skill.

It should not duplicate:

- TDD
- debugging workflow
- verification workflow
- code review workflow
- planning workflow

Those are already better handled by dedicated skills.

## Maintenability Rules To Include

Keep only the rules that directly support repository reference quality:

- do not create one monolithic reference document
- separate source of truth from synthesized maintenance docs
- prefer local implementation first, shared helper or shared contract only after repeated real use
- document shared contracts only when they actually span several surfaces
- whenever a route, critical flow, shared contract, smoke check, or named reference test changes, update the repository reference in the same work

## Deliverables

Skill folder:

- `SKILL.md`
- `references/layout-and-template.md`
- `references/maintainability-heuristics.md`

Installation target:

- `~/.codex/skills/repo-reference-governance/`
