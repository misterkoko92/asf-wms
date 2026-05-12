# First-client identity contract decision audit

Date: 2026-05-12
Branch: `audit/first-client-identity-contract`
Base: `main` at `f88fbe763a3a2d58e635147bf7ea787eddfa200d`
Change classification: B. Generic reusable capability and C. organization configuration, constrained by A. ASF operational continuity.

## 1. Executive decision

The first-client contract must split identity by semantic layer before any more runtime consumers are added. ASF defaults may keep pointing several layers at the same real-world ASF values, but the contract must not collapse legal organization identity, operational brand, product display name, email sender identity, reply routing, print issuer identity, signatory context, shipper identity, privacy contact, security contact, and platform-operator attribution into one generic organization or contact key.

`installation.identity.organization_full_name`, `installation.notifications.email_sender_name`, and `installation.notifications.email_subject_prefix` remain valid only inside their current or narrow future boundaries. `installation.identity.application_display_name`, `organization_short_name`, `contact_email`, and `contact_reference_prefix` must not be consumed broadly. Sender email and reply-to remain deployment/email-provider concerns until domain authentication, mailbox ownership, and privacy routing are confirmed.

For PR11, the shell/site contract should use a renamed product display field plus a separate brand/operational name. For PR15, print/PDF work needs document-scoped issuer and legal-detail boundaries, not generic organization replacement. For PR16, external communications must consume public support, privacy/RGPD, security, sender-display, subject-prefix, and optional platform-attribution policies without changing SMTP/Brevo sender domains casually.

## 2. Semantic identity boundaries

| Layer | Definition | Why it must not collapse | ASF default co-pointing allowed |
|---|---|---|---|
| Legal organization identity | The legal person or entity responsible for legal, regulatory, and official publication surfaces. | A legal entity is not necessarily the visible app brand, email sender display, default shipper, or print signatory. | May point to Aviation Sans Frontieres for ASF legal, print issuer, legal page, and data-controller defaults, while remaining separate keys or policies. |
| Operational / brand identity | The human-facing organization or service brand shown to users in operational shells and partner-facing copy. | A brand name can differ from the legal entity, product name, sender display name, or shipper name. | May point to Aviation Sans Frontieres or ASF/Messagerie Medicale wording where current ASF surfaces do so, but must stay separate from legal and product fields. |
| Product / application display identity | The visible name of the software/application surface, such as browser titles, home/shell names, and PWA names. | Product identity is not the operating organization, legal publisher, support mailbox, or email subject prefix. | May point to `ASF WMS` for ASF visible app surfaces, while staying distinct from `ASF-WMS` technical identifiers and notification fields. |
| Shipper transport identity | The operational party selected as shipper in shipment creation, planning, labels, and transport coordination. | A transport shipper can be a client, branch, partner, or root party and is not automatically the software operator or legal publisher. | May point to Aviation Sans Frontieres for current ASF default shipper behavior, while PR12 keeps the key/policy distinct from organization identity. |
| Shipper customs / legal identity | The party identity used where customs, donation, or transport paperwork requires the legally responsible shipper. | Customs/legal shipper truth can differ from display shipper, product brand, and platform operator attribution. | May point to Aviation Sans Frontieres for current ASF paperwork defaults, while remaining document/party-scoped. |
| Public support contact | The mailbox and optional phone that public or partner users should use for operational help. | Support contact is not necessarily privacy/RGPD, security, reply-to, legal contact, or sender email. | May point to the current MessMed support address and phone lines for ASF defaults, while remaining separate from email transport settings. |
| Privacy / RGPD / DPO contact | The official channel for data-subject rights, privacy questions, and DPO/RGPD escalation. | Privacy rights requests require a controlled channel and owner; routing them through support, reply-to, or sender email can leak or lose sensitive requests. | May point to the same ASF mailbox as support only if ASF confirms it, but the contract must keep it as a distinct field/policy. |
| Security contact | The official channel for vulnerability, incident, or abuse reports. | Security reports require triage ownership and should not be mixed with support, privacy, legal, or reply-to mailboxes. | May point to the same ASF mailbox as support only if ASF confirms it, but the field must remain distinct. |
| Email sender identity | The display name and authenticated From address used by transactional email transports. | Sender display name, sender email/domain, and deliverability configuration have separate risks; display-name branding must not imply domain authentication is solved. | `email_sender_name` may remain `ASF WMS`; sender email may remain current `DEFAULT_FROM_EMAIL`/`BREVO_SENDER_EMAIL` deployment values. |
| Email reply-to identity | The mailbox where replies to transactional emails are routed. | Reply routing controls operational and personal-data flow and can differ from sender email, support, privacy, or security contact. | May point to an ASF operational mailbox when configured, but it remains a deployment/provider policy until PR16 or a mail-ops PR decides otherwise. |
| Print / PDF issuing identity | The organization or branch shown as the issuer of generated documents, footers, certificates, notes, and labels. | Document issuer identity carries trust and regulatory weight and is not always the shell brand, product name, sender identity, or shipper selector. | May point to Aviation Sans Frontieres/Messagerie Medicale for ASF print defaults, while distinct from product and email identities. |
| Print / PDF signatory identity | The named signer, role/title, and document-specific authority statement used on signed or attested documents. | Signatory context is document content with legal/operational meaning, not a reusable global organization identity field. | May keep the current ASF signatory and association mentions where templates already require them, but the mechanism must be document-scoped in PR14/PR15. |
| Platform-operator attribution | A policy for whether first-client surfaces disclose ASF as technical/platform operator, such as "powered by ASF". | Operator attribution is a commercial/partnership/trust decision and is not implied by product, legal, shipper, or print issuer identity. | May be absent or ASF-visible for current ASF production; first-client display is deferred until ASF and the client decide the relationship. |
| Reference namespace identity | The namespace used in generated product, contact, shipper, and integration identifiers. | Identifier namespaces affect persistent data and external references; they must not reuse organization short name or brand by accident. | `sku_prefix` may remain `ASF` for products; contact/root shipper namespaces stay PR12-owned and distinct. |

## 3. Non-goals and scope boundaries

