# Scan Contacts Cockpit Reposition Design

**Date:** 2026-03-14

**Goal:** Reposition the legacy Scan contacts cockpit as the main manual contact-management entry point under `Gestion`, while reducing `/scan/import/` contact handling to bulk-only actions.

## Scope

- Keep all work on the legacy Django stack only.
- Change Scan navigation so the org-role contacts cockpit is exposed from `Gestion`.
- Simplify the `Import contacts` block on `/scan/import/` to bulk-only actions:
  - upload
  - template download
  - export
- Keep the existing `/scan/admin/contacts/` route and current org-role cockpit behavior.
- Correct the shipper-recipient filter mismatch discovered during verification.

## Non-Goals

- Do not redesign the full contacts domain model.
- Do not rename the existing route or rewrite the cockpit backend.
- Do not remove the Django admin fallback links inside the cockpit page.
- Do not simplify imports for products, users, locations, categories, or warehouses in this change.

## Verified Baseline

- The page at `/scan/admin/contacts/` is an active org-role cockpit, not a legacy CRUD page.
- Targeted validation passed:
  - `wms.tests.views.tests_views_scan_admin_contacts_cockpit`
  - `wms.tests.views.tests_views_scan_admin`
  - `wms.tests.scan.tests_scan_admin_contacts_cockpit_helpers`
  - `wms.tests.views.tests_i18n_language_switch`
- Command run during validation:
  - `.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit wms.tests.views.tests_views_scan_admin wms.tests.scan.tests_scan_admin_contacts_cockpit_helpers wms.tests.views.tests_i18n_language_switch -v 1`
- Result:
  - `82 tests OK`
- Browser QA confirmed the cockpit currently exposes:
  - role activation/deactivation
  - organization contact create/update
  - role-contact linking and primary selection
  - shipper scope management
  - shipper-recipient-destination binding management
  - guided organization creation

## Baseline Finding

### Filter mismatch in `Destinataires d'un expéditeur`

- The UI label implies the select should list shipper organizations only.
- The template currently renders `cockpit_organizations`, which includes all active organizations.
- This mismatch should be corrected before the cockpit becomes the primary `Gestion > Contacts` entry point.

## Approaches Considered

### 1. Keep current navigation, simplify imports only

- Remove the single-contact import form from `/scan/import/`.
- Leave the cockpit under `Admin`.
- Rejected because the user explicitly wants `admin/contacts` to become the practical main entry point and does not need the legacy admin-menu habit preserved.

### 2. Promote the cockpit to `Gestion`, keep route stable

- Add `Contacts` to `Gestion`.
- Remove `Contacts` from `Admin`.
- Keep the existing `scan_admin_contacts` route and active key.
- Simplify `Import contacts` to bulk-only.
- Approved because it improves IA without unnecessary backend churn.

### 3. Full route and naming refactor

- Rename the route and align the page name with `Gestion`.
- Rejected because it adds avoidable URL/test/churn without improving the actual workflow.

## Approved Design

### Navigation

- Remove the `Contacts` entry from the `Admin` dropdown in `templates/scan/base.html`.
- Add a `Contacts` entry to the `Gestion` dropdown.
- Keep the route unchanged:
  - `/scan/admin/contacts/`
  - `scan:scan_admin_contacts`
- Keep the page internally marked with `active == "admin_contacts"` unless a targeted template need appears during TDD.

### `/scan/import/` contact block

- Remove the single-contact form from the `Import contacts` card.
- Keep only:
  - file upload
  - `Template contacts`
  - `Exporter contacts`
- Make the card copy explicit that manual creation/update is handled from the contacts cockpit.

### `/scan/admin/contacts/` as primary manual surface

- Preserve the current cockpit structure:
  - search and filters
  - business actions
  - organization summary table
  - contacts table
  - correspondents table
  - Django admin fallback links
- Keep the Django admin links because the cockpit is the primary operational UI, but not a total replacement for every raw `Contact` field.

### Filter correction

- Restrict the `Destinataires d'un expéditeur` filter options to organizations with an active shipper role.
- Keep the existing recipient-binding filtering behavior once a shipper is selected.
- Ensure the shipper and recipient lists inside the cockpit remain aligned with active role assignments.

## Data and Logic Touchpoints

- `templates/scan/base.html`
  - move `Contacts` nav entry from `Admin` to `Gestion`
- `templates/scan/imports.html`
  - remove the single-contact form
  - adjust explanatory copy for contact imports
- `templates/scan/admin_contacts.html`
  - keep rendered structure, but use the corrected shipper filter source
- `wms/scan_admin_contacts_cockpit.py`
  - expose a dedicated shipper-organization list for the cockpit filter
- `wms/views_scan_admin.py`
  - keep the current route and context wiring unless a minimal adaptation is required by tests

## Testing Strategy

- Extend tests in:
  - `wms/tests/views/tests_views_imports.py`
  - `wms/tests/views/tests_views_scan_admin.py`
  - `wms/tests/views/tests_views_scan_admin_contacts_cockpit.py`
  - `wms/tests/views/tests_scan_bootstrap_ui.py`
- Add coverage for:
  - `Contacts` visible under `Gestion`
  - `Contacts` no longer visible under `Admin`
  - single-contact import form removed from `/scan/import/`
  - bulk contact upload/template/export still present
  - shipper filter only lists active shippers

## Validation

- Run targeted navigation, import, admin-contact, and i18n test suites.
- Re-run quick browser QA on:
  - `/scan/import/`
  - `/scan/admin/contacts/`
- Run `git diff --check` before reporting completion.
