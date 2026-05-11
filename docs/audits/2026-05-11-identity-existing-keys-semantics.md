# Identity Existing Keys Semantics Audit

Date: 2026-05-11
Branch: `audit/identity-existing-keys-semantics`
Scope: existing keys declared under `installation.identity` in `wms/config/installation.py`.
Change classification: B. Generic reusable capability, E. Legacy debt reduction, constrained by A. ASF operational continuity.

## 1. Executive summary

`installation.identity` declares 6 keys: `organization_full_name`, `organization_short_name`, `application_display_name`, `contact_email`, `sku_prefix`, and `contact_reference_prefix`. None of the 6 identity keys is currently consumed at runtime through `get_installation_config().identity.*`; current runtime consumers of installation config are limited to `notifications.*` and `vocabulary.portal_partner_label`. The principal identity risk is that the same ASF concepts are split across product name, organization name, legal name, sender identity, support contact, SKU prefix, and contact/reference identifiers, so naive consumption would change visible ASF wording or route contact/email identity incorrectly. Only `sku_prefix` appears obviously safe for a future narrow runtime consumption, and only where it is a direct replacement for the existing `settings.SKU_PREFIX` source with unchanged ASF defaults.

## 2. Key audit

### `organization_full_name`

#### 2.1 Default value

Default string: `"Aviation Sans Frontieres"`.

Declared at `wms/config/installation.py:7` as `ASF_ORG_FULL_NAME`, then exposed through `_setting_text("ORG_NAME", ASF_ORG_FULL_NAME)` at `wms/config/installation.py:145`. The value is settings-derived from `ORG_NAME` when Django settings provide a non-placeholder value; otherwise the ASF fallback string above is used.

#### 2.2 Intended meaning (inferred)

Interpretive: this appears to mean the installation organization name in long form, using the existing `ORG_NAME` deployment setting as the source when present. `git blame` traces the field and default to `764136bbc feat: add installation configuration foundation`, the PR1 foundation commit.

#### 2.3 Runtime consumption status

Declared and tested, but not consumed at runtime through installation identity. `git grep` finds the key in `wms/config/installation.py:27`, `:145`, and config tests at `wms/tests/config/tests_installation_config.py:27`, `:91`, `:267`; no production code reads `get_installation_config().identity.organization_full_name`.

Runtime code does consume the older `ORG_NAME` setting in print context plumbing: `wms/documents.py:10` returns `org_name`, and `wms/print_context.py:331`, `:540`, `:687`, and `:748` merge that context into print/billing contexts. That is not consumption of this identity key.

#### 2.4 Real visible surfaces for the concept

- Print/PDF: `templates/print/partials/donation_certificate_body.html:16` hardcodes the exact default string in the donation certificate association row; `templates/print/partials/donation_certificate_body.html:20` uses the accented variant `Aviation Sans Frontières` in body copy.
- Base templates / shell / navigation: `templates/includes/secondary_shell_masthead.html:53` uses `Aviation Sans Frontières France` as an aria label; `templates/includes/secondary_shell_masthead.html:57` displays `Aviation Sans Frontières`; `templates/scan/base.html:63` and `:88` use `Aviation Sans Frontières France` as aria labels.
- Runtime/business identity concept: `wms/public_order_handlers.py:16` declares `DEFAULT_SHIPPER_NAME = "Aviation Sans Frontieres"`; `wms/shipment_party_setup.py:12` declares `PRIORITY_SHIPPER_NAME = "Aviation Sans Frontieres"`; `wms/shipment_helpers.py:36` recognizes the same name case-insensitively.
- Settings/deployment docs: `.env.example:39`, `README.md:233`, `README.md:293`, `deploy/pythonanywhere/asf-wms.env.template:24`, and `deploy/pythonanywhere/asf-wms.messmed.env.template:16` use `ORG_NAME=Aviation Sans Frontieres`.
- Policy/legal docs: `docs/policies/confidentialite.md:14`, `:18`, `docs/policies/mentions-information-formulaires.md:33`, `:53`, `:69`, `:98`, `docs/policies/mentions-legales.md:15`, `:55`, and `docs/policies/rgpd.md:35` use `Aviation Sans Frontieres` in legal/privacy text.
- Tests: `wms/tests/config/tests_installation_config.py:91` asserts the identity default; many shipper/contact tests use the same string as a runtime party name, for example `wms/tests/views/tests_views_scan_shipments.py:92`.

