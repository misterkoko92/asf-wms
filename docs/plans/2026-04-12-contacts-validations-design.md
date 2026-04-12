# Contacts Validations Design

**Date:** 2026-04-12

**Goal:** Expose contact-sensitive validation workflows under a dedicated `Contacts` navigation group, while removing pending validations from the overloaded contacts cockpit and keeping current business rules stable.

## Scope

- Legacy Django stack only.
- Create a visible `Contacts` group in the Scan sidebar.
- Centralize contact-related validation entry points under `Contacts > Validations`.
- Split validation operations into two explicit sub-surfaces:
  - `Validation expéditeurs`
  - `Validation destinataires`
- Keep the current account-validation business flow and recipient-organization business flow stable for the first delivery.

## Non-Goals

- Do not redesign the shipment-party domain model.
- Do not merge shipper/account validation rules with recipient validation rules into one unified backend workflow.
- Do not move contact import/export into the new `Contacts` group in this delivery.
- Do not remove the current contacts cockpit route or its fallback Django-admin links.

## Baseline Findings

### Navigation and UI patterns

- The Scan sidebar already groups features by workflow area using collapsible groups in `templates/scan/includes/scan_sidebar_navigation.html`.
- The Scan UI consistently uses:
  - `scan-card card border-0 ui-comp-card`
  - simple page headers with title/help/actions
  - KPI cards and plain tables
- The Scan templates do not currently use Bootstrap tabs or another established tabs component. Introducing tabs for validations would add a one-off pattern with little value.

### Existing validation surfaces

- Account validations already expose a clear queue/detail workflow:
  - `templates/scan/account_validation_list.html`
  - `templates/scan/account_validation_detail.html`
- Recipient validations are currently surfaced as an alert table inside:
  - `templates/scan/admin_contacts.html`
- Recipient detail work today is routed through:
  - `templates/scan/admin_recipient_organization_detail.html`
  which is a broad management screen, not a focused validation dossier.

### Alignment with current data-management model

- Account validation writes are already aligned with the canonical shipment-party runtime flow.
- The contacts cockpit reads and writes shipment-party data through the current registry/runtime mechanisms.
- Import/export contacts remain a known alignment gap and should stay outside this navigation refactor.
- Recipient profile editing in portal still includes one direct runtime update helper outside the preferred use-case layer; that is a technical alignment issue, but not a blocker for the navigation/IA refactor.

## Approaches Considered

### 1. Single combined validations table

- One page with shipper and recipient validations mixed together.
- Rejected for the first delivery:
  - permissions differ today
  - dossier shapes differ
  - the screen would be harder to scan quickly

### 2. Validations hub with two explicit sub-surfaces

- `Contacts > Validations` becomes the entry point.
- Two visible cards lead to:
  - `Validation expéditeurs`
  - `Validation destinataires`
- Recommended because it centralizes the workflow without forcing a premature backend merge.

### 3. Keep validations embedded inside contacts pages

- Rejected because it preserves the current overload and weakens discoverability on a business-critical flow.

## Approved Design

### Navigation

- Add a dedicated `Contacts` sidebar group, separate from `Gestion`.
- The group should expose:
  - `Répertoire`
  - `Rôles expédition`
  - `Validations`
- `Validations` is the visible operational entry point for all contact-related validations.

### Validations information architecture

- Use a `hub -> file d'attente -> dossier` flow.
- Avoid tabs.
- Reuse established Scan patterns:
  - header card
  - short explanatory copy
  - KPI/badge count
  - queue table
  - dossier screen with two-column layout

### Contacts > Validations hub

- One lightweight page with two prominent cards:
  - `Validation expéditeurs`
  - `Validation destinataires`
- Each card shows:
  - queue count
  - one-sentence description
  - CTA to open the queue
- Purpose: orient operators quickly without merging unlike workflows.

### Validation expéditeurs queue and dossier

- Reuse the current account-validation list/detail workflow as the basis.
- Keep existing routes and logic stable where possible.
- Prefer a thin UX refactor over business-logic changes.

### Validation destinataires queue and dossier

- Move pending recipient validations out of `admin_contacts.html`.
- Create a dedicated queue page listing pending recipient dossiers.
- Create a validation-focused recipient dossier screen:
  - left column: identity and context
  - right column: ASF decision and required qualification inputs
- Do not turn the recipient validation screen into a full admin cockpit.
- Keep fine-grained maintenance actions in `Rôles expédition`, with links out when needed.

## UX Principles

- Validation pages must feel like short operational queues, not generic admin pages.
- Make queue status immediately visible through counts and concise labels.
- Keep operator choices obvious:
  - open dossier
  - validate
  - refuse
  - return to queue
- Reserve advanced maintenance actions for management pages outside the validation flow.

## Data and Logic Touchpoints

- `templates/scan/includes/scan_sidebar_navigation.html`
  - add the `Contacts` group
- `templates/scan/admin_contacts.html`
  - remove the pending-recipient-validations alert block
- current account-validation templates
  - reused or wrapped by the new IA
- new validation hub/list/detail templates
  - added under `templates/scan/`
- `wms/scan_urls.py`
  - add routes for the hub and recipient-validation queue/detail
- `wms/views_scan_account_validations.py`
  - keep existing flow stable, possibly expose helper/query reuse
- `wms/views_scan_admin.py`
  - stop surfacing recipient validations inside the contacts cockpit
  - expose dedicated recipient-validation pages

## Testing Strategy

- Start with failing tests for:
  - sidebar `Contacts` group visibility
  - `Validations` entry presence
  - pending recipient validations removed from contacts cockpit
  - validation hub rendering both sub-surfaces
  - recipient-validation queue/detail rendering expected content
- Re-run current account-validation tests to confirm no regression.
- Re-run current contacts cockpit tests to confirm the reduced scope still behaves correctly.

## Validation

- Run targeted Django test suites for:
  - scan bootstrap/navigation
  - account validations
  - scan admin contacts / shipment parties
- Re-check repo-reference impact after implementation because navigation and validation entry points are shared UI contracts.
