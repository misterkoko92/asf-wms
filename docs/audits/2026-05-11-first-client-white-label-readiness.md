# First Client White-label Readiness Audit

Date: 2026-05-11
Branch: `audit/first-client-white-label-readiness`
Base: `main` at `1ab48df533fbaa88f99c2e86a4cac04086eea14b`
Change classification: B. Generic reusable capability and C. Organization configuration, constrained by A. ASF operational continuity.

## 1. Executive summary

ASF-WMS is not ready today for a credible first non-ASF installation if that installation exposes the portal, sends transactional email, or prints real shipment documents. The single-tenant strategy remains sound, and PR1-PR8 created useful seams, but the remaining blockers are product-facing and high-trust rather than purely technical.

The strict P0 blockers are narrower than "all ASF strings": high-trust PDF/print identity, visible shell branding on core entry surfaces, and production reference/default-shipper assumptions that would create or depend on ASF identifiers in a first-client database. Legal/privacy/trust surfaces are a decision gate: they become P0 when external portal or public-order users are enabled.

Most other findings are P1 or P2. Portal wording, email bodies, scan/admin labels, planning provider assumptions, and deployment templates are visibly awkward, but can be sequenced as small PRs with ASF defaults unchanged. Broad model renames, global vocabulary substitution, shared-DB tenancy, and "replace all ASF" are still the wrong next moves.

Most important findings:

- P0: Shipment PDFs, customs notes, donation certificates, labels, and print footers still embed ASF logo, ASF legal text, MessMed contact details, signatory context, and Air France wording.
- P0: The main visible shells still show ASF/MessMed identity through logo assets, `Aviation Sans Frontières`, `Messagerie Médicale`, `ASF WMS`, and the scan PWA name.
- P0: Contact/default-shipper setup still depends on `ASF-C-...`, `ASF-ORG-ROOT`, `ASF ID`, and `Aviation Sans Frontieres`; this can pollute first-client production data.
- Decision needed: first-client legal identity, data-controller identity, support/RGPD contacts, portal CGU/privacy exposure, and app-display-name semantics must be decided before implementation.
- P1: Portal copy and transactional email bodies still say ASF in account validation, status, stock, support, and sign-off contexts even after the narrow PR2/PR3/PR5 consumers.

## 2. Scope and assumptions

Target scenario: a first non-ASF single-tenant installation over the next 6-12 months. Manual setup, operator assistance, and a controlled pilot are acceptable. A self-serve SaaS, shared-DB tenancy, automated tenant provisioning, and broad runtime module generalization are not required for this horizon.

ASF production must remain unchanged. Defaults in `main` must reproduce current ASF behavior. White-label behavior should come through installation config overrides, explicit setup data, and narrow consumers. This audit did not run the app visually, inspect every generated PDF output, or deep-audit every model/test fixture. It prioritized first-client credibility and operational blockers over exhaustive string inventory.

Translation work is still paused by policy. Locale files were inspected only to assess white-label risk, not to reopen FR/EN parity.

## 3. Readiness classification

Use exactly this classification:

- `P0 — Blocks first non-ASF installation`

  - visible, operational, legal, trust, or delivery issue that must be fixed before a credible first client.
- `P1 — Should fix before/alongside first pilot`

  - visible or operationally awkward, but can be handled with support or narrow workaround.
- `P2 — White-label debt, not first-client blocking`

  - should be addressed later, but does not block a first controlled pilot.
- `P3 — Internal/dev/docs only`

  - not user-facing or not relevant for first-client readiness.
- `Decision needed`

  - product/legal/ops decision required before implementation.

## 4. Findings by dimension

### 4.1 Visual branding

Classification: P0 for visible shells and high-trust documents; P2 for color palette.

Scan, portal, volunteer, and planning shells still share the ASF logo asset at `wms/static/scan/logo.jpg`. Scan displays `Messagerie Médicale`; portal/volunteer shells display `Aviation Sans Frontières`; planning displays `ASF WMS`; the scan PWA manifest is named `ASF WMS Scan`. These are first-viewport signals on core user surfaces, not obscure footer strings.

Print documents reuse the same logo in shipment notes, customs notes, donation certificates, and packing lists. This is P0 because real first-client paperwork cannot carry ASF identity.

CSS/colors are less blocking. Runtime design tokens already exist, and the current green palette is not uniquely ASF-branded. A first pilot can use the existing palette if logo/name/document identity are corrected first.

Decision needed: brand asset source, fallback logo behavior, favicon/PWA naming, and whether first-client UI should be client-branded, neutral product-branded, or "powered/operated by" branded.

### 4.2 Application naming

Classification: Decision needed, with P1 visible inconsistencies.

