# Shipment-Party Alignment Design

**Date:** 2026-04-12

**Goal:** Align every business-critical contact and recipient management surface on the current shipment-party runtime, keep `AssociationRecipient` only as a temporary compatibility projection, and close the five confirmed alignment findings without destabilizing the legacy Django stack.

## Scope

- Legacy Django stack only.
- Contact and recipient write paths that create, update, rebuild, or synchronize shipment-party runtime data.
- Recipient-scoped HTML and UI API profile surfaces.
- Batch and event-driven flows that materialize or promote recipient runtime rows.
- The legacy contact import/export surface only insofar as its contract boundary must be clarified or redesigned.

## Non-Goals

- Do not touch paused Next/React migration scope.
- Do not reopen translation work.
- Do not remove `AssociationRecipient` in one step while production surfaces still read it.
- Do not redesign unrelated shipment, planning, or inventory flows.
- Do not promise a full bulk import/export redesign in the same wave as the writer-alignment fixes.

## Confirmed Baseline

### Already aligned surfaces

- Scan contacts cockpit writes recipient shared fields through `update_runtime_recipient_shared_profile(...)`.
- Shipper portal recipient create/update flows write shared recipient data through `update_recipient_shared_profile(...)`.
- Public account request review provisions the runtime recipient organization and `PortalAccessGrant` in the same flow.
- Recipient product preferences are already canonical on `ShipmentRecipientOrganization`.
- Operational order and shipment reads already consume shipment-party runtime data instead of a standalone legacy CRUD model.

### Confirmed gaps

1. `rebuild_contacts_from_be_xlsx` rebuilds `ShipmentRecipientOrganization` rows with an organization-only lookup, which violates the shared `(organization, destination)` scope contract.
2. Correspondent-to-recipient promotion still reuses an organization-level recipient runtime row instead of destination-aware runtime rows.
3. The recipient-scoped HTML profile editor writes runtime and legacy projection data directly in `wms/views_portal_account.py` instead of going through the shared application use-case layer.
4. The recipient-scoped UI API does not round-trip recipient flags consistently with the HTML page and still mutates runtime rows partly inline.
5. Contact import/export remains a flat legacy contract, not a shipment-party-aligned registry surface.

## Current Model Decision

- `ShipmentRecipientOrganization`, `ShipmentRecipientContact`, `ShipmentShipperRecipientLink`, `ShipmentAuthorizedRecipientContact`, and `PortalAccessGrant` are the current business runtime.
- `AssociationRecipient` is not the target model anymore.
- `AssociationRecipient` remains temporarily useful only as a compatibility projection for legacy readers that are not migrated yet.

## Approved Strategy

### 1. Writer-first migration

- Fix canonical writers and invariant enforcement before reducing legacy readers.
- Make destination-aware runtime writes the hard rule everywhere new recipient rows are created or resolved.
- Treat any remaining direct `AssociationRecipient` write as technical debt to be removed.

### 2. Keep `AssociationRecipient` as a generated projection during the transition

- Shared writes land on shipment-party runtime first.
- Legacy `AssociationRecipient` refresh stays centralized in `wms/parties/projections.py`.
- Readers that still depend on `AssociationRecipient` are tolerated only until a shipment-party-backed equivalent exists.

### 3. One application contract for recipient profile writes

- Recipient-scoped HTML and UI API profile writes must converge on `wms/application/parties/use_cases.py`.
- The use-case layer owns sequencing for:
  - shared structure fields
  - main contact fields
  - recipient flags
  - structure documents
  - legacy projection refresh when still required

### 4. Destination scope is a hard invariant

- Any code resolving or mutating `ShipmentRecipientOrganization` must use destination-aware selectors or explicit `(organization, destination)` filters.
- Organization-only assumptions are no longer valid shared behavior.

### 5. Legacy bulk import/export gets an explicit contract

- Short term: stop treating contact import/export as another entry point into the canonical shipment-party registry.
- Medium term: decide whether product actually needs a shipment-party-aware bulk workflow before attempting a rewrite.

## Target Architecture

### Canonical write path

1. UI, command, or event adapter gathers validated input.
2. Adapter calls a shared use-case in `wms/application/parties/use_cases.py`.
3. The use-case resolves destination-aware runtime rows and applies graph mutations.
4. If legacy compatibility is still needed, projection refresh runs via `wms/parties/projections.py`.
5. Readers consume shipment-party query helpers, not view-local rebuild logic.

### Canonical read path

- Recipient HTML pages and UI API endpoints should read from shared shipment-party-backed query helpers.
- `AssociationRecipient` should not be the primary read source for new or migrated screens.
- Any flag or summary exposed in both HTML and API must be produced by one shared payload builder or one shared query contract.

## Migration Waves

### Wave 1: Writer and invariant alignment

- Fix the BE rebuild pipeline to honor `(organization, destination)`.
- Fix correspondent promotion and backfill/event sync to materialize destination-aware recipient runtime rows.
- Move recipient profile HTML writes behind the shared application use-case layer.
- Move recipient profile API writes behind the same use-case layer.

### Wave 2: Reader parity and projection minimization

- Align recipient HTML and API read payloads on one shipment-party-backed query contract.
- Remove remaining view-local projection refresh and runtime mutation logic.
- Reduce direct `AssociationRecipient` reads on migrated surfaces.

### Wave 3: Compatibility contraction

- Leave `AssociationRecipient` as a generated projection only for truly unmigrated legacy readers.
- Reclassify or redesign contact import/export so it no longer pretends to be the same canonical referential.
- Remove `AssociationRecipient` only after no critical route, export, or job depends on it as a primary source.

## Exit Criteria

- No business-critical write path creates or updates recipient runtime data outside `wms/application/parties/use_cases.py`.
- No destination-aware runtime flow relies on organization-only `ShipmentRecipientOrganization` resolution.
- Recipient HTML and UI API profile surfaces round-trip the same shared data and flags.
- `AssociationRecipient` is refreshed only as a compatibility projection, not as a source of truth.
- Contact import/export is either explicitly ring-fenced as a legacy bulk contract or replaced by a shipment-party-aware bulk workflow.

## Risks And Guardrails

- The highest regression risk is silent data drift between runtime and projection rows; writer unification must land before reader cleanup.
- Multi-destination organizations need dedicated tests because current single-destination fixtures hide the most important invariant breach.
- Import/export should not be folded into the same execution wave unless the product explicitly wants a real bulk shipment-party registry.

## Recommended Delivery Shape

- Deliver the migration in three waves, not as a big-bang purge.
- Treat findings 1 and 2 as priority blockers because they violate the current destination-scope contract.
- Treat findings 3 and 4 as parity and maintainability blockers because they keep HTML/API behavior divergent.
- Treat finding 5 as a contract-boundary decision: ring-fence first, redesign only if the bulk workflow remains strategically important.
