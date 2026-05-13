# PR12 Audit: Reference Namespace and Default Shipper Policy

Date: 2026-05-13

Scope: audit / decision only. No runtime behavior, tests, templates, migrations, or installation configuration are changed by this document.

Change classification: B. Generic reusable capability and C. Organization configuration, constrained by A. ASF operational need.

## 1. Executive summary

The recommended next step after PR12 is to split implementation into multiple smaller PRs. A single PR13 covering contact identifiers, default shipper policy, integration headers, persisted enum values, import/export contracts, and print/PDF output would mix unrelated risk classes and would make ASF production behavior harder to preserve.

PR12 should precede PR14, PR15, and PR16 because reference namespaces, default shipper semantics, external-facing labels, and integration contracts determine which later print/PDF and external communication strings are identity, operational namespace, shipper identity, or persisted contract. Without this separation, later white-label work could incorrectly consume product or organization identity configuration for operational values.

The main risk of leaving ASF operational namespaces hardcoded is first-client data contamination: newly created client data could receive ASF-specific contact references, shipper defaults, tracking labels, API/header names, or document-facing values.

The main risk of replacing ASF values naively is production breakage: existing `Contact.asf_id` values are unique persisted lookup keys, imports and exports use `asf_id`/`id_asf`, external recovery emails expose the label, `ASF-ORG-ROOT` is a runtime lookup key for default shipper behavior, and `X-ASF-*` headers and `ASF-WMS/*` User-Agent strings may be integration contracts.

A first implementation PR can start immediately only for the contact identifier namespace and contact identifier display labels, with strict boundaries:

- keep the technical field name `Contact.asf_id`;
- keep existing persisted values valid;
- keep import/export column names unchanged;
- keep API/header contracts unchanged;
- keep `ASF-ORG-ROOT` and default shipper behavior unchanged;
- use ASF defaults so `main` continues to generate and display current ASF behavior.

Default shipper configuration must not start until the origin and existence contract for `ASF-ORG-ROOT` is understood. The smallest investigation needed is a read-only production or sanitized-production check confirming whether a `Contact` or organization/shipper party with `asf_id = "ASF-ORG-ROOT"` exists, how it was created, and whether it is part of deployment setup, admin/manual setup, or legacy data.

## 2. Current behavior inventory

Validated inventory summary:

| Literal value | File path(s) | Context | Surface | Data effect | Contract involvement |
|---|---|---|---|---|---|
| `asf_id` | `contacts/models.py`; `contacts/migrations/0002_contact_extensions.py` | `Contact.asf_id` unique nullable field | runtime; migration/historical | both | lookup; uniqueness |
| `ASF-C` | `contacts/asf_ids.py`; contact model/tests | `build_generated_asf_id()` emits `ASF-C-{pk:08d}` for missing contact IDs | runtime; test-only | newly created data; backfill for missing persisted data | persisted identifier namespace; uniqueness-related |
| `asf_id` | `wms/import_services_contacts.py`; `wms/exports.py`; `wms/static/scan/import_templates/contacts.csv` | contact import lookup/update column and contact export header | export/import-facing | both | import/export contract; lookup |
| `id_asf` | `wms/import_services_contacts.py` | alternate inbound import column accepted for contacts | import-facing | both | import contract; lookup |
| `structure_asf_id` | `wms/application/parties/use_cases.py`; `wms/parties/sync.py` | party synchronization input mapped to `Contact.asf_id` | runtime; integration-like internal boundary | both | lookup; unclear externality |
| `ASF ID` | `wms/forms_admin_contacts_contact.py`; `templates/scan/includes/admin_contacts_filters_card.html`; `templates/emails/shipment_tracking_access_recovery.txt`; `templates/emails/shipment_tracking_pending_created.txt` | contact admin/search labels and tracking email label | display-only; external communication | no data mutation | external-facing label; lookup support |
| `ID ASF` | `wms/shipment_tracking_access.py`; `templates/scan/shipment_tracking.html` | tracking access contact-role label and lost-code help copy | runtime display; external communication support | no data mutation | external-facing label; lookup support |
| `ASF-ORG-ROOT` | `wms/policies/shipment_parties.py`; `wms/default_shipper_bindings.py`; portal/default shipper tests | canonical default shipper/root organization lookup key | runtime; test-only | both, if production record exists | lookup; default shipper; default root organization unclear |
| `Aviation Sans Frontieres` | `wms/shipment_party_setup.py`; `wms/public_order_handlers.py`; `wms/shipment_helpers.py`; BE import tests/fixtures | priority/default shipper name, public order default `shipper_name`, priority shipper predicate | runtime; fixture/factory; test-only | newly created data; historical display matching | default shipper; document/output dependency |
| `aviation sans frontieres` | `wms/shipment_helpers.py`; BE import tests | normalized casefold comparison for priority shipper | runtime; test-only | historical/persisted matching | lookup-like display-name predicate |
| `Aviation Sans Frontières` | `wms/print_layouts.py`; print templates/tests; docs | print/PDF institutional text | visible document output | document output only | document output |
| `Aviation Sans Frontières France` | print templates/tests/docs | print/PDF institutional text | visible document output | document output only | document output |
| `ASF` | `asf_wms/settings.py`; `wms/config/installation.py`; `wms/models_domain/catalog.py`; `wms/static/scan/import_templates/products.csv` | SKU prefix default and product import example `ASF-000001` | runtime; export/import-facing; config-backed | newly created product data | generated reference prefix; import example |
| `ASF-000001` | `wms/static/scan/import_templates/products.csv` | product import template example SKU | import-facing template | no direct runtime mutation | import guidance |
| `X-ASF-Integration-Key` | `api/v1/permissions.py` | inbound API integration auth header | runtime; integration-facing | no persisted data directly | inbound integration contract |
| `X-ASF-Source` | `api/v1/views.py` | inbound fallback source header for integration event create | runtime; integration-facing | newly created integration event data | inbound integration contract; persisted payload field |
| `X-ASF-Target` | `api/v1/views.py` | inbound fallback target header for integration event create | runtime; integration-facing | newly created integration event data | inbound integration contract; persisted payload field |
| `X-ASF-Planning-Version` | `wms/views_planning.py` | outbound response header on planning version response | runtime; integration-facing | no persisted data | outbound integration contract |
| `X-ASF-Legacy-Endpoint` | `wms/views_scan_shipments.py` | outbound response header for legacy scan endpoint | runtime; integration-facing | no persisted data | outbound integration contract |
| `X-ASF-Legacy-Sunset` | `wms/views_scan_shipments.py` | outbound response header for legacy scan endpoint | runtime; integration-facing | no persisted data | outbound integration contract |
| `X-ASF-Planning-Helper` | `wms/static/wms/local_document_helper.js`; `wms/static/wms/planning_communications_helper.js` | browser request header to local helper | runtime; integration-facing | no persisted data | internal/local helper contract |
| `ASF-WMS/planning-flight-client` | `wms/planning/flight_providers/airfrance_klm.py` | Air France/KLM HTTP User-Agent | runtime; partner-facing | no persisted data | partner-facing contract |
| `ASF-WMS Billing/1.0` | `wms/billing_exchange_rates.py` | external exchange-rate HTTP User-Agent | runtime; external-facing | no persisted data | outbound external contract |
| `email_asf` | `wms/models_domain/planning.py`; `wms/migrations/0087_communicationdraft_family.py`; planning communication modules | persisted `CommunicationFamily.EMAIL_ASF` value | runtime; migration/historical | both | persisted enum/choice; lookup/filter |
| `Mail ASF interne` | `wms/models_domain/planning.py`; `wms/migrations/0087_communicationdraft_family.py`; legacy planning communication modules | display label for `email_asf` | runtime display; migration/historical | historical display | persisted enum label |
| `ASF interne` | `wms/planning/communication_plan.py`; `wms/planning/legacy_communications.py` | planning communication UI/category label | runtime display | no direct data mutation | display label tied to persisted enum |
| `ASF WMS Planning` | `wms/planning/shipment_updates.py` | default `actor_structure` for planning-created tracking events | runtime | newly created persisted tracking event data | persisted operational actor namespace |
| `Logo ASF` | `templates/print/partials/*.html` | image alt text in print documents | visible document output | document output only | document output |
| `RESP. DOUANE ASF` / `ASF Customs agent` | `templates/print/partials/shipment_note_body.html`; `templates/print/partials/customs_note_body.html` | customs-responsible labels on documents | visible document output | document output only | document output |
| `RESPONSABLE VOL ASF` / `ASF Flight Manager` | `templates/print/partials/shipment_note_body.html` | flight-responsible labels on documents | visible document output | document output only | document output |

## 3. Semantic classification