There is a known naming conflict: `installation.identity.application_display_name` defaults to `ASF-WMS`, while current visible surfaces often use `ASF WMS`. Notifications deliberately use `notifications.email_subject_prefix = "ASF WMS -"` and `notifications.email_sender_name = "ASF WMS"`. The audit found all variants in runtime-visible contexts.

Do not consume `application_display_name` broadly until product naming is decided. The key name implies a general visible app name, but its default does not match current visible UI and notification strings. A first client needs one explicit app-name policy per surface family: browser title/header, PWA manifest, notification sender/prefix, API/User-Agent identifiers, and repo/internal names.

P1 examples: `templates/home.html` uses `ASF WMS`, `templates/planning/base.html` shows `ASF WMS`, `wms/static/scan/manifest.json` names `ASF WMS Scan`, and integration User-Agent strings still use `ASF-WMS`.

### 4.3 Vocabulary and domain labels

Classification: P1 for external portal/account/order copy; P2 for broad domain vocabulary debt; Decision needed for role naming.

PR5 handled the narrow portal shell/account `portal_partner_label` case. Many other portal and public-account surfaces still say `association`, `expéditeur`, `destinataire`, `Stock ASF`, `validation ASF`, and `consignes ASF`. These are not all wrong for ASF, and many are valid logistics roles, but a first client needs decisions about which labels are product concepts and which are ASF service concepts.

PR6 remains valid: the broad existing vocabulary keys are unsafe for direct global consumption. The correct pattern is still narrow key, narrow surface, ASF default unchanged, and targeted override tests.

Staff scan and planning labels such as `Réception association`, `Statut ASF`, `Expéditeur`, `Destinataire`, and `Bénévole` are lower priority than portal/legal/print. They matter for first-client operators, but most can be addressed after the P0 document/reference issues.

Decision needed: whether first-client users are still "associations", whether "shipper/recipient" remain the canonical operational concepts, and how to name ASF-like service-provider actions in a non-ASF installation.

### 4.4 Emails and notifications

Classification: P1; Decision needed for sender/reply-to routing.

PR2 and PR3 created useful notification seams, but producers and bodies still contain ASF wording. Account approval, account received, order confirmation, volunteer, portal forgot-password, shipment tracking, order status, and signal-driven status subjects/bodies still use `ASF WMS`, `ASF`, or `ASF ID`.

One subtle risk: many producers already pass subjects that begin with `ASF WMS -`. `send_email_safe` applies the configured prefix idempotently for the configured prefix, not for every historical ASF-prefixed subject. With a non-ASF override, a producer subject like `ASF WMS - Nouvelle commande` can still leak inside the final subject unless producers are narrowed later.

Do not change `sender_email` or `reply_to_email` as a simple branding fix. Brevo and SMTP sender identity affect SPF, DKIM, DMARC, reply routing, support ownership, and bounce handling. `email_sender_name` is display-only on the Brevo path; SMTP still uses `DEFAULT_FROM_EMAIL`.

Decision needed: public support address, transactional sender domain, reply-to routing, whether first-client email uses Brevo, SMTP, or manual/disabled outbound email during setup.

### 4.5 PDF / print / exports

Classification: P0.

This is the biggest first-client blocker. Print/PDF templates embed ASF identity in places where partners, customs actors, recipients, and client staff will treat the document as authoritative. Examples include `Logo ASF`, MessMed email/phone, `Association reconnue d'utilité publique`, `RESP. DOUANE ASF`, `ASF Flight Manager`, donation-certificate signatory/title, `Aviation Sans Frontieres`, and Air France X-ray wording.

The print pack/template system is reusable, but the default HTML content is not first-client safe. Fixing this should not be a broad layout rewrite. It needs a safety-net PR first, then a narrow identity/copy consumer for the high-trust fields.

Exports are mixed. Product import templates and CSV examples use `ASF-000001`, but these are setup/demo surfaces. Planning exports and document packs require a dedicated follow-up if a first client will use planning.

Decision needed: legal signatory, document footer, public-interest association wording, donation-certificate wording, customs/responsible-party labels, default logo/stamp, and whether Air France-specific statements apply to the client.

### 4.6 Portal readiness

Classification: P1 overall, with P0 dependency on visual/legal decisions when external users are enabled.

Portal shell/account label work has started, but the portal is still visibly ASF-operated in login, FAQ, onboarding, dashboard, order creation, billing, status text, and error copy. Examples include `Portail ASF`, validation by ASF, ASF stock, ASF parcel guidelines, and ASF document validation.

For a controlled first pilot, this can be sequenced after the P0 shell/legal/reference work if operator support explains the remaining vocabulary. It becomes blocking if external users are expected to self-serve without ASF-context explanations.