#### 2.5 Conflict with ASF visible behavior

Would consuming it naively today change visible ASF behavior? Yes on surfaces that currently show `Aviation Sans Frontières` with accents or `Aviation Sans Frontières France`; no on the donation certificate row that already uses the exact unaccented default. The key also risks replacing a product, shell, or legal-entity string with a generic organization string, which would not preserve all current ASF visible wording exactly.

#### 2.6 Boundary with other config sections

This is primarily organization identity, with legal identity risk. It overlaps `installation.vocabulary.organization_label` only by wording proximity, not by meaning: the vocabulary key is a noun label, while this identity key is an organization name. It overlaps Django settings `ORG_NAME`, print document context from `wms/documents.py`, legal/policy documents, and default shipper business rules; it does not overlap `installation.notifications.*` except where organization name could be confused with email sender branding.

#### 2.7 Risk analysis

Risks before runtime consumption: legal name accuracy, accent/France suffix drift, replacing ASF legal or policy text incorrectly, confusing organization identity with default shipper identity, and changing visible shell aria labels or print text used by users and tests. Print/legal surfaces are high-trust surfaces and should not be changed by a generic name substitution.

#### 2.8 Recommendation

**KEEP** — The key is valid as a long organization-name declaration and its default matches the existing `ORG_NAME` setting and at least one print surface exactly. It should only be consumed by a future narrow surface that already uses this exact concept, not as a general replacement for every `Aviation Sans Frontières`, `Aviation Sans Frontières France`, or default shipper occurrence.

### `organization_short_name`

#### 2.1 Default value

Default string: `"ASF"`.

Declared at `wms/config/installation.py:8` as `ASF_ORG_SHORT_NAME`, then exposed through `_setting_text("ORG_SHORT_NAME", ASF_ORG_SHORT_NAME)` at `wms/config/installation.py:146`. `ORG_SHORT_NAME` is not currently declared in `asf_wms/settings.py`, so the field currently falls back to the constant unless a Django setting is added elsewhere.

#### 2.2 Intended meaning (inferred)

Interpretive: this appears to mean a short display form of the installation organization name. `git blame` traces the field and default to `764136bbc feat: add installation configuration foundation`.

#### 2.3 Runtime consumption status

Declared and tested, but not consumed at runtime through installation identity. `git grep` finds the key in `wms/config/installation.py:28`, `:146`, and config tests at `wms/tests/config/tests_installation_config.py:28`, `:92`, `:134`, `:244`, `:268`; no production code reads `get_installation_config().identity.organization_short_name`.

Many runtime occurrences of the literal `ASF` are not identity-key consumption. They include portal text, print labels, API headers, helper names, product brands, contact IDs, and workflow labels.

#### 2.4 Real visible surfaces for the concept

- Portal: `wms/views_portal_auth.py:48` says `Compte non activé par ASF.`; `wms/view_permissions.py:36` and `:39` mention ASF review/blocking; `wms/views_portal_orders.py:89`, `:568`, `:573`, and `:575` mention ASF parcel guidelines and stock; `wms/portal_dashboard_helpers.py:36` and `:38` render validation/preparation labels with ASF.
- Emails: `templates/emails/account_request_approved.txt:4`, `:6`, `:8`, `:24`; `templates/emails/account_request_approved_user.txt:3`, `:11`; `templates/emails/account_request_received.txt:4`; and `templates/emails/volunteer_account_request_confirmation.txt:7` contain ASF wording.
- Print/PDF: `templates/print/partials/shipment_note_body.html:5`, `:74`; `templates/print/partials/customs_note_body.html:5`, `:74`; `templates/print/partials/donation_certificate_body.html:5`; `wms/print_context.py:492` and `:544` use `ASF` for default company/donor context.
- Contact/reference UI: `wms/forms_admin_contacts_contact.py:72` labels the field `ASF ID`; `templates/scan/includes/admin_contacts_filters_card.html:12` uses `ASF ID`; `templates/scan/shipment_tracking.html:351` mentions `ID ASF`.
- Integration/deployment identifiers: `api/v1/permissions.py:12` reads `X-ASF-Integration-Key`; `api/v1/views.py:244` and `:249` read `X-ASF-Source` and `X-ASF-Target`; `tools/planning_comm_helper/server.py:11` uses `X-ASF-Planning-Helper`.
- Tests: widespread tests use `ASF` as shipper, actor structure, product brand, identifier prefix, or visible wording; examples include `wms/tests/views/tests_portal_bootstrap_ui.py:181`, `:273`, `:275`, `:277`, `:279`, `wms/tests/views/tests_views_portal.py:2439`, and `wms/tests/views/tests_print_strict_fidelity.py:78`, `:111`.