This PR does not implement runtime consumers, change configuration defaults, edit templates, add tests, update translations, modify migrations, or draft legal content. It does not re-inventory ASF string surfaces already covered by PR9, and it does not reopen PR7 decisions.

Legal content remains out of scope. This audit defines technical contract boundaries for legal identity, contact, print issuer, and trust surfaces, but legal counsel or authorized ASF stakeholders must validate any published legal text.

Reference namespace and default shipper mechanics remain PR12/PR13 scope. PR10 only states the identity boundary and the risk of collapsing shipper identity into general organization identity.

## 4. Evidence reviewed (with explicit references to PR9 sections)

- PR9 §4.1 Visual branding - scan, portal, volunteer, planning, home, and PWA shell identity remain ASF/MessMed-facing and need PR11.
- PR9 §4.2 Application naming - `application_display_name` defaults to `ASF-WMS`, while visible surfaces and notification defaults often use `ASF WMS`.
- PR9 §4.4 Emails and notifications - PR2/PR3 seams exist, producer subjects/bodies still contain ASF wording, and sender/reply-to routing requires decision.
- PR9 §4.5 PDF / print / exports - print/PDF documents embed ASF logos, MessMed contacts, public-interest association wording, signatory context, and Air France/customs wording.
- PR9 §4.10 URLs, domains, and external links - scan logout and deployment/domain examples still include ASF/MessMed assumptions.
- PR9 §4.11 Legal, privacy, and trust surfaces - policy drafts are placeholders requiring legal/RGPD validation.
- PR9 §4.12 Installation/onboarding/configuration - installation config has narrow consumers, but most identity keys remain unconsumed.
- PR9 §4.16 Seed data, fixtures, and initial database assumptions - `ASF-C`, `ASF ID`, `ASF-ORG-ROOT`, and `Aviation Sans Frontieres` default shipper behavior can pollute first-client data.
- PR7 audit `docs/audits/2026-05-11-identity-existing-keys-semantics.md` - existing identity-key decisions remain in force: `organization_full_name` KEEP, `organization_short_name` SPLIT, `application_display_name` RENAME, `contact_email` SPLIT, `sku_prefix` KEEP, `contact_reference_prefix` SPLIT.
- `docs/repo-reference/04-shared-contracts/08-installation-config.md` - `notifications.email_subject_prefix` is explicitly not the canonical app name, and `email_sender_name` is Brevo-display-only while SMTP remains `DEFAULT_FROM_EMAIL`.
- `wms/emailing.py::format_email_subject(...)` - new evidence beyond PR9: subject prefix is applied centrally in `send_email_safe`, so central ownership is technically enforceable.
- `rg "ASF WMS -"` in `wms/` - new evidence beyond PR9: many producers still include literal producer-level prefixes, so PR16 must clean producers after the ownership decision.
- `wms/emailing.py::_brevo_settings()` - new evidence beyond PR9: Brevo sender email and reply-to are still deployment/provider settings, not installation identity fields.
- `asf_wms/settings.py` - new evidence beyond PR9: `ORG_ADDRESS`, `ORG_CONTACT`, and `ORG_SIGNATORY` exist as settings for some print context, but they are not installation identity contract fields.
- `docs/policies/mentions-legales.md`, `docs/policies/confidentialite.md`, `docs/policies/cgu-portail.md` - new evidence beyond PR9: legal/support/RGPD/security contacts are placeholders, including optional phone on legal surfaces.

## 5. Existing identity / contact / config keys

`installation.identity.organization_full_name` is kept as a narrow long organization-name declaration. It may feed future legal/issuer/brand decisions only when the consumer needs exactly that semantic value and tests preserve current ASF output.

`installation.identity.organization_short_name` remains unsafe as a broad source. It must split because `ASF` currently means organization abbreviation, validation actor, stock/source wording, contact/reference namespace, product SKU prefix, integration namespace, and document signature label.

`installation.identity.application_display_name` must be renamed before visible shell consumption. Its default `ASF-WMS` does not match current visible `ASF WMS` surfaces and would not preserve current ASF behavior exactly.

`installation.identity.contact_email` must split. Its current resolution mixes `ORG_CONTACT`, `BREVO_REPLY_TO_EMAIL`, `BREVO_SENDER_EMAIL`, and `DEFAULT_FROM_EMAIL`, which crosses public support, privacy, security, reply routing, sender identity, and legal contact boundaries.

`installation.identity.sku_prefix` is kept and already has a narrow runtime consumer after PR8 for product SKU generation. It is not a general organization or reference namespace key.

`installation.identity.contact_reference_prefix` must split and remains PR12-owned. It cannot safely cover generated contact IDs, labels such as `ASF ID`, root shipper IDs, and SKU prefixes at once.

`installation.notifications.email_subject_prefix` is kept. Its owner is `send_email_safe`/`format_email_subject`, not individual producers.

`installation.notifications.email_sender_name` is kept. Its owner is the Brevo sender display-name path only, not SMTP From, sender email, reply-to, or legal/brand identity.

`ORG_NAME`, `ORG_ADDRESS`, `ORG_CONTACT`, and `ORG_SIGNATORY` exist as settings used by some document context, but they are not sufficient as the first-client contract because they do not distinguish legal, print issuer, contact, and signatory layers.

## 6. Application and shell identity

Item 1 - Application display name.

- Surfaces: PR9 §4.1 Visual branding and §4.2 Application naming.
- Existing key status: `installation.identity.application_display_name` is unsafe as-is because its default is `ASF-WMS`, while visible UI and notifications use `ASF WMS`.
- Classification: `RENAME_EXISTING_KEY`.
- Proposed field: `installation.identity.product_display_name`.
- Semantic meaning: user-facing software/product name for browser titles, app shells, and PWA display where the app is named rather than the operating organization.
- Allowed consumers: PR11 shell/site surfaces such as home title/header, planning header, portal/volunteer shell where the product name is required, and PWA name if PR11 chooses a safe static/dynamic path.
- Forbidden consumers: legal organization, public support, email sender email, reply-to, print issuer, print signatory, shipper identity, API header namespace, and reference prefixes.
- ASF default behavior: preserve existing visible `ASF WMS` where current shell surfaces show it; do not force `ASF-WMS` onto visible UI.
- First-client override expectation: `<FIRST_CLIENT>` deployment must choose a product display name before PR11 consumes this value.
- Consumer PR: PR11.
- Risk level: P1.
- Risk if wrongly consumed: P1 for shell inconsistency, P0 if it appears on legal/print/trust surfaces as the responsible organization.