| Finding | Classification |
|---|---|
| `Contact.asf_id` field name | `technical_field_name` |
| `Contact.asf_id` stored values | `persisted_identifier_namespace`; `lookup_key`; `uniqueness_related_value` |
| `ASF-C-*` generated IDs | `generated_reference_prefix`; `persisted_identifier_namespace`; `uniqueness_related_value` |
| `asf_id` import/export column | `import_export_column_name`; `lookup_key` |
| `id_asf` import column | `import_export_column_name`; `lookup_key` |
| `structure_asf_id` party sync input | `technical_field_name`; `lookup_key`; `ambiguous_requires_decision` |
| `ASF ID` admin/search/email label | `external_communication_label` when in email; display label elsewhere |
| `ID ASF` tracking label/help text | `external_communication_label` |
| `ASF-ORG-ROOT` | `lookup_key`; `default_shipper`; `default_root_organization`; `ambiguous_requires_decision` |
| `Aviation Sans Frontieres` default/priority shipper name | `default_shipper`; `lookup_key`; `visible_document_output` where rendered |
| `Aviation Sans Frontières` / `Aviation Sans Frontières France` in print | `visible_document_output` |
| SKU prefix `ASF` and `ASF-000001` | `generated_reference_prefix`; `import_export_column_name` for product import template guidance |
| `X-ASF-Integration-Key` | `inbound_integration_contract` |
| `X-ASF-Source` / `X-ASF-Target` | `inbound_integration_contract`; persisted payload source/target fallback |
| `X-ASF-Planning-Version` | `outbound_integration_contract` |
| `X-ASF-Legacy-Endpoint` / `X-ASF-Legacy-Sunset` | `outbound_integration_contract` |
| `X-ASF-Planning-Helper` | `outbound_integration_contract`; internal/local helper boundary |
| `ASF-WMS/planning-flight-client` | `partner_facing_contract` |
| `ASF-WMS Billing/1.0` | `outbound_integration_contract`; external-facing but low-coupling unclear |
| `CommunicationFamily.EMAIL_ASF` / `email_asf` | `persisted_enum_or_choice`; `lookup_key` |
| `Mail ASF interne` / `ASF interne` | `persisted_enum_or_choice` display label |
| `ASF WMS Planning` | `persisted_identifier_namespace`; `ambiguous_requires_decision` |
| Print labels containing `ASF` | `visible_document_output` |
| Test-only ASF literals | `test_fixture_or_factory` |
| Historical migration literals | `migration_or_historical_data` |

## 4. Dual-regime vs migration analysis

| Finding | Safe path | Lookup and uniqueness notes |
|---|---|---|
| `Contact.asf_id` field name | `do not change yet` | Renaming the model field is unnecessary for white-label behavior and would create migration/admin/import/export risk. |
| Existing `Contact.asf_id` values | `dual-regime acceptable` | Existing `ASF-C-*` and manual values must continue to resolve by exact lookup. The unique constraint already prevents collisions across old and new namespaces. |
| New generated contact IDs `ASF-C-*` | `dual-regime acceptable` | A later config-backed generator can emit a configured namespace for newly created or newly backfilled missing contacts while preserving old values. Tests must cover collision avoidance and ASF default output. |
| Backfill of missing contact IDs | `dual-regime acceptable` | Backfill touches historical rows missing values. It can use the active generator for missing values, but must not rewrite non-empty values. |
| Admin/search label `ASF ID` | `display-only override` | No lookup change needed; search can still query `asf_id` while the label changes. |
| Tracking UI label `ID ASF` | `display-only override` | Lookup continues through `contact__asf_id__iexact`; only label/copy changes. |
| Tracking recovery email label `ASF ID` | `display-only override` | External communication copy can change separately from field and lookup semantics. It must be tested because recipients see it. |
| Import column `asf_id` | `do not change yet` | Import lookup depends on this column. A future rename requires `legacy alias required`, not replacement. |
| Import column `id_asf` | `legacy alias required` if a new column is introduced | This is already an alias. Removing it could break existing spreadsheets. |
| Export column `asf_id` | `do not change yet` | Export consumers may depend on the header. A future display/export contract change needs a separate export compatibility decision. |
| `structure_asf_id` | `do not change yet` | It maps to `Contact.asf_id` lookups in party sync. Externality is unclear; changing the name would need boundary tracing. |
| `ASF-ORG-ROOT` | `unclear`; `do not change yet` | Runtime lookup depends on a persisted record that is not created in migrations, fixtures, setup scripts, or import workbooks found in this pass. This blocks default shipper configuration. |
| `Aviation Sans Frontieres` default/priority shipper name | `do not change yet` | It is both a fallback display-name anchor and a newly-created public-order `shipper_name`. Changing before `ASF-ORG-ROOT` origin is known risks breaking default shipper resolution. |
| SKU prefix `ASF` | `dual-regime acceptable` already partly implemented | Existing `identity.sku_prefix` controls product SKU generation. This audit should not reuse it for contact references. |
| `X-ASF-Integration-Key` | `legacy alias required`; `do not change yet` | Inbound auth header. Renaming without aliasing would break clients. |
| `X-ASF-Source` / `X-ASF-Target` | `legacy alias required`; `do not change yet` | Inbound headers can populate newly created integration event source/target values. Contract direction and clients need separate validation. |
| `X-ASF-Planning-Version` | `do not change yet`; `unclear` | Outbound header. Client dependency is unknown. |
| `X-ASF-Legacy-Endpoint` / `X-ASF-Legacy-Sunset` | `do not change yet`; `unclear` | Outbound legacy endpoint headers. Client dependency is unknown. |
| `X-ASF-Planning-Helper` | `legacy alias required`; `do not change yet` | Browser-to-local-helper boundary may be versioned independently. |
| `ASF-WMS/planning-flight-client` | `do not change yet`; `unclear` | Partner-facing User-Agent may be whitelisted or logged by Air France/KLM. |
| `ASF-WMS Billing/1.0` | `do not change yet`; `unclear` | External User-Agent. Lower risk than auth headers, but still external. |
| `email_asf` | `display-only override` first; `migration required` only if value semantics change | Persisted enum value is used in filters and historical rows. Do not rename casually. |
| `Mail ASF interne` / `ASF interne` | `display-only override` | Labels can be overridden without changing persisted value. |
| `ASF WMS Planning` actor structure | `dual-regime acceptable` for newly created events; `do not change yet` for PR13a | Existing tracking events should remain historical. New event actor namespace could be configured later if treated as operational namespace. |
| Print/PDF labels containing `ASF` | `do not change yet` for PR13; later `display-only override` or print identity PR | These inform PR14/PR15 and should not expand contact/default shipper implementation. |

