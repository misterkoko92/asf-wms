# Impact Map System

This file is the dispatcher for all propagation checklists.

Use it before any non-trivial change to identify:

- which specialized impact maps must be read
- which other surfaces may be coupled
- where hidden regressions usually appear
- what minimum verification should happen before merge

This file stays intentionally short.

Detailed operational checklists live in the specialized `03x-impact-*.md` files.

---

## TL;DR — 30 Second Rule

Before changing anything beyond a tiny local fix:

1. Identify the primary surface
2. Open the matching impact map
3. Open any linked cross-surface maps
4. Check shared contracts if relevant
5. Run nearest tests
6. Update docs if behavior changed

---

## Current Registry

| File | Primary Scope |
|------|---------------|
| `03a-impact-scan.md` | Internal scan / warehouse surfaces |
| `03b-impact-portal.md` | Partner portal / external users |
| `03c-impact-shipments.md` | Shipment lifecycle / tracking / cartons |
| `03d-impact-parties.md` | Contacts / recipients / shipment-party graph |
| `03e-impact-print-documents.md` | Labels / customs / PDFs / print flows |
| `03f-impact-planning.md` | Planning runs / exports / artifacts |
| `03g-impact-shared-ui-api.md` | Shared UI primitives / mirrored APIs |
| `03h-impact-email-events.md` | Emails / notifications / async side effects |

---

## Which File To Read

| Change Type | Read First |
|------------|------------|
| Scan page / warehouse UI | `03a-impact-scan.md` |
| Portal page / partner workflow | `03b-impact-portal.md` |
| Shipment edit / carton / tracking | `03c-impact-shipments.md` |
| Contacts / recipients / permissions | `03d-impact-parties.md` |
| Labels / customs / PDFs / print | `03e-impact-print-documents.md` |
| Planning / exports / artifacts | `03f-impact-planning.md` |
| Shared components / CSS / UI API | `03g-impact-shared-ui-api.md` |
| Emails / notifications / jobs | `03h-impact-email-events.md` |

---

## Common Cross-Surface Changes

| Change Type | Read Combination |
|------------|------------------|
| Shipment-party / contacts | `03b` + `03c` + `03d` |
| Public tracking QR flow | `03c` + `03e` + `03h` |
| Shared scan assets | `03a` + `03b` + `03f` + `03g` |
| Shared UI primitive | `03a` + `03b` + `03g` |
| Planning artifact export | `03f` + `03e` |
| Shipment status affecting notifications | `03c` + `03h` |
| Portal order creating shipments | `03b` + `03c` + `03d` |
| New API replacing HTML cockpit | Scan: `03a` + `03g` / Portal: `03b` + `03g` |

If unsure, read more than one file.

---

## Required Structure For Every Specialized File

Every `03x-impact-*.md` file should use one document title, then sections covering:

- when to read this file
- also read
- always check
- ask yourself
- run first

The current files use a document title plus H2 sections. Keep that structure unless there is a specific reason to change it.

Optional but recommended sections:

- known traps
- historical pitfalls
- docs to update

---

## Cross-Link Maintenance Rule

Whenever a specialized impact-map file is modified:

- verify its `Also read` section
- verify reciprocal links where relevant
- remove stale couplings
- add newly discovered couplings
- keep wording concrete and actionable

This takes less than one minute and prevents drift.

---

## Naming Rule

Keep stable filenames once created.

Do not renumber or rename casually.

If a new domain appears, append the next free suffix:

- `03i-impact-...`
- `03j-impact-...`

---

## Scope Rule

Prefer adding a new specialized file over bloating an existing one when:

- the domain has unique risks
- the checklist exceeds readable size
- different tests/docs apply
- ownership is distinct

---

## Anti-Bloat Rule

Do not duplicate detailed checklists in this dispatcher.

This file routes attention.

Specialized files contain operational precision.

---

## Review Rule Before Merge

For medium/high-risk PRs ask:

1. Which impact maps were consulted?
2. Were linked maps also checked?
3. Were tests run?
4. Did docs drift?
5. Any hidden side effect left unverified?

---

## Rule For Future Contributors

Any new `03x-impact-*.md` file must:

- follow the required section format
- declare `Also read`
- be added to the registry above
- be referenced in cross-surface combinations when relevant
- use concrete repo paths, not vague prose

---

## Final Rule

Local changes in ASF-WMS often have non-local consequences.

If a change feels isolated, verify that assumption.