PR5's `portal_partner_label` should remain narrow. The remaining portal surfaces need small decision-backed PRs, not a broad "association to partner" replacement.

### 4.7 Staff scan / warehouse workflows

Classification: P1 for shell/logout/reference leakage; P2 for most staff-only labels.

Scan is the core warehouse surface, so client operators will see it. The visible shell still displays ASF/MessMed identity and logo. `SCAN_LOGOUT_REDIRECT_URL` hardcodes `https://messmed.pythonanywhere.com/`, which is a direct first-client navigation issue.

Operational labels such as `Réception association`, `Statut ASF`, `ASF ID`, and `Préparation ASF` are first-client awkward but not all first-client blockers. Some describe real ASF workflows today; changing them without tests can disrupt operator meaning.

Warehouse workflow semantics should not be generalized in PR9 follow-ups unless they are clearly visible/configuration issues. Stock, packing, carton, shipment, and scan-speed behavior remain sensitive zones.

### 4.8 Planning / shipment orchestration

Classification: P1/Decision needed if planning is in first-client scope; P2 otherwise.

Planning carries ASF aviation assumptions: Air France/KLM provider defaults, CDG/AF defaults, Air France communications, WhatsApp volunteer communications, helper app labels, and `ASF-WMS/planning-flight-client` User-Agent. Planning UI also displays `ASF WMS`.

This does not block a first client that does not use planning. It should block a first client that expects planning, flight imports, or communication drafts to be production-ready under its own identity.

Decision needed: whether first-client planning uses flights at all, whether Air France/KLM is still the provider, what departure origin/airline defaults apply, and whether the local helper is acceptable operationally.

### 4.9 Admin/back-office

Classification: P1 if client operators use Django admin directly; P2 if admin is ASF-maintainer-only.

Django admin and back-office forms expose legacy names: `AssociationProfile`, `AssociationRecipient`, association billing models, `ASF ID`, volunteer labels, and mixed French/English verbose names. This is not ideal, but model/admin naming is not the same as first-client external readiness.

Do not rename models or migrations for the first client. Keep compatibility names and improve visible labels only where client operators actually work. Scan-admin contact screens are more important than raw Django admin model names.

### 4.10 URLs, domains, and external links

Classification: P1 for hardcoded production URLs/contact domains; P2 for generic external CDNs/providers.

`SITE_BASE_URL`, allowed hosts, and CSRF origins are configurable, but some runtime and deployment files still carry ASF/MessMed domains. The scan logout redirect points to `messmed.pythonanywhere.com`. Print footers use `aviation-sans-frontieres.org/messmed` and MessMed email. PythonAnywhere deployment templates include both generic and MessMed-specific variants.

CDN/font links and Nominatim/OpenStreetMap autocomplete are provider decisions rather than white-label brand blockers. They may need client security/legal approval, but they are not inherently ASF-specific.

Decision needed: official client domain, logout destination, public document footer URL, and whether external CDN/geocoding providers are acceptable for the pilot.

### 4.11 Legal, privacy, and trust surfaces

Classification: Decision needed; P0 if portal/public external users are enabled before decisions are closed.

The repo has policy drafts under `docs/policies/`, but they explicitly state they are drafts/placeholders requiring legal/RGPD validation. Contacts, DPO/RGPD channels, support contacts, official entity details, legal bases, CGU acceptance, and data-controller identity remain incomplete.

This audit did not find app template links that expose these legal/privacy/CGU documents as first-client user-facing pages. That absence is acceptable for internal-only manual pilots but not for a credible external portal/public-order pilot without a contractual or published legal alternative.

Decision needed: data controller, processor/subprocessor list, support/RGPD/security contact channels, CGU acceptance moment, legal-page publication route, and whether first-client external users can be onboarded before pages exist.

### 4.12 Installation/onboarding/configuration

Classification: P1.

The installation config contract exists and now has a few consumers: notification subject prefix, Brevo sender display name, portal partner label, and SKU prefix. Most identity keys remain unconsumed for visible UI, documents, reference identifiers, legal text, and setup workflows.

New client setup is still error-prone. `.env.example`, README snippets, and PythonAnywhere templates show `ORG_NAME=Aviation Sans Frontieres`, `SKU_PREFIX=ASF`, Brevo/ASF sender examples, PythonAnywhere paths, and MessMed-specific deployment values. Those are useful for ASF production but risky as first-client onboarding instructions.

This is not a docs-cleanup request for PR9. The first-client setup checklist should come after the P0 identity/reference decisions, so it does not document unstable setup rules.

### 4.13 Integrations and providers

