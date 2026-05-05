# Portal Onboarding Wizards Design

## Goal

Improve first-use clarity for external portal users without changing existing portal business rules.

The portal should show a role-specific guided wizard on first login and allow users to reopen it later. The wizard must explain the standard workflows and the main blocking conditions that users may encounter.

## Classification

- ASF operational need: improve partner autonomy and reduce support friction.
- Generic reusable capability: role-based onboarding for portal scopes.
- Organization configuration: copy can later be adapted for future organizations.

This is not an experimental redesign and should not fork ASF-specific behavior from reusable portal behavior.

## Product Behavior

Add two separate onboarding wizards:

- shipper wizard for `PortalAccessRole.SHIPPER_ADMIN`
- recipient wizard for `PortalAccessRole.RECIPIENT_ADMIN`

The wizard opens automatically after portal scope activation when the current user's onboarding preference says it should be shown.

The wizard includes a checkbox labeled:

> Afficher à la prochaine connexion

The checkbox is checked by default. Its meaning is:

- checked: keep showing this wizard automatically at future logins for this role/scope
- unchecked: stop automatic display for this role/scope

The wizard remains available manually through a permanent masthead action, recommended label:

> Tutoriel

Automatic display must happen after scope selection. Users with several portal scopes should not see any wizard before choosing the active space.

## UX Recommendation

Use a short modal wizard, not a long tutorial page.

Each step should follow this pattern:

- title
- short action-oriented explanation
- why the step matters
- frequent blockers
- one optional action button to the relevant portal page

The goal is not to teach every detail. The goal is to help users understand what to do next and why they may be blocked.

Keep the complete reference material in the portal FAQ.

## Shipper Wizard Content

### 1. Votre espace expéditeur

Explain that the shipper space covers the account, recipients, shipment/transport requests, order follow-up, documents, and billing.

Frequent blockers:

- account still under ASF review
- shipper documents not validated or non-compliant
- some actions remain blocked until ASF review is complete

### 2. Créer un destinataire

Explain that a recipient is required before sending any shipment or transport request.

Frequent blocker:

- without an active recipient marked as the delivery contact, the user cannot create an order or access visible stock/product selection.

Recommended action:

- link to `portal:portal_recipients`

### 3. Définir les besoins et refus produits

Explain product preference statuses:

- requested
- allowed
- refused

Frequent blockers:

- requested and allowed require a target quantity and period
- refused must not carry quantity or period
- an explicitly refused product can block preparation later

Recommended action:

- link to the recipient detail or preferences area when a recipient exists

### 4. Créer une demande d'expédition / transport

Explain that, in the current interface, this is done through **Nouvelle commande**.

The wizard should keep current UI vocabulary but make the concept explicit:

> Dans le portail, une demande d'expédition ou de transport se crée via Nouvelle commande.

Frequent blockers:

- destination is required
- recipient is required
- the recipient list is filtered by destination
- if no recipient appears, the user must check recipient creation and destination linkage

Recommended action:

- link to `portal:portal_order_create`

### 5. Déclarer la source des colis

Explain the supported flows:

- parcels already prepared by the association
- warehouse drop-off
- pickup requested
- ready cartons
- ready kits
- ASF stock products to prepare

Frequent blockers:

- empty request cannot be submitted
- pickup requires complete contact, phone, address, postal code, city, country, carton count, and confirmation
- zero-stock rows may be unavailable or indicative depending on the section

### 6. Suivre et compléter

Explain:

- order status
- shipment status
- ASF requested corrections
- order documents
- billing documents and correction requests

Frequent blockers:

- some document actions depend on ASF validation
- requested corrections must be handled before the workflow can continue cleanly

Recommended action:

- link to `portal:portal_dashboard`
- link to `portal:portal_billing`

## Recipient Wizard Content

### 1. Votre espace destinataire

Explain that the recipient space focuses on:

- organization profile
- delivery stop
- referents
- structure documents
- product needs and refusals

### 2. Vérifier la fiche structure

Explain the key fields:

- structure identity
- delivery stop
- address
- beneficiary count
- notes
- validation status

Frequent blocker:

- incomplete or unvalidated profile information can slow ASF handling.

Recommended action:

- link to `portal:portal_recipient_profile`

### 3. Mettre à jour référents et documents

Explain that contacts and documents are used by ASF and shippers to understand the recipient organization.

Frequent blockers:

- missing documents
- non-compliant documents
- ASF review still pending

Recommended action:

- link to `portal:portal_recipient_profile`

### 4. Déclarer besoins et refus produits

Explain how recipient preferences guide preparation:

- requested products
- allowed products
- refused products
- quantity target
- period

Frequent blockers:

- requested and allowed require quantity and period
- refused must not carry quantity or period
- deleting a rule removes only the explicit preference, not the catalog product

Recommended action:

- link to `portal:portal_recipient_preferences`

### 5. Comprendre l'impact côté ASF / expéditeur

Explain that recipient data guides ASF operations and shipper requests.

Frequent blocker:

- an explicit refusal can prevent a product from being added to a preparation.

## Technical Design

Add a lightweight persistent model, for example `PortalOnboardingPreference`, with fields:

- `user`
- `role`
- optional `shipper`
- optional `recipient_organization`
- `show_on_next_login`, default `True`
- `last_seen_at`
- `created_at`
- `updated_at`

Persist by user and active portal scope, not by user alone. This avoids hiding the wrong wizard for users with several spaces.

Add a small portal onboarding helper under `wms/application/portal/` to:

- resolve the current onboarding key from `request.portal_scope`
- create a default preference when missing
- build the wizard payload for the active role
- determine whether automatic display is enabled
- update `show_on_next_login` and `last_seen_at`

Add one protected POST endpoint to update the preference for the active scope. It must require:

- authenticated user
- active portal scope
- CSRF protection
- no ability to write another user's preference

Add a template include, for example:

- `templates/portal/includes/onboarding_wizard.html`

Add local portal JavaScript, for example:

- `wms/static/portal/portal_onboarding.js`

The JS should:

- open the modal automatically only when the server payload says so
- navigate wizard steps
- keep the checkbox checked by default
- POST the final checkbox value
- allow manual opening from the masthead `Tutoriel` action

If JavaScript fails, the portal must remain usable.

## Integration Points

Likely touched files during implementation:

- `wms/models_domain/portal.py`
- migration under `wms/migrations/`
- `wms/application/portal/onboarding.py`
- `wms/views_portal_misc.py` or a dedicated portal onboarding view module
- `wms/portal_urls.py`
- `templates/portal/base.html`
- `templates/includes/secondary_shell_masthead.html`
- `templates/portal/includes/onboarding_wizard.html`
- `wms/static/portal/portal_onboarding.js`
- `wms/static/portal/portal-bootstrap.css`
- portal view tests under `wms/tests/views/`
- portal domain tests under `wms/tests/portal/`

Avoid touching:

- Next/React migration files
- translation catalogs
- scan service worker files unless shared scan assets change

## Testing Strategy

Focused tests should cover:

- shipper scope renders shipper wizard payload
- recipient scope renders recipient wizard payload
- missing preference defaults to automatic display
- unchecked checkbox disables future automatic display for the same scope
- manual `Tutoriel` action remains present regardless of automatic preference
- multi-scope user sees the wizard for the selected scope only
- preference POST cannot update another user's scope
- no wizard auto-display on `/portal/scope-select/`

Suggested test areas:

- `wms/tests/views/tests_views_portal.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`
- `wms/tests/portal/tests_portal_access_grants.py` or a new focused portal onboarding test file

## Documentation Impact

Documentation update is required because this changes visible portal behavior.

Minimum documentation updates during implementation:

- update portal FAQ content if the wizard copy and FAQ diverge
- add the user-visible change to `wms/faq_changelog.py` once a PR number is known
- recheck `docs/repo-reference/03b-impact-portal.md`
- recheck `docs/repo-reference/04-shared-contracts/02-ui-shell-contracts.md`
- recheck `docs/repo-reference/04-shared-contracts/04-portal-parties.md`

No business-rule contract is intended to change.

## Operational Safety

The wizard must be informational only.

It must not:

- bypass account review
- bypass recipient validation
- alter portal access grants
- alter recipient preference semantics
- change order submission validation
- hide existing portal messages
- block navigation if the modal fails

## Open Decisions Before Implementation

- Final masthead label: `Tutoriel` vs `Aide guidée`.
- Exact endpoint name for preference updates.
- Whether the first implementation stores scope-specific preferences for legacy `AssociationProfile` fallback with a nullable shipper, or normalizes through `ShipmentShipper` when present.
- Final French wording for each step.