## 5. External integration / export risk analysis

| Value | Direction | Assessment |
|---|---|---|
| `asf_id` import column | import | External-facing and potentially contractual. Existing spreadsheets and upload workflows may depend on it. |
| `id_asf` import column | import | External-facing alias. Treat as compatibility surface. |
| `asf_id` export column | export | External-facing and potentially contractual. Consumers may parse this header. |
| `ASF ID` in tracking recovery email | outbound communication | External-facing but informal. Still high visibility because recipients use it to recover access. |
| `ASF ID` in tracking pending-created email | outbound communication | External-facing but informal. It should track the chosen contact identifier display label if changed. |
| `X-ASF-Integration-Key` | inbound API header | Inbound contract. High-risk to rename; legacy alias required if made configurable. |
| `X-ASF-Source` / `X-ASF-Target` | inbound API headers | Inbound contract and source of persisted event data. Needs separate integration-contract PR. |
| `X-ASF-Planning-Version` | outbound response header | Outbound contract. Client dependency is unclear. |
| `X-ASF-Legacy-Endpoint` / `X-ASF-Legacy-Sunset` | outbound response headers | Outbound contract. Client dependency is unclear. |
| `X-ASF-Planning-Helper` | browser-to-local-helper request header | Internal/local helper contract. Because the helper may be external to Django release cadence, aliasing would be needed before renaming. |
| `ASF-WMS/planning-flight-client` | partner-facing outbound User-Agent | Partner-facing contract. Changing could be desirable for white-label identity, but dangerous if partner systems whitelist, filter, or audit by User-Agent. |
| `ASF-WMS Billing/1.0` | external outbound User-Agent | External-facing but likely informal. Still should not change in the first implementation PR. |
| `Aviation Sans Frontieres` in public order shipment creation | internal creation with external document consequences | Newly created shipment/order data can surface externally later. Do not change before default shipper policy is resolved. |
| Print/PDF `ASF` labels | documents sent outside ASF | External-facing and potentially contractual depending on document. Defer to PR14/PR15. |
| `email_asf` | internal persisted enum | Internal-only persisted value, but reports/admin/filtering can depend on it. Keep value stable unless a dedicated migration plan exists. |

## 6. `Contact.asf_id` layered analysis

### Field name

`Contact.asf_id` is a legacy technical field name. It is declared as a unique nullable `CharField` in `contacts/models.py` and introduced by `contacts/migrations/0002_contact_extensions.py`. The audit does not justify renaming it. The next implementation PR should not rename the model field, database column, admin attribute, serializer attribute, or internal lookup field.

Safe path: `do not change yet`.

### Generated value namespace

`contacts/asf_ids.py` generates `ASF-C-{contact_pk:08d}`. `Contact.save()` fills missing values after first save, and `backfill_missing_contact_asf_ids()` fills missing persisted rows without rewriting non-empty values.

Safe path: `dual-regime acceptable`. A later PR can introduce a config-backed generated contact identifier namespace for newly created contacts and for missing-value backfill only. Existing `ASF-C-*` values must remain valid.

### Import/export columns

Contact import accepts `asf_id` and `id_asf`; contact export emits `asf_id`; the static contact import template includes `asf_id`.

Safe path: `do not change yet` in the first implementation PR. A later import/export PR may introduce a new configured or generic column only with `legacy alias required`.

### UI/admin labels

Admin forms and scan filters display `ASF ID`. Tracking contact-role UI displays `ID ASF`.

Safe path: `display-only override`. The next implementation PR can update labels through a dedicated contact identifier label configuration while leaving the field and lookup semantics unchanged.

### Tracking/recovery external labels

`templates/emails/shipment_tracking_access_recovery.txt` sends `ASF ID : {{ identifier }}` to external recipients. `templates/emails/shipment_tracking_pending_created.txt` also sends `ASF ID`. These are not just internal UI labels.

Safe path: `display-only override` with email tests. The label can change, but the identifier value remains `contact.asf_id` and old values remain valid.

### Lookup behavior

Tracking access lookup uses `contact__asf_id__iexact`. Party sync resolves organization contacts through `Contact.objects.filter(asf_id=structure_asf_id)`. Contact import looks up existing contacts by `asf_id`.

Safe path: preserve lookups. New namespaces can coexist because lookup is value-based and uniqueness-protected.

### Uniqueness behavior

`Contact.asf_id` is globally unique. The next implementation PR must preserve this uniqueness and must not create overlapping configured prefixes likely to collide with existing ASF data.