#### 2.5 Conflict with ASF visible behavior

Would consuming it naively today change visible ASF behavior? It could preserve the literal `ASF` where that exact short organization concept is intended, but it would be unsafe as a blanket replacement because `ASF` currently means organization short name, stock source, validation actor, email brand component, API header namespace, product brand, and contact ID prefix depending on surface. Some occurrences are operational workflow wording rather than organization identity.

#### 2.6 Boundary with other config sections

This is mixed/ambiguous unless limited to short organization display. It overlaps `installation.notifications.*` through `ASF WMS` sender and subject branding, `installation.vocabulary.*` where ASF appears in user-facing labels such as validation/review wording, Django settings `SKU_PREFIX`, integration header names, contact `asf_id`, and legal/policy text.

#### 2.7 Risk analysis

Risks before runtime consumption: confusing short organization name with product display name, stock source, validation authority, support sender, API namespace, or generated contact ID prefix; changing test-locked visible labels; and replacing ASF-specific operational rules with generic organization branding. Legal/policy text also uses ASF as an actor, not just a display name.

#### 2.8 Recommendation

**SPLIT** — The key is too broad for direct runtime consumption because the literal `ASF` currently carries multiple independent meanings. Future consumption should use narrower identity or policy keys per surface rather than treating `organization_short_name` as a global replacement token.

### `application_display_name`

#### 2.1 Default value

Default string: `"ASF-WMS"`.

Declared at `wms/config/installation.py:9` as `ASF_APPLICATION_DISPLAY_NAME`, then exposed through `_setting_text("APPLICATION_DISPLAY_NAME", ASF_APPLICATION_DISPLAY_NAME)` at `wms/config/installation.py:147-149`. `APPLICATION_DISPLAY_NAME` is not currently declared in `asf_wms/settings.py`, so the field currently falls back to the constant unless a Django setting is added elsewhere.

#### 2.2 Intended meaning (inferred)

Interpretive: this appears to mean the product/application display name, distinct from the organization identity. `git blame` traces the field and default to `764136bbc feat: add installation configuration foundation`. The installation-config shared contract later clarifies that this is distinct from the historical email prefix: `docs/repo-reference/04-shared-contracts/08-installation-config.md:38-43`.

#### 2.3 Runtime consumption status

Declared and tested, but not consumed at runtime through installation identity. `git grep` finds the key in `wms/config/installation.py:29`, `:147`, docs-only discussion in `docs/audits/2026-05-01-email-layer-inventory.md:308`, `:334`, `:336`, `:346`, `:351`, and config tests at `wms/tests/config/tests_installation_config.py:29`, `:93`, `:269`. No production code reads `get_installation_config().identity.application_display_name`.

#### 2.4 Real visible surfaces for the concept

