# Installation Configuration Contract

Read this file when adding installation-level configuration, white-label defaults,
or future consumers of organization identity, structural vocabulary, high-level
capabilities, or integration descriptors.

---

## Installation Config Foundation

### Primary runtime sources

- `wms/config/__init__.py`
- `wms/config/installation.py`

### Current contract

- `wms.config.get_installation_config()` returns a read-only snapshot of
  installation-level configuration.
- The snapshot is structured as frozen dataclasses for identity, vocabulary,
  feature/capability flags, integration descriptors, and notification
  conventions.
- The module is a leaf dependency. It may depend on Django settings and the
  Python standard library, but not on runtime application code, database models,
  forms, views, admin, jobs, APIs, policies, templates, or services.
- Values preserve current ASF defaults. Existing settings are reflected where
  they already exist, such as organization name, email settings, SKU prefix,
  document scan backend, Graph/PDF settings, and email backend settings.
- Values without an existing settings source use explicit ASF-compatible
  defaults. These defaults are declarations awaiting future externalization, not
  runtime behavior changes.
- The feature/capability flags are declarations only. They do not enable,
  disable, hide, or route any behavior in this PR.
- The integration descriptors document the current provider shape only. They do
  not refactor providers, change credentials, or change integration behavior.
- `notifications.email_subject_prefix` is the installation-level email subject
  prefix convention. It is not the canonical application name: the current
  identity display name remains `ASF-WMS`, while the historical email prefix is
  `ASF WMS -`.
- The default `notifications.email_subject_prefix` is exactly `ASF WMS -` for
  compatibility with existing visible subjects.
- `notifications.email_sender_name` is the installation-level Brevo sender
  display name. The default is exactly `ASF WMS`, and existing deployments may
  still override it through `BREVO_SENDER_NAME` via the installation config
  layer.
- Controlled runtime consumers of notification config live in the email layer:
  `wms.emailing.format_email_subject()` applies the subject prefix at the final
  transport boundary before Brevo or SMTP send, while
  `wms.emailing.resolve_email_sender_name()` is consumed only by the Brevo API
  sender payload. SMTP sender behavior remains governed by `DEFAULT_FROM_EMAIL`.
- `vocabulary.portal_partner_label` is the portal-specific noun for the
  shipper/partner account label family. Its default is exactly `association` to
  preserve current ASF portal output. It is intentionally separate from
  `vocabulary.partner_label`, whose default remains `partenaire` and whose
  broader semantics are not consumed by the portal shell/account surface.
- Controlled runtime consumers of the portal partner vocabulary live only in the
  portal shell/account templates: the portal fallback title, the non-recipient
  portal masthead title, the portal account intro title, and the portal account
  organization-name field label.

### Two categories of feature flags

Feature flags in `InstallationFeatureFlags` have two semantic categories.
Module-level flags, currently portal, planning, and billing, are explicit
declarations that a product module is part of the installation.

Capability-derived flags, currently email, document scan, print pack, and
external flight provider, must stay aligned with their corresponding
`IntegrationDescriptor.enabled` field. The current implementation enforces that
alignment by deriving those flags in `get_installation_config()`.

Future contributors must preserve this distinction. Adding a module-level flag
does not require an integration descriptor; adding a capability-derived flag
requires both the descriptor and construction-time derivation.

### What this is not

- This is not tenant isolation.
- This does not introduce multi-tenancy.
- This does not introduce an Organization, Tenant, Client, or installation model.
- This does not add `organization_id`, tenant fields, migrations, database
  constraints, or tenant-aware query filtering.
- Adding installation config values does not by itself change templates, views,
  URLs, emails, print documents, customs documents, donation documents, shipment
  flows, packing, planning, portal, billing, APIs, or integrations. Runtime
  consumers must stay narrow, explicit, and covered by tests.
- This does not restart or replace i18n work.
- This module was intentionally unused by runtime code in the foundation PR.
  Current controlled runtime consumers are limited to tested notification
  formatting/sender boundaries and the narrow portal partner label family.

### Productization role

- The current supported productization path is single-tenant deployment per
  client for the next 6-12 months.
- The config module supports that path by creating one safe place to describe an
  installation before visible branding, vocabulary, feature-flag, or integration
  documentation work consumes it.
- Shared-DB tenancy, schema-based tenancy, and tenant-scoped Organization models
  remain out of scope until pilot-client needs invalidate the single-tenant
  deployment assumption.

### Maintenance rule

- Keep `wms/config/installation.py` as a leaf module.
- Add new config domains as optional/forward-compatible dataclass fields only
  when a concrete consumer is planned.
- Preserve ASF defaults unless a separate behavior-changing PR explicitly
  updates runtime behavior and its regression tests.
- Do not consume this module from runtime code without tests around the affected
  ASF workflow.
- Do not consume broad vocabulary keys such as `partner_label` when a narrower
  current-ASF label is needed to preserve visible behavior.
- Do not use feature flags from this module to gate production behavior until
  the relevant workflow has targeted tests and rollback guidance.

### Reference tests

- `wms/tests/config/tests_installation_config.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`

---

## Next PRs expected to consume this module

These are roadmap aids, not behavior changes in the foundation PR.

- Home/shell branding: read identity values for controlled, tested display
  surfaces.
- Email subject prefixes: centralize current ASF prefixes before allowing
  installation-specific values. The current implementation exposes the
  notification prefix and applies it in the email transport boundary; future
  work may externalize the value per installation.
- Visible structural vocabulary: continue introducing narrow vocabulary
  consumers one surface at a time. The portal partner label is the first
  runtime vocabulary consumer; broader labels such as organization, partner,
  volunteer, shipper, and recipient still require separate scope decisions and
  tests before consumption.
- Feature/capability flags: document or surface high-level module availability
  before using flags to hide behavior.
- Integration capability documentation: show which provider handles email,
  PDF conversion, document scan, flight data, and local helper capability.
