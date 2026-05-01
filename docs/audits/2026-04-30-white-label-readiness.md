# White-Label Readiness Audit - 2026-04-30

Scope: ASF-WMS on `main` at `24d5147d06425786d384714638d69bda9d491505`, audited on branch `codex/white-label-readiness-audit`.

Change classification: **B. Generic reusable capability** with **E. Legacy debt reduction**, constrained by **A. ASF operational continuity**. This audit recommends incremental productization only; no code changes are included.

## 1. Executive summary

- White-label readiness score: **2/5**.
- The codebase has reusable logistics foundations, but it is not yet white-label ready without careful configuration seams.
- Top blocker 1: no tenant or installation boundary for core data/configuration.
- Top blocker 2: ASF identity and legal/logistics copy are embedded in high-trust print, email, portal, and home surfaces.
- Top blocker 3: portal and billing contracts still expose "Association" as a runtime model/vocabulary layer.
- Top opportunity 1: preserve single-tenant deployments and externalize install-level identity first.
- Top opportunity 2: reuse the existing party graph, runtime settings, integration outbox, and print-template/versioning layers.
- Top opportunity 3: introduce feature/config flags before any module renames or tenancy refactor.
- Mandatory i18n check: Django i18n exists, but translation work is explicitly paused and many high-impact surfaces remain hardcoded French/ASF.
- Mandatory integration check: integrations are mostly environment-configurable but still globally scoped and provider-specific.
- Risk level for ASF production: **low for audit/docs; low-to-medium for first config PRs; high for shared-DB tenancy or broad renames now**.

## 2. Top blocking issues

### 1. No product installation or tenant boundary

Description: Core data and runtime configuration are single-installation. `WmsRuntimeSettings` is a singleton, core models do not carry an installation/client scope, and API keys/integration settings are global.

Why it blocks productization: a white-label product needs at least a clear "this deployment belongs to client X" boundary. Shared-DB multi-tenant productization would require broad data-model propagation across stock, shipments, receipts, planning, documents, portal access, and integrations.

Concrete evidence:
- `wms/models_domain/integration.py:304-420` defines singleton `WmsRuntimeSettings` with `pk=1`.
- `wms/models_domain/catalog.py:61-142` defines `Product` with global `sku`, category, stock defaults, and no organization/client scope.
- `wms/models_domain/inventory.py:10-220` defines global `Warehouse`, `Location`, `ProductLot`, and `Receipt` models.
- `wms/models_domain/shipment.py:58-143` defines `Shipment` without tenant/client ownership.
- `asf_wms/settings.py:429-449` exposes global `ORG_*`, `SKU_PREFIX`, `INTEGRATION_API_KEY`, and print-template directories.

Risk if changed: high if implemented as broad tenancy now; low if first limited to an installation config facade preserving current defaults.

Suggested direction: for the next 6-12 months, keep single-tenant deployments per client. Add a small installation/profile configuration layer first; do not add `organization_id` to operational tables until there is a proven need.

### 2. ASF identity is embedded in trusted user-facing and document surfaces

Description: ASF brand, contact details, legal wording, signatory, logo, and operational assumptions are directly embedded in templates and email subjects.

Why it blocks productization: pilots cannot safely reuse documents, account flows, or trust surfaces if they print ASF contact/legal identity or send ASF-branded emails.

Concrete evidence:
- `templates/home.html:6` and `templates/home.html:192-200` hardcode `ASF WMS` and logistics copy.
- `templates/print/partials/shipment_note_body.html:5-9`, `:74`, and `:122` hardcode ASF logo/contact and ASF customs/flight-manager labels.
- `templates/print/partials/customs_note_body.html:5-9`, `:74`, and `:121-123` hardcode ASF/Air France customs wording.
- `templates/print/partials/donation_certificate_body.html:14-20` hardcodes signatory, Messagerie Medicale title, Aviation Sans Frontieres, and Orly address.
- `wms/account_request_handlers.py:431-436`, `wms/admin_account_request_approval.py:265`, and `wms/views_portal_auth.py:59` use ASF WMS email subjects.
- `deploy/pythonanywhere/asf-wms.messmed.env.template:16-37` carries ASF/Messmed defaults.