Item 3 - Organization short / brand / operational name.

- Surfaces: PR9 §4.1 Visual branding, §4.3 Vocabulary and domain labels, and §4.7 Staff scan / warehouse workflows.
- Existing key status: `organization_short_name` is unsafe because `ASF` has many unrelated meanings.
- Classification: `SPLIT_EXISTING_KEY`.
- Proposed field: `installation.identity.organization_brand_name`.
- Semantic meaning: visible operating brand or organization/service name shown to users when the surface is naming the operator, not the product.
- Allowed consumers: narrow PR11 shell/masthead copy where current surfaces show `Aviation Sans Frontieres`, `Aviation Sans Frontieres France`, or MessMed branch identity.
- Forbidden consumers: product name, email subject prefix, sender email, reply-to, reference IDs, API headers, legal details, print signatory, shipper selector, stock/source labels, and broad vocabulary labels.
- ASF default behavior: preserve each current ASF shell wording exactly until PR11 maps which display string belongs to brand versus product.
- First-client override expectation: `<FIRST_CLIENT>` brand/operator display if the client is the visible operator; otherwise an explicitly approved operator brand.
- Consumer PR: PR11.
- Risk level: P1.
- Risk if wrongly consumed: P1/P0 depending on surface; broad use can change workflow labels or legal attribution without review.

## 7. Organization and legal identity

Item 2 - Organization legal identity: legal name, legal form, registration number, registered address.

- Surfaces: PR9 §4.5 PDF / print / exports and §4.11 Legal, privacy, and trust surfaces.
- Existing key status: `organization_full_name` is safe only as a narrow long organization name; legal form, registration number, and registered address are not installation identity fields today. `ORG_ADDRESS` exists as a setting for some document context, but it is not a full legal contract.
- Classification: `KEEP_EXISTING_KEY` for legal/long name, `ADD_NEW_KEY` for legal form, registration number, and registered address.
- Proposed fields: `installation.identity.organization_full_name`; `installation.legal.organization_legal_form`; `installation.legal.organization_registration_number`; `installation.legal.organization_registered_address`.
- Semantic meaning: the legal/official organization details required by legal pages or official document issuer details, without drafting the legal text itself.
- Allowed consumers: legal-page identity, print/PDF issuer legal details, and document context where the document is naming the responsible legal entity.
- Forbidden consumers: generic shell product names, email subject prefix, email sender email, reply-to, public support, privacy/security contacts, shipper display names, root shipper IDs, and broad portal copy.
- ASF default behavior: preserve current ASF legal/document output until PR15 or a legal publication PR replaces hardcoded legal details with validated defaults.
- First-client override expectation: `<FIRST_CLIENT>` legal entity details are TBD and must be supplied by the first-client stakeholder/legal counsel before external portal or official print use.
- Consumer PR: PR15 for print/PDF issuer details; a later legal-publication PR for public legal pages if exposed.
- Risk level: P0.
- Risk if wrongly consumed: P0 on legal/print/trust surfaces because the wrong entity can be presented as publisher, issuer, or data controller.

Item 15 - Legal page identity.

- Surfaces: PR9 §4.11 Legal, privacy, and trust surfaces.
- Existing key status: current policy docs are drafts with placeholders and are not a runtime legal-page contract.
- Classification: `ADD_NEW_KEY`.
- Proposed field or policy: `installation.legal.service_editor_identity`.
- Semantic meaning: the entity presented as editor/responsible publisher of public legal pages.
- Allowed consumers: future legal page publication route and legal-page metadata only.
- Forbidden consumers: shell branding, email sender identity, reply-to, print signatory, shipper identity, and producer email copy.
- ASF default behavior: current ASF production remains unchanged because these docs are not published runtime surfaces by this PR.
- First-client override expectation: `<FIRST_CLIENT>` must confirm whether it, ASF, or another entity is the service editor before external users are exposed.
- Consumer PR: later legal/trust publication PR; PR16 may reference the decision but must not draft legal text.
- Risk level: P0.
- Risk if wrongly consumed: P0 when external users see the wrong legal publisher or responsible entity.

## 8. Contact identity

Item 4 - Public support contact: email and optional phone.

- Surfaces: PR9 §4.5 PDF / print / exports, §4.11 Legal, privacy, and trust surfaces, and §4.12 Installation/onboarding/configuration.
- Existing key status: `contact_email` is overloaded and unsafe; phone values exist only as hardcoded print/legal placeholders, not as an installation contract.
- Classification: `SPLIT_EXISTING_KEY` for email; `ADD_NEW_KEY` for optional phone.
- Proposed fields: `installation.contacts.public_support_email`; `installation.contacts.public_support_phone`.
- Semantic meaning: the operational help channel that public users, portal users, and partners should use for ordinary support questions.
- Allowed consumers: PR16 external email/body support copy, portal trust/help copy, and PR15 print contact lines when the line is operational support rather than legal issuer details.
- Forbidden consumers: privacy/RGPD, DPO, security, sender email, reply-to, legal-page editor identity, print signatory, and shipper identity.
- ASF default behavior: preserve current MessMed support email and existing visible phone lines where they already appear until PR15/PR16 introduce narrow consumers.
- First-client override expectation: `<FIRST_CLIENT>` must provide a monitored support mailbox; phone remains optional and can be blank unless a surface requires it.
- Consumer PR: PR15 for print contact lines; PR16 for external communications and portal support copy.
- Risk level: P1.
- Risk if wrongly consumed: P1/P0; replies and sensitive requests can be sent to an unmonitored or wrong mailbox, and print trust can be damaged.

Item 5 - Privacy / RGPD / DPO contact.

