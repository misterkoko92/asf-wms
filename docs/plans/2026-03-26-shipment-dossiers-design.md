# Shipment Dossiers Design

**Date:** 2026-03-26

## Goal

Reorganize the legacy Django shipment UI so existing shipments are managed through a lighter `Dossiers` list and a dedicated `Dossier expédition` cockpit, while keeping `Suivi des expéditions` unchanged and `Préparation expédition` focused on creation only.

## Context

The current shipment UI mixes three different intents:
- [templates/scan/shipments_ready.html](/Users/EdouardGonnu/asf-wms/templates/scan/shipments_ready.html) acts as a consultation list, document launcher, and quick-action cockpit at the same time
- [templates/scan/shipment_create.html](/Users/EdouardGonnu/asf-wms/templates/scan/shipment_create.html) is named as a creation or edit screen, but already contains most of the operational controls for an existing shipment
- [templates/scan/shipments_tracking.html](/Users/EdouardGonnu/asf-wms/templates/scan/shipments_tracking.html) is the transversal tracking board and should remain unchanged for this change set

That overlap makes the list heavy to scan and blurs the operator mental model:
- `Vue Expéditions` is no longer a pure view
- `Modifier expédition` behaves more like a shipment cockpit than a narrow edit form
- `Préparation expédition` and existing-shipment operations are not clearly separated in navigation

Validated user constraints:
- keep `Préparation expédition` separate and dedicated to creation
- turn `Expéditions` into a group with exactly two pages:
  - `Dossiers`
  - `Suivi des expéditions`
- keep `Suivi des expéditions` unchanged
- simplify the current shipment list so each row exposes only one action: `Ouvrir`
- move administrative information, documents, modification options, and shipment follow-up controls into the opened dossier page
- allow shipment search from `Dossiers` by number, shipper, recipient, and destination

## Scope

### In Scope

- legacy Django navigation for shipment pages
- rename and reshape `Vue Expéditions` into `Dossiers`
- create a `Dossier expédition` UI for existing shipments using current legacy shipment-edit logic
- add shipment search on the dossier list
- preserve the current `Suivi des expéditions` page behavior
- update help and copy so the new information architecture is explicit

### Out of Scope

- Next/React shipment pages
- translation scope
- changes to the public QR tracking page behavior
- shipment creation workflow redesign
- shipment workflow rules and status semantics

## Approaches Considered

### 1. Split list and cockpit, recommended

Idea:
- turn the current shipment list into a lighter `Dossiers` page
- move all per-shipment control into a dedicated `Dossier expédition` page
- keep the current tracking board as-is

Pros:
- clearest mental model for operators
- lowest product ambiguity
- large reuse of the current legacy shipment-edit page and supporting handlers

Cons:
- requires copy, navigation, and template restructuring in more than one place
- needs clear differentiation between `Préparation expédition` and `Dossier expédition`

### 2. Minimal rename only

Idea:
- rename the list to `Dossiers`
- remove extra row buttons
- keep the current edit page mostly unchanged

Pros:
- smallest implementation
- low technical risk

Cons:
- does not fully fix the current ambiguity around the shipment cockpit
- keeps an edit-first UI instead of a dossier-first UI

### 3. Master-detail shipment workspace

Idea:
- turn shipment management into a single master-detail page with list and dossier together

Pros:
- efficient for high-volume operators

Cons:
- heavy for legacy Django
- much higher implementation risk
- more complexity than the validated need

## Recommended Decision

Take approach 1.

Target information architecture:
- `Préparation` group keeps `Préparation expédition`
- `Expéditions` becomes a collapsible group
- `Expéditions` contains:
  - `Dossiers`
  - `Suivi des expéditions`

Target page roles:
- `Préparation expédition`: create a new shipment
- `Dossiers`: find, inspect, and open existing shipments
- `Dossier expédition`: central cockpit for one existing shipment
- `Suivi des expéditions`: unchanged transversal milestone board

## Navigation Design

Update [templates/scan/includes/scan_sidebar_navigation.html](/Users/EdouardGonnu/asf-wms/templates/scan/includes/scan_sidebar_navigation.html) so shipment pages are grouped consistently:

- keep the existing `Préparation` group with `Préparation expédition`
- replace the current single `Expéditions` link with a group containing:
  - `Dossiers`
  - `Suivi des expéditions`

Implementation direction:
- keep legacy route names where practical to reduce risk
- change UI labels and active states first
- do not introduce unnecessary route churn in the first pass

This preserves URL stability while changing the product mental model.

## Dossiers Page

The current [templates/scan/shipments_ready.html](/Users/EdouardGonnu/asf-wms/templates/scan/shipments_ready.html) becomes `Dossiers`.

### Role

The page is a consultation and access surface only:
- find existing shipments
- review the current state at a glance
- open the shipment dossier

It is not a quick-action cockpit anymore.

### Search

Use one free-text `GET` search field, `q`, filtering on:
- shipment reference
- shipper label
- recipient label
- destination label or IATA code

List scope:
- include non-archived shipments
- include temporary drafts
- exclude archived shipments

Sorting:
- keep reverse chronological order by creation date

### Table Shape

Recommended columns:
- `N° expédition`
- `Statut`
- `Destination`
- `Expéditeur`
- `Destinataire`
- `Nb colis`
- `Date création`
- `Date mise en disponible`
- `Documents`
- `Action`