Risk if changed: medium to high for print/legal documents; low for home/header/email subject defaults if protected by snapshot tests.

Suggested direction: externalize install-level identity in layers, starting with low-risk shell/email labels, then print-document identity only after targeted print regression tests.

### 3. Portal and billing are still semantically "Association" contracts

Description: The product has better shipper/recipient scopes now, but model names, serializers, permissions, and billing models still expose `AssociationProfile`, `AssociationRecipient`, and association-named fields.

Why it blocks productization: future clients may be hospitals, charities, commercial donors, public agencies, or warehouses. "Association" as a runtime contract confuses generic users and makes future migrations harder if renamed abruptly.

Concrete evidence:
- `wms/models_domain/portal.py:194-253` defines `AssociationProfile`.
- `wms/models_domain/portal.py:433-470` defines `AssociationRecipient` and related fields.
- `wms/models_domain/billing.py:14-30` and `:116-149` define association billing profile/frequency concepts.
- `api/v1/serializers.py:303-312` exposes `association_name`, `association_email`, and `association_phone`.
- `api/v1/permissions.py:40-44` uses `IsAssociationProfileUser`.
- `wms/admin_account_request_approval.py:223-232` provisions `AssociationProfile` for non-recipient portal users.

Risk if changed: high if models/routes are renamed; medium for visible vocabulary; low if compatibility names stay in code and only labels/config adapt.

Suggested direction: do not rename models now. Introduce partner/shipper vocabulary at the presentation and API-adapter edges first, while preserving existing database contracts.

### 4. Default ASF shipper binding is hardcoded into recipient approval

Description: recipient account approval can attach recipients to a default ASF shipper identified by hardcoded ASF ID/name.

Why it blocks productization: a pilot client may not have a root ASF shipper. The default binding is operationally useful for ASF but should be client configuration, not product logic.

Concrete evidence:
- `wms/policies/shipment_parties.py:5-13` defines `DEFAULT_RECIPIENT_SHIPPER_ASF_ID = "ASF-ORG-ROOT"`.
- `wms/shipment_party_setup.py:12-14` defines `PRIORITY_SHIPPER_NAME = "Aviation Sans Frontieres"` and default portal referent names.
- `wms/default_shipper_bindings.py:29-93` resolves the default shipper by ASF ID/name.
- `wms/admin_account_request_approval.py:31-39` includes the skip reason `expediteur ASF manquant`.
- `docs/repo-reference/04-shared-contracts/04-portal-parties.md` documents that recipient approval provisions default ASF shipper binding.

Risk if changed: medium/high because it affects portal approval, recipient scope, and shipment eligibility.

Suggested direction: make this an explicit per-installation default-shipper policy with ASF defaults and tests around account approval.

### 5. ASF logistics workflow rules are mixed with generic warehouse logic

Description: some operational logic encodes ASF-specific cargo families, ready locations, and flight-courier planning assumptions.

Why it blocks productization: clients with different product families, pack zones, or transport models cannot reuse the workflow without code edits.

Concrete evidence:
- `wms/pack_handlers.py:47-58` hardcodes preparateur families `MM`/`CN` and ready-zone labels.
- `wms/pack_handlers.py:82-124` resolves carton family from root product category and location labels.
- `wms/forms.py:776-778` exposes "Famille MM/CN".
- `wms/planning/config.py:1-5` contains legacy planning constants.
- `wms/planning/legacy_communications.py:11-50` hardcodes communication families including WhatsApp volunteers, ASF internal email, and Air France email.
- `wms/planning/flight_providers/airfrance_klm.py:14-32` defaults to Air France/KLM, CDG, and AF.

Risk if changed: high in packing/planning paths; these are operationally sensitive.

Suggested direction: add feature/config flags and explicit "ASF logistics preset" configuration. Do not generalize packing/planning behavior before tests cover current MM/CN and planning reference cases.

### 6. Internationalization is present but not product-ready