- Surfaces: PR9 §4.11 Legal, privacy, and trust surfaces.
- Existing key status: `contact_email` is insufficient; policy drafts require a distinct RGPD/DPO contact and owner.
- Classification: `SPLIT_EXISTING_KEY`.
- Proposed field: `installation.contacts.privacy_contact_email`.
- Semantic meaning: official mailbox for data-subject rights, privacy questions, and RGPD/DPO escalation.
- Allowed consumers: future privacy page, legal page contact block, RGPD request instructions, and PR16 if external copy needs to direct privacy requests.
- Forbidden consumers: transactional reply-to, sender email, public support unless explicitly cross-posted, security, print signatory, shipper identity, and shell branding.
- ASF default behavior: may point to the current ASF contact only after ASF confirms the mailbox is appropriate; otherwise keep existing unpublished placeholders untouched.
- First-client override expectation: `<FIRST_CLIENT>` or legal counsel must provide a privacy/RGPD/DPO mailbox before external users are onboarded.
- Consumer PR: later legal/trust publication PR; PR16 only if privacy contact copy becomes user-facing.
- Risk level: P0.
- Risk if wrongly consumed: P0 for privacy compliance and sensitive-data routing.

Item 6 - Security contact.

- Surfaces: PR9 §4.11 Legal, privacy, and trust surfaces.
- Existing key status: `contact_email` is insufficient; legal drafts include incident/security contact placeholders.
- Classification: `SPLIT_EXISTING_KEY`.
- Proposed field: `installation.contacts.security_contact_email`.
- Semantic meaning: official mailbox for vulnerability, incident, or abuse reports.
- Allowed consumers: future legal/trust/security reporting surfaces and incident-contact copy.
- Forbidden consumers: public support by default, privacy/RGPD, sender email, reply-to, print issuer identity, signatory, shipper identity, and broad portal copy.
- ASF default behavior: may point to a confirmed ASF security/incident mailbox or remain unpublished until a legal/trust surface is added.
- First-client override expectation: `<FIRST_CLIENT>` must confirm whether security reports route to the client, ASF, or both.
- Consumer PR: later legal/trust publication PR; PR16 if external trust copy exposes the contact.
- Risk level: P1.
- Risk if wrongly consumed: P1/P0; vulnerability or incident reports can be missed or routed to the wrong organization.

## 9. Email identity

Item 7 - Email sender display name.

- Surfaces: PR9 §4.4 Emails and notifications; PR3 email sender work.
- Existing key status: `installation.notifications.email_sender_name` is safe only for Brevo `sender.name`.
- Classification: `KEEP_EXISTING_KEY`.
- Proposed field: `installation.notifications.email_sender_name`.
- Semantic meaning: display name attached to Brevo transactional sender payloads.
- Allowed consumers: Brevo API sender display-name resolution only.
- Forbidden consumers: SMTP `from_email`, sender email, reply-to, subject prefix, shell name, legal organization, public support, privacy/security contacts, and print issuer.
- ASF default behavior: preserve `ASF WMS` for Brevo display name; SMTP behavior remains governed by `DEFAULT_FROM_EMAIL`.
- First-client override expectation: `<FIRST_CLIENT>` must choose a transactional sender display name if Brevo API is used.
- Consumer PR: already consumed by PR3; PR16 may validate external copy but must not broaden it.
- Risk level: P1.
- Risk if wrongly consumed: P1 user trust risk; if used for sender domain it becomes deliverability/security risk.

Item 8 - Email subject prefix.

- Surfaces: PR9 §4.4 Emails and notifications, PR2, and PR9 P1 double-prefix risk.
- Existing key status: `installation.notifications.email_subject_prefix` is safe as a central notification convention.
- Classification: `KEEP_EXISTING_KEY`.
- Proposed field: `installation.notifications.email_subject_prefix`.
- Semantic meaning: prefix applied once to transactional email subjects at the final send boundary.
- Allowed consumers: `send_email_safe` through `format_email_subject`.
- Forbidden consumers: producer-level hardcoding, shell titles, email body branding, legal pages, sender display name, sender email, reply-to, and print surfaces.
- ASF default behavior: preserve exact `ASF WMS -` behavior and current idempotence for ASF-prefixed subjects.
- First-client override expectation: `<FIRST_CLIENT>` must provide a non-ASF subject prefix or approve a neutral product prefix before outbound email pilot use.
- Consumer PR: already consumed by PR2; producer cleanup belongs to PR16.
- Risk level: P1.
- Risk if wrongly consumed: P1; mixed subjects like client prefix plus hardcoded `ASF WMS -` damage trust.

Ownership decision: `send_email_safe` owns transactional subject prefixes. Producers must eventually pass unprefixed semantic subjects. The current hardcoded producer prefixes are legacy debt to clean in PR16, not evidence that producers should own prefixing.

Item 9 - Sender email address (`From:` address).

- Surfaces: PR9 §4.4 Emails and notifications; PR3 sender inventory.
- Existing key status: no installation key should own this today; current behavior uses `BREVO_SENDER_EMAIL` or `DEFAULT_FROM_EMAIL`.
- Classification: `DEFER_TO_LATER_PR`.
- Proposed field or policy: deployment/email-provider sender identity remains in environment/provider configuration until sender-domain validation is complete.
- Semantic meaning: authenticated email address/domain used as the message From identity.
- Allowed consumers: Brevo/SMTP transport configuration only.
- Forbidden consumers: application identity, legal organization, public support, reply-to, privacy/security contacts, print issuer, and producer code.
- ASF default behavior: preserve current `BREVO_SENDER_EMAIL`/`DEFAULT_FROM_EMAIL` behavior.
- First-client override expectation: `<FIRST_CLIENT>` sender domain must not be activated until SPF/DKIM/DMARC and provider authorization are confirmed.
- Consumer PR: later email-operations PR if sender domain changes are required; PR16 must not implement sender-email changes.
- Risk level: P1.
- Risk if wrongly consumed: P1/P0; failed DMARC, spoofing-like behavior, provider rejection, or damaged deliverability.

Item 10 - Reply-to email address.

