# Default Repository Reference Layout

Use this default layout unless the repository already has a stronger convention:

```text
docs/
  repo-reference/
    README.md
    01-architecture-and-entrypoints.md
    02-key-flows-and-living-tests.md
    03-impact-map.md
    04-shared-contracts.md
```

## File Roles

### `README.md`

Canonical maintenance entry point.

Should explain:

- what the reference is for
- what it does not replace
- source hierarchy
- when to read it
- when to update it

### `01-architecture-and-entrypoints.md`

Fast mental model rebuild.

Should cover:

- routing or application roots
- runtime layers
- main file clusters
- first files to open by change type

### `02-key-flows-and-living-tests.md`

Critical flows plus the tests that currently encode them.

Should cover:

- main runtime files per flow
- what the flow actually covers
- fastest living reference tests
- operational or functional docs that must stay aligned

### `03-impact-map.md`

Propagation checklist for recurring work.

Should answer:

- what else probably changes with this change?
- what docs or smoke checks should move?
- what tests are the quickest proof of intact wiring?

### `04-shared-contracts.md`

Shared cross-surface contracts that are easy to forget.

Typical examples:

- view or model facades
- shared UI primitives
- cross-surface business registries or synchronization rules
- operations and smoke contracts

## Wiring Expectations

Link the repository reference from:

- `README.md`
- `docs/README.md` when present
- `AGENTS.md` or equivalent repo instructions when present

The agent guardrail should require:

- reading the repository reference before substantial work
- re-checking the impact-map and shared-contract sections before completion
- updating the repository reference when critical routes, flows, contracts, smoke rules, or named reference tests change