- Base/home shell: `templates/home.html:6` sets `<title>ASF WMS</title>`; `templates/home.html:194` displays `ASF WMS`.
- Planning shell: `templates/includes/secondary_shell_masthead.html:21` uses `ASF WMS Planning` as an aria label; `templates/planning/base.html:39` displays `ASF WMS`.
- Emails and email subjects: `templates/emails/account_request_approved.txt:26`, `templates/emails/account_request_approved_user.txt:13`, `templates/emails/account_request_received.txt:7`, `templates/emails/order_confirmation.txt:3`, `:13`, `templates/emails/portal_forgot_password.txt:13`, `templates/emails/volunteer_forgot_password.txt:13`; runtime subjects include `wms/account_request_handlers.py:579`, `:584`, `wms/order_notifications.py:15`, `:16`, `wms/public_order_handlers.py:23`, `:24`, `wms/views_portal_auth.py:65`, `wms/views_volunteer_auth.py:54`, and `wms/views_shipment_tracking_access.py:55`. <!-- pragma: allowlist secret -->
- Scan/PWA: `wms/static/scan/manifest.json:2` names the PWA `ASF WMS Scan`; `wms/tests/views/tests_scan_bootstrap_ui.py:2463` asserts one page does not expose that string.
- Runtime non-UI identifiers: `wms/billing_exchange_rates.py:29` uses `ASF-WMS Billing/1.0` as a User-Agent; `wms/planning/flight_providers/airfrance_klm.py:82` uses `ASF-WMS/planning-flight-client`.
- Docs-only references: `README.md:1` uses `ASF WMS`; `AGENTS.md:1`, `:7`, `:14` use `ASF-WMS`; `docs/repo-reference/00-product-context.md:16` uses `ASF-WMS`.
- Tests: email and config tests assert the spaced form for notifications and the hyphenated form for identity, for example `wms/tests/config/tests_installation_config.py:93`, `:100`, `:101`, `wms/tests/emailing/tests_email_subject_formatting.py:17`, `:20`, and `wms/tests/emailing/tests_emailing_extra.py:189`, `:293`.

#### 2.5 Conflict with ASF visible behavior

Would consuming it naively today change visible ASF behavior? Yes for visible surfaces that currently display `ASF WMS` with a space, including the home title/header, planning header, email bodies, email sender name, and email subject prefix. The identity default is `ASF-WMS`, while current visible UI and notification defaults often use `ASF WMS` or `ASF WMS -`.

#### 2.6 Boundary with other config sections

This is product identity. It overlaps strongly with `installation.notifications.email_subject_prefix` and `installation.notifications.email_sender_name`, but those notification keys deliberately preserve `ASF WMS -` and `ASF WMS` separately. It also overlaps deployment/repo names (`asf-wms`), User-Agent strings, PWA manifest naming, and legal/policy documents that describe the service as `ASF WMS`.

#### 2.7 Risk analysis

Risks before runtime consumption: changing visible titles used in tests, replacing the historical spaced email prefix with a hyphenated product name, confusing product name with organization name, and creating inconsistent public branding across home, portal, planning, email, and docs. The absence of an `APPLICATION_DISPLAY_NAME` setting in `asf_wms/settings.py` also means deployment override readiness is incomplete today.

#### 2.8 Recommendation

**RENAME** — The key name suggests a visible display name, but the default does not match several current visible ASF display surfaces that use `ASF WMS`. Any rename or default revision would require a separate compatibility-aware decision before runtime consumption.

### `contact_email`

#### 2.1 Default value

Default fallback string: `"messmed@aviation-sans-frontieres-fr.org"`.

Declared at `wms/config/installation.py:10` as `ASF_CONTACT_EMAIL`. The exposed value is derived at `wms/config/installation.py:136-141` from the first non-placeholder of `ORG_CONTACT`, `BREVO_REPLY_TO_EMAIL`, `BREVO_SENDER_EMAIL`, and `DEFAULT_FROM_EMAIL`, falling back to the default string above.

#### 2.2 Intended meaning (inferred)

Interpretive: this appears to mean the installation contact email for public or support-style contact surfaces. `git blame` traces the field and default to `764136bbc feat: add installation configuration foundation`.

#### 2.3 Runtime consumption status

Declared and tested, but not consumed at runtime through installation identity. `git grep` finds the identity key in `wms/config/installation.py:30`, `:136`, `:151`, and config tests at `wms/tests/config/tests_installation_config.py:30`, `:94`, `:270`.