Description: Django i18n is enabled, FR/EN locale files exist, and some templates use `{% trans %}`, but translation work is explicitly paused and high-impact strings remain hardcoded.

Why it blocks productization: white-label clients may not need multiple languages immediately, but incomplete i18n makes labels, email subjects, documents, and portal copy harder to configure and localize later.

Concrete evidence:
- `asf_wms/settings.py:357-365` enables `fr`/`en`, locale paths, `USE_I18N`, and `LocaleMiddleware`.
- `locale/fr/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po` exist.
- `docs/policies/translation-paused.md:3-28` says translation work and locale maintenance are paused.
- `wms/tests/views/tests_i18n_language_switch.py:40-73` asserts the language switch is hidden.
- `templates/home.html:190-228` and `templates/print/partials/*.html` contain hardcoded French/ASF copy rather than translatable/configured text.

Risk if changed: medium, because changing translation behavior can alter many user-visible workflows. Full FR/EN parity is not a safe first productization step.

Suggested direction: keep translation paused for now, but use the same audit inventory to separate "configurable product vocabulary" from full i18n. Do not restart translation parity unless a pilot requirement demands it.

### 7. External integrations are configurable, but globally scoped and provider-specific

Description: email, flight import, document scanning, Microsoft Graph PDF conversion, integration API keys, and local helper tooling are installed as global environment/runtime settings. Some provider names are hardcoded.

Why it blocks productization: pilots may use different mail providers, antivirus availability, flight/transport sources, document conversion backends, and deployment environments.

Concrete evidence:
- `asf_wms/settings.py:378-446` defines global email, Brevo, integration API, Microsoft Graph, and print pack settings.
- `api/v1/permissions.py:10-13` uses one `X-ASF-Integration-Key`.
- `api/v1/views.py:241-249` reads `X-ASF-Source` and `X-ASF-Target` headers.
- `wms/emailing.py:25-29` and `:366-449` use Brevo first, then Django SMTP fallback.
- `wms/document_scan_queue.py:26-54` defaults to ClamAV and local file paths.
- `wms/print_pack_graph.py:25-33` requires Microsoft Graph credentials for conversion.
- `wms/runtime_settings.py:229-289` defaults the planning flight provider to `airfrance_klm`, CDG, and AF.
- `tools/planning_comm_helper/README.md:1-25` describes ASF-specific local helper names and paths.

Risk if changed: medium. Integrations are operational but already isolated enough to wrap behind clearer provider/capability flags.

Suggested direction: introduce an integration capability matrix and per-installation provider settings, preserving ASF defaults. Avoid replacing providers until pilots actually need alternatives.

### 8. Current permission/scope model is not tenant isolation

Description: portal scopes control external-user access to shipper/recipient contexts, but they do not isolate all operational data for multiple clients in one database.

Why it blocks productization: `PortalAccessGrant` is useful for partner scopes, but shared-DB tenants would need pervasive query filtering, admin scoping, media isolation, integration key partitioning, and tests across every route.

Concrete evidence:
- `wms/models_domain/portal.py:256-347` scopes `PortalAccessGrant` to one `ShipmentShipper` or one `ShipmentRecipientOrganization`.
- `docs/repo-reference/04-shared-contracts/04-portal-parties.md` documents destination-aware recipient scope and portal access behavior.
- `wms/models_domain/catalog.py`, `wms/models_domain/inventory.py`, and `wms/models_domain/shipment.py` define global operational tables without tenant filtering.
- `api/v1/views.py:52-58`, `:198-219`, and `:222-234` expose global querysets filtered by request params, not by tenant.

Risk if changed: very high for shared DB tenancy. A missed filter would be a data leak.

Suggested direction: treat the current scope model as partner-access control, not tenant isolation. Use separate deployments/databases for pilots.

## 3. ASF-specific leakage (HIGH IMPACT ONLY)