- Surfaces: PR9 §4.4 Emails and notifications; PR3 sender inventory.
- Existing key status: no installation contact key should own this today; current Brevo reply-to is `BREVO_REPLY_TO_EMAIL`, and SMTP path does not set reply-to.
- Classification: `DEFER_TO_LATER_PR`.
- Proposed field or policy: reply-to remains a deployment/provider routing setting until mailbox ownership and privacy routing are confirmed.
- Semantic meaning: monitored mailbox where transactional email replies are delivered.
- Allowed consumers: Brevo `replyTo` payload and a future SMTP reply-to path only after explicit mail-ops decision.
- Forbidden consumers: public support by default, privacy/RGPD, security, sender email, legal contact, shell branding, print issuer, and producer body copy.
- ASF default behavior: preserve current Brevo reply-to if configured and preserve SMTP no-reply-to behavior.
- First-client override expectation: `<FIRST_CLIENT>` must confirm a monitored mailbox and whether replies are handled by client, ASF, or shared operations.
- Consumer PR: later email-operations PR or PR16 decision-only follow-up if external copy needs reply-routing disclosure.
- Risk level: P1.
- Risk if wrongly consumed: P1/P0; partner replies or personal data can route to the wrong organization.

## 10. Print/PDF identity

Item 11 - Print / PDF issuing identity.

- Surfaces: PR9 §4.5 PDF / print / exports.
- Existing key status: `organization_full_name`, `ORG_NAME`, `ORG_ADDRESS`, and `ORG_CONTACT` are insufficient because print documents also include logo, branch/service contact, legal status lines, issuer address, and footer URLs.
- Classification: `ADD_NEW_KEY`.
- Proposed field or policy: `installation.print.issuer_identity`.
- Semantic meaning: document-scoped issuer identity bundle for high-trust generated documents.
- Allowed consumers: PR15 print/PDF headers, footers, donation/customs/shipment note issuer blocks, and document contact lines.
- Forbidden consumers: app shell, email sender, reply-to, public support by default, default shipper selection, legal page publisher, and broad portal copy.
- ASF default behavior: preserve current ASF/MessMed print issuer output exactly until PR14 safety tests and PR15 narrow consumers protect it.
- First-client override expectation: `<FIRST_CLIENT>` must supply the issuer identity required for any document the first-client pilot will generate.
- Consumer PR: PR14 safety net, then PR15 implementation.
- Risk level: P0.
- Risk if wrongly consumed: P0; documents may identify the wrong issuer or lose required trust/legal information.

Item 12 - Print / PDF signatory context, including name, role, and association mentions.

- Surfaces: PR9 §4.5 PDF / print / exports.
- Existing key status: `ORG_SIGNATORY` exists but is insufficient for document-specific name, title, role, and association-status mentions; donation-certificate context is currently hardcoded.
- Classification: `DEFER_TO_LATER_PR`.
- Proposed field or policy: document-scoped signatory policy owned by PR14/PR15, not a global `installation.identity` field.
- Semantic meaning: per-document signer name, role/title, and authority/legal-status wording where a document requires a signer.
- Allowed consumers: only specific print/PDF templates that PR14 proves and PR15 explicitly configures.
- Forbidden consumers: shell branding, email sender, reply-to, public support, legal page identity, shipper identity, and generic print footer identity.
- ASF default behavior: preserve existing signatory and public-interest association wording until PR14/PR15 decide safe per-document defaults.
- First-client override expectation: `<FIRST_CLIENT>` must provide signatory details only for documents where the first-client pilot requires a signed/attested output.
- Consumer PR: PR14 and PR15.
- Risk level: P0.
- Risk if wrongly consumed: P0; a document can falsely attest authority, role, legal status, or signatory responsibility.

## 11. Shipper and namespace identity

Item 13 - Shipper identity, operational / transport.

- Surfaces: PR9 §4.16 Seed data, fixtures, and initial database assumptions; PR9 §4.5 PDF / print / exports.
- Existing key status: no current identity key safely owns shipper display. `organization_full_name` overlaps current default shipper name but must not define party selection.
- Classification: `DEFER_TO_LATER_PR`.
- Proposed field or policy: PR12-owned shipper identity policy, likely separate from installation organization identity.
- Semantic meaning: operational party used as shipper in transport workflows and visible shipment-party selectors/documents.
- Allowed consumers: PR13 default shipper resolution and shipment-party display after PR12 decides the policy.
- Forbidden consumers: shell brand, product display, legal page publisher, email sender identity, support contacts, and product SKU prefix.
- ASF default behavior: preserve current Aviation Sans Frontieres shipper behavior and priority/default shipper resolution.
- First-client override expectation: `<FIRST_CLIENT>` must decide whether default shipper is the client, ASF, a branch, or no automatic default.
- Consumer PR: PR12 decision, PR13 implementation.
- Risk level: P0.
- Risk if wrongly consumed: P0; shipments can be created under the wrong operational party.

Item 14 - Default / root shipper identity, including `ASF-C`, `ASF ID`, `ASF-ORG-ROOT`, and `Aviation Sans Frontieres`.

- Surfaces: PR9 §4.16 Seed data, fixtures, and initial database assumptions.
- Existing key status: `contact_reference_prefix` is unsafe because generated contact IDs, labels, and root shipper IDs are separate persistent contracts.
- Classification: `DEFER_TO_LATER_PR`.
- Proposed field or policy: PR12-owned reference namespace and root shipper policy.
- Semantic meaning: persistent namespace for contact identifiers, root shipper references, and user-facing labels such as ID names.
- Allowed consumers: only PR13 reference/default-shipper code after PR12 defines migration/setup behavior.
- Forbidden consumers: organization short name, brand name, product display, SKU prefix except where product SKU generation already uses it, email prefix, legal identity, and print signatory.
- ASF default behavior: preserve current `ASF-C`, `ASF ID`, `ASF-ORG-ROOT`, and Aviation Sans Frontieres root/default shipper behavior.
- First-client override expectation: `<FIRST_CLIENT>` must provide a non-ASF namespace/root-shipper policy before first-client production data is created.
- Consumer PR: PR12 decision, PR13 implementation.
- Risk level: P0.
- Risk if wrongly consumed: P0; first-client production data can be permanently polluted with ASF identifiers.

## 12. Legal / privacy / trust identity

Item 15 is covered in Section 7 because legal page identity depends on legal organization fields and service editor identity.

