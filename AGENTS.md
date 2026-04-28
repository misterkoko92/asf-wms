# AGENTS.md — ASF-WMS

## Prime Directive

Do not break ASF operations to improve the software.

ASF-WMS is a real production system supporting humanitarian logistics.
Operational continuity, data integrity, workflow reliability, and user trust are more important than technical elegance.

---

## Mission

ASF-WMS serves two parallel goals through one shared codebase:

1. Operate and improve the real ASF logistics system.
2. Progressively shape reusable capabilities for future organizations.

Do not create permanent ASF/product forks.

---

## Priority Order

When tradeoffs exist, prefer:

1. Production safety
2. Data integrity
3. Workflow reliability
4. Security
5. Speed for frequent users
6. Maintainability
7. Reduce founder dependency
8. Productization readiness
9. Technical elegance

---

## Execution Style

Prefer:

- small reversible changes
- clear ownership
- tests near risk
- incremental refactors
- pragmatic improvements
- explicit contracts

Avoid:

- big-bang rewrites
- speculative architecture
- behavior drift without tests
- accidental UX friction
- exposing real ASF data
- hidden coupling growth

---

## Change Classification

Before acting, classify the request:

- A. ASF operational need
- B. Generic reusable capability
- C. Organization configuration
- D. ASF-specific extension
- E. Legacy debt reduction
- F. Experimental feature

Prefer solutions that satisfy A+B or A+C when reasonable.

---

## Repository Navigation Rule

Before substantial work, read:

1. `docs/repo-reference/README.md`
2. Relevant linked sections
3. `docs/policies/agent-guardrails.md`

Use the repository reference to understand:

- architecture ownership
- critical flows
- propagation risk
- shared contracts
- reference tests

Never assume a local file is isolated.

---

## Codex Git Workflow

- Do not create commits without explicit user approval.
- Before committing, show a concise summary of intended changes and the proposed commit message.
- Stage only the files intentionally included in the requested commit.
- Commit staged files only.
- If there are no meaningful changes, do not create empty or cosmetic commits.
- Use concise conventional-style commit messages unless the user provides another format.
- After committing, show the commit hash, committed files, and `git status --short`.

---

## Production Reality Rule

Current production constraints matter.

Prefer solutions that work well with modest infrastructure, legacy Django flows, and low-maintenance operations.

Do not introduce heavy platform assumptions unless explicitly requested.

---

## User Reality Rule

Warehouse and operations users optimize for:

- speed
- clarity
- low friction
- reliability

Back-office users optimize for:

- truth
- traceability
- exports
- coordination

External partners optimize for:

- trust
- simplicity
- visibility

Respect the real user before idealized UX theory.

---

## Sensitive Zones

Use extra caution when touching:

- stock logic
- cartons / packing
- shipment statuses
- planning eligibility
- permissions
- portal scopes
- document generation
- notifications
- shared templates and assets
- data migrations

---

## Documentation Drift Control

Every implementation task must include a documentation impact check before completion.

If documentation is impacted, update the minimum relevant docs in the same work.

If documentation is not impacted, explicitly state:

`No documentation update required.`

Before stating that, verify the change did not alter:

- user-visible behavior
- core workflows or critical routes
- roles, permissions, or access rules
- shared contracts or service boundaries
- data model, field meaning, or business rules
- operational, deployment, or security expectations
- agent governance or repo-reference guidance

---

## Completion Rule

Before declaring work complete, re-check:

- propagation impact
- tests
- docs drift
- permissions
- user-visible behavior
- operational safety

---

## If Unsure

1. Read more context
2. Preserve behavior
3. Choose the smallest safe path
4. Ask before risky actions

---

## Final Principle

This software exists to move humanitarian aid efficiently and safely.

Every change should remain aligned with that purpose.
