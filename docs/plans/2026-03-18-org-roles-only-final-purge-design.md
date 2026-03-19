# Org-Roles-Only Final Purge Design

## Context

- Current production data has already been reset and rebuilt from the canonical BE workbook.
- Core shipment and portal authorization flows already validate through `OrganizationRoleAssignment`, `ShipperScope`, `RecipientBinding`, `OrganizationContact`, and `Destination.correspondent_contact`.
- The repository is not yet org-roles-only: runtime code still exposes or consumes legacy contact concepts such as `ContactTag`, `Contact.tags`, `Contact.destination`, `Contact.destinations`, `Contact.linked_shippers`, and `MigrationReviewItem.legacy_contact`.
- The user goal is explicit: remove every remaining legacy reference from runtime and active tests, clean the Django admin and contact UI surfaces, and end with a verified and provable `100% org-roles` state.

## Goals

1. Make org-role models the only source of truth for contact capabilities and permissions across admin, scan, portal, imports, exports, volunteer, planning, communication, and print.
2. Remove legacy runtime behavior, legacy compatibility UI, and legacy compatibility data contracts to avoid user confusion.
3. Simplify contact management around a single model:
   - `Contact` remains the base entity for organizations and people.
   - role semantics move exclusively to `OrganizationRoleAssignment`, `OrganizationContact`, `OrganizationRoleContact`, `ShipperScope`, `RecipientBinding`, and `Destination.correspondent_contact`.
4. End with automated proof:
   - full test suite green,
   - anti-legacy guardrails green,
   - repo-wide audit updated,
   - final canonical reset runbook ready.

## Non-Goals

- No Next/React work. Legacy Django stack only.
- No new product features beyond what is required to remove legacy contact behavior.
- No attempt to preserve old CSV/import/export compatibility fields. Legacy aliases are removed, not hidden.

## Current Confirmed Gaps

### Runtime gaps

- Django admin still exposes legacy contact fields and `ContactTag`.
- Contact import/export still reads or emits legacy concepts (`tags`, `destinations`, `linked_shippers`).
- Portal recipient sync still keeps a legacy fallback lookup.
- Legacy helper modules remain callable in runtime (`contact_filters`, `view_utils`, destination scope helpers, correspondent promotion helpers).
- Migration review tooling still carries `legacy_contact` and legacy option suggestion logic.

### Schema gaps

- `contacts.ContactTag`
- `contacts.Contact.tags`
- `contacts.Contact.destination`
- `contacts.Contact.destinations`
- `contacts.Contact.linked_shippers`
- `wms.MigrationReviewItem.legacy_contact`

### Test-suite gaps

- Some tests still encode or mention legacy fields, tags, or linked shipper semantics.
- There is no repository guard that fails when forbidden legacy symbols reappear.

## Target State

### Contact domain

- `Contact` stores only identity, organization membership, addresses, operational identifiers (`asf_id`), and active state.
- `OrganizationRoleAssignment` is the only role switch.
- `OrganizationContact` and `OrganizationRoleContact` manage people attached to organizations and role primaries.
- `ShipperScope` and `RecipientBinding` are the only authorization scope/binding mechanisms.
- `Destination.correspondent_contact` is the only correspondent source for active destinations unless an explicit org-role based replacement is introduced.

### Admin domain

- Django admin no longer exposes legacy contact fields or `ContactTag`.
- Admin contact editing becomes role-oriented:
  - organization/person identity,
  - addresses,
  - organization membership,
  - role assignments,
  - organization contacts,
  - shipper scopes,
  - recipient bindings,
  - destination correspondent assignment.
- Migration-review-only screens and legacy rescue panels are removed once the schema is gone.

### Scan and contact management UI

- Contact creation, edition, deletion, import, and export stop using legacy columns and selectors.
- Scan import/export exposes canonical org-role data instead of flat legacy compatibility fields.
- The scan contacts cockpit, if kept, becomes an org-role-only surface with no legacy fallback actions.

