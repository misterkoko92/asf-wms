# Recipient Portal Product Preferences Design

## Goal

Allow a recipient-scoped portal user to add, modify, and delete product preferences individually from the recipient portal, instead of only seeing the read-only summary currently shown on the recipient home page.

## Current State

- Recipient-scoped users land on `/portal/`, rendered by `portal_dashboard` in `wms/views_portal_orders.py`.
- That recipient surface uses `build_recipient_scope_home_payload` from `wms/application/portal/dashboard_queries.py` and `templates/portal/recipient_scope_home.html`.
- The page currently shows shared structure data, contacts, documents, and a summary table of explicit product preferences.
- Line-by-line product preference editing already exists on the shipper-side recipient detail page at `/portal/recipients/<id>/`, implemented in `wms/views_portal_account.py` and `templates/portal/recipient_detail.html`.

## Problem

Recipient-scoped users can review their product preferences but cannot maintain them directly. This creates an asymmetry with the shipper-side maintenance surface and forces users to rely on ASF or a shipper-side operator for product preference changes that belong to the recipient organization.

## Decision

Keep the recipient home page as a lightweight dashboard and add a dedicated recipient-scoped maintenance page for product preferences.

## Why This Approach

### Recommended approach: dedicated maintenance page

- Reuses the existing product-by-product editing contract already proven on the shipper-side recipient detail page.
- Keeps the recipient home page readable and focused on shared structure information.
- Minimizes behavioral drift by reusing the same validation and save flow for product preferences.
- Gives us a clear place to add explicit delete actions without overloading the home page.

### Rejected approach: inline editing on the recipient home page

- Would turn the recipient dashboard into a large persistent form.
- Increases template complexity on the active-scope dashboard surface.
- Makes success/error handling on the home page heavier and more fragile.

### Rejected approach: direct reuse of shipper recipient detail route

- The current route and lookup semantics are built around `AssociationRecipient` compatibility rows.
- Recipient scope should operate directly from the active `ShipmentRecipientOrganization`.
- Reusing the shipper detail route would mix two permission models and increase coupling.

## Target UX

### Recipient home page

- Keep the existing summary table of explicit preferences.
- Add a CTA near the preferences card header: `Gérer les préférences produits`.
- The CTA points to a new recipient-scoped route dedicated to preference maintenance.

### Recipient preference maintenance page

- New page under the portal recipient scope.
- Shows the same product-by-product editing table style already used on the shipper detail page.
- Allows:
  - changing status for a product
  - editing quantity target and period when applicable
  - editing notes
  - saving one line at a time
  - deleting an explicit preference with a dedicated button
- Keep support for `Non précisé` so existing semantics remain valid, but expose a dedicated `Supprimer` action for explicit rows.

## Runtime Design

### Routing

- Add a recipient-scoped route in `wms/portal_urls.py`.
- Route should be protected by `portal_scope_required`, not `association_required`.

### View

- Add a new view in `wms/views_portal_account.py` that:
  - requires an active `recipient_admin` portal scope
  - reads the active `scope.recipient_organization`
  - reuses the existing preference form extraction, validation, effective-row building, and save helpers used by `portal_recipient_detail`
  - supports explicit delete action by preference id

### Template

- Add a new template for recipient-scoped preference maintenance.
- Keep Bootstrap classes aligned with the current portal recipient detail table.
- Show success and error states with the same conventions as existing portal pages.

## Data And Rule Constraints

- Source must remain `RecipientProductPreferenceSource.PORTAL`.
- Resolution and validation rules stay on the shared `RecipientProductPreference` runtime model.
- No change to category preference semantics in this ticket.
- No change to scan or preparation preference resolution logic in this ticket.
- No change to translation or Next/React paused scope.

## Tests

Add or update view/UI tests for:

- CTA presence on recipient home
- recipient-scoped maintenance page GET
- add preference
- update preference
- delete preference through explicit button
- invalid refused-with-quantity flow preserving entered values
- recipient-scope permission guard
- Bootstrap contract on the new page

## Docs Impact

If the new route becomes part of the maintained recipient-scoped portal contract, update the relevant `docs/repo-reference/` sections that describe portal recipient scope behavior and route coverage.