Classification: P1/Decision needed when the integration is in pilot scope; P2 otherwise.

Email uses Brevo API first and Django SMTP fallback. Document scanning defaults to ClamAV. PDF conversion relies on Microsoft Graph/OneDrive or local helper tooling. Planning flight import defaults to Air France/KLM. Address autocomplete uses Nominatim/OpenStreetMap. Helper tools use local HTTP and ASF-prefixed helper headers.

These integrations are mostly configurable enough for a controlled pilot, but capability decisions are not fully mapped to first-client exposure. A client that does not use planning should not see planning helper requirements; a client without Microsoft 365 should not depend on Graph PDF conversion.

Decision needed: integration capability matrix for the pilot, including enabled modules, providers, credentials, data residency/privacy approval, support owner, and fallback behavior.

### 4.14 Feature flags and capability flags

Classification: P2; Decision needed for pilot module exposure.

`InstallationFeatureFlags` exists, but module-level flags currently default to enabled and are not a route-level product surface gate. Capability-derived flags exist for print pack/document scan/PDF conversion/external flight/local helper descriptors, but consumers are still incremental.

This does not require a new feature-flag system. For a first client, decide which modules are in scope and then add narrow consumers only where hiding or disabling a module avoids visible broken functionality.

Missing useful pilot decisions: portal on/off, planning on/off, billing on/off, document scan on/off, print pack/PDF conversion mode, public account/order flows, local helper requirement.

### 4.15 i18n / gettext

Classification: P2.

Gettext catalogs contain many ASF and association strings, including translated ASF email subjects and document strings. Many visible strings also remain direct template/Python strings. This proves white-label vocabulary is not the same as translation.

Do not reopen translation parity to solve white-label. Continue using narrow installation/config consumers for product vocabulary and identity. Locale cleanup can follow once first-client surfaces are stable.

Risk: if a non-French pilot requires English UI, this becomes a separate product requirement and should be audited independently.

### 4.16 Seed data, fixtures, and initial database assumptions

Classification: P0 for production reference/default-shipper namespace; P1 for onboarding data hazards; P3 for local-only demo fixtures.

The production-relevant blocker is not demo data itself; it is that contact IDs and default shipper policy still encode ASF. Generated contact references use `ASF-C-...`, scan/email recovery labels say `ASF ID`, and default recipient shipper binding resolves `ASF-ORG-ROOT` / `Aviation Sans Frontieres`. A first-client production database should not start by creating ASF-root records or ASF-prefixed contacts.

Fixtures, demo seed commands, and local exhaustive data are mostly P3 if they remain local/test-only. They use association language, ASF product brands, demo users, Air France sample flights, and `ASF-000001` product examples. They become P1 only if onboarding docs tell operators to load them into a first-client production database.

No evidence was found that these fixtures auto-run in production. The risk is manual setup misuse and persistent reference pollution.

## 5. Cross-cutting findings

- Hardcoded ASF identity is concentrated in shells, documents, email bodies/subjects, legal drafts, deployment examples, contact/reference identifiers, and default shipper setup.
- Broad vocabulary keys remain ambiguous. The safe pattern is still surface-specific config with ASF defaults and targeted tests.
- Contact/email routing is a trust and deliverability risk. Display-name changes are not equivalent to sender/reply-to/domain changes.
- Branding assets are shared across scan, portal, volunteer, planning, and print. A visual-brand PR must be narrow but cross-surface-aware.
- Legal/product decisions block implementation more than code mechanics in several areas: application name, legal identity, support contacts, CGU/privacy exposure, and provider approvals.
- Safe micro-PRs exist, but they should be ordered: decision first, shell/reference safety, print safety, then external-copy cleanup.

## 6. First-client blocker list