| file | type | example | impact | severity |
|---|---|---|---|---|
| `templates/print/partials/donation_certificate_body.html` | branding / legal copy | ASF signatory, Messagerie Medicale title, Aviation Sans Frontieres, Orly address | Wrong legal identity on pilot documents | Critical |
| `templates/print/partials/shipment_note_body.html` | branding / workflow | ASF logo/contact, "RESP. DOUANE ASF", "RESPONSABLE VOL ASF" | Shipment paperwork not reusable | Critical |
| `templates/print/partials/customs_note_body.html` | integration / regulatory | Air France X-ray wording, ASF customs label | Customs/document trust risk if reused | Critical |
| `wms/policies/shipment_parties.py` and `wms/default_shipper_bindings.py` | business rule | `ASF-ORG-ROOT`, default ASF shipper binding | Recipient approvals depend on ASF root shipper | Critical |
| `wms/shipment_party_setup.py` | business rule / vocabulary | `Aviation Sans Frontieres`, default referent names | Default party graph assumes ASF | High |
| `wms/models_domain/portal.py` and `wms/models_domain/billing.py` | vocabulary / data model | `AssociationProfile`, `AssociationRecipient`, association billing | Generic partner model leaks legacy naming | High |
| `api/v1/permissions.py` and `api/v1/views.py` | integrations | `X-ASF-Integration-Key`, `X-ASF-Source`, `X-ASF-Target` | API contract is ASF-branded | High |
| `wms/pack_handlers.py` and `wms/forms.py` | workflow | `MM`/`CN`, "Colis Prets MM/CN" | Packing rules assume ASF cargo taxonomy | High |
| `wms/planning/legacy_communications.py` | integrations / workflow | WhatsApp volunteers, Mail ASF interne, Mail Air France | Planning communications assume ASF transport workflow | High |
| `wms/planning/flight_providers/airfrance_klm.py` | external integration | default CDG/AF/Air France KLM provider | Flight import assumes ASF aviation network | High |
| `templates/home.html` | branding / vocabulary | `ASF WMS`, "Demande benevole" | First screen not white-label | Medium |
| `deploy/pythonanywhere/*messmed*` | deployment | `messmed.pythonanywhere.com`, ASF sender, Brevo sender | Pilot deployments require copy/edit and risk mistakes | Medium |
| `contacts/asf_ids.py` | identifiers | generated IDs `ASF-C-...` | Export/import identifiers expose ASF prefix | Medium |

## 4. Already generic parts (REUSE READY)

### Contact and shipment-party graph

Module/area: `contacts.models`, `wms/models_domain/shipment_parties.py`, `wms/parties/*`, `wms/application/parties/use_cases.py`.

Why it is generic: it already separates organizations, people, shippers, recipients, destination-scoped recipient organizations, contacts, links, and validation status.

Refactor effort: **light to moderate**. Keep the graph; add product-facing vocabulary and configuration around defaults.

### Portal access grants

Module/area: `wms/models_domain/portal.py:256-347`, `wms/portal_access.py`.

Why it is generic: explicit grants scoped to shipper or recipient contexts are a reusable partner-access pattern.

Refactor effort: **light** for labels; **high** only if reused as tenant isolation, which is not recommended now.

### Runtime settings and design tokens

Module/area: `wms/models_domain/integration.py:304-454`, `wms/runtime_settings.py`, `wms/context_processors.py:31-90`.

Why it is generic: operational thresholds, email queue tuning, legacy feature flag, and UI design tokens are already runtime-configurable.

Refactor effort: **moderate** to extend into installation identity/config without changing behavior.

### Integration event / outbox pattern

Module/area: `wms/models_domain/integration.py:36-76`, `wms/events/outbox.py`, `wms/emailing.py`, `wms/document_scan_queue.py`.

Why it is generic: durable event rows with direction/source/target/event type/status/payload can support provider-specific adapters.

Refactor effort: **light** to document capability flags; **moderate** to support provider plugins.

### Print template and Print Pack versioning

Module/area: `wms/models_domain/shipment.py:655-848`, `templates/scan/print_template_list.html`, `wms/print_pack_engine.py`.

Why it is generic: templates, packs, versions, XLSX mappings, generated artifacts, and Graph conversion are already abstract enough for other document layouts.