Other runtime `contact_email` occurrences are unrelated local variables, form fields, or contact synchronization logic, for example `wms/signals.py:496`, `:499`, `:502`, `:503`, `wms/static/scan/import_selectors.js:659`, and `wms/views_shipment_tracking_access.py:283-288`. Those do not consume installation identity.

#### 2.4 Real visible surfaces for the concept

- Print/PDF: `templates/print/partials/shipment_note_body.html:8` and `templates/print/partials/customs_note_body.html:8` hardcode the exact default email with phone number; `templates/print/base_document.html:79` and `templates/print/base_a5.html:79` use the same MessMed email with HTML entity encoding in the footer.
- Settings/deployment: `asf_wms/settings.py:379` defines `DEFAULT_FROM_EMAIL`; `asf_wms/settings.py:390-392` define Brevo sender/reply-to settings; `asf_wms/settings.py:431` defines `ORG_CONTACT`; `.env.example:41` uses placeholder `contact@example.com`; `.env.example:57` uses `no-reply@example.com`; `deploy/pythonanywhere/asf-wms.env.template:26`, `:31`, `:44`, `:46`, `:47` and `deploy/pythonanywhere/asf-wms.messmed.env.template:18`, `:22`, `:34`, `:36`, `:37` show the current deployment split between placeholder org contact and real sender/reply-to values.
- Print context plumbing: `wms/documents.py:12` exposes `org_contact` from `settings.ORG_CONTACT`; `templates/print/attestation_aide_humanitaire.html:14` displays `{{ org_contact }}`.
- Tests: `wms/tests/config/tests_installation_config.py:94` asserts the identity fallback; `wms/tests/views/tests_print_strict_fidelity.py:81` and `:115` assert the exact print contact line.

#### 2.5 Conflict with ASF visible behavior

Would consuming it naively today change visible ASF behavior? It could preserve the two print note bodies that already hardcode `messmed@aviation-sans-frontieres-fr.org`, but it could also change behavior in deployments where `BREVO_REPLY_TO_EMAIL`, `BREVO_SENDER_EMAIL`, or `DEFAULT_FROM_EMAIL` resolve first. The PythonAnywhere templates currently use placeholder `ORG_CONTACT` but personal ASF sender/reply-to email values, so this key can resolve as a sender/contact hybrid rather than the public MessMed address.

#### 2.6 Boundary with other config sections

This is mixed support/contact identity and email deployment identity. It overlaps `installation.notifications.email_sender_name`, Django `DEFAULT_FROM_EMAIL`, `BREVO_SENDER_EMAIL`, `BREVO_REPLY_TO_EMAIL`, `ORG_CONTACT`, support/contact routing, and print document contact lines. It does not overlap `installation.vocabulary.*` except through public wording around contact/support surfaces.

#### 2.7 Risk analysis

Risks before runtime consumption: email deliverability and reply-to routing changes, public exposure of a personal sender address, replacing print/legal contact lines incorrectly, confusing support contact with sender identity, and production deployment drift because placeholder values and real sender values are intentionally mixed today. This key is high-risk for email and document surfaces.

#### 2.8 Recommendation

**SPLIT** — The key conflates public support contact, organization contact, sender email, reply-to email, and deployment fallback. Future surfaces should consume narrower contact or email-routing keys, while `contact_email` should not be used as a generic replacement without a dedicated boundary decision.

### `sku_prefix`

#### 2.1 Default value

Default string: `"ASF"`.

Declared at `wms/config/installation.py:11` as `ASF_SKU_PREFIX`, then exposed through `_setting_text("SKU_PREFIX", ASF_SKU_PREFIX)` at `wms/config/installation.py:135` and `:152`. The value is settings-derived from `SKU_PREFIX` when present, falling back to the ASF default string.

#### 2.2 Intended meaning (inferred)

Interpretive: this appears to mean the prefix used for generated product SKUs. `git blame` traces the field and default to `764136bbc feat: add installation configuration foundation`.

#### 2.3 Runtime consumption status

Declared and tested, but not consumed at runtime through installation identity. `git grep` finds the key in `wms/config/installation.py:31`, `:135`, `:152`, `:155`, and config tests at `wms/tests/config/tests_installation_config.py:31`, `:95`, `:271`.

