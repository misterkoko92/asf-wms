# Shipment-Party Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate the remaining recipient and contact surfaces toward shipment-party runtime as the single business source of truth, while keeping `AssociationRecipient` only as a temporary compatibility projection and closing the five confirmed alignment findings.

**Architecture:** Execute the migration in three waves. Wave 1 fixes destination-scope invariant breaches and unifies recipient-profile writes behind `wms/application/parties/use_cases.py`. Wave 2 aligns HTML and UI API reads on shared shipment-party-backed query helpers and reduces projection-specific logic. Wave 3 contracts the remaining compatibility surface around `AssociationRecipient` and formally ring-fences or redesigns legacy bulk contact import/export.

**Tech Stack:** Django views, Django ORM, Django management commands, shipment-party application/use-case modules, Django tests, repo-reference docs

---

## Wave 1: Fix writers and destination-scope invariants

### Task 1: Lock the BE rebuild contract against organization-only recipient upserts

**Files:**
- Modify: `wms/tests/management/tests_management_rebuild_contacts_from_be_xlsx.py`
- Verify: `wms/contact_import/canonical_writer.py`
- Verify: `wms/models_domain/shipment_parties.py`

**Step 1: Write the failing tests**

- Add a dataset fixture where the same organization appears as a recipient on two destinations.
- Assert the rebuild creates two `ShipmentRecipientOrganization` rows, not one overwritten row.
- Add an idempotency check confirming a second run does not collapse the pair back into one runtime row.

**Step 2: Run the focused suite**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.management.tests_management_rebuild_contacts_from_be_xlsx -v 2
```

Expected:

- FAIL because the current writer still resolves recipients by `organization` only.

### Task 2: Fix the canonical writer and command wrapper

**Files:**
- Modify: `wms/contact_import/canonical_writer.py`
- Modify: `wms/management/commands/rebuild_contacts_from_be_xlsx.py`
- Modify: `wms/tests/management/tests_management_rebuild_contacts_from_be_xlsx.py`

**Step 1: Write the minimal implementation**

- Change the canonical writer to resolve `ShipmentRecipientOrganization` with explicit `(organization, destination)` scope.
- Keep the command wrapper thin and reuse the corrected writer.
- Re-check default authorized-contact handling so it remains valid per destination-scoped runtime row.

**Step 2: Re-run the focused suite**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.management.tests_management_rebuild_contacts_from_be_xlsx -v 2
```

Expected:

- PASS on the new multi-destination coverage.

### Task 3: Lock correspondent promotion on destination-aware runtime behavior

**Files:**
- Modify: `wms/tests/core/tests_correspondent_recipient_promotion.py`
- Modify: `wms/tests/management/tests_management_backfill_correspondent_recipients.py`
- Verify: `contacts/correspondent_recipient_promotion.py`
- Verify: `wms/events/handlers_sync.py`

**Step 1: Write the failing tests**

- Add a case where one organization is promoted as a recipient for two destinations and must not reuse one shared runtime row.
- Add a backfill/event-driven case that proves the same logic is applied outside the direct promotion call.
- Keep single-destination expectations unchanged.

**Step 2: Run the focused suites**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.core.tests_correspondent_recipient_promotion wms.tests.management.tests_management_backfill_correspondent_recipients -v 2
```

Expected:

- FAIL because the promotion service still uses an organization-only runtime lookup.

### Task 4: Refactor correspondent promotion to use destination-aware helpers

**Files:**
- Modify: `contacts/correspondent_recipient_promotion.py`
- Modify: `wms/events/handlers_sync.py`
- Modify: `wms/tests/core/tests_correspondent_recipient_promotion.py`
- Modify: `wms/tests/management/tests_management_backfill_correspondent_recipients.py`

**Step 1: Write the minimal implementation**

- Replace organization-only runtime recipient reuse with explicit destination-aware resolution.
- Reuse the same helper in event and backfill paths where possible.
- Keep projection or ancillary role/tag synchronization unchanged unless the new tests show a true dependency.

**Step 2: Re-run the focused suites**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.core.tests_correspondent_recipient_promotion wms.tests.management.tests_management_backfill_correspondent_recipients -v 2
```