Refactor effort: **moderate** because current HTML document copy is ASF-specific.

### Extracted application/service layers

Module/area: `wms/application/*`, `wms/policies/*`, `wms/jobs/*`, `wms/artifacts/*`, `wms/parties/*`.

Why it is generic: newer modules provide usable boundaries for incremental extraction without rewriting legacy views.

Refactor effort: **light** when adding new configuration readers; **moderate** when replacing legacy hardcoded rules.

### Shared UI primitives and shell assets

Module/area: `templates/wms/components/`, `wms/templatetags/wms_ui.py`, `templates/includes/secondary_shell_*`, `wms/static/scan/scan-bootstrap.css`.

Why it is generic: shared controls and shells are reused across scan, portal, planning, benevole, and admin surfaces.

Refactor effort: **light** for brand colors/tokens; **moderate** for vocabulary/navigation changes.

### Billing computation profiles

Module/area: `wms/models_domain/billing.py`.

Why it is generic: computation profiles, currencies, grouping modes, payment methods, and corrections can be reused once "association" labels are isolated.

Refactor effort: **moderate** because model names and portal bindings remain association-specific.

## 5. Configuration opportunities (TOP 10 ONLY)

| what to externalize | where it is today | expected impact |
|---|---|---|
| Organization identity: name, address, phone/email, logo, stamp, signatory, legal title | `asf_wms/settings.py:429-433`, print partials, `templates/home.html` | Highest; enables pilot branding without forks |
| Product/reference prefixes: SKU, contact ID, shipment/carton prefixes where applicable | `asf_wms/settings.py:437`, `contacts/asf_ids.py`, shipment/carton code helpers | High; prevents ASF IDs in pilot exports |
| Portal vocabulary: association/partner/shipper/recipient/user labels | `wms/models_domain/portal.py`, `api/v1/serializers.py`, portal templates | High; improves external-user fit |
| Default shipper policy for recipient approvals | `wms/policies/shipment_parties.py`, `wms/default_shipper_bindings.py` | High; removes ASF root assumption |
| Print-document legal copy and routing defaults: origin, departure IATA, customs wording, donation certificate text | `templates/print/partials/*` | High; required before real pilot paperwork |
| Packing families and ready-zone mapping | `wms/pack_handlers.py`, `wms/forms.py`, `wms/static/scan/scan.js` | High; allows different warehouse taxonomies |
| Planning provider and communication families/templates | `wms/planning/legacy_communications.py`, `wms/planning/flight_providers/airfrance_klm.py`, `wms/runtime_settings.py` | Medium/high; separates ASF aviation planning from generic logistics |
| Email sender, subject prefixes, recipient group names, reply-to behavior | `asf_wms/settings.py:378-405`, `wms/emailing.py`, account/portal/tracking handlers | Medium/high; avoids ASF-branded notifications |
| Feature/capability flags: portal billing, planning, document scan, Print Pack, public orders, local helper | `wms/runtime_settings.py`, `asf_wms/settings.py`, route modules | Medium/high; supports small pilots without exposing unused modules |
| Deployment/integration profile: PythonAnywhere paths, Brevo, Graph, ClamAV, local planning helper | `deploy/pythonanywhere/*`, `tools/planning_comm_helper/*`, `wms/print_pack_graph.py` | Medium; reduces setup errors and clarifies pilot support envelope |

## 6. Multi-tenancy: pragmatic assessment

| option | effort | main risks for ASF | when it becomes necessary |
|---|---|---|---|
| Option A - single-tenant per client | Low | Operational deployment overhead; config drift between installations; duplicated maintenance | Default for small pilots, especially when ASF production must stay isolated |
| Option B - shared DB with `organization_id` | High | Data leaks from missed filters; broad migrations across stock, shipments, documents, media, portal, APIs, admin, jobs, integrations | Only when there are many clients, shared operations, centralized analytics, or strong cost pressure |
| Option C - schema-based tenancy | Medium/high | Operational complexity, migrations per schema, PythonAnywhere/simple hosting mismatch, harder support/debugging | When client count grows but database-level isolation is required without separate deployments |