The trust contract must keep legal publisher, data controller/privacy contact, public support contact, and security contact distinct even when ASF defaults eventually point them to the same mailbox or entity. Legal drafts in `docs/policies/` are evidence of required fields and owners, not approved text.

No legal page content, CGU content, privacy-policy text, or legal wording is approved by this PR.

## 13. Powered-by / platform-operator attribution

Item 16 - "Powered by ASF" / platform-operator attribution.

- Surfaces: PR9 §4.1 Visual branding, §4.11 Legal, privacy, and trust surfaces, and §7 recommended PR16.
- Existing key status: no repo key or policy defines platform-operator attribution.
- Classification: `DEFER_TO_LATER_PR`.
- Proposed field or policy: `installation.trust.platform_operator_attribution_policy`.
- Semantic meaning: whether and where a first-client installation identifies ASF as platform operator, technical operator, sponsor, or not at all.
- Allowed consumers: future PR16 external communications/trust copy and possibly shell/footer display only after commercial/partnership decision.
- Forbidden consumers: legal entity, shipper identity, print issuer, sender email, reply-to, product display name, and default support contact.
- ASF default behavior: current ASF production remains unchanged; no new attribution is required for ASF itself.
- First-client override expectation: `<FIRST_CLIENT>` attribution remains TBD until ASF and the first-client stakeholder answer the partnership positioning question.
- Consumer PR: PR16 or a later trust/partnership copy PR.
- Risk level: Deferred.
- Risk if wrongly consumed: P1/P0 depending on surface; it can misrepresent who operates, endorses, or is legally responsible for the service.

Default recommendation: defer. The repo does not contain enough commercial or partnership evidence to decide whether the first-client UI should say "powered by ASF", "operated by ASF", "in partnership with ASF", or nothing.

## 14. Proposed first-client identity contract (form)

The proposed contract form is semantic, not an implementation patch:

- `identity.product_display_name`: renamed product/app display name for PR11 shell/site use.
- `identity.organization_full_name`: existing long organization name, kept for narrow legal/issuer/organization surfaces.
- `identity.organization_brand_name`: split operational brand/display name for PR11.
- `legal.organization_legal_form`: legal form when legal/print surfaces require it.
- `legal.organization_registration_number`: registration identifier when legal/print surfaces require it.
- `legal.organization_registered_address`: registered address when legal/print surfaces require it.
- `legal.service_editor_identity`: responsible entity for published legal pages.
- `contacts.public_support_email`: operational support mailbox.
- `contacts.public_support_phone`: optional public support phone.
- `contacts.privacy_contact_email`: RGPD/DPO/privacy mailbox.
- `contacts.security_contact_email`: vulnerability/incident/security mailbox.
- `notifications.email_sender_name`: existing Brevo display name.
- `notifications.email_subject_prefix`: existing central subject prefix.
- Deployment email policy: sender email remains `BREVO_SENDER_EMAIL`/`DEFAULT_FROM_EMAIL` or provider settings until authenticated.
- Deployment reply-to policy: reply-to remains `BREVO_REPLY_TO_EMAIL` or future provider/SMTP setting until mailbox ownership is confirmed.
- `print.issuer_identity`: document-scoped print/PDF issuer identity bundle.
- Print signatory policy: document-scoped signatory fields or content decisions, deferred to PR14/PR15.
- Shipper policy: PR12-owned transport/default/root shipper identity and namespace.
- Trust attribution policy: PR16/later decision for ASF platform-operator attribution.

## 15. First-client values (using `<FIRST_CLIENT>` placeholder where unknown)

| Contract value | ASF default expectation | First-client expectation |
|---|---|---|
| Product display name | Preserve current `ASF WMS` visible app naming where used. | `<FIRST_CLIENT>` product/app display name, exact value TBD. |
| Organization full/legal name | Aviation Sans Frontieres where current ASF legal/issuer surfaces require it. | `<FIRST_CLIENT>` legal name, exact legal value TBD. |
| Organization brand name | Preserve current Aviation Sans Frontieres/MessMed shell brand wording per surface. | `<FIRST_CLIENT>` brand/operator display, exact value TBD. |
| Legal form | Preserve current hardcoded/draft ASF behavior until legal fields are consumed. | `<FIRST_CLIENT>` legal form, counsel/stakeholder to provide if needed. |
| Registration number | No runtime change; current docs remain placeholders. | `<FIRST_CLIENT>` registration number if relevant, counsel/stakeholder to provide. |
| Registered address | Preserve current print/legal output until PR15/legal publication. | `<FIRST_CLIENT>` registered address if relevant. |
| Public support email | Current MessMed support email where currently visible. | `<FIRST_CLIENT>` monitored support mailbox. |
| Public support phone | Current hardcoded ASF/MessMed phone lines where currently visible. | `<FIRST_CLIENT>` support phone if the client wants or the surface requires one. |
| Privacy/RGPD email | TBD for ASF legal publication; no runtime change now. | `<FIRST_CLIENT>` privacy/RGPD/DPO mailbox before external users. |
| Security email | TBD for ASF legal publication; no runtime change now. | `<FIRST_CLIENT>` security/incident mailbox or shared ASF/client route. |
| Sender display name | `ASF WMS` for Brevo display name. | `<FIRST_CLIENT>` approved transactional sender display name. |
| Subject prefix | `ASF WMS -`. | `<FIRST_CLIENT>` approved transactional subject prefix. |
| Sender email | Current deployment/provider settings. | `<FIRST_CLIENT>` sender domain only after provider/DNS authentication. |
| Reply-to email | Current deployment/provider settings. | `<FIRST_CLIENT>` monitored reply mailbox if enabled. |
| Print issuer | Current ASF/MessMed issuer details. | `<FIRST_CLIENT>` print issuer details for documents used in pilot. |
| Print signatory | Current document-specific ASF signatory context. | `<FIRST_CLIENT>` signatory context only if required by active documents. |
| Shipper/default root | Current ASF root/default shipper behavior. | `<FIRST_CLIENT>` shipper policy TBD in PR12. |
| Powered-by attribution | No new attribution for ASF production. | `<FIRST_CLIENT>` attribution policy TBD. |