| Priority | Finding | Surface | Evidence | Why it matters | Suggested next action |
| -------- | ------- | ------- | -------- | -------------- | --------------------- |
| P0 | ASF legal/document identity in generated paperwork | PDF/print | `templates/print/partials/donation_certificate_body.html:16`, `templates/print/partials/customs_note_body.html:121` | Real shipment/customs/donation documents cannot legally or credibly identify the wrong organization | Add print identity safety net, then narrow document-identity config consumers |
| P0 | ASF/MessMed shell branding on core UI | Scan, portal, volunteer, planning, home, PWA | `templates/scan/base.html:72`, `templates/includes/secondary_shell_masthead.html:57`, `wms/static/scan/manifest.json:2` | First client users immediately see ASF/MessMed branding | Decide app/organization display contract, then update narrow shell consumers |
| P0 | ASF reference/default-shipper namespace in production data | Contacts, portal approval, tracking recovery | `contacts/asf_ids.py:7`, `wms/policies/shipment_parties.py:5`, `wms/shipment_party_setup.py:12` | First-client contacts/default shipper can be created with ASF identifiers or require ASF-root setup | Run a focused decision PR, then implement explicit client-safe defaults |
| Decision needed / P0 if external portal enabled | Legal/privacy/CGU identity and publication route are unresolved | Portal/public trust surfaces | `docs/policies/mentions-legales.md:3`, `docs/policies/confidentialite.md:3`, `docs/policies/cgu-portail.md:3` | External users need valid controller/contact/terms/privacy information or a contractual substitute | Product/legal decision before exposing external self-service users |
| P1 | Transactional emails still contain ASF in bodies and producer subjects | Account, portal, order, tracking, volunteer emails | `templates/emails/account_request_approved.txt:4`, `wms/order_notifications.py:15`, `wms/emailing.py:128` | First-client users may receive mixed client/ASF messages | Narrow email-copy PR after sender/reply-to decisions |
| P1 | Portal first-client copy still explains ASF validation, stock, and parcel guidelines | Portal FAQ, onboarding, order flow, billing | `wms/application/portal/onboarding.py:19`, `templates/portal/includes/order_create_shipper_inbound_card.html:12`, `templates/portal/billing_list.html:9` | External users need clear ownership and next actions | Follow shell/legal work with a portal-copy decision and narrow consumers |
| P1 | Setup templates still encode ASF/MessMed defaults | `.env`, README, deploy templates | `deploy/pythonanywhere/asf-wms.env.template:24`, `README.md:293`, `.env.example:39` | First-client setup can accidentally reproduce ASF identity | Create first-client setup checklist/templates after identity/reference decisions |
| P1 | Hardcoded MessMed logout/domain remains | Scan logout | `wms/views_scan_misc.py:19` | Client staff can be redirected to ASF production domain | Include in shell/site identity PR |

## 7. Recommended next PRs

I recommend 7 next PRs because the remaining blockers split across distinct risk classes: legal/product decisions, UI shell identity, persistent data references, high-trust print documents, and external communications copy. Fewer PRs would mix sensitive surfaces; more would add process overhead without reducing risk.

### PR10 — Decide first-client identity, legal, and contact contract

Type: audit/decision.

Scope: one decision document that fixes the first-client app-name policy, organization/legal identity, public support email, RGPD/DPO/security contacts, legal page exposure, and sender/reply-to routing constraints.

Likely files/surfaces: `docs/audits/` or `docs/decisions/` only.

Why next: shell, print, legal, and email implementation need stable answers first.

Main risks: deciding too broadly or changing ASF defaults implicitly.

Out of scope: runtime code, sender-email implementation, model renames, legal text finalization beyond decision capture.

### PR11 — Implement narrow shell/site identity consumers

Type: implementation.

Scope: visible browser/header/app-shell identity only: home title/header, scan shell logo/name, portal/volunteer masthead, planning header, PWA manifest if a safe static/dynamic path is chosen, and `SCAN_LOGOUT_REDIRECT_URL`.

Likely files/surfaces: `templates/home.html`, `templates/scan/base.html`, `templates/includes/secondary_shell_masthead.html`, `templates/planning/base.html`, `wms/views_scan_misc.py`, possibly static manifest handling.

Why next: removes first-viewport ASF/MessMed leakage without touching documents, emails, or workflow labels.

Main risks: app-name conflict (`ASF-WMS` vs `ASF WMS`), asset handling, service-worker/PWA cache behavior.

Out of scope: print documents, email subjects/bodies, broad vocabulary replacement, CSS theme redesign.

### PR12 — Decide reference namespace and default shipper policy

Type: audit/decision.

Scope: choose how first-client contact IDs, `ASF ID` labels, default root shipper, recipient default binding, and recovery identifiers should work in a single-tenant client install.

Likely files/surfaces: decision doc plus evidence from `contacts/asf_ids.py`, `wms/default_shipper_bindings.py`, `wms/policies/shipment_parties.py`, `wms/shipment_party_setup.py`, tracking recovery templates.

Why next: this affects persistent production data and portal recipient approval.

Main risks: breaking current ASF default shipper behavior or confusing contact ID namespace with SKU prefix.

Out of scope: shared-DB tenancy, contact model rename, broad party-graph rewrite.

### PR13 — Implement configured reference/default-shipper behavior

Type: implementation.

Scope: after PR12, add the smallest runtime consumers needed so first-client contact IDs/default shipper setup do not require `ASF-C`, `ASF ID`, `ASF-ORG-ROOT`, or `Aviation Sans Frontieres` records while ASF defaults remain unchanged.