Expected:

- PASS with multi-destination coverage.

### Task 5: Move recipient HTML profile writes behind the shared use-case layer

**Files:**
- Modify: `wms/application/parties/use_cases.py`
- Modify: `wms/views_portal_account.py`
- Modify: `wms/parties/projections.py`
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/core/tests_parties_use_cases.py`

**Step 1: Write the failing tests**

- Add or extend recipient-scope POST tests proving the HTML view uses the shared application contract for:
  - shared structure fields
  - main contact fields
  - recipient flags
  - structure documents
- Add use-case-level tests for the new sequencing.

**Step 2: Run the focused suites**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.core.tests_parties_use_cases -v 2
```

Expected:

- FAIL because the current view still owns part of the runtime mutation sequencing inline.

**Step 3: Write the minimal implementation**

- Extract or extend one recipient-profile write use case in `wms/application/parties/use_cases.py`.
- Make the HTML view an adapter for permission checks, form parsing, and messages only.
- Keep any legacy `AssociationRecipient` refresh behind `wms/parties/projections.py`.

**Step 4: Re-run the focused suites**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.core.tests_parties_use_cases -v 2
```

Expected:

- PASS with the HTML surface now aligned on the shared write contract.

### Task 6: Route recipient UI API PATCH through the same use-case layer

**Files:**
- Modify: `api/v1/ui_views.py`
- Modify: `api/v1/serializers.py`
- Modify: `wms/application/parties/use_cases.py`
- Modify: `api/tests/tests_ui_endpoints.py`

**Step 1: Write the failing tests**

- Add recipient-scope API PATCH tests proving the shared profile fields and recipient flags are actually persisted.
- Assert API write behavior matches the HTML page for the same runtime fixture.

**Step 2: Run the focused suite**

Run:

```bash
./.venv/bin/python manage.py test api.tests.tests_ui_endpoints -v 2
```

Expected:

- FAIL because the current API code still mutates runtime rows partly inline and does not fully round-trip flags.

**Step 3: Write the minimal implementation**

- Remove API-local mutation sequencing where the shared use case should own it.
- Keep serializer validation in the API adapter.
- Reuse the recipient-profile use case introduced in Task 5.

**Step 4: Re-run the focused suite**

Run:

```bash
./.venv/bin/python manage.py test api.tests.tests_ui_endpoints -v 2
```

Expected:

- PASS on shared write-path parity.

## Wave 2: Align readers and reduce projection-specific logic

### Task 7: Unify recipient HTML and API reads on one shipment-party-backed payload contract

**Files:**
- Modify: `wms/application/portal/dashboard_queries.py` or create a dedicated shared recipient-profile query helper
- Modify: `wms/views_portal_account.py`
- Modify: `api/v1/ui_views.py`
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `api/tests/tests_ui_endpoints.py`
- Optional: `api/tests/tests_ui_e2e_workflows.py`

**Step 1: Write the failing tests**

- Assert the HTML recipient profile and `GET /api/v1/ui/portal/recipients/<id>/` expose the same persisted flags and shared fields.
- Add a regression test proving the API no longer hardcodes `notify_deliveries=False` and `is_delivery_contact=False`.

**Step 2: Run the focused suites**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal api.tests.tests_ui_endpoints -v 2
```

Expected:

- FAIL until both adapters consume the same shared payload contract.

**Step 3: Write the minimal implementation**

- Move recipient payload assembly into one shared shipment-party-backed query helper.
- Keep HTML and API adapters thin and format-specific.
- Remove duplicated fallback logic that only exists to keep `AssociationRecipient` readable on already migrated surfaces.

