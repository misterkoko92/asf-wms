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
  feature/capability flags, and integration descriptors.
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
- This does not change templates, views, URLs, emails, print documents, customs
  documents, donation documents, shipment flows, packing, planning, portal,
  billing, APIs, or integrations.
- This does not restart or replace i18n work.
- This module is intentionally unused by runtime code in the foundation PR.

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
- Do not use feature flags from this module to gate production behavior until
  the relevant workflow has targeted tests and rollback guidance.

### Reference tests

- `wms/tests/config/tests_installation_config.py`

---

## Next PRs expected to consume this module

These are roadmap aids, not behavior changes in the foundation PR.

- Home/shell branding: read identity values for controlled, tested display
  surfaces.
- Email subject prefixes: centralize current ASF prefixes before allowing
  installation-specific values.
- Visible structural vocabulary: introduce a narrow vocabulary layer for labels
  such as organization, partner, volunteer, shipper, and recipient.
- Feature/capability flags: document or surface high-level module availability
  before using flags to hide behavior.
- Integration capability documentation: show which provider handles email,
  PDF conversion, document scan, flight data, and local helper capability.