## 16. Decision matrix

| Item | Current key / status | Classification | Proposed key or policy | ASF default expectation | First-client override expectation | Consumer PR | Risk level |
|---|---|---|---|---|---|---|---|
| application display name | `application_display_name` exists, unsafe default `ASF-WMS` | `RENAME_EXISTING_KEY` | `identity.product_display_name` | Preserve visible `ASF WMS` shell naming | `<FIRST_CLIENT>` product/app name TBD | PR11 | P1 |
| organization legal name | `organization_full_name` exists | `KEEP_EXISTING_KEY` | `identity.organization_full_name` | Aviation Sans Frontieres where current legal/issuer surfaces use it | `<FIRST_CLIENT>` legal name TBD | PR15 / legal publication PR | P0 |
| organization legal form | Legal docs placeholders only | `ADD_NEW_KEY` | `legal.organization_legal_form` | Preserve current behavior until consumed | `<FIRST_CLIENT>` legal form TBD | PR15 / legal publication PR | P0 |
| organization registration number, if relevant | Legal docs placeholders only | `ADD_NEW_KEY` | `legal.organization_registration_number` | Preserve current behavior until consumed | `<FIRST_CLIENT>` registration number TBD if relevant | PR15 / legal publication PR | P0 |
| organization registered address, if relevant | `ORG_ADDRESS` setting exists, not installation contract | `ADD_NEW_KEY` | `legal.organization_registered_address` | Preserve current print/legal output until consumed | `<FIRST_CLIENT>` registered address TBD if relevant | PR15 / legal publication PR | P0 |
| organization short / brand name | `organization_short_name` unsafe | `SPLIT_EXISTING_KEY` | `identity.organization_brand_name` | Preserve current ASF/MessMed shell brand wording | `<FIRST_CLIENT>` brand/operator name TBD | PR11 | P1 |
| public support email | `contact_email` overloaded | `SPLIT_EXISTING_KEY` | `contacts.public_support_email` | Current MessMed support address where visible | `<FIRST_CLIENT>` monitored support email | PR15 / PR16 | P1 |
| public support phone, if present | Hardcoded print/legal phone lines, no key | `ADD_NEW_KEY` | `contacts.public_support_phone` | Current phone lines where visible | `<FIRST_CLIENT>` optional phone if required | PR15 / PR16 | P2 |
| privacy / RGPD / DPO email | Legal docs placeholders; `contact_email` unsafe | `SPLIT_EXISTING_KEY` | `contacts.privacy_contact_email` | No runtime change; legal placeholder remains unpublished | `<FIRST_CLIENT>` privacy/RGPD/DPO mailbox TBD | legal publication PR / PR16 if needed | P0 |
| security email | Legal docs placeholders; `contact_email` unsafe | `SPLIT_EXISTING_KEY` | `contacts.security_contact_email` | No runtime change; legal placeholder remains unpublished | `<FIRST_CLIENT>` security/incident mailbox TBD | legal publication PR / PR16 if needed | P1 |
| email sender display name | `notifications.email_sender_name` consumed for Brevo only | `KEEP_EXISTING_KEY` | `notifications.email_sender_name` | `ASF WMS` | `<FIRST_CLIENT>` approved sender display name | PR3 existing / PR16 review | P1 |
| email subject prefix | `notifications.email_subject_prefix` consumed centrally | `KEEP_EXISTING_KEY` | `notifications.email_subject_prefix`; `send_email_safe` owns prefixing | `ASF WMS -` | `<FIRST_CLIENT>` approved subject prefix | PR2 existing / PR16 cleanup | P1 |
| sender email | `BREVO_SENDER_EMAIL` / `DEFAULT_FROM_EMAIL` deployment settings | `DEFER_TO_LATER_PR` | Deployment/provider sender-domain policy | Preserve current transport behavior | `<FIRST_CLIENT>` domain only after SPF/DKIM/DMARC/provider validation | email-ops PR, not PR16 | P1 |
| reply-to email | `BREVO_REPLY_TO_EMAIL`; no SMTP reply-to path | `DEFER_TO_LATER_PR` | Deployment/provider reply-routing policy | Preserve current reply-to behavior | `<FIRST_CLIENT>` monitored reply mailbox TBD | email-ops PR / PR16 decision if needed | P1 |
| print / PDF issuer name | Hardcoded print identity plus partial `ORG_NAME` context | `ADD_NEW_KEY` | `print.issuer_identity` | Preserve ASF/MessMed issuer output exactly | `<FIRST_CLIENT>` print issuer TBD | PR14 / PR15 | P0 |
| print / PDF issuer legal details, if relevant | Hardcoded print footers/status lines plus placeholders | `ADD_NEW_KEY` | Print issuer legal-detail policy/bundle | Preserve current footer/legal details | `<FIRST_CLIENT>` issuer legal details TBD | PR14 / PR15 | P0 |
| print / PDF signatory name / title, if relevant | Hardcoded donation context; `ORG_SIGNATORY` insufficient | `DEFER_TO_LATER_PR` | Document-scoped signatory policy | Preserve current document-specific signatory context | `<FIRST_CLIENT>` signatory TBD per active document | PR14 / PR15 | P0 |
| shipper display name | Hardcoded/default policy uses Aviation Sans Frontieres | `DEFER_TO_LATER_PR` | PR12 shipper identity policy | Preserve current ASF default shipper display | `<FIRST_CLIENT>` default shipper choice TBD | PR12 / PR13 | P0 |
| shipper legal / customs name | Print/customs surfaces identify ASF today | `DEFER_TO_LATER_PR` | PR12 plus PR15 document-party policy | Preserve current ASF customs/shipper truth | `<FIRST_CLIENT>` customs/legal shipper TBD | PR12 / PR15 | P0 |
| default / root shipper reference | `ASF-ORG-ROOT`, `ASF-C`, `ASF ID` hardcoded | `DEFER_TO_LATER_PR` | PR12 reference namespace/root shipper policy | Preserve `ASF-ORG-ROOT`, `ASF-C`, `ASF ID` | `<FIRST_CLIENT>` namespace/root policy TBD before production data | PR12 / PR13 | P0 |
| legal page organization identity | Draft policy docs only | `ADD_NEW_KEY` | `legal.service_editor_identity` | No runtime legal publication change | `<FIRST_CLIENT>`/ASF responsible entity TBD | legal publication PR / PR16 reference | P0 |
| powered-by ASF display policy | No key/policy | `DEFER_TO_LATER_PR` | `trust.platform_operator_attribution_policy` | No new attribution required | `<FIRST_CLIENT>` attribution TBD | PR16 or later trust PR | Deferred |