**Step 4: Re-run the focused suites**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_portal api.tests.tests_ui_endpoints -v 2
```

Expected:

- PASS with HTML/API parity.

### Task 8: Audit remaining migrated-surface reads of `AssociationRecipient`

**Files:**
- Verify/modify: `wms/views_portal_account.py`
- Verify/modify: `wms/application/portal/dashboard_queries.py`
- Verify/modify: `api/v1/ui_views.py`
- Verify/modify: `wms/parties/projections.py`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Inspect the migrated surfaces**

- Confirm migrated recipient profile HTML/API surfaces no longer depend on `AssociationRecipient` as a primary read model.
- Keep only projection refresh paths that are still needed for unmigrated legacy readers.

**Step 2: Update docs**

- Document the narrowed role of `AssociationRecipient` as a compatibility projection.
- Document the shared write and read boundaries for recipient profile data.

## Wave 3: Contract the compatibility surface

### Task 9: Ring-fence legacy contact import/export

**Files:**
- Modify: `wms/import_services_contacts.py`
- Modify: `wms/exports.py`
- Modify: relevant scan templates or copy if they currently imply shipment-party parity
- Modify: `wms/tests/imports/tests_import_services_contacts_extra.py`
- Modify: `wms/tests/exports/tests_exports.py`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Write the failing tests or documentation checks**

- Add regression checks that the feature is described as a legacy bulk contact import/export surface.
- If there is user-visible copy that implies canonical shipment-party parity, lock the corrected wording in tests.

**Step 2: Write the minimal implementation**

- Clarify the contract boundary in code comments, help text, or docs.
- Avoid accidental coupling to shipment-party semantics unless a dedicated redesign is explicitly approved.

**Step 3: Re-run the focused suites**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.imports.tests_import_services_contacts_extra wms.tests.exports.tests_exports -v 2
```

Expected:

- PASS with the legacy boundary made explicit.

### Task 10: Decide whether a shipment-party bulk redesign is needed

**Files:**
- Create later only if approved: a separate design and implementation plan

**Step 1: Product decision**

- If bulk shipment-party management is required, open a separate design slice covering:
  - destination-aware recipient rows
  - shipper-recipient links
  - authorized recipient contacts
  - import/export conflict resolution and review UX

**Step 2: If not approved**

- Keep the legacy bulk surface explicitly ring-fenced and out of the canonical alignment claims.

## Final Verification

### Task 11: Run the targeted regression suites

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.management.tests_management_rebuild_contacts_from_be_xlsx \
  wms.tests.management.tests_management_backfill_correspondent_recipients \
  wms.tests.core.tests_correspondent_recipient_promotion \
  wms.tests.core.tests_parties_destination_scope \
  wms.tests.core.tests_parties_use_cases \
  wms.tests.views.tests_views_portal \
  api.tests.tests_ui_endpoints \
  wms.tests.imports.tests_import_services_contacts_extra \
  wms.tests.exports.tests_exports \
  -v 2
```

Expected:

- PASS on the multi-destination invariant tests, recipient HTML/API parity, and legacy import/export boundary checks.

### Task 12: Inspect the final diff

Run:

```bash
git diff -- \
  wms/contact_import/canonical_writer.py \
  wms/management/commands/rebuild_contacts_from_be_xlsx.py \
  contacts/correspondent_recipient_promotion.py \
  wms/events/handlers_sync.py \
  wms/application/parties/use_cases.py \
  wms/application/portal/dashboard_queries.py \
  wms/views_portal_account.py \
  api/v1/ui_views.py \
  api/v1/serializers.py \
  wms/import_services_contacts.py \
  wms/exports.py \
  docs/repo-reference/02-key-flows-and-living-tests.md \
  docs/repo-reference/04-shared-contracts.md \
  docs/plans/2026-04-12-shipment-party-alignment-design.md \
  docs/plans/2026-04-12-shipment-party-findings-remediation-plan.md \
  docs/plans/2026-04-12-shipment-party-alignment-implementation-plan.md
```

Expected:

- Only shipment-party alignment, compatibility-projection narrowing, import/export contract-boundary, and documentation updates are touched.