Likely files/surfaces: `contacts/asf_ids.py`, `wms/policies/shipment_parties.py`, `wms/default_shipper_bindings.py`, `wms/shipment_party_setup.py`, scan/tracking labels, targeted tests.

Why next: prevents first-client production data pollution.

Main risks: portal approval, recipient binding, shipment-party selectors, tracking recovery.

Out of scope: model renames, migration of existing ASF IDs, global replacement of `ASF`.

### PR14 — Add print identity safety net

Type: implementation/tests-only.

Scope: fixture/snapshot coverage for current ASF print output across donation certificate, shipment note, customs note, packing list, labels, and footers before behavior changes.

Likely files/surfaces: `wms/tests/print/`, `wms/tests/views/tests_print_strict_fidelity.py`, representative print fixtures.

Why next: high-trust print output is the largest P0 surface and needs protection before configuration consumers.

Main risks: brittle layout assertions or over-testing incidental whitespace.

Out of scope: runtime print changes, template redesign, legal wording changes.

### PR15 — Implement narrow print/PDF identity consumers

Type: implementation.

Scope: configurable logo/contact/footer/legal/signatory fields for the high-trust document identity surfaces identified by PR14, preserving exact ASF defaults.

Likely files/surfaces: `templates/print/partials/*`, `templates/print/base_document.html`, `templates/print/base_a5.html`, print context helpers, targeted print tests.

Why next: removes the biggest first-client credibility blocker.

Main risks: legal text accuracy, print layout regressions, customs/document truth, confusing organization identity with shipper/donor identity.

Out of scope: print layout redesign, all document wording, Air France workflow generalization unless explicitly covered by the decision.

### PR16 — Clean first-client external communications copy

Type: implementation.

Scope: narrow account/order/tracking/portal email bodies and producer subjects that still leak ASF identity, plus the most visible portal status/help copy required for first pilot.

Likely files/surfaces: `templates/emails/*`, `wms/account_request_handlers.py`, `wms/order_notifications.py`, `wms/public_order_handlers.py`, `wms/views_portal_auth.py`, `wms/application/portal/onboarding.py`, selected portal templates.

Why next: external users should not receive mixed client/ASF messages after shell and print identity are handled.

Main risks: email deliverability assumptions, sender/reply-to confusion, broad vocabulary changes.

Out of scope: sender email/reply-to changes without SPF/DKIM/DMARC decision, full portal FAQ rewrite, gettext parity.

## 8. Explicit non-goals

PR9 does not:

- change runtime code;
- implement any white-label behavior;
- change configuration;
- add migrations;
- add or change tests;
- change templates;
- change JS/CSS;
- change gettext catalogs;
- change dependencies;
- update docs outside this single audit file;
- propose a new framework;
- propose shared-DB tenancy;
- recommend broad replacement of ASF strings;
- recommend model renames or long-lived forks.

## 9. Evidence appendix

Representative evidence only; this is not a raw grep dump.

### Visual branding and application naming

- `templates/scan/base.html:63` — scan shell aria label uses `Aviation Sans Frontières France`.
- `templates/scan/base.html:65` — scan shell loads `scan/logo.jpg`.
- `templates/scan/base.html:72` — scan shell displays `Messagerie Médicale`.
- `templates/includes/secondary_shell_masthead.html:21` — planning link aria label uses `ASF WMS Planning`.
- `templates/includes/secondary_shell_masthead.html:55` — portal/volunteer masthead loads `scan/logo.jpg`.
- `templates/includes/secondary_shell_masthead.html:57` — masthead displays `Aviation Sans Frontières`.
- `templates/home.html:6` — browser title is `ASF WMS`.
- `templates/home.html:194` — home page displays `ASF WMS`.
- `templates/planning/base.html:39` — planning header displays `ASF WMS`.
- `wms/static/scan/manifest.json:2` — PWA name is `ASF WMS Scan`.
- `wms/config/installation.py:9` — `ASF_APPLICATION_DISPLAY_NAME = "ASF-WMS"`.
- `wms/config/installation.py:12` — notification subject default is `ASF WMS -`.
- `wms/config/installation.py:13` — Brevo sender display-name default is `ASF WMS`.

### Vocabulary and portal copy

