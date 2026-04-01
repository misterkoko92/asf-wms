# ASF WMS V3 Structural Design

## Goal

Deliver a structural V3 that reduces orchestration debt, removes duplicated business composition across legacy Django surfaces, and hardens the production runtime without reopening paused Next/React or translation work.

## Context

V2 improved operational visibility and pilotage, but it also made several architectural limits more visible:

- business composition is duplicated between legacy HTML views and the UI API
- decision rules remain spread across views, handlers, runtime settings, and helpers
- side effects are concentrated in Django signals and management commands
- the portal recipient and shipment-party graph remains expensive to reason about
- the legacy frontend is still monolithic on the `scan` surface
- type-checking and static guarantees cover only a narrow slice of the runtime

Key hotspot modules today include:

- `api/v1/ui_views.py`
- `wms/views_scan_dashboard.py`
- `wms/views_scan_shipments.py`
- `wms/signals.py`
- `wms/planning/exports.py`
- `wms/portal_recipient_sync.py`
- `wms/static/scan/scan.js`

## Non-Goals

V3 does not target:

- a Next/React migration
- FR/EN parity work
- a big-bang rewrite of legacy routes
- large new end-user features as the primary objective

The goal is to improve the structure that future product work will rely on.

## Recommended Strategy

Use an incremental migration with a fixed architecture target.

Do not attempt a full rewrite. Do not rely on opportunistic refactors only.

The migration should:

- keep legacy routes and templates stable at first
- use existing living tests as safety rails
- extract new layers behind current views and API endpoints
- accept temporary coexistence between old and new code during each wave
- remove legacy duplication only after the replacement path is stable

## Target Architecture

### 1. Application Layer

Create `wms/application/` as the home for cross-surface use cases and queries.

Recommended packages:

- `wms/application/scan/`
- `wms/application/portal/`
- `wms/application/planning/`
- `wms/application/pilotage/`

Rules:

- `queries` return read models used by HTML, UI API, exports, and jobs
- `use_cases` handle mutations and orchestration
- views and API endpoints become adapters, not business composition layers

### 2. Policies Layer

Create `wms/policies/` to centralize business rules that are currently scattered.

Priority policy groups:

- SLA thresholds and segment rules
- workflow blockage classification
- pilotage priorities and escalation thresholds
- planning capacity states
- default shipper binding rules
- document requirements and document readiness rules
- integration and provider defaults where they represent business policy

The objective is not only to remove hard-coded values, but to make business decisions discoverable and testable in one place.

### 3. Events Layer

Create `wms/events/` so side effects become explicit.

Recommended modules:

- `wms/events/types.py`
- `wms/events/publishers.py`
- `wms/events/handlers_notifications.py`
- `wms/events/handlers_projections.py`
- `wms/events/handlers_sync.py`

Migration rule:

- keep Django signals as temporary triggers
- move real side-effect logic out of `wms/signals.py`
- make event contracts explicit before changing behavior

### 4. Jobs Layer

Create `wms/jobs/` as the runtime home for queue processing and scheduled operations.

Priority job domains:

- email queue processing
- document scan queue processing
- print artifact generation and verification
- workflow projection refresh
- pilotage snapshot capture
- escalation evaluation

Management commands should become thin wrappers over this layer.

### 5. Projections Layer

Consolidate read models and operational aggregates into a more explicit projection layer.

Target responsibilities:

- shipment workflow projection
- destination aggregates
- destination-week aggregates
- pilotage snapshots
- escalation views
- future BI-oriented exports

### 6. Simplified Domain Boundaries

Keep the current data model at first, but reduce orchestration ambiguity around:

- portal recipients
- shipment recipients
- shipment shippers
- authorized recipient contacts
- default shipper bindings

The long-term target is a clearer source of truth and fewer implicit sync behaviors.

### 7. Legacy Frontend Modularization

Do not migrate to React in V3. Instead:

- split `scan.js` by surface
- split large CSS files by functional blocks
- keep shared primitives stable
- reduce page-specific JS/CSS coupling inside large staff templates

### 8. Stronger Quality Gates

Extend static checking and contract coverage to the real hotspots.

Priority targets:

- `api/v1/ui_views.py`
- `wms/views_scan_dashboard.py`
- `wms/views_scan_shipments.py`
- `wms/signals.py`
- application and policy layers introduced by V3

## Waves

### Wave 1: Application and Policies

Primary objective:

- extract shared query and use-case composition out of views and UI API
- centralize operational policies

Primary output:

- a reusable `application` layer
- a first `policies` layer
- thinner scan and pilotage surfaces

### Wave 2: Events and Jobs

Primary objective:

- replace implicit orchestration with explicit event and job boundaries

Primary output:

- signal bridge to events
- job wrappers below management commands
- durable run and retry visibility

### Wave 3: Domain and Runtime Simplification

Primary objective:

- simplify the most expensive shared domains and reduce legacy surface complexity

Primary output:

- clearer parties/contact graph orchestration
- hardened document and export pipeline
- modularized legacy frontend
- broader quality gates

## Migration Principles

- preserve legacy URLs and user-facing behavior during each extraction step
- keep HTML and UI API aligned through shared application queries
- prefer additive migration first, deletion second
- commit in small slices with living tests as proof
- update `docs/repo-reference/` when shared contracts, flow wiring, or runtime maps move

## Success Criteria

V3 can be considered structurally successful when:

- critical scan and pilotage reads are served by shared query modules
- major cockpit rules no longer live directly in view modules
- `wms/signals.py` becomes mostly registration and bridging logic
- core operational commands delegate to explicit job modules
- the recipient/shipper synchronization chain is easier to reason about and test
- static analysis covers the main hotspots rather than only peripheral slices

## Main Risks

- partial migrations that leave two sources of truth indefinitely
- extracting generic abstractions too early instead of solving concrete duplicated flows
- mixing structural V3 work with unrelated product changes
- under-testing cross-surface contracts while moving orchestration code

## Delivery Recommendation

Start with `scan/dashboard`, `scan/pilotage`, and the mirrored UI API payloads. They offer the best ratio of structural payoff to migration risk.

Do not start with the portal recipient graph or the full event runtime first. Those become safer once the application and policy layers exist.
