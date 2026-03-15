# Operational Reset and Contact Rebuild Design

**Date:** 2026-03-15

**Goal:** Reset the local WMS database down to stable reference/configuration data, then rebuild a clean contact and destination baseline from the user-provided `BE 2025 full.xlsx` so the resulting data matches real operational usage rather than the current test-only state.

## Scope

- Keep all work on the legacy Django stack only.
- Add a safe reset flow for operational data and contact data.
- Preserve stable reference/configuration data:
  - auth/contenttypes/sessions
  - warehouses, locations, rack colors
  - product catalog and related reference objects
  - print templates/packs/mappings
  - communication templates
  - runtime settings and other stable rules/templates
- Rebuild a clean baseline for:
  - contacts and contact addresses
  - destinations and destination correspondents
  - organization role assignments
  - shipper scopes
  - recipient bindings
  - legacy `linked_shippers` compatibility data
- Produce review output for ambiguous rows instead of silently guessing.

## Non-Goals

- Do not touch paused Next/React migration files.
- Do not preserve historical operational objects such as shipments, receipts, cartons, orders, planning runs, billing documents, or generated artifacts.
- Do not attempt to reconstruct planning runs, flights, billing history, or print artifact history from the BE workbook.
- Do not rebuild `PlanningDestinationRule` during the first reconstruction pass; those rules can be recreated later once destinations are back in place.
- Do not import the raw XLSX directly into runtime tables without a normalization/review step.

## Constraints

- The reset must be explicit and allowlisted, not heuristic.
- The reset must run in a single transaction so a failure rolls back the whole purge.
- The rebuild must be replayable on an empty post-reset database.
- The rebuild target should match real runtime usage:
  - legacy contact/destination flows must keep working
  - org-role structures should become the cleaner source of truth
- `Destination` cannot be preserved across the reset because it depends on correspondent contacts that are being rebuilt.
- `PlanningDestinationRule` must be removed together with `Destination`, while `PlanningParameterSet` can stay.

## Data Classification

### Keep

- `auth.*`
- `contenttypes.*`
- `sessions.*`
- `wms.Warehouse`, `wms.Location`, `wms.RackColor`
- `wms.Product`, `wms.ProductCategory`, `wms.ProductTag`, `wms.ProductKitItem`
- `wms.CartonFormat`
- `wms.PrintTemplate`, `wms.PrintPack`, `wms.PrintPackDocument`, `wms.PrintCellMapping`
- `wms.DocumentRequirementTemplate`
- `wms.CommunicationTemplate`
- `wms.PlanningParameterSet`
- `wms.BillingComputationProfile`, `wms.BillingServiceCatalogItem`
- `wms.RoleEventPolicy`
- `wms.ShipmentUnitEquivalenceRule`
- `wms.WmsRuntimeSettings`

### Delete

- `admin.LogEntry`
- `contacts.Contact`, `contacts.ContactAddress`, `contacts.ContactTag`
- `wms.Destination`, `wms.DestinationCorrespondentDefault`, `wms.DestinationCorrespondentOverride`
- `wms.OrganizationRoleAssignment`, `wms.OrganizationContact`, `wms.OrganizationRoleContact`, `wms.OrganizationRoleDocument`
- `wms.RecipientBinding`, `wms.ShipperScope`, `wms.ContactSubscription`, `wms.ComplianceOverride`, `wms.MigrationReviewItem`
- `wms.Shipment`, `wms.ShipmentTrackingEvent`, `wms.ShipmentSequence`
- `wms.Document`, `wms.GeneratedPrintArtifact`, `wms.GeneratedPrintArtifactItem`
- `wms.Order`, `wms.OrderLine`, `wms.OrderDocument`, `wms.OrderReservation`, `wms.PublicOrderLink`
- `wms.Receipt`, `wms.ReceiptLine`, `wms.ReceiptHorsFormat`, `wms.ReceiptShipmentAllocation`, `wms.ReceiptSequence`, `wms.ReceiptDonorSequence`
- `wms.Carton`, `wms.CartonItem`, `wms.CartonStatusEvent`
- `wms.ProductLot`, `wms.StockMovement`
- `wms.AssociationProfile`, `wms.AssociationPortalContact`, `wms.AssociationRecipient`
- `wms.PublicAccountRequest`, `wms.VolunteerAccountRequest`, `wms.AccountDocument`
- `wms.AssociationBillingProfile`, `wms.AssociationBillingChangeRequest`, `wms.BillingAssociationPriceOverride`
- `wms.BillingDocument`, `wms.BillingDocumentLine`, `wms.BillingDocumentReceipt`, `wms.BillingDocumentShipment`, `wms.BillingPayment`, `wms.BillingIssue`
- `wms.CommunicationDraft`
- `wms.FlightSourceBatch`, `wms.Flight`
- `wms.PlanningRun`, `wms.PlanningVersion`, `wms.PlanningAssignment`, `wms.PlanningIssue`, `wms.PlanningArtifact`
- `wms.PlanningFlightSnapshot`, `wms.PlanningShipmentSnapshot`, `wms.PlanningVolunteerSnapshot`
- `wms.PlanningDestinationRule`
- `wms.VolunteerProfile`, `wms.VolunteerAvailability`, `wms.VolunteerConstraint`, `wms.VolunteerUnavailability`
- `wms.IntegrationEvent`, `wms.UserUiPreference`, `wms.WmsChange`, `wms.WmsRuntimeSettingsAudit`
- `wms.PrintTemplateVersion`, `wms.PrintPackDocumentVersion`

## Approaches Considered

### 1. Clean contacts in place

