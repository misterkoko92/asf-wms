# Recipient Preference Table Alignment Design

## Goal

Align the line-by-line recipient product preference tables used by portal shipper, portal recipient, and scan/admin, and add a shared `Qté par colis (estimation)` column derived from the existing carton capacity logic.

## Current State

- The shipper portal recipient detail page at `/portal/recipients/<id>/` renders a line-by-line product preference table in `templates/portal/recipient_detail.html`.
- The recipient-scoped portal maintenance page at `/portal/recipient/preferences/` renders a near-identical table in `templates/portal/recipient_preferences.html`.
- The scan/admin recipient organization detail page renders the same business rows in `templates/scan/admin_recipient_organization_detail.html`.
- All three surfaces read and write the same canonical `RecipientProductPreference` rows on `ShipmentRecipientOrganization`.
- Existing order/carton estimation logic already computes carton capacity from product weight/volume and carton format in `wms/order_helpers.py`, using `get_product_weight_g`, `get_product_volume_cm3`, and carton format constraints.

## Problem

- Operators cannot see, on the recipient preference tables, how many units of a product typically fit in one carton.
- The three tables have drifted slightly in wording and column balance even though they expose the same business rows.
- The user specifically wants the same capacity hint shown on portal shipper, portal recipient, and scan/admin, and wants the column widths adjusted for readability.

## Decision

Keep the three tables aligned and add one shared estimate field per row: the estimated number of units that fit in the default carton format.

## Why This Approach

### Recommended approach: shared helper plus aligned tables

- Preserves one cross-surface contract for canonical recipient preference rows.
- Reuses the same weight/volume carton-capacity logic already trusted elsewhere in scan/portal order estimation.
- Avoids recomputing three slightly different estimates in three views.
- Makes operator training easier because the same table semantics appear on all three surfaces.

### Rejected approach: portal-only UI tweak

- Would create unnecessary drift with scan/admin even though scan/admin is already using the same preference rows.
- Leaves the operational cockpit without the same capacity hint that portal users would see.

### Rejected approach: duplicate scan estimation logic inside each view

- Would fork a weight/volume business rule that already exists.
- Makes it easy for portal and scan/admin to diverge on unknown-data handling or carton defaults.

## Target UX

For all three line-by-line preference tables:

- Add `Qté par colis (estimation)` immediately after `Produit`.
- Show an integer estimate when the product and default carton format expose enough data.
- Show `--` when the estimate cannot be computed.
- Keep `Quantité cible` compact because values stay in the `1..999` range.
- Keep `Notes` narrower than today.
- Give `Statut` and `Période` more width so their labels remain fully visible.

No change to:

- the recipient-scope home summary table
- preference semantics or validation
- translation or Next/React paused scope

## Runtime Design

### Shared estimate helper

- Add a helper in `wms/order_helpers.py` that returns the maximum number of units of one product that fit in one carton format.
- Derive the value from the same limits already used for order estimation:
  - product weight
  - product volume
  - carton max weight
  - carton internal volume approximation from dimensions
- Keep behavior conservative and compatible with existing `estimate_cartons_for_line`:
  - if both weight and volume limits are known, use the minimum
  - if only one limit is known, use that limit
  - if neither limit is known, return `None`

### View integration

- Fetch the default carton format once in the context builder.
- Attach `units_per_carton_estimate` to each `recipient_product_rows` entry for:
  - `wms/views_portal_account.py::_build_recipient_detail_context`
  - `wms/views_scan_admin.py::_build_admin_recipient_preference_context`
- The recipient-scoped portal page will inherit the same row payload because it already reuses `_build_recipient_detail_context`.

### Template integration

- Update the three templates to render the new column and rebalance the editable columns.
- Keep the business wording and row actions unchanged outside the requested UI adjustments.

## Data And Rule Constraints

- Use the default carton format returned by `wms/portal_helpers.py::get_default_carton_format`.
- Do not create or persist a new recipient preference field for this estimate; it remains computed display metadata.
- Do not change the canonical write path: portal and scan/admin must continue to write through `save_recipient_product_preference`.
- Preserve `--` for unknown estimate cases instead of guessing.

## Tests

Add or update tests for:

- row context exposing `units_per_carton_estimate`
- portal recipient detail rendering the new column and estimate
- portal recipient-scope maintenance rendering the new column and estimate
- scan/admin recipient detail rendering the new column and estimate
- unknown-data fallback rendering `--`
- table class/width contract changes that are now shared across the three surfaces

## Docs Impact

Update `docs/repo-reference/04-shared-contracts.md` because the shared recipient preference table contract now includes a cross-surface estimate column and aligned column-balance expectations.
