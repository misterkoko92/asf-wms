# Shipment-Party Findings Remediation Plan

**Date:** 2026-04-12

**Goal:** Turn the five confirmed shipment-party alignment findings into executable remediation slices with explicit ownership, sequencing, validation, and closure criteria.

## Remediation Principles

- Fix invariant breaches before refactoring convenience layers.
- Prefer shared use-case and selector helpers over view-local mutations.
- Keep `AssociationRecipient` only as a refreshed projection while readers are being migrated.
- Close a finding only when both runtime behavior and regression coverage are in place.

## Closure Matrix

| Finding | Severity | Primary area | Recommended wave | Closure mode |
| --- | --- | --- | --- | --- |
| F1. BE rebuild ignores destination scope | P1 | management command + canonical writer | Wave 1 | runtime fix + regression tests |
| F2. Correspondent promotion is organization-only | P1 | event sync + promotion service | Wave 1 | runtime fix + regression tests |
| F3. Recipient HTML profile bypasses use-case layer | P2 | portal HTML | Wave 1 | writer refactor + parity tests |
| F4. Recipient UI API diverges from HTML profile | P2 | UI API | Wave 1 / 2 | writer refactor + shared read payload |
| F5. Import/export contacts is a legacy flat contract | P2 | scan bulk tooling | Wave 3 | explicit ring-fence now, redesign only if approved |

## Finding F1: `rebuild_contacts_from_be_xlsx` is not destination-scoped

### Problem

- `wms/contact_import/canonical_writer.py` resolves `ShipmentRecipientOrganization` by `organization` only.
- The shared contract in `docs/repo-reference/04-shared-contracts.md` requires `(organization, destination)` uniqueness.
- Current tests miss the bug because they cover single-destination scenarios only.

### Remediation

- Change the canonical writer to resolve recipient runtime rows with explicit `(organization, destination)` scope.
- Re-check any helper that assumes one recipient runtime row per organization.
- Keep the command thin; fix the writer/service layer first, then let `rebuild_contacts_from_be_xlsx` inherit the correct behavior.

### Files

- `wms/contact_import/canonical_writer.py`
- `wms/management/commands/rebuild_contacts_from_be_xlsx.py`
- `wms/tests/management/tests_management_rebuild_contacts_from_be_xlsx.py`
- `wms/tests/core/tests_parties_destination_scope.py`

### Tests to add or extend

- One dataset with the same recipient structure on two destinations creates two runtime rows.
- Re-running the rebuild remains idempotent and does not collapse the two rows back into one.
- If shipment links or authorized contacts are present, the rebuild still respects single-default constraints per destination-scoped runtime row.

### Operational follow-up

- After the fix lands, run a one-off audit or repair command against existing data to detect collapsed multi-destination recipient rows.

### Closure criteria

- Multi-destination rebuild fixtures pass.
- Runtime rows remain distinct per destination after repeated rebuilds.
- The writer no longer contains organization-only `ShipmentRecipientOrganization` upserts.

## Finding F2: Correspondent promotion remains organization-only

### Problem

- `contacts/correspondent_recipient_promotion.py` reuses the first runtime recipient row for an organization without destination filtering.
- The event hook in `wms/events/handlers_sync.py` can therefore materialize or reuse the wrong runtime row for multi-destination structures.

### Remediation

- Refactor the promotion service so recipient runtime resolution is destination-aware.
- Reuse the same destination-aware helper for both event-driven promotion and any backfill/repair command.
- Preserve current promotion semantics for single-destination structures.

### Files

- `contacts/correspondent_recipient_promotion.py`
- `wms/events/handlers_sync.py`
- `wms/tests/core/tests_correspondent_recipient_promotion.py`
- `wms/tests/management/tests_management_backfill_correspondent_recipients.py`

### Tests to add or extend

- A correspondent attached to one destination creates or reuses only that destination-scoped runtime recipient.
- A structure active on two destinations produces two distinct runtime recipient rows when needed.
- Re-running promotion/backfill is idempotent.

### Operational follow-up

- Re-run the backfill or equivalent repair job after the code change if existing promoted correspondents were previously collapsed onto one destination.

### Closure criteria

- No organization-only `ShipmentRecipientOrganization.objects.filter(organization=...).first()` remains in the promotion flow.
- Event and backfill paths share the same destination-aware runtime logic.
- Multi-destination promotion tests pass.

## Finding F3: Recipient HTML profile bypasses the shared use-case layer

### Problem

- `wms/views_portal_account.py` still mutates shared runtime and legacy projection rows inline for recipient-scoped profile writes.
- This keeps the portal HTML surface out of the shared V3.3 application boundary.