- `templates/portal/base.html:7` — portal base consumes only `portal_partner_label`.
- `wms/templatetags/wms_vocabulary.py:10` — `portal_partner_label` reads installation vocabulary.
- `templates/portal/faq.html:49` — shipper FAQ still says the space serves association requests.
- `templates/portal/faq.html:99` — portal FAQ mentions ASF review/non-conforming documents.
- `templates/portal/includes/order_create_shipper_inbound_card.html:12` — portal order copy says parcels must respect ASF dimensions.
- `templates/portal/includes/order_create_shipper_inbound_card.html:237` — user certifies compliance with ASF guidelines and random control.
- `templates/portal/billing_list.html:9` — portal billing says quotes/invoices are issued by ASF.
- `wms/application/portal/onboarding.py:19` — onboarding says data structures requests sent to ASF.
- `wms/application/portal/onboarding.py:73` — onboarding says ASF uses order data for preparation/transport.
- `wms/portal_dashboard_helpers.py:36` — portal next step can be `Attendre la validation ASF`.
- `wms/views_portal_auth.py:48` — inactive account error says account not activated by ASF.

### Emails and notifications

- `wms/emailing.py:128` — central subject formatter exists.
- `wms/emailing.py:140` — formatter reads `notifications.email_subject_prefix`.
- `wms/emailing.py:150` — Brevo sender display name reads `notifications.email_sender_name`.
- `wms/emailing.py:395` — Brevo sender email still comes from `BREVO_SENDER_EMAIL` or `DEFAULT_FROM_EMAIL`.
- `wms/emailing.py:401` — Brevo reply-to still comes from `BREVO_REPLY_TO_EMAIL`.
- `wms/emailing.py:454` — `send_email_safe` applies the central formatted subject.
- `wms/order_notifications.py:15` — producer subject still starts `ASF WMS - Nouvelle commande`.
- `wms/public_order_handlers.py:24` — public order confirmation subject still starts `ASF WMS -`.
- `wms/signals.py:292` — shipment status subject still starts `ASF WMS -`.
- `templates/emails/account_request_approved.txt:4` — body says recipient account was approved by ASF.
- `templates/emails/account_request_received.txt:4` — body says an ASF superuser will review the request.
- `templates/emails/order_confirmation.txt:3` — body says the order was received by ASF WMS.
- `templates/emails/shipment_tracking_access_recovery.txt:3` — recovery email shows `ASF ID`.

### PDF, print, and exports

- `templates/print/partials/shipment_note_body.html:5` — shipment note includes `Logo ASF`.
- `templates/print/partials/shipment_note_body.html:8` — shipment note hardcodes MessMed email and phone.
- `templates/print/partials/shipment_note_body.html:74` — shipment note labels `RESP. DOUANE ASF`.
- `templates/print/partials/shipment_note_body.html:122` — shipment note labels `ASF Flight Manager`.
- `templates/print/partials/customs_note_body.html:5` — customs note includes `Logo ASF`.
- `templates/print/partials/customs_note_body.html:121` — customs note says parcels are X-rayed by Air France security.
- `templates/print/partials/donation_certificate_body.html:15` — donation certificate title is `Responsable de la Messagerie Médicale`.
- `templates/print/partials/donation_certificate_body.html:16` — donation certificate organization is `Aviation Sans Frontieres`.
- `templates/print/partials/donation_certificate_body.html:20` — donation certificate body references shipment through `Aviation Sans Frontières`.
- `templates/print/base_document.html:79` — print footer links to ASF MessMed URL and email.
- `templates/print/base_document.html:82` — print footer says ASF is recognized as public-interest association.
- `templates/print/blocks/signatures.html:4` — default signature label is `Signature ASF`.
- `docs/import/products_template.csv:2` — product import example uses `ASF-000001`.

### Scan, staff, and back-office

- `wms/views_scan_misc.py:19` — scan logout redirects to `https://messmed.pythonanywhere.com/`.
- `templates/scan/includes/scan_sidebar_navigation.html:99` — scan navigation includes `Réception association`.
- `templates/scan/includes/receive_association_create_card.html:39` — receive form label is `Nom de l'association`.
- `templates/scan/includes/receive_association_create_card.html:112` — action says `Enregistrer la réception association`.
- `templates/scan/recipient_validation_detail.html:221` — validation panel title is `Décision ASF`.
- `templates/scan/admin_recipient_organization_detail.html:28` — scan/admin field is `Statut ASF`.
- `templates/scan/includes/admin_contacts_filters_card.html:12` — scan contact search placeholder includes `ASF ID`.
- `wms/forms_admin_contacts_contact.py:72` — admin contact form label is `ASF ID`.
- `wms/forms.py:777` — unknown-product flow exposes `Famille MM/CN`.
- `wms/forms_billing.py:181` — billing override form labels `Association`.
- `wms/models_domain/billing.py:149` — billing model string says billing profile for association.

### Planning and integrations