Safe path: `dual-regime acceptable`, with tests for ASF default output and configured new-contact output.

### Backfill behavior

Backfill only fills missing values. It should not rewrite existing values.

Safe path: `dual-regime acceptable`, but tests must prove non-empty `asf_id` values remain untouched.

### What should change next

The first implementation PR may change only:

- generated contact identifier namespace defaults and override path;
- admin/tracking/email display labels for the contact identifier;
- tests proving ASF defaults are unchanged and configured overrides affect only newly generated/missing identifiers and display labels.

### What should not change next

The first implementation PR should not change:

- `Contact.asf_id` field or database column;
- import/export column names;
- party sync field names;
- tracking lookup semantics;
- existing persisted values;
- `ASF-ORG-ROOT`;
- default shipper resolution;
- API headers;
- print/PDF identity.

## 7. `ASF-ORG-ROOT` / default shipper analysis

### What consumes it

`wms/policies/shipment_parties.py` defines `DEFAULT_RECIPIENT_SHIPPER_ASF_ID = "ASF-ORG-ROOT"`. `wms/default_shipper_bindings.py` consumes it to resolve the default recipient shipper:

- first by `ShipmentShipper.organization__asf_id = "ASF-ORG-ROOT"`;
- then by fallback shipper name `Aviation Sans Frontieres`;
- then by `Contact.asf_id = "ASF-ORG-ROOT"`;
- then by fallback organization/contact name.

Recipient account approval and review provisioning call this default shipper resolution before creating default recipient shipper links.

### What creates it or expects it to exist

This pass found runtime consumers and tests, but did not find a creation source for a production `Contact` or organization/shipper party with `asf_id = "ASF-ORG-ROOT"`:

- no migration data found;
- no seed command creation found;
- no fixture creation found outside tests;
- no setup script creation found;
- no import workbook occurrence found in scanned spreadsheet archives;
- tests create the needed records directly.

The current evidence indicates `ASF-ORG-ROOT` behaves as a policy constant and persisted lookup key. It may also encode a root organization and default shipper convention, but the source of truth for creating or maintaining that record is not visible in the repository.

### Root organization, default shipper, or both

The value is ambiguous:

- as `organization__asf_id`, it behaves like a root organization lookup;
- as a resolution path for `ShipmentShipper`, it behaves like a default shipper lookup;
- as `Contact.asf_id`, it behaves like a persisted contact identifier;
- as a test-created value, it behaves like a setup convention.

It should not be collapsed into product branding, organization full name, or sender identity.

### Scope and deployment implications

The value appears organization-scoped through `ShipmentShipper.organization` and contact-scoped through `Contact.asf_id`. It is not tenant-scoped in the current single-codebase model. Changing it could require seed/setup changes, config changes, deployment verification, or data migration/manual data procedure, depending on the missing origin evidence.

### Blocker

Default shipper configuration is blocked.

Missing evidence: where the production `ASF-ORG-ROOT` record is created, whether it exists in ASF production, and whether operations rely on an admin/manual setup convention or historical imported data.

Required investigation before any implementation PR touches default shipper behavior:

1. Run a read-only query against production or a sanitized production copy for `Contact.objects.filter(asf_id="ASF-ORG-ROOT")` and related `ShipmentShipper` rows.
2. Inspect deployment/setup notes or admin operating procedure for creation of the ASF root/default shipper organization.
3. Confirm whether fallback name matching to `Aviation Sans Frontieres` is an intentional compatibility path or a silent recovery path for missing canonical IDs.

Until this is resolved, do not implement configurable default shipper behavior.

## 8. Persisted enum / choice analysis

`CommunicationFamily.EMAIL_ASF` has persisted value `email_asf` and display label `Mail ASF interne`. The migration `wms/migrations/0087_communicationdraft_family.py` records the choice value and label. Runtime logic references the enum/value in:

- planning communication generation;
- communication plan display and ordering;
- legacy communication mapping;
- artifact attachment behavior;
- planning artifact use cases;
- version dashboard openability checks.

Safe path:

- keep the persisted value `email_asf`;
- do not rename `CommunicationFamily.EMAIL_ASF` in a first implementation PR;
- allow only a later `display-only override` for labels if needed;
- require `legacy mapping required` or `migration required` only if a future design changes the underlying family semantics.

Renaming `email_asf` directly would risk historical data, filters, and choice validation. A new enum value would require dual-regime handling and explicit migration/filter behavior. No such need is proven for the first implementation PR.

Similar label values `ASF interne` and `Mail ASF interne` should be treated as display labels tied to the persisted enum and not as general branding strings.

## 9. General risk analysis

First-client data contamination: newly created non-ASF contacts, products, tracking events, shipments, or documents could receive ASF-specific generated IDs, actor names, default shipper names, or document labels if operational namespaces remain hardcoded.

Historical compatibility: existing `ASF-C-*`, manual `asf_id`, `ASF-ORG-ROOT`, `email_asf`, exported `asf_id` columns, and generated documents may need to remain readable indefinitely.

