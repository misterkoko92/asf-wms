# Preparation Run Magasin Design

## Goal

Add a new legacy-Django `run magasin` engine that proposes shipments and cartons to prepare from
ASF stock and/or already deposited association cartons, then lets operators validate, reject,
modify, and convert those proposals into real shipments without polluting the existing `planning
vols` flow.

## Scope

- legacy Django only
- no Next/React work
- no translation-scope work
- explicit architectural split between:
  - `planning vols`
  - `planning magasin`
- V1 proposal engine for:
  - flow 3: association deposit + ASF stock complement
  - flow 4: ASF own preparation from ASF stock
- manual creation remains available for:
  - flow 1: deposited association shipments
  - flow 2: association requests prepared entirely from ASF stock
  - urgent requests

## Why This Lot Exists

ASF-WMS already has useful building blocks:

- flight import and capacity rules in the planning stack
- destination-scoped recipient runtime rows
- stock lots, reservations, and carton/shipment preparation flows
- recipient product preferences work in progress

What is missing is a dedicated operational layer that answers:

- what should the warehouse prepare this week
- which proposals best match recipient preferences and remaining need
- how to prioritize non-ASF requests over ASF while still serving ASF
- how to reserve stock during operator review
- how to keep the planning-vols cockpit honest by excluding not-yet-physically-prepared shipments

## Approaches Considered

### 1. Extend the existing `PlanningRun` domain

Pros:

- fewer new tables
- some reuse of run/version vocabulary

Cons:

- mixes two different business problems
- makes planning-vols states harder to reason about
- creates a high risk of coupling warehouse preparation with flight-planning solve logic

### 2. Create a separate `run magasin` domain and UI, recommended

Pros:

- clean separation of concerns
- easier audit and stock reservation tracing
- keeps flight-planning rules reusable without merging the two domains
- supports future V2 evolution without destabilizing the current planning stack

Cons:

- more new models and services up front

### 3. Build a stateless proposal helper without persistence

Pros:

- quick prototype

Cons:

- weak auditability
- poor operator recovery
- no safe stock reservation lifecycle
- no stable review/reject/convert workflow

## Recommended Architecture

Create a new warehouse-preparation domain separate from `wms/models_domain/planning.py`.

Recommended runtime placement:

- UI surface under `scan`, not under `planning`
- dedicated domain models under a new `wms/models_domain/preparation.py`
- dedicated orchestration under a new `wms/preparation/` package
- thin scan views and forms for operator review

The two domains should interact through explicit contracts:

- `planning vols` remains the source of truth for flight batches, usable flights, and destination
  capacity rules
- `run magasin` consumes those constraints and decides what to prepare
- `run magasin` never writes back planning-vols assignments or versions

## Surface Placement

Recommended operator surface:

- add a new scan flow, for example under `wms/scan_urls.py`
- runtime view module: `wms/views_scan_preparation.py`
- templates under `templates/scan/preparation_*`

Reason:

- this is a stock/warehouse workflow first
- it should not be confused with the current planning-vols cockpit
- it stays aligned with the active legacy Django delivery surface

## Core V1 Business Rules

### Run perimeter

- one active `run magasin` per ASF stock pool
- V1 perimeter uses all ASF stock
- the run must respect a configurable manual/urgent reserve
- manual urgent overrides may reclaim reserved run stock with audit

### Proposal granularity

- one shipment proposal = one `shipper + operational recipient + destination`
- multiple cartons may exist inside one proposal
- a proposal may be:
  - deposit only
  - ASF stock only
  - mixed

### Deposited cartons

- deposited association cartons are already attached to a precise `recipient + destination`
- V1 does not reassign deposited cartons to another destination or recipient
- deposited cartons do not count in ASF-stock fairness calculations

### ASF stock generation

- V1 generated cartons are mono-product only
- kits are treated as a mono-product candidate at proposal time
- physical preparation may still explode the kit into components during packing

### Shipment lifecycle

- accepting a proposal does not create a `ShipmentStatus.PACKED` shipment
- accepted proposals convert to real `Shipment` rows in `ShipmentStatus.PICKING`
- operator confirmation is required before the shipment becomes `ShipmentStatus.PACKED`
- `planning vols` continues to see only `PACKED` or `PLANNED` shipments

## Parameter Model

### Run-time operator inputs

- flight window start/end or launch-date offsets
- destinations to serve
- shippers to include
- target total equivalent cartons
- target total shipment count
- target shipment size in equivalent cartons
- active parameter set
- include backlog or not

### Persistent warehouse parameter set

- target shipment size default
- shipment split tolerance
- minimum shipment size before automatic backlog
- fairness category level `L2/L3`
- fairness horizon in weeks
- urgent/manual reserve
- ASF score penalty
- scoring weights
- allowed scoring statuses, so `unspecified` can be enabled later without a redesign

### Destination rules

- max equivalent cartons per flight
- max usable flights per week
- max equivalent cartons per week
- max shipments per week
- allowed weekdays
- capacity buffer
- optional local priority / fairness weight

### Shipper rules

- active in engine
- mode:
  - `deposit_only`
  - `asf_complement_allowed`
  - `asf_auto_allowed`
- shipper score coefficient
- ASF penalty remains configurable rather than hard-coded

## Recurrent Needs

Use a hybrid model:

- persistent recurring need request
- snapshot copied into each run at generation time
- local override allowed inside the run

V1 scope:

- recurring need is anchored to `shipper + recipient_organization + destination`
- recurring need is used for complement authorization and target demand
- run snapshot is the audit source; it must not mutate silently when recurring rules change later

## Recipient Preference Resolution

### V1 supported preference levels