### Remediation

- Introduce or extend a recipient-profile write use case in `wms/application/parties/use_cases.py`.
- Move sequencing of shared structure fields, main contact fields, recipient flags, and structure-document side effects behind that use case.
- Keep the view responsible only for permissions, form binding, and user-facing messages.

### Files

- `wms/application/parties/use_cases.py`
- `wms/views_portal_account.py`
- `wms/parties/projections.py`
- `wms/tests/views/tests_views_portal.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`
- `wms/tests/core/tests_parties_use_cases.py`

### Tests to add or extend

- Recipient HTML POST updates shared fields through the application use-case.
- Recipient flags round-trip correctly after POST and reload.
- Legacy projection refresh still keeps shipper-side legacy readers aligned while they exist.

### Closure criteria

- The recipient HTML view no longer contains direct shared runtime mutation logic beyond adapter concerns.
- Shared profile write sequencing is covered at the use-case layer.
- HTML recipient profile tests continue to pass with the new boundary.

## Finding F4: Recipient UI API diverges from the HTML profile

### Problem

- `api/v1/ui_views.py` still mutates runtime state partly inline.
- Recipient-scope GET payloads hardcode `notify_deliveries` and `is_delivery_contact` instead of round-tripping the current state.
- The API and HTML surfaces therefore disagree on the same recipient profile contract.

### Remediation

- Route API PATCH through the same recipient-profile use-case used by HTML.
- Replace API-local payload assembly with a shared shipment-party-backed query helper or payload builder.
- Keep permission and serializer validation in the API adapter, not the business write logic.

### Files

- `api/v1/ui_views.py`
- `api/v1/serializers.py`
- `wms/application/parties/use_cases.py`
- `wms/application/portal/dashboard_queries.py` or a new shared recipient-profile query helper
- `api/tests/tests_ui_endpoints.py`
- `api/tests/tests_ui_e2e_workflows.py`

### Tests to add or extend

- `GET /api/v1/ui/portal/recipients/<id>/` returns persisted `notify_deliveries` and `is_delivery_contact`.
- API PATCH updates the same fields as the HTML page and returns the same post-save state.
- Recipient-scope permissions still match the HTML flow.

### Closure criteria

- API PATCH no longer owns inline shipment-party mutation sequencing.
- Recipient-scope GET payload no longer hardcodes recipient flags.
- HTML and API parity tests pass on the same fixture set.

## Finding F5: Contact import/export is still a legacy flat contract

### Problem

- `wms/import_services_contacts.py` and `wms/exports.py` operate on flat contact/address data, not on destination-scoped shipment-party runtime.
- This is not equivalent to the canonical cockpit or recipient registry.

### Recommended closure shape

#### Stage 1: Ring-fence the legacy contract

- Update UI copy, docs, and tests so the feature is clearly presented as bulk contact import/export, not as a second canonical shipment-party entry point.
- Add a regression check that no code path in this feature claims shipment-party parity.

#### Stage 2: Optional redesign

- Only if product needs it, design a dedicated shipment-party-aware bulk import/export workflow with explicit destination, shipper-recipient binding, and contact authorization semantics.
- Treat that redesign as a separate product/project slice, not a hidden subtask of the core migration.

### Files

- `wms/import_services_contacts.py`
- `wms/exports.py`
- `wms/tests/imports/tests_import_services_contacts_extra.py`
- `wms/tests/exports/tests_exports.py`
- relevant scan templates or help text if the UI wording is adjusted
- `docs/repo-reference/02-key-flows-and-living-tests.md`
- `docs/repo-reference/04-shared-contracts.md`

### Closure criteria

- The repo no longer presents import/export as an aligned shipment-party registry surface.
- If a redesign is not approved, the feature is explicitly documented and tested as a legacy bulk boundary.
- If a redesign is approved later, it gets its own design and implementation plan before delivery.

## Sequencing

1. Fix F1 and F2 first because they violate the shared destination-scope contract.
2. Fix F3 next to establish one canonical recipient-profile write boundary.
3. Fix F4 immediately after F3 so API and HTML converge on the same contract.
4. Close F5 by ring-fencing in the same overall migration branch or explicitly defer its redesign with documented rationale.

## Release Gate

Do not call the migration complete until:

- the multi-destination rebuild and promotion tests exist and pass
- recipient HTML/API round-trip the same profile data
- `AssociationRecipient` is no longer a direct write target on migrated surfaces
- repo-reference docs reflect the updated shipment-party boundary
