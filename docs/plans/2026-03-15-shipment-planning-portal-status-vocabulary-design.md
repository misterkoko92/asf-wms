# Shipment Planning Portal Status Vocabulary Design

**Date:** 2026-03-15

**Goal:** Harmonize status vocabulary and visible status presentation across legacy Scan shipment pages, Portal order pages, and Planning shipment summaries without erasing the distinct business meaning of order status versus shipment status.

## Scope

- Keep all work on the legacy Django stack only.
- Cover visible status vocabulary and status badges used by:
  - `scan/shipments-ready`
  - Portal order dashboard and order detail pages
  - Planning version dashboards and shipment summary blocks
- Harmonize:
  - shipment status labels
  - order status labels
  - order review labels
  - visible badge tone mapping for key shipment states
- Add a separate shipment-status reading to Portal instead of overloading the existing order status field.

## Non-Goals

- Do not touch paused Next/React migration files.
- Do not redesign shipment actor selection rules; that was handled in the previous lot.
- Do not redesign shipment notifications in this sub-lot.
- Do not refactor the Planning solver or broaden Planning status concepts beyond vocabulary and visible presentation.
- Do not change the persisted shipment and order status codes.

## Constraints

- Preserve the real business distinction between:
  - command lifecycle
  - ASF validation lifecycle
  - shipment lifecycle
- Avoid changing stored database values only to improve visible wording.
- Prefer one shared backend presentation layer over template-specific renames.
- Keep Portal readable for association users who need to understand both their request and its shipment progress.

## Approaches Considered

### 1. Replace Portal status with shipment status everywhere

- Make Portal speak only in shipment terms.
- Rejected because it would hide the actual order lifecycle and make early-stage orders harder to understand.

### 2. Dual command and shipment status presentation

- Keep Portal order status and ASF review status, and add a distinct shipment status presentation.
- Harmonize shipment vocabulary and badge colors across Scan, Portal, and Planning.
- Approved because it preserves the business model while removing vocabulary drift.

### 3. Visual rename only

- Keep the same structures and change only a few labels in templates.
- Rejected because it would leave duplicated logic and would not provide a clean place to maintain the canonical vocabulary.

## Approved Design

### Canonical Visible Vocabulary

#### Shipment lifecycle

- `draft` -> `Brouillon`
- `picking` -> `En cours`
- `packed` -> `Disponible`
- `planned` -> `Planifie`
- `shipped` -> `Expedie`
- `received_correspondent` -> `Recu escale`
- `delivered` -> `Livre`
- disputed shipments keep the current `Litige - <statut>` prefix behavior

#### Portal order lifecycle

- `draft` -> `Brouillon`
- `reserved` -> `Reservee`
- `preparing` -> `En preparation`
- `ready` -> `Prete`
- `cancelled` -> `Annulee`

#### ASF validation lifecycle

- `pending_validation` -> `En attente de validation`
- `approved` -> `Validee`
- `changes_requested` -> `Modifications demandees`
- `rejected` -> `Refusee`

### Shared Presentation Layer

- Add a small shared backend presentation helper dedicated to visible status labels and status metadata.
- This layer should:
  - expose canonical shipment status labels
  - expose canonical order and review labels for Portal
  - expose a Portal shipment status projection from the linked shipment
  - keep badge tone decisions centralized for the key visible domains
- The layer should not replace model enums or business transitions. It only owns visible presentation.

### Portal Surfaces

- Portal dashboard:
  - rename current `Statut` column to `Statut commande`
  - add a new `Statut expedition` column
  - keep shipment milestone dates and make them visually consistent with the shipment status column
- Portal order detail:
  - show three separate lines:
    - `Statut commande`
    - `Validation ASF`
    - `Statut expedition`
  - display `-` for shipment status when no shipment exists yet

### Scan Shipment Surface

- Keep Scan centered on shipment lifecycle only.
- Replace the visible `Pret` label with `Disponible` wherever shipment status labels are derived for the shipments-ready screen.
- Preserve the `Litige - ...` prefix and current derived-progress behavior, but align the final visible wording with the canonical shipment vocabulary.

### Planning Surfaces

- Keep Planning centered on planning-specific concepts such as `Non partant`.
- When Planning displays a shipment lifecycle label sourced from shipment data, use the same canonical shipment vocabulary as Scan and Portal.
- `Non partant` remains Planning-specific because it represents a planning result, not a stored shipment lifecycle state.

### Badge and Color Mapping

- Make shipment badge colors more distinguishable than the current mostly-progress palette.
- Recommended visible intent:
  - `Brouillon` -> neutral/progress
  - `En cours` -> progress/info
  - `Disponible` -> ready
  - `Planifie` -> dedicated planned tone distinct from `En cours`
  - `Expedie` -> blue/in-transit tone
  - `Recu escale` -> distinct intermediate tone
  - `Livre` -> strong ready/success tone
  - `Litige`, `Annulee`, `Refusee` -> error tone
  - `Modifications demandees` -> warning tone
- Implement this in the shared status badge mapping instead of adding ad hoc template classes where possible.

## Data and Logic Touchpoints

- New shared status presentation helper module in `wms/`
- `wms/status_badges.py`
  - badge tone mapping for shipment, order, and review statuses
- `wms/shipment_view_helpers.py`
  - canonical shipment labels for Scan shipments-ready rows
- `wms/views_portal_orders.py`
  - portal dashboard/detail payloads for order status, review status, and shipment status
- `wms/planning/version_dashboard.py`
  - planning shipment summary rows that show shipment lifecycle labels
- `templates/portal/dashboard.html`
  - new `Statut commande` and `Statut expedition` columns
- `templates/portal/order_detail.html`
  - separate visible lines for order status, review status, and shipment status

## Testing Strategy

- Add presenter/helper tests for canonical visible labels and shipment status projection.
- Extend shipment helper tests to prove `packed` is rendered as `Disponible`.
- Extend Portal view tests to prove:
  - dashboard exposes separate order and shipment statuses
  - detail page exposes separate order, review, and shipment status values
  - shipment status falls back to `-` without a linked shipment
- Extend Planning dashboard tests to prove shipment labels use the canonical shipment vocabulary.
- Extend badge tests or Bootstrap UI tests to prove key visible shipment states map to distinct badge tones.

## Validation

- Run focused helper, Portal, Planning, and Scan tests during implementation.
- Re-run a combined regression suite covering:
  - status presenters/helpers
  - Portal views and Portal UI rendering
  - shipment view helpers
  - Planning dashboard summaries
- Keep this lot scoped to vocabulary and visible status semantics, not workflow transitions or notifications.