### Portal domain

- `sync_association_recipient_to_contact` resolves and writes only through org-role structures.
- No fallback lookup based on old note markers or legacy synced contact conventions.
- No runtime dependency on migration review items or legacy contact references.

### Volunteer / planning / communication / print

- These domains must not read legacy contact fields directly.
- Any remaining contact lookup must resolve through active organizations, role assignments, or explicit foreign keys.

## Migration Strategy

This refactor stays in one initiative, but uses two technical checkpoints to keep debugging tractable.

### Checkpoint A: Runtime purge

- Remove all legacy reads and writes from runtime code.
- Replace Django admin and scan/import/export surfaces with org-role-only behavior.
- Remove portal fallbacks and helper utilities that keep legacy semantics alive.
- Update active tests and fixtures so runtime behavior is exercised only through org-role models.

Checkpoint A succeeds when:
- runtime grep shows no legacy symbol usage outside allowed historical areas,
- full suite is green,
- admin and scan surfaces no longer mention or manipulate legacy fields.

### Checkpoint B: Schema purge

- Remove legacy schema and the runtime code that only existed to bridge migration.
- Delete or refactor migration review tooling that depends on `legacy_contact`.
- Add migrations that physically drop obsolete legacy tables/columns.
- Re-run the full suite and anti-legacy audit after schema removal.

Checkpoint B succeeds when:
- forbidden symbols no longer exist in runtime code or active tests,
- migrations apply cleanly from current `main`,
- canonical reset command works without recreating legacy artifacts.

## Verification Strategy

### Automated proof

- Full `uv run make coverage` on the branch.
- Repo guard test that scans runtime and active test paths for forbidden legacy symbols.
- Targeted smoke tests for:
  - shipment creation,
  - scan imports,
  - portal recipient sync,
  - Django admin contact flows,
  - contact export/import,
  - canonical reset/rebuild.

### Manual proof

- Django admin:
  - no `ContactTag` admin,
  - no editable `tags`, `destination`, `destinations`, `linked_shippers`.
- Scan contact management:
  - create/edit/import/export flows expose only org-role data.
- Portal:
  - association recipient sync works without legacy lookup.
- Final data:
  - canonical reset completes,
  - no legacy contact artifacts recreated.

## Test Strategy

- Rewrite fixtures to build contacts through `Contact`, `OrganizationRoleAssignment`, `OrganizationContact`, `OrganizationRoleContact`, `ShipperScope`, `RecipientBinding`, and `Destination.correspondent_contact`.
- Remove tests that only validate forbidden legacy behavior.
- Keep historical migration tests only if they protect migration graph integrity; do not keep them as runtime behavior evidence.
- Add one repo-wide anti-legacy guard with a small explicit allowlist for historical migrations and archived docs.

## Risks

- Contact admin cleanup may break staff workflows if org-role management screens do not replace the removed fields cleanly.
- Schema removal may surface hidden dependencies in management commands or old tests.
- Import/export replacement may require a new documented workbook format for non-BE operational contact administration.
- Historical migration references to removed models must remain untouched; the purge applies to runtime code and new migrations, not to past migration files.

## Recommended Order

1. Create a baseline audit and guard tests.
2. Remove runtime legacy reads/writes.
3. Clean admin and scan/import/export surfaces.
4. Remove portal and migration review fallbacks.
5. Update secondary domains and fixtures.
6. Drop the legacy schema.
7. Run full verification.
8. Perform a final canonical reset and smoke test.

## Definition of Done

- Runtime code and active tests are org-roles-only.
- Django admin and scan contact management no longer expose legacy concepts.
- Portal sync and contact rebuild no longer depend on legacy compatibility helpers.
- Legacy schema is removed.
- Canonical reset completes successfully on the final branch.
- A repo-wide audit plus automated guardrails let us answer, with evidence, that the repository is now `100%` migrated to org roles.