- `wms/runtime_settings.py:233` — planning flight provider default is `airfrance_klm`.
- `wms/runtime_settings.py:266` — planning origin default is `CDG`.
- `wms/runtime_settings.py:274` — airline code default is `AF`.
- `wms/planning/flight_providers/airfrance_klm.py:14` — default flight API URL is Air France/KLM.
- `wms/planning/flight_providers/airfrance_klm.py:82` — planning flight User-Agent is `ASF-WMS/planning-flight-client`.
- `templates/planning/_version_communications_block.html:32` — planning helper expects local origin `127.0.0.1:38555`.
- `templates/planning/_version_communications_block.html:138` — planning communication logic treats `email_asf` and `email_airfrance` specially.
- `wms/static/wms/planning_communications_helper.js:306` — local helper sends `X-ASF-Planning-Helper`.
- `api/v1/permissions.py:12` — integration API header is `X-ASF-Integration-Key`.
- `api/v1/views.py:244` — integration source header is `X-ASF-Source`.
- `api/v1/views.py:249` — integration target header is `X-ASF-Target`.
- `asf_wms/settings.py:239` — document scan backend defaults to `clamav`.
- `wms/config/installation.py:163` — installation config reports document scan provider from `DOCUMENT_SCAN_BACKEND`.
- `wms/config/installation.py:164` — installation config reports flight provider from `PLANNING_FLIGHT_API_PROVIDER`.
- `wms/config/installation.py:200` — PDF conversion provider defaults to `microsoft_graph`.

### URLs, legal, privacy, and deployment

- `.env.example:39` — example `ORG_NAME` is `Aviation Sans Frontieres`.
- `.env.example:43` — example `SKU_PREFIX` is `ASF`.
- `deploy/pythonanywhere/asf-wms.env.template:24` — generic PythonAnywhere template sets `ORG_NAME='Aviation Sans Frontieres'`.
- `deploy/pythonanywhere/asf-wms.env.template:31` — generic template uses an ASF email as `DEFAULT_FROM_EMAIL`.
- `deploy/pythonanywhere/asf-wms.env.template:46` — generic template uses `BREVO_SENDER_NAME='ASF WMS'`.
- `deploy/pythonanywhere/asf-wms.messmed.env.template:6` — MessMed template uses `messmed.pythonanywhere.com`.
- `deploy/pythonanywhere/asf-wms.messmed.env.template:36` — MessMed template uses `BREVO_SENDER_NAME='ASF WMS'`.
- `README.md:293` — PythonAnywhere setup snippet uses `ORG_NAME=Aviation Sans Frontieres`.
- `README.md:297` — setup snippet uses `SKU_PREFIX=ASF`.
- `docs/policies/mentions-legales.md:3` — legal page is a draft to complete and validate before publication.
- `docs/policies/mentions-legales.md:18` — legal address is `[a completer]`.
- `docs/policies/confidentialite.md:3` — privacy policy is a draft requiring legal/RGPD validation.
- `docs/policies/confidentialite.md:21` — general contact is `[a completer]`.
- `docs/policies/cgu-portail.md:3` — portal CGU are a draft requiring legal validation.
- `docs/policies/cgu-portail.md:165` — operational/support/RGPD/security contacts are placeholders.
- `docs/policies/rgpd.md:222` — RGPD checklist still requires referent/DPO identification and legal-basis validation.

### References, seed data, and initial assumptions

- `contacts/asf_ids.py:7` — generated contact IDs are `ASF-C-<pk>`.
- `wms/policies/shipment_parties.py:5` — default recipient shipper ASF ID is `ASF-ORG-ROOT`.
- `wms/shipment_party_setup.py:12` — priority shipper name is `Aviation Sans Frontieres`.
- `wms/default_shipper_bindings.py:50` — default shipper resolution queries by `organization__asf_id`.
- `wms/default_shipper_bindings.py:80` — default shipper resolution also queries by configured ASF ID.
- `wms/shipment_helpers.py:36` — priority shipper helper compares to `aviation sans frontieres`.
- `wms/shipment_tracking_access.py:131` — tracking identifier label is `ID ASF`.
- `wms/static/scan/import_templates/contacts.csv:1` — import template contains an `asf_id` column.
- `wms/static/scan/import_templates/products.csv:2` — import template example SKU is `ASF-000001`.
- `contacts/fixtures/sample_contacts.json:61` — sample fixture contains `Expediteur Y`.
- `wms/management/commands/seed_planning_demo_data.py:58` — planning demo command is explicitly for local verification.
- `wms/management/commands/seed_local_exhaustive_data.py:10` — local exhaustive seed command is local-only manual QA/e2e data.
- `wms/local_exhaustive_seed.py:554` — local exhaustive seed uses product brand `ASF`.
- `wms/local_exhaustive_seed.py:2651` — local exhaustive tracking events use `actor_structure="ASF"`.
