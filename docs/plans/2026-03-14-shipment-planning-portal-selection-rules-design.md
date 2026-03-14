# Shipment Planning Portal Selection Rules Design

**Date:** 2026-03-14

**Goal:** Harmonize shipment party selection rules across legacy Scan shipment creation, Portal order creation, and Planning consumption so the same destination and contact choices lead to the same business decision everywhere.

## Scope

- Keep all work on the legacy Django stack only.
- Cover the shipment actor rules used by:
  - `scan/shipment`
  - `portal/orders`
  - shipment creation from `wms/domain/orders.py`
  - planning snapshots and planning communications
- Align the handling of:
  - destination
  - shipper
  - recipient
  - correspondent
- Treat organization-role rules as the source of truth when the org-role engine is enabled.

## Non-Goals

- Do not touch paused Next/React migration files.
- Do not redesign the Planning UI or the solver.
- Do not broaden this lot into status/color harmonization.
- Do not broaden this lot into shipment notification redesign.
- Do not refactor unrelated shipment, portal, or planning flows that do not participate in actor selection or actor consumption.

## Constraints

- Prefer one backend business rule over screen-specific heuristics.
- Keep the existing Scan and Portal screens, and minimize UI churn.
- Preserve current legacy behavior when the org-role engine is disabled.
- Support contacts of type `person` linked to an organization without letting each surface reinterpret them differently.

## Approaches Considered

### 1. Screen-by-screen patching

- Patch `scan/shipment`, `portal/orders`, and planning consumption independently.
- Rejected because it would keep business drift likely and would duplicate the same organization/contact normalization logic in multiple places.

### 2. Shared shipment-party rule layer

- Introduce a shared legacy Django helper layer that centralizes actor normalization and actor eligibility.
- Make Scan, Portal, domain shipment creation, and Planning consume that common rule set.
- Approved because it addresses the root cause of the current drift without forcing a large UI rewrite.

### 3. Full shipment actor refactor

- Redesign actor payloads, screen JS, planning references, and related workflows in one pass.
- Rejected because it is too large for the current sub-lot and would mix structural cleanup with business harmonization.

## Approved Design

### Shared Shipment-Party Rule Layer

- Add a shared backend layer dedicated to shipment parties.
- Centralize:
  - contact-to-organization normalization
  - eligible shipper contacts for a destination
  - eligible recipient contacts for a `shipper + destination` pair
  - eligible correspondent contact for a destination
- Keep the existing `organization_role_resolvers.py` contract intact where possible, but stop making each caller reinvent how to prepare contacts for those resolvers.

### Scan Shipment Surface

- Keep the current Scan shipment UI and grouped selectors.
- Replace any remaining form/queryset-specific actor logic with the shared shipment-party rule layer.
- Ensure the same actor rule is used for:
  - GET querysets
  - edit initial values
  - draft save validation
  - final create/edit validation
- Keep JS as a renderer of server-aligned payloads, not as a second source of truth.

### Portal Order Surface

- Keep the current Portal order flow and `Moi-même` option.
- Change the visible recipient filtering so it reflects the same real business rule as Scan:
  - destination must be compatible
  - recipient must be allowed for the Portal shipper and the selected destination
- Remove the current gap where Portal mostly filters by destination first and only rejects the org-role binding late during submission.
- Continue to resolve the final recipient contact from the Portal recipient record, but do so through the shared shipment-party rule layer.

### Domain Order-to-Shipment Creation

- Make `wms/domain/orders.py` use the same shipment-party normalization and eligibility logic as Scan and Portal.
- Prevent a case where a combination is allowed by one entry surface but rejected later when a shipment is created from an order.

### Planning Consumption

- Keep Planning out of the creation flow for this sub-lot.
- Align Planning on actor consumption only:
  - shipment contact references
  - snapshot payload references
  - communication plan recipient/contact values
- Normalize actor references through the same shared shipment-party logic so Planning presents the same shipper, recipient, and correspondent identity as Scan and Portal.

## Data and Logic Touchpoints

- New shared rule module in `wms/` for shipment-party normalization and eligibility.
- `wms/forms.py`
  - Scan shipment querysets and validation
- `wms/scan_shipment_handlers.py`
  - draft/create/edit actor validation
- `wms/shipment_helpers.py`
  - shipment contact payload generation for Scan UI
- `wms/views_portal_orders.py`
  - destination/recipient option filtering and submission validation
- `wms/domain/orders.py`
  - order-to-shipment actor resolution
- `wms/planning/sources.py`
  - shipper/recipient/correspondent reference building
- `wms/planning/communication_plan.py`
  - downstream use of normalized contact references when needed

## Testing Strategy

- Add shared-rule tests for:
  - contact-to-organization normalization
  - eligible shipper contacts per destination
  - eligible recipient contacts per `shipper + destination`
  - correspondent resolution by destination
- Extend Scan shipment tests to prove the form/queryset behavior still matches the approved org-role contract.
- Extend Portal order tests to prove:
  - recipient options are filtered consistently with the binding rules
  - invalid recipients are rejected before shipment creation
  - `Moi-même` still works where allowed
- Extend domain order tests so shipment creation from orders uses the same actor rule layer.
- Extend Planning tests only for actor consumption:
  - normalized references in snapshots
  - normalized contact values in communication planning

## Validation

- Run focused Scan, Portal, domain-order, and Planning tests during implementation.
- Re-run the cross-surface regression suite after the lot is complete.
- Keep the verification limited to actor rules and actor consumption, not solver behavior or unrelated UI differences.
