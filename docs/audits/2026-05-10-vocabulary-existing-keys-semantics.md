# Vocabulary Existing Keys Semantics Audit

## 1. Executive summary

`installation.vocabulary` currently declares 6 keys. Only 1 key is currently consumed at runtime: `portal_partner_label`, through the `portal_partner_label` template tag used by the portal shell/account templates. The principal semantic risk across the set is that broad nouns such as `partner_label`, `organization_label`, `shipper_label`, and `recipient_label` look reusable but cross many unrelated ASF surfaces, grammatical forms, and legacy/business meanings, so naive consumption would change visible behavior or collapse distinct concepts.

## 2. Key audit

### 2.1 `organization_label`

#### 2.1.1 Default value

`"organisation"`

#### 2.1.2 Intended meaning (inferred)

Interpretive: the key name suggests a generic label for an organization or structure. `git blame` traces the key to `764136bb feat: add installation configuration foundation`; no narrower runtime surface is implied by the key name itself.

#### 2.1.3 Real UI surfaces

Found by `git grep` on `organisation` / `organisations`:

- Print templates: `templates/print/attestation_aide_humanitaire.html:12`, `templates/print/partials/contact_label_body.html:16`, `:29`, `:42`, `templates/print/partials/customs_note_body.html:87`, `:100`, `:113`, `templates/print/partials/shipment_note_body.html:87`, `:100`, `:113`.
- Scan FAQ and admin templates: `templates/scan/faq.html:97`, `:296`, `:297`, `templates/scan/includes/admin_contacts_contact_form.html:364`, `templates/scan/includes/admin_contacts_correspondents_card.html:13`, `templates/scan/includes/admin_contacts_directory_card.html:14`.
- Python-rendered messages and labels: `wms/forms.py:1188`, `wms/views_scan_admin.py:131`, `wms/print_layouts.py:105`, `:129`, `:138`.
- Tests: `wms/tests/forms/tests_forms.py:1160`, `wms/tests/print/tests_print_renderer.py:99`, `:112`, `wms/tests/views/tests_portal_bootstrap_ui.py:377`, `:389`, `:390`, `:393`.
- Docs-only examples were also found, for example `docs/plans/2026-03-04-admin-contacts-cockpit-org-roles-design.md:11`, `docs/templates/attestation_aide_humanitaire.html:22`.

#### 2.1.4 Conflict with ASF visible wording

The default matches visible ASF wording where exact `organisation` / `Organisation` surfaces were found. Because the key is unconsumed, naive consumption would not obviously contradict the exact default term, but it could still change capitalization or collapse distinct meanings such as contact type, legal entity, print company label, and user-facing structure label.

#### 2.1.5 Grammatical ambiguities

`organisation` is feminine and appears as standalone `Organisation`, plural `Organisations`, and in sentence fragments such as `sans organisation` or `organisation avec rôle`. Article-bearing forms such as `l'organisation` and `de l'organisation` would need morphology beyond a simple noun substitution. A simple template tag could plausibly cover narrow standalone labels, but not the mixed print, FAQ, validation, and sentence-fragment surfaces found here.

#### 2.1.6 Runtime consumption status

Declared but unused as installation vocabulary. `git grep` finds `organization_label` in unrelated runtime data variables in `wms/contact_labels.py`, `wms/print_context.py`, `wms/print_pack_engine.py`, and `wms/shipment_party_snapshot.py`, plus config tests, but no production code path reads `get_installation_config().vocabulary.organization_label`.

#### 2.1.7 Recommendation

**SPLIT** — The concept is real, but the declared key is too broad to consume directly. Future consumption should use narrower surface-specific keys if a concrete label family is identified, because current occurrences span print documents, scan/admin contacts, data labels, and validation text.

### 2.2 `partner_label`

#### 2.2.1 Default value

`"partenaire"`

#### 2.2.2 Intended meaning (inferred)