Recommended default path for the next 6-12 months: **Option A - single-tenant per client**.

Underlying assumptions:
- Small number of pilot clients.
- Limited operational complexity.
- No strong data sovereignty constraints.
- ASF production must remain isolated and stable.
- The team can tolerate a few separate deployments/databases.
- Pilot learning matters more than centralized tenant administration.

What would invalidate this recommendation:
- More than a small handful of active clients.
- Need for shared cross-client admin, support dashboards, or analytics.
- Strong data-residency or contractual isolation requirements that separate deployments cannot handle cleanly.
- Per-client configuration churn becomes operationally expensive.
- A pilot requires shared workflows between client datasets.
- Infrastructure moves away from modest single-process hosting and supports heavier tenancy operations.

## 7. Suggested target direction

What good looks like in 6 months:
- ASF production still behaves the same by default.
- New pilot deployments can set organization identity, visible vocabulary, feature flags, and integration providers without code forks.
- High-risk operational workflows such as stock, carton status, planning eligibility, portal scopes, and print truth remain covered by reference tests.
- ASF-specific behavior is explicit as an "ASF preset" or configuration profile, not hidden in generic-looking code.
- Compatibility model names such as `AssociationProfile` may still exist internally, but visible labels and new API contracts avoid hardcoding "association" where possible.

Key principles:
- Config over code for identity, labels, document copy, provider choices, and feature availability.
- Feature flags before removing or generalizing operational modules.
- Separate ASF defaults from generic behavior through small adapters/policies, not module renames.
- Preserve existing database contracts until tests and pilots prove a migration is worth the risk.
- Do not productize by forking ASF paths into permanent client-specific branches.

Organization model recommendation:
- **Do not introduce an early tenant-scoping `Organization` model.**
- Reason: the recommended tenancy path is single-tenant per deployment, and `contacts.Contact` already represents organizations/people inside the operational domain. Adding a broad `Organization` model now would be ambiguous: tenant, legal entity, shipper, recipient, or contact?
- Introduce an **installation configuration abstraction** instead, initially backed by existing settings and/or singleton runtime settings. If the product later moves to shared DB tenancy, introduce an explicit `Tenant` or `Client` model and propagate it deliberately through core tables.

## 8. Migration strategy (PR-oriented)

Step 1:
- goal: define a read-only installation configuration contract.
- scope: settings-backed resolver for organization identity, vocabulary keys, and feature flags; tests assert ASF defaults.
- risk level: low.
- expected benefit: creates one safe place to add pilot configuration without touching workflows.

Step 2:
- goal: move low-risk branding to the installation config.
- scope: home page brand/title, non-regulatory shell labels, email subject prefix defaults.
- risk level: low.
- expected benefit: visible white-label progress with minimal operational blast radius.

Step 3:
- goal: inventory and protect high-risk document identity.
- scope: add focused tests/snapshots for shipment note, customs note, donation certificate, packing list, and email/account templates before changing copy.
- risk level: low for tests, medium for later edits.
- expected benefit: makes print/legal refactors safer.

Step 4:
- goal: externalize document identity and legal copy behind ASF defaults.
- scope: logo/stamp/signatory/contact/origin/customs text context for print templates; no layout redesign.
- risk level: medium/high.
- expected benefit: enables real pilot paperwork while protecting ASF print truth.

Step 5:
- goal: isolate partner vocabulary from internal compatibility names.
- scope: labels/forms/serializers where "association" is user-facing; keep model/table names unchanged.
- risk level: medium.
- expected benefit: generic portal experience without risky data migrations.

Step 6:
- goal: add explicit capability flags and provider descriptors.
- scope: planning flight API, local helper, Brevo/SMTP, Graph PDF, ClamAV/document scan, portal billing/public orders.
- risk level: medium.
- expected benefit: pilot deployments can disable irrelevant features and document required integrations.

Step 7:
- goal: pilot deployment checklist for single-tenant installs.
- scope: generic env template, smoke checklist, seed-data guidance, integration capability matrix.
- risk level: low.
- expected benefit: reduces founder dependency and setup mistakes without changing runtime behavior.