## 17. PR mapping

- PR11: consume only product/app display and operational brand identity for shell/site surfaces; do not touch print, email routing, legal pages, or shipper/reference policy.
- PR12: decide reference namespace, contact ID label, default/root shipper identity, and persistent shipper/reference setup; PR10 does not decide those mechanics.
- PR13: implement PR12 reference/default-shipper decisions with ASF defaults unchanged.
- PR14: add print identity safety tests/snapshots before any print identity changes.
- PR15: consume print issuer, print legal-detail, and document-scoped signatory policies only after PR14 protects ASF print output.
- PR16: clean external communications copy, producer subject prefixes, support/contact wording, and any approved platform-operator attribution; do not change sender email or reply-to unless a separate mail-ops decision has closed.
- Later legal/trust publication PR: publish or expose legal/privacy/CGU/security surfaces only after legal counsel/stakeholders supply approved values and text.
- Later email-operations PR: change sender email or reply-to only after provider, DNS, domain authentication, mailbox ownership, privacy routing, and rollback are documented.

## 18. Risks, blockers, and open questions requiring arbitration

1. Powered-by attribution - Owner: ASF stakeholder plus first-client stakeholder. Question: Should first-client user-facing surfaces display no ASF attribution, "powered by ASF", "operated by ASF", or "in partnership with ASF"?

2. First-client legal publisher - Owner: legal counsel plus first-client stakeholder. Question: Is the service editor/responsible legal entity `<FIRST_CLIENT>`, ASF, or another named entity?

3. First-client data controller/privacy owner - Owner: legal counsel. Question: Is the data controller `<FIRST_CLIENT>`, ASF, joint controllers, or another arrangement?

4. First-client product display value - Owner: me plus first-client stakeholder. Question: What exact product/app display name should PR11 use for `<FIRST_CLIENT>`?

5. First-client brand/operator display value - Owner: first-client stakeholder. Question: What exact brand/operator name should PR11 show where the surface names the operating organization?

6. Public support mailbox - Owner: first-client stakeholder. Question: Should public support route to `<FIRST_CLIENT>`, ASF, or a shared monitored mailbox?

7. Privacy/RGPD/DPO mailbox - Owner: legal counsel. Question: What mailbox must receive privacy/RGPD/DPO requests for `<FIRST_CLIENT>`?

8. Security/incident mailbox - Owner: ASF stakeholder plus first-client stakeholder. Question: Should security reports route to `<FIRST_CLIENT>`, ASF, or both?

9. Sender email layer - Owner: me plus first-client stakeholder. Question: Will first-client email use ASF-controlled sender domain, `<FIRST_CLIENT>` sender domain, or outbound email disabled/manual during pilot?

10. Reply-to layer - Owner: first-client stakeholder. Question: Should transactional replies route to `<FIRST_CLIENT>`, ASF, or a shared monitored mailbox?

11. Print issuer identity - Owner: legal counsel plus first-client stakeholder. Question: Which entity appears as issuer on each document type used in the first-client pilot?

12. Print signatory - Owner: legal counsel plus first-client stakeholder. Question: For each signed/attested document in pilot scope, is a named signatory required, and is the signer from `<FIRST_CLIENT>`, ASF, or another entity?

13. Shipper/default root policy - Owner: ASF stakeholder plus first-client stakeholder. Question: Should the default/root shipper be `<FIRST_CLIENT>`, ASF, a branch-specific party, or disabled until explicitly selected?

14. PR7 reopening signal - Owner: me. Question: Should `application_display_name` be renamed to `product_display_name` exactly, or does the project prefer another name before PR11? This does not reopen the PR7 decision that the existing key is unsafe.

No remaining email subject prefix arbitration is required: PR2 and current code support central ownership by `send_email_safe`.

## 19. Explicitly rejected options

- Reject a global find/replace of `ASF`, `Aviation Sans Frontieres`, or MessMed strings. PR9 already showed different surfaces carry different meanings.
- Reject broad consumption of `organization_short_name` as an ASF replacement token.
- Reject broad consumption of `contact_email` for support, privacy, security, reply-to, legal contact, and sender identity.
- Reject deriving sender email from installation identity or support contact before sender-domain authentication is proven.
- Reject producer-owned email subject prefixes. Central `send_email_safe` ownership is already implemented and should be made clean by PR16.
- Reject using `application_display_name` as-is for PR11 visible shell work because the default does not preserve current visible `ASF WMS` behavior.
- Reject treating print/PDF signatory as a global organization identity field.
- Reject deciding "powered by ASF" from code evidence alone.
- Reject using PR10 to decide PR12 reference/default-shipper mechanics.

## 20. Validation checklist

- Propagation impact checked: yes; print, email, parties/shipper, shell, legal/trust, and installation-config contracts were reviewed.
- Tests: no test run required because this PR is audit/document-only and changes no runtime behavior.
- Documentation drift: this PR is itself the documentation update; no repo-reference update is required because no runtime/shared contract changes are made.
- Permissions: no permissions, roles, access rules, or portal scopes changed.
- User-visible behavior: no runtime behavior changed.
- Operational safety: current ASF defaults and production behavior remain untouched.
- Forbidden surfaces checked: no runtime code, config, test files, templates, JavaScript, CSS, gettext catalogs, migrations, dependency files, README/setup/deployment files, or legal drafting changed.
- PR7 decisions checked: no PR7 decision is reopened; unsafe items are split/renamed/deferred consistently.
- PR9 dependency checked: PR #205 is merged into `main`, and `docs/audits/2026-05-11-first-client-white-label-readiness.md` exists.
- `.secrets.baseline`: not touched.