The same concept is already consumed directly from Django settings by product SKU generation: `wms/models_domain/catalog.py:140-142` reads `settings.SKU_PREFIX` and returns `f"{prefix}-{temp}"`.

#### 2.4 Real visible surfaces for the concept

- Runtime generation: `wms/models_domain/catalog.py:140-142` uses `SKU_PREFIX`, defaulting to `ASF`, for generated SKUs.
- Settings/deployment: `asf_wms/settings.py:437` defines `SKU_PREFIX`; `.env.example:43`, `README.md:237`, `README.md:297`, `deploy/pythonanywhere/asf-wms.env.template:28`, and `deploy/pythonanywhere/asf-wms.messmed.env.template:20` use `SKU_PREFIX=ASF`.
- Import/template examples: `wms/static/scan/import_templates/products.csv:2` contains `ASF-000001` as a product SKU example.
- Tests: `wms/tests/config/tests_installation_config.py:95` asserts the identity default; `wms/tests/imports/tests_import_services_products_extra.py:53` asserts generated product SKUs start with `ASF-`.
- Related but not SKU surfaces: `contacts/asf_ids.py:7` also generates `ASF-C-...`, but that is contact reference identity, not product SKU identity.

#### 2.5 Conflict with ASF visible behavior

Would consuming it naively today change visible ASF behavior? A narrow replacement of direct `settings.SKU_PREFIX` reads in product SKU generation would preserve current ASF behavior because both defaults and deployment setting source are the same. Consuming it outside product SKU generation would be unsafe because `ASF` is also used for organization short name, contact IDs, stock source, and integration headers.

#### 2.6 Boundary with other config sections

This is product/reference identity. It overlaps Django `SKU_PREFIX` directly and should stay separate from `organization_short_name`, `contact_reference_prefix`, and `installation.vocabulary.*`. It does not overlap `installation.notifications.*` except through the shared `ASF` literal.

#### 2.7 Risk analysis

Risks before runtime consumption: accidental broad replacement of `ASF`, generated SKU format changes, import/export expectations, QR code payload changes, and tests that assert `ASF-` generated SKUs. The risk is comparatively low only for a direct settings-source equivalent path.

#### 2.8 Recommendation

**KEEP** — The key is narrow, matches an existing settings source, and its default coheres with current generated SKU behavior. It is the only identity key in this audit that appears obviously safe for a future narrow runtime consumer, provided the consumer is limited to product SKU-prefix behavior and preserves the exact current default.

### `contact_reference_prefix`

#### 2.1 Default value

Effective ASF default string: `"ASF"`.

Declared as an `InstallationIdentity` field at `wms/config/installation.py:32` and exposed through `_setting_text("CONTACT_REFERENCE_PREFIX", sku_prefix)` at `wms/config/installation.py:153-156`. The default is derived from `sku_prefix`; because `CONTACT_REFERENCE_PREFIX` is not currently declared in `asf_wms/settings.py`, the current effective default is the current `SKU_PREFIX` value, which defaults to `"ASF"`.

#### 2.2 Intended meaning (inferred)

Interpretive: this appears to mean the prefix for generated contact or contact-reference identifiers. `git blame` traces the field to `764136bbc feat: add installation configuration foundation`.

#### 2.3 Runtime consumption status

Declared and tested, but not consumed at runtime through installation identity. `git grep` finds the key only in `wms/config/installation.py:32`, `:153`, and config tests at `wms/tests/config/tests_installation_config.py:32`, `:96`, `:272`. `git grep` finds `CONTACT_REFERENCE_PREFIX` only in `wms/config/installation.py:154`.

Existing contact-reference runtime code uses hardcoded ASF-specific names and prefixes directly, not this identity key.

#### 2.4 Real visible surfaces for the concept

