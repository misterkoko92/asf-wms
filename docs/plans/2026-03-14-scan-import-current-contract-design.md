# Scan Import Current Contract Design

**Date:** 2026-03-14

**Goal:** Align the legacy `/scan/import/` page, import templates, and CSV exports with the current business reality, while keeping legacy header aliases tolerated in the import parsers.

## Scope

- Keep all work on the legacy Django stack only.
- Update the legacy Scan imports page at `scan/import`.
- Cover the product, contact, and user import blocks that the user explicitly flagged.
- Treat static CSV templates and CSV exports as the reference documentation for the supported import contract.

## Non-Goals

- Do not touch paused Next/React migration files.
- Do not redesign the full import UX beyond the requested corrections.
- Do not remove parser tolerance for legacy column aliases unless a field is now actively harmful.
- Do not broaden this lot into unrelated scan-page work already handled in the visual batch.

## Constraints

- Prefer the current parser behavior as the source of truth for what the backend can read.
- Prefer the current business rules for contacts over historical import examples.
- Keep imports backward tolerant where possible, but document only the current supported schema.
- Preserve superuser-only access and the existing import flow structure.

## Approaches Considered

### 1. UI-only correction

- Fix the default checkbox state and radio alignment in the template.
- Rejected because it would leave contact/user templates and exports potentially out of sync with the actual business contract.

### 2. Current-contract alignment with tolerant readers

- Update UI, static CSV templates, exports, and tests to reflect the current supported contract.
- Keep legacy parser aliases in place so old files are still readable.
- Approved because it matches the user's request while minimizing migration risk for historical files.

### 3. Strict parser cleanup

- Remove old aliases and only accept the newly documented headers.
- Rejected because it raises unnecessary operational risk for older spreadsheets still in circulation.

## Approved Design

### `Import produits`

- Keep the current product import/export schema as the documented contract because it is already aligned between:
  - `wms/import_services_products.py`
  - `wms/static/scan/import_templates/products.csv`
  - `wms/exports.py`
- Make `Présélectionner "Mettre à jour" si un produit existe` checked by default in the file-import form.
- Keep the stock-mode backend behavior unchanged, but restyle the radio controls so each option is rendered inline as radio then label on one line.

### `Import contacts`

- Officially document the current contact schema already supported by the parser and export:
  - contact identity fields for organizations and persons
  - tags
  - destination scope
  - `linked_shippers`
  - `use_organization_address`
  - organization linkage for persons
  - address fields
- Keep legacy aliases accepted in `wms/import_services_contacts.py`, but do not surface them in the reference template.
- Review the single-contact form on `/scan/import/` and add/remove fields only if the current business rules require it for parity with the documented contract.

### `Import utilisateurs`

- Keep the documented schema centered on:
  - `username`
  - `email`
  - `first_name`
  - `last_name`
  - `is_staff`
  - `is_superuser`
  - `is_active`
  - `password`
- Preserve the backend rule in `wms/import_services_users.py`:
  - password is required for new users only when neither a row password nor `IMPORT_DEFAULT_PASSWORD` is available
- Align the single-user form so the HTML does not require a password when a default password is configured in settings.

### Templates and Exports as Living Documentation

- Static CSV templates under `wms/static/scan/import_templates/` become the user-facing reference examples.
- CSV exports in `wms/exports.py` must emit the same current fields and field order as the documented contract where applicable.
- When a field is obsolete or no longer useful in the current business model, remove it from the documented template/export surface even if the parser still tolerates it.
- When a field is now required for operational clarity, add it to both the documented template and the export.

## Data and Logic Touchpoints

- `templates/scan/imports.html`
  - default checkbox state
  - radio markup presentation
  - optional user-form password requirement adjustment
- `wms/static/scan/import_selectors.css`
  - inline radio alignment style update
- `wms/static/scan/import_templates/contacts.csv`
  - update reference example to current contact business rules
- `wms/static/scan/import_templates/users.csv`
  - ensure the example reflects the current user contract
- `wms/exports.py`
  - keep contact/user export headers and rows aligned with the documented contract
- `wms/import_services_contacts.py`
  - only minimal logic changes if a current-rule gap is found during TDD
- `wms/import_services_users.py`
  - only minimal logic changes if HTML/backend expectations diverge

## Testing Strategy

- Extend `wms/tests/views/tests_views_imports.py` to assert:
  - import selector assets still render
  - product update checkbox is checked by default
  - stock-mode radios use the intended inline markup
  - user password field requirement matches `IMPORT_DEFAULT_PASSWORD`
- Extend `wms/tests/scan/tests_scan_import_handlers.py` to cover any current-rule behavior gaps discovered for contacts/users.
- Extend `wms/tests/exports/tests_exports.py` to lock the contact/user export headers and rows to the approved current contract.
- Keep tests focused on the legacy import page, handlers, and exports only.

## Validation

- Run targeted import view, handler, and export tests red/green during implementation.
- Re-run the focused import regression suite after the changes.
- Run `git diff --check` before reporting completion.