- Delete or patch only bad contacts and keep the rest of the current operational graph.
- Rejected because the existing local base already contains shipments, receipts, cartons, stock movements, org-role rows, and legacy references tied to test data. Cleaning in place would preserve hidden inconsistencies.

### 2. Reset operational data, then import the raw XLSX directly

- Reset the database, then feed workbook rows straight into runtime tables.
- Rejected because the workbook is a denormalized business export with repeated entities, mixed roles, and ambiguous relationships. Direct import would recreate duplicates and low-quality links.

### 3. Reset operational data, then rebuild through a normalized double-write pipeline

- Reset only operational/generated data.
- Normalize the workbook into structured actor/destination/link datasets.
- Rebuild both:
  - legacy-compatible `Contact`/`Destination`/`linked_shippers`
  - cleaner org-role structures (`OrganizationRoleAssignment`, `ShipperScope`, `RecipientBinding`)
- Approved because it matches the future real usage model while keeping the legacy Django flows operational.

## Approved Design

### Reset command

- Add a dedicated management command, tentatively `reset_operational_data`.
- Default mode is `--dry-run`.
- Real deletion requires `--apply`.
- The command owns explicit keep/delete model lists in code.
- The command deletes models in a defined order from most dependent to most root-level.
- The command runs in one transaction.
- The command prints:
  - per-model counts before deletion
  - per-model counts deleted
  - preserved model counts
  - a final consistency summary
- The command fails fast if a supposedly preserved model still depends on a deleted model in a way that would make the result invalid.

### Reset ordering

1. Generated history, logs, snapshots, drafts, version history
2. Link tables and secondary operational relations
3. Primary operational objects (shipments, receipts, cartons, orders, product lots, planning runs, flights, billing history)
4. Org-role, portal, volunteer, compliance, and account-request layers
5. Destinations and contacts
6. Operational sequence/counter rows

### Rebuild target model

The rebuild should treat org roles as the cleaner runtime truth while preserving legacy compatibility:

- `Contact` remains required for:
  - legacy Django UI and selectors
  - destination correspondents
  - shipment and receipt contact references
  - compatibility with existing helper code
- `OrganizationRoleAssignment` becomes the role layer:
  - donor
  - shipper
  - recipient
  - correspondent
- `ShipperScope` represents shipper-to-destination availability.
- `RecipientBinding` represents recipient-to-shipper-to-destination relationships.
- `linked_shippers` is filled from the same source relationships so legacy recipient filtering stays consistent.

### Workbook normalization pipeline

The BE workbook should be processed into five normalized datasets:

1. donors
2. shippers
3. recipients
4. correspondents
5. destinations

Each dataset should aggregate repeated workbook rows into canonical entities using normalization rules for:

- organization names
- person names
- city/country labels
- IATA codes
- active/inactive status
- phone and email formatting
- address consolidation

### Relationship resolution

- `Destination` is built from destination city/country/IATA plus the resolved correspondent.
- `ShipperScope` is inferred from all destination memberships seen for a shipper in the workbook.
- `RecipientBinding` is inferred from each distinct recipient/shipper/destination combination in the workbook.
- `linked_shippers` mirrors the set of shippers used by the recipient bindings for that recipient.
- Multi-shipper recipients are allowed when the workbook supports them.

### Ambiguity handling

The rebuild must not silently invent data for ambiguous cases. Instead it should emit a review output for rows such as:

- same actor name with incompatible address/email/role data
- destination with no usable correspondent
- recipient with insufficient shipper evidence
- conflicting role interpretation for the same entity
- suspicious name variants that may or may not be duplicates

The review output should be generated as files under `docs/import/` or another explicit repo-local review path so the operator can inspect and correct them before or after import.

### Import order

1. Create or update `ContactTag` rows needed by the rebuild.
2. Create base organization/person contacts.
3. Create contact addresses.
4. Create destinations and destination correspondents.
5. Create organization role assignments.
6. Create shipper scopes.
7. Create recipient bindings.
8. Backfill legacy `linked_shippers` from the same resolved recipient-binding relationships.

### Validation

The rebuild is acceptable only if all of the following hold:

- no FK errors during reset or rebuild
- replayable reset/rebuild flow on an empty post-reset database
- no duplicate organizations created for the same canonical actor without being surfaced in review output
- destinations are unique and correspondent-backed
- shipper scopes and recipient bindings match the workbook-derived relationship graph
- legacy `linked_shippers` remains consistent with recipient bindings
- preserved reference/configuration models still exist after reset
- `PlanningParameterSet` survives the reset even though `PlanningDestinationRule` is intentionally removed

## Testing Strategy

- Add command-level tests for `reset_operational_data`:
  - dry-run summary
  - apply behavior
  - preserved models untouched
  - deleted models emptied
- Add rebuild normalization tests for workbook parsing and canonical grouping.
- Add rebuild persistence tests for:
  - contacts
  - destinations
  - role assignments
  - shipper scopes
  - recipient bindings
  - legacy linked shipper mirroring
- Add ambiguity/report tests to prove suspicious rows are surfaced rather than auto-merged.
- Run the reset command in dry-run mode against the local database before any destructive apply run.

## Acceptance Criteria

- A safe reset command exists and can report the purge plan before deleting anything.
- The reset preserves only the approved stable reference/configuration models.
- The rebuild can start from the provided workbook and recreate a clean contact/destination/org-role baseline.
- The resulting database works with the current legacy Django contact flows.
- The resulting database also carries the cleaner org-role/binding/scope structures needed for real usage.
- Planning rules can be reconstructed later on top of the rebuilt destinations without structural conflict.