Interpretive: the key name suggests a generic label for a partner organization or partner contact category. `git blame` traces the key to `764136bb feat: add installation configuration foundation`; later PR5 explicitly kept `portal_partner_label` separate from this broader key.

#### 2.2.3 Real UI surfaces

Found by `git grep` on `partenaire` / `partenaires`:

- Scan/admin contact category surfaces: `contacts/models.py:17`, `wms/forms_admin_contacts_contact.py:18`, `templates/scan/admin_contacts.html:37`, `wms/tests/views/tests_views_scan_admin.py:206`.
- Migrations and fixtures/tests: `contacts/migrations/0011_contactcapability_partner_other.py:21`, `contacts/tests/tests_capabilities.py:61`, `wms/tests/forms/tests_forms_admin_contacts_contact.py:173`, `:196`, `wms/tests/scan/tests_admin_contacts_crud.py:118`, `wms/tests/views/tests_views_scan_admin_contacts_crud.py:139`.
- Docs and policy text: `docs/policies/cgu-portail.md:30`, `docs/policies/droits-des-personnes.md:35`, `docs/policies/mentions-information-formulaires.md:15`, `docs/policies/rgpd.md:54`.
- Portal tests explicitly guard against this wording in the portal shell/account surfaces: `wms/tests/views/tests_portal_bootstrap_ui.py:361`, `:373`.

#### 2.2.4 Conflict with ASF visible wording

The default matches some scan/admin contact category wording (`Partenaire`), but it conflicts with the historical ASF portal wording where the visible label was `association`. This is the PR5 precedent: `partner_label = "partenaire"` existed, but consuming it in portal account/shell labels would have changed `association` to `partenaire`, so PR5 introduced `portal_partner_label = "association"` instead.

#### 2.2.5 Grammatical ambiguities

`partenaire` is grammatically flexible as a noun/adjective, but it still varies by number (`partenaire`, `partenaires`) and by syntactic role (`structure partenaire`, `associations partenaires`, standalone `Partenaire`). It does not carry the same legal/user-facing meaning as `association` on portal surfaces. A simple substitution might work for a narrow contact category label, but not across portal, policy, contact category, and organization relationship surfaces.

#### 2.2.6 Runtime consumption status

Declared and tested, but not consumed in production code paths. `wms/tests/config/tests_installation_config.py:97` asserts the default, and `docs/repo-reference/04-shared-contracts/08-installation-config.md:54` and `:112` document that the broad key should not be used where a narrower label is needed. Other `partner` matches are contact capability runtime concepts, not installation vocabulary consumption.

#### 2.2.7 Recommendation

**SPLIT** — The key is too broad and already proved unsafe for portal consumption. It may remain declared, but runtime code should prefer narrower keys in the style of `portal_partner_label` whenever a specific surface needs configurable wording.

### 2.3 `portal_partner_label`

#### 2.3.1 Default value

`"association"`

#### 2.3.2 Intended meaning (inferred)

Interpretive: the key name suggests the portal-specific noun for the partner/account label family. `git blame` traces it to `6ba55f5b feat: add portal partner vocabulary label`, and the installation-config contract describes it as distinct from broad `partner_label`.

#### 2.3.3 Real UI surfaces

Found by `git grep` on `association` / `associations` and the key name:

- Runtime template-tag consumption: `templates/includes/secondary_shell_masthead.html:63`, `templates/portal/base.html:7`, `templates/portal/includes/account_intro_card.html:2`, `templates/portal/includes/account_profile_card.html:20`, with implementation at `wms/templatetags/wms_vocabulary.py:9` and `:10`.
- Portal templates with exact/default-term surfaces: `templates/portal/dashboard.html:26`, `templates/portal/faq.html:49`, `:90`, `templates/portal/login.html:7`, `:26`, `templates/portal/includes/account_profile_card.html:20`, `:24`, `:25`, `:26`, `:31`, `:35`, `:36`, `:37`.
- Emails: `templates/emails/account_request_admin_notification.txt:3`, `:4`, `templates/emails/account_request_approved.txt:1`, `:8`, `:20`, `templates/emails/order_admin_notification_portal.txt:3`, `templates/emails/order_admin_notification_public.txt:3`, `templates/emails/order_confirmation.txt:1`, `templates/emails/portal_forgot_password.txt:8`.
- Scan and billing templates: `templates/scan/billing_editor.html:13`, `:22`, `:70`, `:145`, `templates/scan/billing_settings.html:13`, `:250`, `:309`, `templates/scan/faq.html:190`, `:193`, `:369`, `:371`, `:409`, `:411`, `:430`, `:511`, `:514`, `:517`, `templates/scan/includes/receive_association_create_card.html:7`, `:39`, `:112`, `:114`, `templates/scan/includes/scan_sidebar_navigation.html:99`.
- Public order/account request templates and JavaScript identifiers: `templates/scan/public_account_request.html:44`, `:60`, `:74`, `:86`, `:95`, `:102`, `:163`, `templates/scan/public_order.html:7`, `:36`, `:63`, `:65`, `:174`, `:181`.
- Print templates: `templates/print/base_a5.html:82`, `templates/print/base_document.html:82`, `templates/print/order_summary.html:39`, `templates/print/partials/customs_note_body.html:9`, `templates/print/partials/donation_certificate_body.html:16`, `:20`, `templates/print/partials/shipment_note_body.html:9`.
- Python/API/model compatibility surfaces and tests also contain many `AssociationProfile`, `AssociationRecipient`, `association_name`, and `association_contact` matches, for example `api/v1/serializers.py:304`, `api/v1/permissions.py:40`, `wms/view_permissions.py:142`, `wms/views_portal_account.py:145`, `:1028`, and `wms/views_portal_orders.py:81`.

#### 2.3.4 Conflict with ASF visible wording

The default matches the current controlled ASF portal wording for the four PR5 runtime consumers. Naively expanding this key outside the narrow portal shell/account family would be unsafe because many other `association` occurrences are legacy model/API names, billing concepts, receipt types, public order fields, legal ASF print text, or sentence fragments.

#### 2.3.5 Grammatical ambiguities

`association` is feminine and appears as standalone `Association`, plural `associations`, and article-bearing forms such as `l'association`, `de l'Association`, and `d'une association`. The current narrow template-tag use can handle the controlled surfaces because it is used as a standalone noun or with `capfirst`. Broader surfaces would require richer morphology and context awareness.

#### 2.3.6 Runtime consumption status

Consumed via template tag. `wms/templatetags/wms_vocabulary.py:9-10` reads `get_installation_config().vocabulary.portal_partner_label`, and the tag is used in four templates: `templates/includes/secondary_shell_masthead.html:63`, `templates/portal/base.html:7`, `templates/portal/includes/account_intro_card.html:2`, and `templates/portal/includes/account_profile_card.html:19-20`. Tests cover the ASF default and runtime override at `wms/tests/views/tests_portal_bootstrap_ui.py:351`, `:368`, `:375`.

#### 2.3.7 Recommendation

**KEEP** — This key is valid as declared for the narrow portal shell/account label family, and its default preserves ASF visible wording. It should remain narrow; other `association` surfaces should not consume it merely because they use the same word.

### 2.4 `volunteer_label`

#### 2.4.1 Default value

`"benevole"`

#### 2.4.2 Intended meaning (inferred)

Interpretive: the key name suggests a generic label for volunteer users or volunteer-facing surfaces. `git blame` traces the key to `764136bb feat: add installation configuration foundation`.

#### 2.4.3 Real UI surfaces

Found by `git grep` on `benevole`, `bénévole`, and plural/case variants:

- Volunteer templates: `templates/benevole/availability_list.html:4`, `templates/benevole/availability_recap.html:34`, `:61`, `templates/benevole/base.html:7`, `templates/benevole/constraints.html:4`, `templates/benevole/dashboard.html:4`, `templates/benevole/login.html:7`, `:28`, `templates/benevole/profile.html:4`, `templates/benevole/request_account.html:4`, `:8`, `templates/benevole/request_account_done.html:9`, `templates/benevole/set_password.html:9`.
- Volunteer emails: `templates/emails/volunteer_access_created.txt:3`, `templates/emails/volunteer_account_approved.txt:3`, `:9`, `templates/emails/volunteer_account_request_confirmation.txt:1`, `templates/emails/volunteer_account_request_received.txt:1`, `templates/emails/volunteer_forgot_password.txt:3`, `:8`.
- Shared shell/home/help: `templates/home.html:227`, `templates/includes/secondary_shell_masthead.html:46`, `:67`, `:77`, `:158`, `templates/includes/secondary_shell_offcanvas.html:109`, `:113`, `templates/password_help.html:82`.
- Planning templates: `templates/planning/_version_header.html:67`, `:72`, `:74`, `templates/planning/_version_planning_block.html:102`, `:183`, `templates/planning/_version_planning_summary_block.html:9`, `:16`, `:38`, `templates/planning/_version_stats_block.html:13`, `templates/planning/_version_unassigned_block.html:62`, `templates/planning/_version_week_view_block.html:9`, `:20`, `:42`.
- Scan/preparateur templates and FAQ: `templates/scan/faq.html:523`, `:525`, `:526`, `:529`, `templates/scan/preparateur_home.html:9`, `:11`, `:18`, `:25`.
- Python-rendered messages and labels: `wms/admin.py:1336`, `:1353`, `:1356`, `:1405`, `:1414`, `wms/forms_admin_contacts_contact.py:20`, `:210`, `wms/forms_planning.py:82`, `wms/pack_handlers.py:417`, `:687`, `wms/shipment_tracking_access.py:129`, `wms/views_volunteer_account_request.py:18`, `:19`, `wms/views_volunteer_auth.py:39`, `:46`, `:54`, `wms/volunteer_access.py:11`, `wms/volunteer_account_request_handlers.py:12`.
- Tests: `wms/tests/config/tests_installation_config.py:99`, `wms/tests/views/tests_views_planning.py:1081`, `:1084`, `:1292`, `wms/tests/views/tests_views_scan_misc.py:63`, `wms/tests/views/tests_views_scan_preparateur.py:107`, `wms/tests/views/tests_views_volunteer.py:65`, `:253`, `wms/tests/views/tests_views_volunteer_account_request.py:16`.

#### 2.4.4 Conflict with ASF visible wording

The default matches some current unaccented surfaces (`Benevole`, `benevole`) but conflicts with other current ASF visible surfaces using `bénévole` / `Bénévole`. Because the key is unconsumed, naive consumption would change visible behavior on accented labels and could also flatten distinct contexts such as volunteer portal, planning assignment, preparateur identity, and email subjects.

#### 2.4.5 Grammatical ambiguities

`bénévole` is used as both noun and adjective, with singular/plural forms and mixed accent/capitalization in current UI. Surfaces include `Portail benevole`, `Demande de compte bénévole`, `Choisir un bénévole`, `Bilan Bénévoles`, and `WhatsApp bénévoles`. A simple substitution would not cover articles, pluralization, accents, capitalization, or the noun/adjective distinction across these surfaces.

#### 2.4.6 Runtime consumption status

Declared and tested, but not consumed as installation vocabulary in production code. `wms/tests/config/tests_installation_config.py:99` asserts the default. Many `volunteer_label` key-name matches are planning snapshot/model/data fields, for example `wms/models_domain/planning.py:300`, `wms/planning/version_dashboard.py:389`, and `templates/planning/_version_planning_block.html:120`; they do not read `installation.vocabulary.volunteer_label`.

#### 2.4.7 Recommendation