Reference collision: a configured contact identifier namespace must not collide with existing ASF values. The existing unique constraint protects storage, but a poor configured prefix could cause creation failures or confusing mixed data.

Dual-regime complexity: contact identifiers can support dual-regime behavior reasonably because lookups use exact stored values. Default shipper and integration headers cannot be assumed to support the same approach without origin and client-contract evidence.

Migration risk: renaming fields, persisted enum values, import/export columns, or default shipper IDs would require data migration or legacy mapping. None is justified in the first implementation PR.

External integration/export breakage: `X-ASF-*` headers, User-Agent strings, import headers, export headers, and tracking emails can be consumed outside Django. They need targeted compatibility plans.

Document output inconsistency: print/PDF templates currently include ASF-specific document labels. Changing contact or shipper policy without PR14/PR15 coordination could produce inconsistent documents.

Identity confusion: product branding, legal identity, operational namespace, sender identity, shipper identity, root organization identity, and integration contracts are distinct. Existing `identity.*` config should not be reused for operational namespace or default shipper behavior without concrete semantic proof.

ASF production behavior: all defaults in `main` must continue to produce current ASF values until an explicit override is configured for another installation.

## 10. Decision proposal for implementation after PR12

Implementation should be split.

### PR13a: contact identifier namespace and labels

Purpose: configure the generated contact identifier namespace and contact identifier display labels while preserving existing ASF behavior by default.

Likely files to change:

- `wms/config/installation.py`;
- `contacts/asf_ids.py`;
- `contacts/models.py` only if needed to pass config into generation without changing the field;
- `wms/forms_admin_contacts_contact.py`;
- `wms/shipment_tracking_access.py`;
- `templates/scan/includes/admin_contacts_filters_card.html`;
- `templates/scan/shipment_tracking.html`;
- `templates/emails/shipment_tracking_access_recovery.txt`;
- `templates/emails/shipment_tracking_pending_created.txt`;
- focused tests for contact ID generation, backfill, admin/tracking labels, and recovery email copy.

Files/surfaces that must not change:

- `Contact.asf_id` field name or migration;
- contact import/export column names;
- party sync `structure_asf_id`;
- `ASF-ORG-ROOT`;
- default shipper binding logic;
- API headers/User-Agent strings;
- print/PDF templates except tracking email templates listed above.

Tests to add/update:

- ASF default generated contact ID remains `ASF-C-00000001` style;
- configured contact ID namespace affects newly generated IDs only;
- existing `asf_id` values are not rewritten;
- missing-value backfill uses the active generator and preserves non-empty values;
- admin/tracking/recovery labels use the configured label while ASF defaults remain unchanged;
- tracking lookup accepts legacy `ASF-C-*` values.

Acceptance criteria:

- no migration;
- no import/export contract change;
- no default shipper change;
- ASF default behavior identical;
- configured install can generate non-ASF contact references for new contacts;
- recovery email label is configurable or derived from the same contact identifier label.

Rollback considerations:

- reverting code returns to static `ASF-C` generation and labels;
- already-created configured contact IDs remain valid because lookup is stored-value based;
- no data migration rollback is required.

Existing-data vs newly-created-data rule: existing values remain untouched; configured namespace applies only to newly generated or missing backfilled values.

### PR13b: default shipper and `ASF-ORG-ROOT`

Purpose: only after the blocker is resolved, decide whether default shipper/root organization lookup should be configurable.

Likely files to change after investigation:

- `wms/policies/shipment_parties.py`;
- `wms/default_shipper_bindings.py`;
- `wms/admin_account_request_approval.py`;
- `wms/account_request_review_service.py`;
- tests under `wms/tests/portal/` and account request review/approval tests.

Files/surfaces that must not change initially:

- contact identifier generation;
- import/export columns;
- API headers;
- print/PDF templates;
- public order default shipper name, unless the investigation proves it is part of the same policy.

Tests to add/update:

- ASF default still resolves `ASF-ORG-ROOT`;
- fallback name behavior is preserved or deliberately constrained;
- configured default shipper lookup works only after setup data exists;
- missing configured shipper fails with existing safe skip/error behavior.

Acceptance criteria:

- origin of `ASF-ORG-ROOT` is documented;
- existing ASF deployment remains deployable;
- no silent creation of incorrect shipper records;
- existing default shipper links are not rewritten unintentionally.

Rollback considerations:

- revert config consumption while keeping existing shipper data untouched;
- no broad data migration unless explicitly planned.

Existing-data vs newly-created-data rule: existing shipper links and historical shipments remain unchanged; configured default applies only to future provisioning/link creation after setup data is confirmed.

Status: blocked until origin/existence investigation is complete.

### PR13c: integration headers and User-Agent contracts

Purpose: decide whether any `X-ASF-*` headers or `ASF-WMS/*` User-Agent strings should be configurable, aliased, or left unchanged.

Likely files to change:

- `api/v1/permissions.py`;
- `api/v1/views.py`;
- `wms/views_planning.py`;
- `wms/views_scan_shipments.py`;
- `wms/static/wms/local_document_helper.js`;
- `wms/static/wms/planning_communications_helper.js`;
- `wms/planning/flight_providers/airfrance_klm.py`;
- `wms/billing_exchange_rates.py`;
- API/integration tests.

Files/surfaces that must not change:

- contact identifier field/generation;
- default shipper behavior;
- print/PDF templates;
- persisted enum values.

Tests to add/update:

- inbound legacy headers still work;
- any new configurable headers are accepted as aliases, not replacements;
- outbound headers remain stable or are covered by explicit compatibility tests;
- User-Agent changes are isolated and default to current ASF values.

Acceptance criteria:

- contract direction documented for each header;
- no inbound auth breakage;
- no partner-facing User-Agent change without explicit approval;
- defaults preserve ASF behavior.

Rollback considerations:

- retain legacy aliases;
- revert configured outbound names without breaking inbound legacy clients.

Existing-data vs newly-created-data rule: inbound source/target values may affect newly created integration events; existing events remain unchanged.

### Later PR: persisted enum display strategy

Purpose: if white-label planning communication labels need cleanup, override display labels while preserving persisted enum values.

Likely files to change:

- `wms/models_domain/planning.py`;
- `wms/planning/communications.py`;
- `wms/planning/communication_plan.py`;
- `wms/planning/legacy_communications.py`;
- focused planning communication tests.

Files/surfaces that must not change:

- migration `0087` unless a dedicated migration PR is approved;
- persisted value `email_asf` in existing data;
- filters that assume the existing enum value, unless dual-regime support is implemented.

Acceptance criteria:

- persisted `email_asf` still loads and filters correctly;
- display labels can change without data migration;
- ASF defaults keep current labels.

Existing-data vs newly-created-data rule: persisted family values remain unchanged for both old and new rows unless a later migration is explicitly approved.

### PR14/PR15: print/PDF identity safety net and consumers

Purpose: treat document-facing ASF strings as print/PDF identity and operational-role labels, not as contact namespace or default shipper implementation.

Likely files to change:

- `wms/print_layouts.py`;
- `templates/print/partials/*.html`;
- print context tests and snapshot/HTML assertions.

Acceptance criteria:

- document outputs remain ASF by default;
- configured installation output is consistent across labels, institutional names, logos, and role labels;
- shipper/reference values rendered from data remain separate from static document identity.

Existing-data vs newly-created-data rule: generated documents render current data plus configured document identity; persisted shipment/contact values are not rewritten.

## 11. Config contract proposal, only if justified

Only contact identifier configuration is justified for the first implementation PR.

Proposed dedicated section: `references`.

Proposed keys tied to concrete usages:

| Proposed key | Default | Concrete future consumer |
|---|---|---|
| `references.contact_identifier_generated_prefix` | `ASF-C` | `contacts/asf_ids.py::build_generated_asf_id()` |
| `references.contact_identifier_label` | `ASF ID` | `wms/forms_admin_contacts_contact.py`; admin filter placeholder; tracking recovery and pending-created email labels |
| `references.tracking_contact_identifier_label` | `ID ASF` | `wms/shipment_tracking_access.py` contact role label; `templates/scan/shipment_tracking.html` lost-code copy |

`references.contact_identifier_generated_prefix` intentionally keeps `generated` in the key name because `Contact.asf_id` can also hold manually entered or imported values, and the configured prefix applies only to the generated branch. The current ASF defaults differ (`ASF ID` admin/email vs `ID ASF` tracking). PR13a implementation must decide whether to preserve this distinction or merge into a single label, based on whether the difference is intentional or historical.

Rationale: these are operational reference/label values, not product identity, organization full name, sender identity, or portal vocabulary. They should not consume `identity.product_display_name`, `identity.organization_brand_name`, `identity.organization_full_name`, `notifications.email_subject_prefix`, or `vocabulary.portal_partner_label`.

No default shipper config key is proposed in this audit because `ASF-ORG-ROOT` origin/existence is unresolved. No API/header config key is proposed because contract direction and client dependency need a separate integration-contract PR. No import/export column config is proposed because column compatibility requires a separate decision and likely legacy aliases.

## 12. Non-goals

PR12 and the immediate implementation PR(s) should not address:

- scan branding;
- PWA manifest;
- service worker;
- logout redirect;
- logo replacement;
- broad email copy cleanup, except the tracking recovery and pending-created contact identifier labels if handled in PR13a;
- full print/PDF identity implementation, except dependency decisions for PR14/PR15;
- legal/privacy/trust copy;
- portal wording cleanup;
- broad replacement of `ASF`, `Aviation Sans Frontières`, or `Messagerie Médicale`;
- gettext catalogs;
- migrations unless explicitly recommended as a future separate PR;
- API/header renames in PR13a;
- default shipper configuration before `ASF-ORG-ROOT` origin is understood.

## 13. Open questions / blockers

### Blockers for the first implementation PR