- Generated contact IDs: `contacts/asf_ids.py:7` generates `ASF-C-<pk-zero-padded>`; tests assert that format at `contacts/tests/test_asf_ids.py:8`, `contacts/tests/test_management_backfill_contact_asf_ids.py:76-77`, and `contacts/tests/tests_models.py:171`.
- Contact/admin UI: `wms/forms_admin_contacts_contact.py:72` labels the field `ASF ID`; `templates/scan/includes/admin_contacts_filters_card.html:12` uses the placeholder `Nom, email, téléphone, ASF ID`.
- Shipment tracking and emails: `wms/shipment_tracking_access.py:131` labels the identifier `ID ASF`; `templates/scan/shipment_tracking.html:351` explains lost-code recovery with `ID ASF`; `templates/emails/shipment_tracking_access_recovery.txt:3` and `templates/emails/shipment_tracking_pending_created.txt:6` send `ASF ID : {{ identifier }}`.
- Default shipper root identifier: `wms/policies/shipment_parties.py:5` declares `ASF-ORG-ROOT`; `wms/tests/portal/tests_default_shipper_bindings.py:22` mirrors it in tests.
- Exports/imports and docs: `wms/exports.py:302`, `:344`, and `:378` expose `asf_id`; `docs/operations.md:780-781` documents recovery with existing ASF IDs; `docs/audits/2026-04-30-white-label-readiness.md:180` calls out generated `ASF-C-...` as white-label leakage.

#### 2.5 Conflict with ASF visible behavior

Would consuming it naively today change visible ASF behavior? If used only to preserve `ASF-C-...` generated contact IDs, the default could preserve the visible prefix. But consuming it naively is risky because the key default is derived from `sku_prefix`, while current contact-reference behavior has its own `ASF-C` namespace, a separate `ASF-ORG-ROOT` default shipper identifier, and user-facing labels `ASF ID` / `ID ASF`.

#### 2.6 Boundary with other config sections

This is contact/reference identity, but currently mixed with deployment and product-prefix identity because it defaults to `sku_prefix`. It overlaps Django `SKU_PREFIX`, contact model field `asf_id`, shipment tracking identity recovery, default shipper policy, exports/imports, and legal/support identity where identifiers are shown externally. It does not directly overlap `installation.notifications.*` or `installation.vocabulary.*`.

#### 2.7 Risk analysis

Risks before runtime consumption: changing generated contact IDs, breaking imports/exports keyed by `asf_id`, changing external tracking recovery emails, conflating contact ID prefix with product SKU prefix, changing the canonical default shipper root ID, and introducing a deployment override that is not actually wired in `asf_wms/settings.py`.

#### 2.8 Recommendation

**SPLIT** — The existing key is too broad for the current identifier landscape because contact IDs, default shipper IDs, and product SKUs have different contracts. Future surfaces should consume narrower identifier keys; this generic key should not be consumed directly until those boundaries are clarified.

## 3. Synthesis table

| key | default | consumed | identity type | recommendation |
|---|---|---:|---|---|
| `organization_full_name` | `"Aviation Sans Frontieres"` | no | organization identity | KEEP |
| `organization_short_name` | `"ASF"` | no | mixed/ambiguous | SPLIT |
| `application_display_name` | `"ASF-WMS"` | no | product identity | RENAME |
| `contact_email` | `"messmed@aviation-sans-frontieres-fr.org"` | no | support/contact identity | SPLIT |
| `sku_prefix` | `"ASF"` | no | product identity | KEEP |
| `contact_reference_prefix` | `"ASF"` derived from `sku_prefix` | no | mixed/ambiguous | SPLIT |

## 4. Cross-key and cross-section conflicts

`application_display_name` conflicts most directly with `notifications.email_subject_prefix` and `notifications.email_sender_name`: the identity default is `ASF-WMS`, while current runtime notification defaults are `ASF WMS -` and `ASF WMS`, and those notification defaults are already consumed at the email boundary. The installation-config contract explicitly documents this split at `docs/repo-reference/04-shared-contracts/08-installation-config.md:38-50`.

`organization_short_name`, `sku_prefix`, and `contact_reference_prefix` all default to or derive from `ASF`, but current runtime uses `ASF` for unrelated contracts: organization short display, product SKU generation, generated `asf_id` values, default shipper root ID, integration header names, stock source labels, and validation authority wording. Treating any one of these keys as a global `ASF` replacement would cross business, UI, integration, and identifier boundaries.

