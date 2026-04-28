# Repository Reference

This directory is the canonical maintenance entry point for the repository.

Use it to re-enter the codebase quickly, understand propagation risk before a change, and verify cross-surface impact before merge.

It is designed for:

- maintainers
- new contributors
- AI coding agents
- future you after context loss

> Last updated: 2026-04-27

---

# Purpose

This reference exists because the repository contains:

- multiple business surfaces (`/scan/`, `/portal/`, `/planning/`, `/benevole/`, APIs)
- legacy and newer architectural layers
- shared contracts reused in many places
- operational workflows where regressions are costly
- hidden coupling not always obvious from local files

Reading only the touched file is often insufficient.

This directory helps recover the real system map fast.

---

# Start Here

## Standard reading order

1. `00-product-context.md`
2. `01-architecture-and-entrypoints.md`
3. `02-key-flows-and-living-tests.md`
4. `03-impact-map.md`
5. `04-shared-contracts.md`

---

# Fast Reading Modes

## If the task is very local

Read:

1. `00-product-context.md`
2. `01-architecture-and-entrypoints.md`

Then jump to the relevant section in:

- `02-key-flows-and-living-tests.md`
- `03-impact-map.md`

## If the task changes business behavior

Read all files in order.

## If the task changes UI used by operators

Read especially:

- `00-product-context.md`
- `02-key-flows-and-living-tests.md`
- `04-shared-contracts.md`

## If the task changes models / permissions / portal scopes

Read especially:

- `01-architecture-and-entrypoints.md`
- `03-impact-map.md`
- `04-shared-contracts.md`

---

# What Each File Does

## `00-product-context.md`

Explains:

- mission
- users
- production reality
- constraints
- what must be protected

Read first.

---

## `01-architecture-and-entrypoints.md`

Explains:

- URL entrypoints
- runtime structure
- main modules
- where logic tends to live
- where to start reading code

Use when locating implementation ownership.

---

## `02-key-flows-and-living-tests.md`

Explains:

- critical workflows
- real user journeys
- test files that document intended behavior

Use when changing flows.

---

## `03-impact-map.md`

Explains:

- common propagation paths
- if X changes, what else usually moves
- where regressions often hide

Use before coding and before merge.

---

## `04-shared-contracts.md`

Explains:

- reusable cross-surface contracts
- shared UI semantics
- data invariants
- compatibility boundaries

Use before changing anything reused in several places.

---

# How To Use During A Ticket

## Before coding

Ask:

- what surface is touched?
- what other surfaces depend on it?
- does a shared contract exist?
- what tests should move too?

Then read the relevant reference sections.

---

## During coding

Use the reference to:

- avoid duplicate logic
- find canonical helpers
- respect contracts
- detect forgotten propagation

---

## Before merge

Re-read relevant sections and ask:

- docs drift?
- tests drift?
- permission drift?
- UI drift?
- naming drift?
- hidden consumers forgotten?

---

# Source Hierarchy

When sources disagree, trust them in this order:

1. Runtime code
2. Tests proving intended behavior
3. Operational docs
4. Repository reference summaries

This directory is a guide, not the source of truth.

If runtime changed, update this reference.

---

# Rules For Contributors

## Good use

- update relevant sections when architecture changes
- update test references when renamed
- add newly discovered coupling
- simplify wording when clearer

## Bad use

- duplicate full code behavior line by line
- write historical essays
- document temporary branches
- let stale sections accumulate

---

# Writing Standard

Prefer:

- concise facts
- stable truths
- propagation guidance
- canonical ownership hints
- test references

Avoid:

- speculation
- implementation noise
- subjective opinions
- obsolete migration details

---

# For AI Coding Agents

Before major edits:

1. Read `00`
2. Read relevant architecture sections
3. Read impact map
4. Read shared contracts
5. Then modify code

Before finalizing:

1. Re-check propagation
2. Re-check tests
3. Re-check docs drift

Never assume a local file is isolated.

---

# Signals That You Should Read More First

Stop and read more reference docs if you notice:

- duplicated logic
- multiple similar views
- surprising tests failing
- permissions behaving strangely
- portal + scan touching same data
- templates sharing includes
- old helper names with newer wrappers

These usually indicate hidden contracts.

---

# Maintenance Cadence

Update this directory when:

- architecture ownership changes
- critical workflows move
- major tests renamed
- new shared contracts emerge
- repeated regressions reveal hidden coupling

---

# Final Principle

Move fast only after understanding what is connected.

This directory exists to make that understanding fast.