**SPLIT** — The volunteer concept is real, but this key is too broad and its default cannot safely cover the current mix of accented, unaccented, plural, adjective, and role-specific surfaces. Future consumption should be surface-specific and preserve existing ASF wording for that surface.

### 2.5 `shipper_label`

#### 2.5.1 Default value

`"expediteur"`

#### 2.5.2 Intended meaning (inferred)

Interpretive: the key name suggests a label for the shipment shipper / expéditeur role. `git blame` traces the key to `764136bb feat: add installation configuration foundation`.

#### 2.5.3 Real UI surfaces

Found by `git grep` on `expediteur`, `expéditeur`, and plural/case variants:

- Emails: `templates/emails/account_request_admin_notification.txt:3`, `templates/emails/account_request_approved.txt:6`, `:18`.
- Portal templates: `templates/portal/faq.html:13`, `:21`, `:41`, `:47`, `:49`, `:99`, `:149`, `templates/portal/recipient_detail.html:28`.
- Planning templates: `templates/planning/_version_planning_summary_block.html:74`, `templates/planning/_version_unassigned_block.html:16`.
- Print templates: `templates/print/attestation_aide_humanitaire.html:15`, `templates/print/feuille_contact.html:60`, `templates/print/partials/contact_label_body.html:14`, `templates/print/partials/customs_note_body.html:85`, `templates/print/partials/shipment_note_body.html:85`.
- Scan templates: `templates/scan/account_validation_list.html:3`, `:9`, `:10`, `templates/scan/contact_roles.html:10`, `templates/scan/contact_validations_hub.html:10`, `:22`, `templates/scan/faq.html:85`, `:86`, `:87`, `:98`, `:100`, `:101`, `:168`, `:181`, `:295`, `:296`, `:323`, `:536`, `:547`, `templates/scan/includes/admin_contacts_shipment_cockpit.html:5`, `:11`, `:39`, `:95`, `:102`, `:118`, `:172`, `:184`, `templates/scan/includes/shipment_create_party_sections.html:6`, `:16`, `:19`, `:21`, `:45`, `templates/scan/order.html:33`, `:45`, `:49`, `templates/scan/order_detail.html:28`, `templates/scan/recipient_needs_view.html:151`, `templates/scan/shipment_batch_create.html:20`, `templates/scan/shipment_batch_summary.html:24`, `templates/scan/shipments_ready.html:33`, `:64`, `templates/scan/shipments_tracking.html:25`.
- Python/API/JavaScript messages and labels: `api/v1/ui_views.py:2313`, `:2342`, `:2350`, `:2458`, `:2607`, `wms/forms.py:583`, `:977`, `:1170`, `:1304`, `:1313`, `:1329`, `:1566`, `:1570`, `wms/forms_admin_contacts_contact.py:13`, `wms/models_domain/portal.py:137`, `:258`, `:684`, `wms/models_domain/shipment.py:239`, `:447`, `wms/models_domain/shipment_parties.py:76`, `:78`, `:82`, `:88`, `:91`, `:93`, `wms/scan_shipment_handlers.py:182`, `:185`, `:194`, `:486`, `wms/shipment_party_rules.py:27`, `:28`, `:29`, `:32`, `wms/static/scan/scan.js:3222`, `:3225`.
- Tests: `wms/tests/views/tests_portal_bootstrap_ui.py:471`, `:1146`, `wms/tests/views/tests_scan_bootstrap_ui.py:572`, `:1747`, `wms/tests/views/tests_views_scan_account_validations.py:81`, `wms/tests/views/tests_views_scan_admin_shipment_parties.py:139`, `wms/tests/views/tests_views_scan_shipments.py:1036`, `:2421`, `:2550`.

#### 2.5.4 Conflict with ASF visible wording

The default matches some ASCII legacy surfaces (`Expediteur`, `expediteur`) but conflicts with many current visible ASF labels that use `Expéditeur`, `expéditeur`, `Expéditeurs`, or uppercase `EXPEDITEUR`. Because the key is unconsumed, naive consumption would change accents, capitalization, and sometimes the role context.