- exact product
- category `L2`
- category `L3`
- implicit `unspecified`

### V1 supported statuses

- product level:
  - `requested`
  - `allowed`
  - `refused`
- category level:
  - `requested`
  - `allowed`
- category-level `refused` is out of scope in V1

### Resolution order

1. exact product preference
2. most specific category preference
3. implicit `unspecified`

### Kits

- kits are resolved as kit products, not by their internal components
- a recipient may declare a preference on a kit without declaring preferences on each component

## Need, Backlog, And Fairness

### Need coverage

Remaining need must deduct all relevant shipments already in `PACKED` or `PLANNED`, regardless of
whether they were created manually or by the automatic run.

This avoids recreating demand that is already covered by active outbound logistics.

### Fairness

Fairness is distinct from need.

V1 fairness rules:

- fairness applies only to ASF-stock or mixed proposals
- deposited-only association cartons are excluded
- fairness uses shipment history already `PACKED` or `PLANNED`, not only `DELIVERED`
- purpose: include backlog and avoid fake scarcity
- fairness is computed by `(destination, category reference)`
- default category reference is `L2`
- `L3` is an advanced parameter

### Shipment-size rules

- target shipment size is configurable
- shipments may exceed the target within a configured tolerance
- above that tolerance, the engine splits into multiple proposals
- proposals under the configured minimum size go to backlog unless an operator overrides manually

## Scoring Model

### Hard exclusions

Exclude a candidate when:

- shipper is not eligible in the parameter set
- no active recurring need snapshot exists for an association-complement flow
- effective preference resolves to `refused`
- ASF stock is unavailable after existing reservations and urgent reserve
- destination capacity is exhausted on the selected flight window
- proposal is below minimum shipment threshold and no manual override exists

### Soft scoring

Use weighted scoring for the remaining candidates:

- strong bonus for `requested` with remaining need
- medium bonus for `allowed` with remaining need
- `unspecified` excluded by default in V1, but keep this status switchable in configuration
- bonus for better target-size fit
- bonus or malus from fairness
- bonus for non-ASF shipper requests
- configurable ASF penalty
- bonus for complementing deposited association cartons when the association explicitly allows it

### Deterministic ordering

At equal score:

1. non-ASF before ASF
2. higher remaining need
3. older backlog
4. better fit to target shipment size
5. stable id ordering

### Explainability

Each proposal should carry readable reasons such as:

- `requested need covered`
- `association complement`
- `L2 fairness bonus`
- `ASF penalty applied`
- `capacity nearly saturated`

## Stock Reservation Strategy

Reuse the existing reservation principle built around `ProductLot.quantity_reserved`, but do not
reuse order-specific reservation tables directly for the new run.

V1 warehouse run behavior:

- generation reserves the necessary stock
- accept/convert consumes the reservation
- reject/delete releases the reservation
- urgent manual override may reclaim the reservation and marks the proposal `needs_recalc`

Important:

- keep a dedicated run-reservation trace model for audit
- do not silently consume or release stock without a decision log

## Data Freshness, Obsolescence, And Flight Fallback

### Frozen run snapshot

Once generated, a run is frozen:

- proposals do not mutate silently while an operator reviews them
- if manual work impacts stock or coverage, impacted proposals become `needs_recalc`

### Recalculation

V1 recommendation:

- explicit operator action only
- recalculation creates a new `run magasin`
- previous run remains in history for audit

### Flight fallback

If the Air France API fails:

- use the last exploitable flight batch from a previous run
- mark the current run as using a fallback source
- show data freshness explicitly in the UI

## Minimal V1 Data Model

Recommended new models:

- `PreparationParameterSet`
- `PreparationDestinationRule`
- `PreparationShipperRule`
- `RecurringPreparationNeed`
- `PreparationRun`
- `PreparationRunNeedSnapshot`
- `PreparationShipmentProposal`
- `PreparationCartonProposal`
- `PreparationReservation`
- `PreparationDecisionLog`

Recommended placement:

- new domain module: `wms/models_domain/preparation.py`
- re-export through `wms/models.py`

## Run And Proposal Lifecycle

### Run states

- `draft`
- `generated`
- `reviewing`
- `partially_validated`
- `validated`
- `closed`

### Proposal states

- `proposed`
- `accepted`
- `partially_accepted`
- `refused_keep_draft`
- `refused_delete`
- `needs_recalc`
- `converted`

### Real shipment states

- created from proposal in `ShipmentStatus.PICKING`
- manually confirmed by operator
- promoted to `ShipmentStatus.PACKED`
- then eligible for the flight-planning flow

## Audit And Reporting

V1 should retain enough evidence to answer:

- why a proposal was created
- why it was rejected
- which stock lots were reserved, released, consumed, or reclaimed by urgency
- which destination/category fairness adjustment was applied
- how much backlog remains after the run
- how much ASF stock was committed to non-ASF vs ASF requests

## Out Of Scope

- automatic multi-product carton composition
- category-level `refused`
- substitution/family-based preference resolution
- reallocation of deposited cartons to another recipient
- concurrent active runs on the same stock pool
- silent recalculation while an operator is reviewing a run
- direct integration of run-magasin objects into `PlanningRun`

## Testing Strategy

Required proof for V1:

- model validation and preference-resolution tests
- recurrent-need snapshot tests
- scoring tests covering:
  - product vs category precedence
  - ASF penalty
  - fairness on `PACKED/PLANNED` history
  - deposit exclusion from fairness
- stock reservation, release, consume, and urgent override tests
- run obsolescence tests after manual stock or shipment changes
- scan UI tests for generation, review, accept/refuse, and conversion
- regression tests proving that `planning vols` still reads only `PACKED` and `PLANNED`