## 9. No-go zones

- Shared-DB `organization_id` migration across core tables now: too much propagation risk for stock, shipments, documents, media, portal, APIs, admin, jobs, and integrations.
- Renaming `AssociationProfile`, `AssociationRecipient`, routes, or modules now: high migration/test churn with limited pilot value.
- Changing shipment status semantics, especially `PICKING` vs `PACKED`: repo reference marks this as a critical planning/readiness invariant.
- Generalizing MM/CN packing before coverage is strengthened: it affects preparateur speed, carton codes, ready locations, and shipment handoff.
- Rewriting planning solver or communication flows before pilot need is proven: high operational impact and many legacy reference cases.
- Editing customs/donation certificate legal copy without print tests and ASF signoff: document trust/regulatory risk.
- Restarting full translation parity as part of white-label work: i18n is paused by policy; treat visible vocabulary configuration separately.
- Creating permanent ASF/client forks: violates the shared-codebase mission and raises maintenance risk.

## 10. Quick wins (HIGH ROI ONLY)

1. Create an installation-config inventory file or constants map covering identity, vocabulary, feature flags, and integrations.
2. Add a small test that asserts current ASF defaults for organization identity and email subject prefix before any refactor.
3. Use the existing `ORG_*` and `SKU_PREFIX` settings consistently in low-risk non-print surfaces.
4. Add a generic PythonAnywhere env template for pilot clients, derived from `deploy/pythonanywhere/asf-wms.env.template`.
5. Add a provider/capability matrix documenting Brevo/SMTP, Graph PDF, ClamAV, Air France/KLM, and local planning helper requirements.
6. Add an audit check that reports high-impact hardcoded `ASF`, `Messagerie Medicale`, `MM/CN`, and `Air France` occurrences outside tests/docs.
7. Add feature-flag documentation for modules that pilots may not need: planning, portal billing, document scan, Print Pack, public orders, local helper.
8. Create print-document fixture tests before changing any regulatory or legal text.
9. Add a vocabulary map for visible labels only, preserving internal compatibility names.
10. Document "single-tenant per client" as the default pilot deployment policy until invalidated.

## 11. Tests needed BEFORE refactor

| what to test | why it matters | effort |
|---|---|---|
| Installation identity rendering across home, shell, email subjects, and selected portal auth pages | Catches accidental ASF branding removal or wrong pilot labels in low-risk surfaces | S |
| Print document truth and identity snapshots for shipment note, customs note, donation certificate, packing list, and labels | These are high-trust operational/regulatory outputs | M |
| Portal scope and party permissions across shipper/recipient grants, legacy `AssociationProfile` fallback, and account approval | Prevents external data leaks and broken partner access | M |
| Packing/preparateur MM/CN workflows and shipment readiness/planning eligibility | Protects warehouse throughput and false-ready prevention | M |
| Integration provider fallback paths for email queue, document scan, Graph PDF, planning flight import, and integration API key auth | Prevents silent failures in modest deployment environments | M |

## 12. Open product questions

1. Are pilot clients expected to run the same humanitarian aviation logistics workflow, or more general warehouse/partner shipment workflows?
2. Is French-only acceptable for the first pilots, or is English/customer-language support a launch blocker?
3. Which modules are mandatory for pilots: scan, portal, billing, planning, volunteer, print pack, document scan, public orders?
4. Who owns legal document copy per client, especially donation certificates, customs notes, and packing lists?
5. Do pilots need Air France/KLM flight planning, another carrier integration, or no flight planning at all?
6. What data-isolation guarantees must be promised contractually for pilot clients?
7. Should product vocabulary center on "partner", "shipper", "recipient", "organization", or another domain term?

## Documentation impact check

This task is itself documentation. No repo-reference update is required because no runtime behavior, routes, permissions, shared contracts, deployment process, or data model changed. Future implementation PRs should update the repo reference if they introduce new configuration boundaries, feature flags, or changed shared contracts.