#### 2.5.5 Grammatical ambiguities

`expéditeur` is masculine in common UI use and appears as singular, plural, lower case, title case, uppercase print block title, role adjective, and in combined phrases such as `expéditeur/destinataire` or `l'expéditeur`. It also appears in legacy planning names such as `BE_Expediteur`. A simple substitution is not adequate across portal, scan, planning, print, API, and JavaScript surfaces.

#### 2.5.6 Runtime consumption status

Declared but unused as installation vocabulary. `git grep` finds unrelated `shipper_label` local variables and row keys, for example `templates/scan/recipient_needs_view.html:208`, `wms/application/scan/recipient_needs_queries.py:73`, `:165`, `:307`, and `wms/views_scan_shipments.py:333`, but no production code reads `get_installation_config().vocabulary.shipper_label`. The config field is present in tests at `wms/tests/config/tests_installation_config.py:42` and `:279`.

#### 2.5.7 Recommendation

**SPLIT** — The shipper concept is real and heavily used, but the key is too broad for direct runtime consumption. Existing ASF wording varies by surface, grammar, accenting, and print/API context, so any future consumption needs narrower contracts with surface-appropriate defaults.

### 2.6 `recipient_label`

#### 2.6.1 Default value

`"destinataire"`

#### 2.6.2 Intended meaning (inferred)

Interpretive: the key name suggests a label for the shipment recipient / destinataire role. `git blame` traces the key to `764136bb feat: add installation configuration foundation`.

#### 2.6.3 Real UI surfaces

Found by `git grep` on `destinataire` / `destinataires`:

- Emails: `templates/emails/account_request_admin_notification.txt:3`, `templates/emails/account_request_approved.txt:4`, `:16`.
- Shared shell and planning templates: `templates/includes/secondary_shell_masthead.html:61`, `:203`, `templates/includes/secondary_shell_offcanvas.html:80`, `templates/planning/_version_communications_block.html:162`, `:260`, `templates/planning/_version_planning_summary_block.html:75`, `templates/planning/_version_unassigned_block.html:17`.
- Portal templates: `templates/portal/dashboard.html:45`, `:50`, `templates/portal/faq.html:13`, `:19`, `:41`, `:49`, `:61`, `:66`, `:70`, `:78`, `:79`, `:85`, `:86`, `:117`, `:119`, `:123`, `templates/portal/includes/order_create_review_card.html:28`, `templates/portal/includes/order_create_routing_card.html:17`, `:47`, `:57`, `:60`, `templates/portal/order_detail.html:16`, `templates/portal/recipient_detail.html:8`, `:18`, `:28`, `:41`, `:212`, `templates/portal/recipient_profile.html:9`, `templates/portal/recipient_scope_home.html:4`, `:10`, `:49`, `templates/portal/recipients.html:4`, `:16`, `:35`, `:76`, `:81`, `:206`, `:341`.
- Print templates: `templates/print/attestation_aide_humanitaire.html:16`, `templates/print/blocks/contacts_row.html:29`, `templates/print/feuille_contact.html:76`, `templates/print/partials/contact_label_body.html:27`, `templates/print/partials/customs_note_body.html:98`, `templates/print/partials/packing_list_shipment_body.html:19`, `templates/print/partials/shipment_note_body.html:98`.
- Scan templates: `templates/scan/admin_product_detail.html:197`, `templates/scan/admin_recipient_organization_detail.html:4`, `:12`, `templates/scan/contact_roles.html:10`, `templates/scan/contact_validations_hub.html:10`, `:38`, `:41`, `templates/scan/faq.html:85`, `:87`, `:98`, `:101`, `:168`, `:181`, `:194`, `:295`, `:297`, `:323`, `:474`, `:475`, `:515`, `:516`, `:536`, `:547`, `templates/scan/includes/account_validation_request_summary.html:28`, `templates/scan/includes/admin_contacts_contact_form.html:424`, `templates/scan/includes/admin_contacts_shipment_cockpit.html:5`, `:51`, `:83`, `:95`, `:103`, `:118`, `:170`, `:172`, `:184`, `:227`, `:240`, `:267`, `templates/scan/includes/public_account_request_association_fields.html:99`, `:101`, `:113`, `:130`, `:159`, `:196`, `:200`, `:202`, `:206`, `templates/scan/includes/shipment_create_party_sections.html:31`, `:41`, `:45`, `:71`, `templates/scan/order.html:37`, `:54`, `:58`, `templates/scan/order_detail.html:35`, `templates/scan/orders_view.html:24`, `templates/scan/recipient_needs_view.html:18`, `:37`, `:39`, `:150`, `templates/scan/recipient_validation_detail.html:4`, `:11`, `:232`, `templates/scan/recipient_validation_list.html:3`, `:9`, `:10`, `:48`, `templates/scan/shipment_batch_create.html:21`, `templates/scan/shipment_batch_summary.html:25`, `templates/scan/shipment_tracking.html:286`, `templates/scan/shipments_ready.html:33`, `:65`, `templates/scan/shipments_tracking.html:25`.
- Python/API/JavaScript messages and labels: `api/v1/ui_views.py:657`, `:2190`, `:2192`, `:2200`, `:2202`, `:2429`, `:2447`, `:2473`, `:2530`, `:2564`, `:2587`, `:2645`, `wms/account_request_handlers.py:50`, `:51`, `:52`, `:53`, `:54`, `:56`, `:59`, `:61`, `wms/application/portal/onboarding.py:27`, `:28`, `:32`, `:36`, `:41`, `:48`, `:57`, `:60`, `:61`, `:62`, `:104`, `:218`, `wms/forms.py:981`, `:1171`, `:1329`, `:1567`, `:1575`, `wms/forms_admin_contacts_contact.py:14`, `wms/views_portal_account.py:97`, `:98`, `:130`, `:134`, `:141`, `:143`, `wms/views_portal_auth.py:222`, `:234`, `wms/views_portal_orders.py:74`, `:78`, `:82`, `wms/views_scan_stock.py:175`.
- Tests: `wms/tests/config/tests_installation_config.py:43`, `:280`, `wms/tests/views/tests_portal_bootstrap_ui.py:472`, `:534`, `:597`, `:624`, `:808`, `:1147`, `wms/tests/views/tests_scan_bootstrap_ui.py:650`, `:1748`, `wms/tests/views/tests_views_portal.py:619`, `:1334`, `:1703`, `:2770`, `:3616`, `:4205`, `wms/tests/views/tests_views_scan_admin.py:441`, `wms/tests/views/tests_views_scan_contact_validations.py:211`, `:227`, `:241`.

#### 2.6.4 Conflict with ASF visible wording

The default matches common current ASF visible wording for the recipient concept. Because the key is unconsumed, naive consumption would still risk changing behavior by flattening context-specific labels such as `Structure destinataire`, `Fiche destinataire`, `Destinataire (contact)`, `BE_Destinataire`, all-caps print headings, and sentence fragments.

#### 2.6.5 Grammatical ambiguities

`destinataire` appears as singular, plural, standalone title, role adjective, uppercase print heading, and in article-bearing fragments such as `d'un destinataire`, `du destinataire`, and `au destinataire`. It also appears in compound labels with `expéditeur`, `correspondant`, `BE_`, and portal scope wording. A simple substitution might work for a narrow standalone field label, but not across the surfaces found.

#### 2.6.6 Runtime consumption status