### Row Actions

Each row exposes only one action:
- `Ouvrir`

Removed from the list:
- direct `Suivi`
- direct `Modifier`
- direct document-opening actions

### Documents Column

The list should expose document presence as a summary only, not as a launcher.

Recommended behavior:
- show a concise indicator that documents exist and whether additional files are present
- keep detailed document opening and file operations inside the shipment dossier

### List-Level Actions

Keep the stale-draft archive action at page level:
- `Archiver brouillons anciens`

This action remains relevant on the list because it targets list hygiene rather than a single shipment dossier.

## Dossier Expédition Page

The current legacy shipment edit screen becomes a `Dossier expédition` cockpit for existing shipments.

### Role

This page becomes the canonical operational surface for one shipment:
- review administrative information
- access generated and uploaded documents
- access shipment tracking
- perform allowed actions
- see whether the case can be closed or is blocked

The page should feel like a structured dossier first, not like a large form first.

### Recommended Structure

Top to bottom:
- header
- administrative summary
- documents
- tracking
- actions

### Header

The dossier header should show:
- shipment reference
- current status with the existing tone system
- destination
- key dates:
  - created
  - ready
  - optionally closed
- strong state indicators:
  - modifiable
  - locked
  - disputed
  - closed

### Administrative Summary

This block should summarize:
- destination
- shipper
- recipient
- correspondent
- carton count
- equivalent carton count when available
- linked association receipts

The operator should understand the shipment state without entering edit mode.

### Documents

This block centralizes:
- generated documents
- carton-level documents and labels
- additional uploaded documents
- upload and delete controls for additional documents

The current generated-document and additional-document panels can be reused, but they should be positioned under a clearer dossier hierarchy.

### Tracking

This block should expose:
- shipment QR code
- public tracking link
- current tracking entry point
- a compact milestone summary if available

The dedicated `Suivi des expéditions` page stays unchanged, but the dossier must still provide shipment-level access to follow-up operations.

### Actions

Primary dossier actions should be explicit and grouped:
- `Modifier` when editing is allowed
- `Ouvrir suivi`
- `Clore le dossier` when eligible
- document actions that belong to the shipment context

Design rule:
- actions belong in one or two clear action zones
- do not scatter operational controls across every block

### Editing Model

Recommended behavior:
- the default dossier remains consultation-first
- shipment editing stays available, but it should not dominate the visual hierarchy

Preferred implementation strategy:
- keep the current edit mechanics and permissions
- visually present the page as a dossier cockpit
- show `Modifier` as the explicit gateway to editable controls when needed

This allows reuse of current server-side form logic without preserving the current edit-first product framing.

## Behavior Rules

### Search and Return Context

- `Dossiers` uses `GET` search with a single `q` parameter
- opening a shipment should preserve a return target back to `Dossiers`
- post-action redirects from dossier operations should keep the operator in the correct context

### State Handling

The dossier must clearly communicate state:
- modifiable shipment: editing action is available
- locked shipment: editing action is absent or disabled with clear explanation
- disputed shipment: dispute state is prominent near the header
- closed shipment: page remains readable, with closure metadata shown clearly

Documents and shipment follow-up access remain visible even when business editing is no longer allowed.

## Implementation Shape

Recommended legacy implementation path:

1. reshape [templates/scan/shipments_ready.html](/Users/EdouardGonnu/asf-wms/templates/scan/shipments_ready.html) into `Dossiers`
2. add search support in [wms/views_scan_shipments.py](/Users/EdouardGonnu/asf-wms/wms/views_scan_shipments.py) and supporting row builders in [wms/shipment_view_helpers.py](/Users/EdouardGonnu/asf-wms/wms/shipment_view_helpers.py)
3. update sidebar grouping in [templates/scan/includes/scan_sidebar_navigation.html](/Users/EdouardGonnu/asf-wms/templates/scan/includes/scan_sidebar_navigation.html)
4. refactor the shipment edit presentation from [templates/scan/shipment_create.html](/Users/EdouardGonnu/asf-wms/templates/scan/shipment_create.html) and its include blocks into a dossier-first hierarchy for existing shipments
5. preserve [templates/scan/shipments_tracking.html](/Users/EdouardGonnu/asf-wms/templates/scan/shipments_tracking.html) behavior
6. update FAQ and copy to reflect the new roles

## Risks

- the current edit template mixes create and edit in one file, so dossier-first changes must avoid regressions on creation
- shipment return targets currently distinguish `shipments_ready` and `shipments_tracking`; dossier flows need a consistent return path from `Dossiers`
- search behavior depends on shipment-party labels that may come from snapshots or contact refs, so filtering must match what operators actually see
- list simplification must not remove access to critical actions that operators still need for locked or disputed shipments

## Testing

Add or update legacy Django tests for:
- sidebar shipment grouping and active states
- dossiers page title, search form, and reduced row actions
- dossier search by reference, shipper, recipient, and destination
- dossier list inclusion rules for drafts and exclusion rules for archived shipments
- dossier page structure for existing shipments
- dossier state markers for modifiable, locked, disputed, and closed shipments
- preserved tracking page behavior
- FAQ and copy updates where current page names appear