No blocker for PR13a contact identifier namespace and labels, provided PR13a does not change imports/exports, field names, default shipper behavior, API headers, persisted enum values, or print/PDF templates.

### Blockers for later PRs

Default shipper behavior is blocked by missing `ASF-ORG-ROOT` origin/existence evidence:

- Does ASF production have `Contact.asf_id = "ASF-ORG-ROOT"`?
- Does a `ShipmentShipper` exist for that contact/organization?
- Was it created manually, through admin setup, through legacy data import, or through a deployment script outside the repository?
- Is fallback name matching to `Aviation Sans Frontieres` intended compatibility or emergency recovery?

Integration/header configuration is blocked by unknown external client dependencies:

- Which clients send `X-ASF-Integration-Key`?
- Do clients send `X-ASF-Source` / `X-ASF-Target`?
- Do clients depend on outbound `X-ASF-Planning-*` or `X-ASF-Legacy-*` headers?
- Are Air France/KLM or other partners sensitive to `ASF-WMS/planning-flight-client`?

Persisted enum changes are blocked unless a later PR proves display-only override is insufficient.

### Nice-to-have clarifications

- Whether exported `asf_id` headers are consumed by external partners or only internal back office workflows.
- Whether `ASF WMS Planning` actor structure is shown to external users or only internal audit views.
- Whether public order default `Aviation Sans Frontieres` should eventually follow default shipper policy or document identity policy.

## 14. Evidence appendix

### `ASF-ORG-ROOT` ambiguity

Why ambiguous: runtime code treats `ASF-ORG-ROOT` as a canonical default shipper/root organization lookup key, but repository search found no production creation path. Tests create it directly, which proves the expected shape but not the operational origin.

Missing evidence: production or sanitized-production data showing whether the record exists, and setup/deployment documentation showing how it is created.

Investigation to resolve: run read-only ORM queries for `Contact.asf_id = "ASF-ORG-ROOT"` and related `ShipmentShipper` rows, then inspect deployment/admin setup notes.

### Default shipper name `Aviation Sans Frontieres`

Why ambiguous: the value is used as a public order default shipper name, priority shipper predicate, and fallback default shipper lookup name. It may be operational shipper identity rather than organization brand or print identity.

Missing evidence: whether the name fallback exists only for legacy data without `ASF-ORG-ROOT`, and whether public orders are expected to use this default for all installations.

Investigation to resolve: trace production default shipper records and public order creation data; confirm whether fallback name resolution is intentional policy.

### `structure_asf_id`

Why ambiguous: the name appears at an application/party sync boundary and maps to `Contact.asf_id`. It may be an internal legacy technical key or an external integration field.

Missing evidence: source payload or caller contract for party sync inputs.

Investigation to resolve: trace all callers and any import/API payloads that construct `structure_asf_id`.

### Import/export `asf_id` / `id_asf`

Why ambiguous: these are operationally named columns and may be used by external spreadsheets, but the current evidence does not identify all consumers.

Missing evidence: which partners or back-office workflows depend on the exact headers.

Investigation to resolve: review sample imports/exports, user documentation, and operational spreadsheet templates before changing column contracts.

### API/header contracts

Why ambiguous: direction is clear for several headers, but client dependency is not.

Missing evidence: deployed API clients, local helper versioning expectations, partner documentation, and logs showing header use.

Investigation to resolve: inspect API access logs/configured integrations and local helper deployment process before any rename or configurable alias rollout.

### Partner-facing User-Agent strings

Why ambiguous: User-Agent values may be informational, monitored, or whitelisted by partners.

Missing evidence: Air France/KLM and exchange-rate provider expectations for User-Agent strings.

Investigation to resolve: check partner integration documentation or logs before changing `ASF-WMS/planning-flight-client` or `ASF-WMS Billing/1.0`.

### `CommunicationFamily.email_asf`

Why ambiguous: `email_asf` encodes ASF-specific wording, but it is also a persisted enum value used by filters and workflow logic.

Missing evidence: whether white-label installations need a different persisted family semantics or only display labels.

Investigation to resolve: inspect planning communication UI requirements for a first non-ASF installation. Until then, keep persisted value stable and treat label cleanup as display-only.

### `ASF WMS Planning`

Why ambiguous: the value is written as `actor_structure` for planning-created shipment tracking events, so it is a persisted operational actor label rather than simple branding. It may appear in internal or external tracking views depending on how tracking events are exposed.

Missing evidence: whether external recipients see this actor structure, and whether it should follow product identity, operational namespace, or a dedicated planning actor configuration.

Investigation to resolve: trace tracking-event rendering surfaces and exported tracking data before changing the value.

### Print/PDF ASF labels

Why ambiguous: some document labels are static identity text, while shipper/reference values rendered in documents may come from persisted shipment/contact data.

Missing evidence: full PR14/PR15 print identity contract, including which labels are legal/institutional identity and which are operational role labels.

Investigation to resolve: audit print templates with document owners during PR14/PR15 and keep static identity separate from persisted shipper/reference data.