`contact_email` overlaps with `DEFAULT_FROM_EMAIL`, `BREVO_SENDER_EMAIL`, `BREVO_REPLY_TO_EMAIL`, and `notifications.email_sender_name`. The current key resolution falls through email delivery settings, while current print surfaces hardcode the MessMed address and deployment templates contain placeholder `ORG_CONTACT` plus real sender/reply-to email values. Sender identity, reply-to routing, public support contact, and print contact identity are not the same contract today.

`organization_full_name` overlaps with `vocabulary.organization_label` only by natural language proximity. The former is a concrete organization name; the latter is a structural noun label. It also overlaps legal/policy files where `Aviation Sans Frontieres` can mean the responsible legal actor, and with default shipper logic where the same text is a business party name.

Legal/policy files remain high-risk for identity consumption. `docs/policies/mentions-legales.md:13-15`, `docs/policies/confidentialite.md:13-18`, and `docs/policies/rgpd.md:12`, `:35` use ASF identity in legal/privacy framing, but they also state validation requirements; these documents should not become installation-configurable by incidental identity-key consumption.

## 5. Open questions

- Should product display name and legal organization name remain separate, and what exact visible defaults should each preserve?
- Is `application_display_name` intended to be the user-facing product name, a technical product identifier, or both?
- Should email sender identity remain entirely under `notifications`, or should any part of sender/reply-to/support identity move under narrower identity/contact keys?
- Which surfaces may safely use organization identity versus legal identity versus product identity?
- Are legal/policy documents allowed to become installation-configurable, and who validates legal-name accuracy before publication?
- Should contact/support email be public contact identity, notification routing, deployment config, or multiple separate keys?
- Should contact/reference identifiers share `SKU_PREFIX`, or should product SKU prefixes and contact ID prefixes be independent contracts?
- What is the compatibility policy for existing `asf_id` values if any identifier prefix becomes configurable?

## 6. Appendix — reproducibility

    # Shared runtime-consumption checks
    git grep -n "get_installation_config" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n "\.identity" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n "identity\." -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'

    # Key: organization_full_name
    git grep -n "organization_full_name" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n -i "Aviation Sans Frontieres" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n -i "Aviation Sans Frontières" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n -i "Aviation Sans Frontières France" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n -i "Aviation Sans Frontieres France" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n "ORG_NAME"

    # Key: organization_short_name
    git grep -n "organization_short_name" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n "ORG_SHORT_NAME"
    git grep -n -w "ASF" -- templates '*.py' '*.html' '*.txt' '*.md'
    git grep -n -w "ASF" -- wms contacts api '*.py'
    git grep -n -w "ASF" -- docs '*.md' '*.txt'

    # Key: application_display_name
    git grep -n "application_display_name" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n "APPLICATION_DISPLAY_NAME"
    git grep -n -i "ASF-WMS" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n -i "ASF WMS" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n -i "ASF - WMS" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'

    # Key: contact_email
    git grep -n "contact_email" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n -i "messmed@aviation-sans-frontieres-fr.org" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n -i "messmed@"
    git grep -n "ORG_CONTACT" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n "BREVO_REPLY_TO_EMAIL" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n "BREVO_SENDER_EMAIL" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n "DEFAULT_FROM_EMAIL" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n "DEFAULT_FROM_EMAIL"

    # Key: sku_prefix
    git grep -n "sku_prefix" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n "SKU_PREFIX"
    git grep -n "ASF-" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'

    # Key: contact_reference_prefix
    git grep -n "contact_reference_prefix" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n "CONTACT_REFERENCE_PREFIX"
    git grep -n "asf_id" -- '*.py' '*.html' '*.js' '*.md' '*.txt' '*.yml' '*.yaml' '*.json'
    git grep -n "ASF ID" -- '*.py' '*.html' '*.txt' '*.md'
    git grep -n "ID ASF" -- '*.py' '*.html' '*.txt' '*.md'
    git grep -n "ASF-C" -- '*.py' '*.html' '*.txt' '*.md' '*.json' '*.csv'
    git grep -n "ASF-ORG-ROOT" -- '*.py' '*.html' '*.txt' '*.md'
