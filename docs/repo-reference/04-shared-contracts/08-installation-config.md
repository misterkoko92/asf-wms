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
- `references.contact_identifier_generated_prefix` is the installation-level
  generated contact identifier prefix. Its ASF default is exactly `ASF-C`, so
  generated contact identifiers continue to render as `ASF-C-{pk:08d}` by
  default, including examples such as `ASF-C-00000001`.
- The reference prefix applies only to the generated branch of
  `Contact.asf_id`, through `contacts.asf_ids.build_generated_asf_id()`. It does
  not apply to manually entered, imported, historical, or special values.
- `references.contact_identifier_generated_prefix` is validated at first use by
  the contact identifier generation helper. Empty values, any whitespace,
  leading `-`, and trailing `-` fail loudly with `ValueError`; invalid
  configured values must not silently fall back to `ASF-C`.
- `Contact.asf_id` remains the technical field name. The model field, database
  column, form field name, URLs, variables, lookup semantics, and import/export
  column names are not renamed by the references config.
- Existing non-empty contact identifiers are not rewritten when the generated
  prefix changes. This includes manual values, imported values, legacy values,
  historical `ASF-C-*` values, and special values such as `ASF-ORG-ROOT`.
- `references.contact_identifier_label` is the installation-level visible label
  for narrow contact identifier display surfaces whose ASF wording is exactly
  `ASF ID`. Controlled consumers are the explicit contact admin form label and
  the shipment tracking access recovery / pending-created email templates.
- `references.tracking_contact_identifier_label` is the installation-level
  visible label for the public shipment tracking identifier prompt whose ASF
  wording is exactly `ID ASF`. Controlled consumers are the tracking identifier
  helper and the gateway form that already delegates to that helper.
- Contact identifier label configuration does not set
  `Contact.asf_id.verbose_name`, rename Django model/admin metadata, alter
  gettext catalogs, scan placeholder/prose, import/export columns, generated
  prefixes, stored values, or print/PDF output.
- `vocabulary.portal_partner_label` is the portal-specific noun for the
  shipper/partner account label family. Its default is exactly `association` to
  preserve current ASF portal output. It is intentionally separate from
  `vocabulary.partner_label`, whose default remains `partenaire` and whose
  broader semantics are not consumed by the portal shell/account surface.
- Controlled runtime consumers of the portal partner vocabulary live only in the
  portal shell/account templates: the portal fallback title, the non-recipient
  portal masthead title, the portal account intro title, and the portal account
  organization-name field label.
- `identity.product_display_name` is the narrow visible product/application
  name for approved shell surfaces only. Its ASF default is exactly `ASF WMS`.
- `identity.organization_brand_name` is the narrow short operator/brand label
  for approved shell surfaces only. Its ASF default is exactly `ASF`; it must
  not be used for full institutional strings such as Aviation Sans Frontières or
  Aviation Sans Frontières France.
- PR11 shell identity composition stays template-local and non-generic. Existing
  surrounding literals remain in the touched templates; there is no shared
  composition helper, word-order logic, preposition logic, casing logic, or i18n
  format-string contract for these labels.
- `identity.organization_full_name` is the long organization-name declaration.
  Its ASF default is exactly `Aviation Sans Frontieres`, and existing `ORG_NAME`
  environment overrides continue to flow through the installation config layer.
  Placeholder values such as the raw settings fallback `ORG_NAME` normalize to
  the ASF default through the existing installation-config placeholder contract.
- `identity.organization_full_name` has one narrow runtime consumer in document
  context construction: `wms.documents.build_org_context()` uses it only for the
  existing `org_name` print context key. This is a replacement for the legacy
  direct `settings.ORG_NAME` read and does not introduce a new print header,
  footer, logo, address, contact line, public-utility statement, legal/signatory
  field, or broad print/PDF identity contract.
- Other print/PDF identity, legal/trust/footer identity, scan branding, PWA
  identity, shipper/reference namespace behavior, and contact routing remain
  outside the PR11 shell identity scope.

### Print namespace

`installation.print` is currently a narrow print-rendering policy namespace.
Its first contract is limited to the four HTML print footer line fields below.

| Key | Exact ASF default | Description |
|---|---|---|
| `print.html_footer_public_contact_line` | `https://aviation-sans-frontieres.org/messmed // messmed@aviation-sans-frontières-fr.org` | Public service URL and email footer line. |
| `print.html_footer_headquarters_line` | `Siège: Bat 293, Porte 1150, Orly Fret 768 - 94398 Orly Aérogare Cedex - Tel: (33) 1 49 75 74 36` | Headquarters address and phone footer line. |
| `print.html_footer_warehouse_line` | `Magasin: Bat. 7200, Porte 2D520, rue de la Remise - 95700 ROISSY en France - Tél: (33) 1 74 25 03 22` | Warehouse address and phone footer line. |
| `print.html_footer_legal_notice_line` | `Association reconnue d'utilité publique par décret du 12 novembre 1993` | Public-utility legal notice footer line. |

These fields are consumed by the shared HTML print footers in
`templates/print/base_document.html` and `templates/print/base_a5.html`.

The four fields are HTML print footer contract fields. They intentionally do not
reuse `ORG_CONTACT`, `ORG_ADDRESS`, or `ORG_NAME`: those settings do not carry
the current four-line footer contract and must not become hidden fallback
sources for footer policy.

Do not broaden `installation.print` into a generic document identity namespace
without a dedicated decision. Footer text, donation certificates, customs
documents, XLSX/Graph print packs, logos, stamps, role labels, legal identity,
and broader document metadata have different contracts and review risks.

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
- Generated contact identifier configuration does not change visible labels
  (`ASF ID` / `ID ASF`), contact import/export columns (`asf_id` / `id_asf`),
  default shipper behavior, `ASF-ORG-ROOT`, API headers, print/PDF output, or
  persisted planning communication values such as `email_asf`.
- Contact identifier label configuration does not change generated identifiers,
  contact import/export columns (`asf_id` / `id_asf`), default shipper behavior,
  `ASF-ORG-ROOT`, API headers, print/PDF output, scan branding/prose, or
  persisted planning communication values such as `email_asf`.
- This does not restart or replace i18n work.
- This module was intentionally unused by runtime code in the foundation PR.
  Current controlled runtime consumers are limited to tested notification
  formatting/sender boundaries, the narrow contact identifier label surfaces,
  the narrow portal partner label family, and approved shell/site product or
  short-brand identity surfaces.

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