Declared but unused as installation vocabulary. `git grep` finds many unrelated `recipient_label` fields in planning, portal, and tests, for example `templates/planning/_version_communications_block.html:180`, `wms/models_domain/planning.py:538`, `wms/planning/version_dashboard.py:179`, `:562`, `wms/views_portal_orders.py:691`, and `:720`, but no production code reads `get_installation_config().vocabulary.recipient_label`. The config field is present in tests at `wms/tests/config/tests_installation_config.py:43` and `:280`.

#### 2.6.7 Recommendation

**SPLIT** — The default is broadly coherent with ASF wording, but the key is too broad to consume directly. Future runtime usage should use narrower contracts tied to a specific surface and grammatical role.

## 3. Synthesis table

| key | default | consumed | recommendation |
|---|---|---:|---|
| `organization_label` | `"organisation"` | no | **SPLIT** |
| `partner_label` | `"partenaire"` | no | **SPLIT** |
| `portal_partner_label` | `"association"` | yes, via template tag | **KEEP** |
| `volunteer_label` | `"benevole"` | no | **SPLIT** |
| `shipper_label` | `"expediteur"` | no | **SPLIT** |
| `recipient_label` | `"destinataire"` | no | **SPLIT** |

## 4. Open questions

- Should the broad `partenaire` surfaces be audited before deciding whether `partner_label` should remain unused outside contact category contexts?
- Is `organization_label` meant to describe a contact/entity type, a user-facing structure field, or an installation identity concept related to `installation.identity.*`?
- Which concepts need article-aware, gender-aware, plural-aware, or accent-preserving vocabulary handling before any runtime consumption?
- Which existing ASCII labels are intentional legacy compatibility wording, and which are merely historical accent drift?
- Should print, email, portal, scan, planning, and API-visible messages each get separate vocabulary decisions rather than sharing broad role nouns?

## 5. Appendix - reproducibility

    # Key: organization_label
    git grep -n "organization_label" -- '*.py' '*.html' '*.js' '*.md' '*.txt'
    git grep -n -i -E "organisations?" -- '*.py' '*.html' '*.js' '*.md' '*.txt'
    git grep -n -i -E "organisations?" -- templates wms api contacts

    # Key: partner_label
    git grep -n "partner_label" -- '*.py' '*.html' '*.js' '*.md' '*.txt'
    git grep -n -i -E "partenaires?" -- '*.py' '*.html' '*.js' '*.md' '*.txt'
    git grep -n -i -E "partenaires?" -- templates wms api contacts

    # Key: portal_partner_label
    git grep -n "portal_partner_label" -- '*.py' '*.html' '*.js' '*.md' '*.txt'
    git grep -n -i -E "associations?" -- '*.py' '*.html' '*.js' '*.md' '*.txt'
    git grep -n -i -E "associations?" -- templates wms api contacts
    git grep -n -i -E "associations?" -- templates

    # Key: volunteer_label
    git grep -n "volunteer_label" -- '*.py' '*.html' '*.js' '*.md' '*.txt'
    git grep -n -i -E "b[eé]n[eé]voles?" -- '*.py' '*.html' '*.js' '*.md' '*.txt'
    git grep -n -i -E "b[eé]n[eé]voles?" -- templates wms api contacts
    git grep -n -i -E "b[eé]n[eé]voles?" -- templates

    # Key: shipper_label
    git grep -n "shipper_label" -- '*.py' '*.html' '*.js' '*.md' '*.txt'
    git grep -n -i -E "exp[eé]diteurs?" -- '*.py' '*.html' '*.js' '*.md' '*.txt'
    git grep -n -i -E "exp[eé]diteurs?" -- templates wms api contacts
    git grep -n -i -E "exp[eé]diteurs?" -- templates

    # Key: recipient_label
    git grep -n "recipient_label" -- '*.py' '*.html' '*.js' '*.md' '*.txt'
    git grep -n -i -E "destinataires?" -- '*.py' '*.html' '*.js' '*.md' '*.txt'
    git grep -n -i -E "destinataires?" -- templates wms api contacts
    git grep -n -i -E "destinataires?" -- templates
