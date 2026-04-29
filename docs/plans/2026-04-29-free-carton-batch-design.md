# Free Carton Batch Preparation Design

## Goal

Allow operators and preparateur volunteers to produce many identical free cartons in one
validated action, without destination or shipment assignment, then assign only the needed
cartons from `Vue Colis` later.

Example target workflow:

1. A volunteer prepares 32 cartons of syringes during the day.
2. The cartons are created as real stock-bearing `Carton` rows in `Disponible`.
3. They have no shipment and no preassigned destination.
4. The next day, staff selects 4 cartons for shipment Y, 7 for shipment Z, and leaves the
   remaining cartons free.

## Classification

- Primary: A. ASF operational need.
- Secondary: B. generic reusable capability.

This touches stock, cartons, preparateur productivity, and shipment assignment. It must
preserve stock truth and shipment readiness truth.

## Current Context

`/scan/pack/` already creates cartons from product lines and can mark cartons
`Disponible` through `prepare_available`.

The existing `forced_carton_count` input is not the right semantic for this need. It
forces a packing split across N cartons. For a free carton batch, the operator needs the
opposite: the entered lines describe one carton type, and the system creates N identical
cartons.

`Vue Colis` already supports selecting free cartons and assigning selected cartons to an
editable shipment. The missing piece is a fast and safe way to manufacture the free
carton stock in bulk.

## Decision

Add a `Batch colis libres` mode to the existing pack surface rather than creating a new
carton-batch object or a separate cockpit.

The operator enters:

- carton format;
- product lines for one carton type;
- lot / expiry data as today;
- number of identical cartons to create;
- confirmation in a popup before stock is mutated.

On confirmation, the backend creates one real `Carton` per requested carton. Each carton:

- is independent;
- is set to `CartonStatus.PACKED` / `Disponible`;
- has no `shipment`;
- has no `preassigned_destination`;
- consumes stock immediately;
- appears in the normal `Vue Colis` list;
- can later be assigned with existing bulk assignment.

## Confirmation Contract

The browser popup must summarize:

- number of cartons to create;
- product lines per carton;
- total product quantity consumed across the batch;
- the fact that no destination or shipment will be assigned.

The server must also require an explicit confirmation marker for batch creation. If the
marker is absent, no carton is created.

This prevents accidental creation such as entering `32` when the operator intended a
quantity of `32` units.

## Stock And Data Rules

- Stock is decremented during batch validation, not during later shipment assignment.
- The whole batch creation is atomic. If one carton cannot be packed, no carton from the
  batch remains created.
- The typed one-carton content must fit into exactly one carton format before it is
  repeated.
- Missing weight/volume rules reuse the existing pack confirmation behavior.
- If stock is insufficient for `quantity per carton * carton count`, the operation fails
  and no partial batch is persisted.
- The batch must not set destination, shipment, or planning readiness.
- Shipment readiness continues to depend only on real assigned cartons and explicit
  shipment status transitions.

## Preparateur / Volunteer Behavior

When used by a preparateur-only user:

- the existing active volunteer session remains required;
- created cartons record the volunteer attribution already used by preparateur pack;
- the success modal can reuse the current pack result list and print actions.

For V1, if preparateur mode detects products spanning multiple MM/CN families, reject the
batch and ask the operator to create separate batches. One free batch should represent one
repeatable carton type.

## Vue Colis Follow-Up

`Vue Colis` remains the assignment surface. To support next-day assignment, add filters
or query controls for:

- free cartons only;
- available cartons only;
- product search;
- created date;
- prepared volunteer where available.

The existing bulk assignment flow remains the way to assign 4 cartons to shipment Y and 7
cartons to shipment Z.

## Non-Goals

- No fake cartons.
- No persistent `CartonBatch` model in V1.
- No destination preassignment in this flow.
- No automatic shipment creation.
- No planning visibility change.
- No Next / React scope.
- No translation parity scope.

## Documentation Impact

Documentation update required if implemented:

- `wms/faq_changelog.py`;
- `templates/scan/faq.html`;
- `docs/repo-reference/02-key-flows-and-living-tests.md`;
- `docs/repo-reference/04-shared-contracts/03-scan-operations.md`;
- `docs/release_checklist.md` if a smoke item is added.
