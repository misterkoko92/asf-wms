# Vocabulary White-Label Inventory Audit

Date: 2026-05-02
PR: PR4 — audit only
Branch: audit/vocabulary-white-label-inventory

## 1. Executive summary

This audit maps user-visible business vocabulary that can prevent ASF-WMS from being presented as a generic humanitarian or associative WMS. It covers Scope C: user-visible wording plus model-layer wording that can surface through forms, admin, choices, generated documents, emails, API-backed UI payloads, or operational messages.

This PR does not implement runtime vocabulary changes. It does not replace strings, add config fields, modify templates, modify Python logic, change tests, rename symbols, or alter behavior. The only intended change is this audit report.

The main vocabulary risks are not limited to a few aviation words. The repository has widespread wording coupling across:

- portal identity for external organizations: `association`, `expéditeur`, `destinataire`, `structure`, `compte association`;
- shipment and warehouse nouns: `commande`, `expédition`, `colis`, `carton`, `réception`;
- aviation and planning vocabulary: `vol`, `escale`, `IATA`, `mise à bord`, `Air France`, `planning`;
- people and role vocabulary: `bénévole`, `correspondant`, `donateur`, `transporteur`, `bénéficiaire`;
- document and trust vocabulary: `donation`, `aide humanitaire`, `douane`, `matériel médical`, `dons humanitaires`;
- API/JS messages that may be displayed by current or future front-end clients.

The repo is blocked by both high-value concentrated surfaces and broad domain coupling. A future PR5 should not try to generalize the whole vocabulary layer. The safest first runtime consumer is a single visible portal label family, probably around `association` as the partner/shipper-facing noun, with the ASF default kept identical and narrow regression tests.

Important finding for PR5: the existing read-only `installation.vocabulary` defaults in `wms/config/installation.py:109-113` are not automatically safe to consume as visible ASF labels. For example, `partner_label="partenaire"` would not preserve current visible ASF wording where the UI says `association`. PR5 must choose an explicit current-ASF default for the exact surface it consumes.

## 2. Scope and exclusions

Included scope:

- visible HTML templates;
- business emails, subjects, and bodies;
- flash messages, validation errors, confirmation messages;
- form labels;
- navigation labels;
- `verbose_name`, `verbose_name_plural`, `help_text`;
- visible choices and enums used in dropdowns or UI;
- Django admin labels when visible to operational teams;
- generated exports and documents;
- API labels when clearly consumed by UI or likely displayed by a front-end.

Excluded by default:

- file names, class names, function names, route names, comments, and test names;
- dev or architecture documentation;
- purely technical routes;
- tests, except when test strings mirror visible UI/email/export content;
- old migrations, except when they still define visible choices used at runtime;
- paused translation scope under `locale/`;
- paused Next/React migration scope under `frontend-next/`.

Identity strings are out of scope as vocabulary findings:

- `ASF`;
- `Aviation Sans Frontières`;
- `Aviation Sans Frontieres`;
- `ASF WMS`;
- `Messagerie Médicale`;
- `MessMed`.

Identity-adjacent phrases are still audited when they contain business vocabulary. For example, `Aviation Sans Frontières` alone is identity and out of scope, but a phrase about `transport`, `expédition`, `colis`, `don`, `matériel médical`, or `douane` remains in vocabulary scope.

## 3. Operational definition of user-visible vs internal vocabulary

For this audit, user-visible wording means any literal or rendered label that can be read by a warehouse user, partner portal user, volunteer, back-office user, admin user, email recipient, print-document recipient, or API-backed UI user.

Operational-user-visible wording appears in daily warehouse or staff workflows. Examples:

- scan navigation labels in `templates/scan/includes/scan_sidebar_navigation.html:58`, `:91`, `:113`, `:137`, `:158`, and `:189`;
- scan dashboard labels such as `Expéditions créées`, `Colis créés`, and `Commandes créées` in `wms/application/scan/dashboard_queries.py:578`, `:584`, and `:596`;
- shipment/tracking terms such as `OK mise à bord` and `Reçu escale` in `wms/application/scan/dashboard_queries.py:82-84`.

Admin-visible wording appears in Django admin, scan admin, form labels, model choices, or validation errors used by staff. Examples:

- contact business types in `wms/forms_admin_contacts_contact.py:13-20`;
- model choices such as `PublicAccountRequestType` in `wms/models_domain/portal.py:135-138`;
- validation errors such as `Le contact d'association doit être une organisation.` in `wms/models_domain/portal.py:220`.

Generated-document-visible wording appears in printed labels, PDFs, customs files, billing documents, or generated packs. Examples:

- `Bon d'expédition` in `wms/print_layouts.py:314`;
- `Dons humanitaires non destinés à être revendus` in `templates/print/partials/packing_list_carton_body.html:7`;
- donation certificate wording in `templates/print/partials/donation_certificate_body.html:20`, `:32`, and `:38`.

Email-visible wording appears in subject producers or email templates. Examples:

- `ASF WMS - Nouvelle commande` in `wms/order_notifications.py:15`;
- `Nouvelle commande portail` in `templates/emails/order_admin_notification_portal.txt:1`;
- `Votre expédition est marquée comme livrée.` in `templates/emails/shipment_delivery_notification.txt:3`.

Internal-only wording is not considered a vocabulary finding by itself. Examples:

- `AssociationProfile` as a class name in `wms/models_domain/portal.py:194` is a code symbol and not itself user-visible;
- `association_profile` as a field or payload key can be technical if it is only an internal contract;
- file paths such as `templates/benevole/` or route names such as `volunteer_urls.py` are not findings by themselves.

Ambiguous wording is wording whose visibility or product meaning is unclear. Examples:

- UI API constants such as `DASHBOARD_WORKFLOW_BLOCKAGE_CATEGORY_LABELS` in `api/v1/ui_views.py:334-345` are likely displayed by a front-end, but also act as API payload content;
- serializer validation messages such as `Choisissez un carton OU creez un colis depuis un produit.` in `api/v1/serializers.py:229` are visible if returned to the UI;
- English model choice labels such as `Per shipment` in `wms/models_domain/billing.py:15` may appear in admin and billing forms, but the exact audience needs confirmation.

## 4. Wording surface map

| Surface / zone | Files or modules inspected | Visibility level | Type of wording | Audit priority | Notes |
|---|---|---:|---|---:|---|
| Public home | `templates/home.html` | High | entry copy, navigation CTA | Medium | Home is a first-contact surface; identity terms are excluded but WMS nouns remain relevant. |
| Portal shell | `templates/includes/secondary_shell_masthead.html`, `templates/includes/secondary_shell_offcanvas.html`, `templates/portal/base.html` | High | navigation, portal titles, account scope labels | High | Concentrated candidate surface for PR5. |
| Portal dashboard/order | `templates/portal/dashboard.html`, `templates/portal/order_create.html`, `templates/portal/includes/order_create_*.html`, `wms/views_portal_orders.py` | High | commands, shipment/order status, logistics instructions | High | Many strings are partner-facing and trust-sensitive. |
| Portal recipient area | `templates/portal/recipients.html`, `templates/portal/recipient_*.html`, portal application helpers | High | recipient, escale, beneficiary, preferences | High | Terms may not map cleanly to all organizations. |
| Scan navigation | `templates/scan/includes/scan_sidebar_navigation.html`, `templates/scan/base.html` | High | operational navigation | High | Daily staff speed and training depend on stable labels. |
| Scan shipment/carton/tracking | `templates/scan/shipment_*.html`, `templates/scan/includes/shipment_*`, `wms/views_scan_shipments.py`, `wms/shipment_tracking_handlers.py`, `wms/static/scan/scan.js` | High | shipment, carton, tracking, confirmation messages | High | Highly coupled to operational truth. |
| Scan contact/admin roles | `templates/scan/includes/admin_contacts_*`, `wms/forms_admin_contacts_contact.py`, `contacts/models.py`, party modules | Medium/High | party roles, legal form, recipient graph labels | High | Model choices and form labels surface to operators. |
| Receipts and inbound flows | `templates/scan/includes/receive_*`, `wms/models_domain/inventory.py`, receipt handlers/forms | High | donation, pallet, association, transporter, donor | High | Intake vocabulary affects operational classification. |
| Volunteer area | `templates/benevole/*`, `wms/views_volunteer*.py`, `wms/forms_volunteer.py`, `wms/models_domain/volunteer.py` | High | volunteer, availability, constraints | Medium | `volunteer_label` exists but is not consumed by UI. |
| Planning cockpit | `templates/planning/*`, `wms/views_planning.py`, `wms/forms_planning.py`, `wms/forms_preparation.py`, `wms/models_domain/planning.py` | Medium/High | flights, volunteers, cartons, planning versions | High | Aviation terms are operationally meaningful for ASF. |
| Planning communications | `wms/planning/legacy_communications.py`, `wms/planning/communication_plan.py`, `templates/planning/_version_communications_block.html` | Medium/High | WhatsApp, Air France, correspondent, expedition subjects | High | May generate external drafts. |
| Generated print/documents | `templates/print/*`, `templates/print/partials/*`, `wms/print_context.py`, `wms/print_layouts.py`, print handlers | High | donation, customs, humanitarian, medical, IATA, shipment labels | High | Legal/trust/regulatory sensitive. |
| Email layer | `templates/emails/*`, email producers in `wms/*`, `wms/signals.py`, `wms/events/handlers_notifications.py` | High | subjects, body copy, flow names | High | PR2/PR3 handled notification config, not vocabulary. |
| Billing | `templates/scan/billing_*.html`, `templates/portal/billing_*.html`, `wms/forms_billing.py`, `wms/models_domain/billing.py` | Medium/High | association billing, shipment units, invoices/corrections | High | Financial copy must be precise. |
| UI API and serializers | `api/v1/ui_views.py`, `api/v1/serializers.py` | Ambiguous/High | payload labels, messages, field names | High | Include displayed labels; keep technical keys out of PR5. |
| Static JS messages | `wms/static/scan/scan.js`, `wms/static/scan/modules/*.js` | High | modal text, placeholders, dynamic labels | Medium | Visible strings are easy to miss outside templates. |
| Installation vocabulary config | `wms/config/installation.py` | Low at runtime, high for future | read-only vocabulary defaults | High | Current defaults are not safe to consume blindly. |

## 5. Findings by surface / zone

### Finding F1: public home WMS copy mixes generic and ASF-default workflow nouns

- Surface: public home.
- Example files: `templates/home.html`.
- Representative wording: `Gestion des stocks, réception de produits et préparation des expéditions` at `templates/home.html:200`; `Demande bénévole` at `templates/home.html:227`.
- Why it matters for white-label: the home page is a first-viewport signal. The identity string `ASF WMS` is out of scope for this audit, but the workflow nouns tell prospective users what kind of product this is. `stock`, `réception`, and `expédition` are probably generic WMS vocabulary; `bénévole` may be organization-type dependent.
- Classification: C. Can be generalized directly.
- Recommended next action: leave out of PR5 unless the first runtime consumer targets a public shell. Treat this as lower risk than portal/account and generated documents.
- PR5 suitability: low. It is visible, but not the best first controlled vocabulary consumer because it mixes product positioning and identity.

### Finding F2: portal shell still presents external users as associations

- Surface: portal shell and portal account.
- Example files: `templates/portal/base.html`, `templates/includes/secondary_shell_masthead.html`, `templates/includes/secondary_shell_offcanvas.html`, `templates/portal/includes/account_intro_card.html`, `templates/portal/includes/account_profile_card.html`.
- Representative wording: `Portail association` at `templates/portal/base.html:7` and `templates/includes/secondary_shell_masthead.html:63`; `Compte association` at `templates/portal/includes/account_intro_card.html:3`; account field label `Association` at `templates/portal/includes/account_profile_card.html:19`.
- Why it matters for white-label: `association` is one of the highest-value visible blockers for a generic humanitarian WMS. Future clients may call this actor an organization, partner, client, shipper, donor, hospital, or project owner.
- Classification: B. Should become vocabulary-configurable later.
- Recommended next action: PR5 should consider one portal-shell/account surface only, with current ASF default exactly `association`.
- PR5 suitability: high. This is concentrated, visible, and can be tested without changing data models.

### Finding F3: portal order flow vocabulary combines orders, parcels, logistics mode, ASF stock, and transport guidance

- Surface: portal order creation and review.
- Example files: `templates/portal/order_create.html`, `templates/portal/includes/order_create_intro_card.html`, `templates/portal/includes/order_create_shipper_inbound_card.html`, `templates/portal/includes/order_create_review_card.html`, `wms/views_portal_orders.py`.
- Representative wording: `Nouvelle commande` at `templates/portal/includes/order_create_intro_card.html:3`; `choisir l'itinéraire` at `templates/portal/includes/order_create_intro_card.html:5`; `stock ASF` at `templates/portal/includes/order_create_shipper_inbound_card.html:9`; `La structure prépare ses propres colis` at `templates/portal/includes/order_create_shipper_inbound_card.html:24`; `Nombre de colis` at `templates/portal/includes/order_create_shipper_inbound_card.html:45`; transport/pallet guidance at `templates/portal/includes/order_create_shipper_inbound_card.html:59-60`.
- Why it matters for white-label: `commande` may be acceptable, but it might really mean `demande`, `request`, `shipment request`, or `order` depending on the future product. `stock ASF` contains identity, but the surrounding concept of client-prepared parcels plus platform stock is vocabulary/product behavior.
- Classification: E. Product decision required / ambiguous / risky.
- Recommended next action: do not make this PR5 unless product chooses a taxonomy for order/request/parcel/source. Keep current ASF behavior and wording until then.
- PR5 suitability: medium only after a decision on `commande` vs `demande`.

### Finding F4: portal recipient vocabulary may not generalize to all humanitarian organizations

- Surface: portal recipient profile, recipient list, recipient preferences.
- Example files: `templates/portal/recipients.html`, `templates/portal/recipient_detail.html`, `templates/portal/recipient_profile.html`, `templates/portal/recipient_scope_home.html`, `templates/portal/recipient_preferences.html`.
- Representative wording: `Fiche destinataire` at `templates/portal/recipient_scope_home.html:4`; `Escale de livraison` at `templates/portal/recipient_profile.html:42`; `Nombre de bénéficiaires` at `templates/portal/recipient_profile.html:61`; `Contact réception escale` at `templates/portal/recipients.html:58`; `Qté par colis (estimation)` at `templates/portal/recipient_preferences.html:41`.
- Why it matters for white-label: `destinataire`, `bénéficiaire`, `patient`, `recipient`, and `structure` are not interchangeable. Changing one label may alter expectations about legal responsibility, medical sensitivity, delivery ownership, and portal permissions.
- Classification: E. Product decision required / ambiguous / risky.
- Recommended next action: keep as audit-only. Future work should decide whether `recipient_label` means receiving organization, end beneficiary, patient, or destination contact.
- PR5 suitability: low until product taxonomy is decided.

### Finding F5: scan navigation uses operational WMS nouns that are reusable but workflow-sensitive

- Surface: scan sidebar and staff shell.
- Example files: `templates/scan/includes/scan_sidebar_navigation.html`.
- Representative wording: group labels `Stocks`, `Réception`, `Préparation`, `Expéditions`, `Contacts`, `Gestion` at `templates/scan/includes/scan_sidebar_navigation.html:58`, `:91`, `:113`, `:137`, `:158`, `:189`; child links `Réception association`, `Préparation expédition`, `Batch expéditions`, `Suivi des expéditions`, `Rôles expédition` at `:99`, `:121`, `:122`, `:144`, `:166`.
- Why it matters for white-label: the labels are visible and repeated daily, but most are core operational WMS terms. Changing them carelessly would add training friction for ASF operators.
- Classification: B. Should become vocabulary-configurable later.
- Recommended next action: do not start with scan navigation in PR5 unless tests lock exact ASF defaults and only one label is consumed.
- PR5 suitability: medium. High visibility, but high operational sensitivity.

### Finding F6: shipment, carton, and tracking wording encodes workflow semantics, not just labels

- Surface: scan shipment creation, dossier, tracking, ready shipments, static JS messages, model status choices.
- Example files: `templates/scan/shipment_tracking.html`, `templates/scan/includes/shipment_create_*`, `templates/scan/shipments_ready.html`, `wms/models_domain/shipment.py`, `wms/static/scan/scan.js`.
- Representative wording: `Suivi expédition` at `templates/scan/shipment_tracking.html:39`; `Escale` and `Photo du colis face IATA` at `templates/scan/shipment_tracking.html:267` and `:284`; `Destination (IATA)` at `templates/scan/shipments_ready.html:63`; `OK mise à bord` and `Reçu correspondant` in `wms/models_domain/shipment.py:232-233`; JS confirmation `Ce colis est déjà affecté... à cette expédition` in `wms/static/scan/scan.js:2356`.
- Why it matters for white-label: `expédition`, `colis`, `carton`, `mise à bord`, `escale`, and `IATA` carry operational meaning. Some are generic WMS concepts; others assume aviation logistics.
- Classification: E. Product decision required / ambiguous / risky.
- Recommended next action: do not collapse these into generic labels before deciding which concepts are true domain entities versus ASF transport vocabulary.
- PR5 suitability: low for first consumer.

### Finding F7: contact and party-role vocabulary is the central reusable vocabulary seam, but risky

- Surface: contact admin forms, shipment-party cockpit, contact model choices.
- Example files: `wms/forms_admin_contacts_contact.py`, `templates/scan/includes/admin_contacts_shipment_cockpit.html`, `contacts/models.py`, `wms/models_domain/shipment_parties.py`.
- Representative wording: form business types `Expéditeur`, `Destinataire`, `Donateur`, `Transporteur`, `Partenaire`, `Bénévole` at `wms/forms_admin_contacts_contact.py:13-20`; `Expéditeurs autorisés` at `wms/forms_admin_contacts_contact.py:105`; `Lecture du registre expéditeurs, structures destinataires, liens autorisés et correspondants d'escale` at `templates/scan/includes/admin_contacts_shipment_cockpit.html:5`; contact capabilities `Donateur`, `Transporteur`, `Benevole`, `Partenaire` at `contacts/models.py:13-17`.
- Why it matters for white-label: these labels map to actual access, shipping, billing, and document roles. They are likely the vocabulary layer's eventual center, but changing them can mislead staff about permissions and responsibility.
- Classification: E. Product decision required / ambiguous / risky.
- Recommended next action: use this finding to design a product vocabulary taxonomy, not as a PR5 implementation target.
- PR5 suitability: low for first consumer, high for later roadmap.

### Finding F8: receipt vocabulary splits donations, pallets, associations, transporters, and donors

- Surface: scan receipt pages and inventory model choices.
- Example files: `templates/scan/includes/receive_association_create_card.html`, `templates/scan/includes/receive_pallet_create_card.html`, `templates/scan/includes/receive_association_workflow_card.html`, `wms/models_domain/inventory.py`.
- Representative wording: `Réception association` at `templates/scan/includes/receive_association_create_card.html:7`; `Nom de l'association` at `:39`; `Ajouter association` and `Ajouter transporteur` at `:114-117`; `Réception palette`, `Ajouter donateur`, `Ajouter transporteur` at `templates/scan/includes/receive_pallet_create_card.html:5`, `:81`, `:84`; receipt choices `Donation`, `Pallet`, `Association` at `wms/models_domain/inventory.py:127-130`.
- Why it matters for white-label: intake classification is operational and billing-relevant. `association` may be a partner, shipper, donor, or client in another installation. `donation` and `pallet` may be true business concepts or ASF-specific intake categories.
- Classification: E. Product decision required / ambiguous / risky.
- Recommended next action: keep current defaults. Future work should separate receipt source type labels from portal partner labels.
- PR5 suitability: low.

### Finding F9: volunteer vocabulary is visible across a dedicated module

- Surface: volunteer portal, volunteer account request, preparateur selection, planning.
- Example files: `templates/benevole/*`, `wms/views_volunteer_auth.py`, `wms/views_volunteer_account_request.py`, `wms/volunteer_access.py`, `templates/scan/preparateur_home.html`.
- Representative wording: `Portail benevole` at `templates/benevole/base.html:7`; `Connexion Bénévole` at `templates/benevole/login.html:7` and `:28`; `Demande de compte bénévole` at `templates/benevole/request_account.html:4` and `:8`; `Choisir un bénévole` at `templates/scan/preparateur_home.html:9`; email subjects such as `ASF WMS - Acces benevole` at `wms/volunteer_access.py:11`.
- Why it matters for white-label: future organizations may call these actors volunteers, couriers, staff, drivers, field operators, or helpers. `installation.vocabulary.volunteer_label` exists but is not consumed.
- Classification: B. Should become vocabulary-configurable later.
- Recommended next action: possible future low-risk surface after partner/association. Preserve ASF default `bénévole`.
- PR5 suitability: medium, but lower business value than association/partner.

### Finding F10: planning cockpit vocabulary is aviation-first and operationally meaningful

- Surface: planning cockpit, planning forms, preparation forms, planning models.
- Example files: `templates/planning/_version_header.html`, `templates/planning/_version_unassigned_block.html`, `wms/forms_planning.py`, `wms/forms_preparation.py`, `wms/models_domain/planning.py`, `wms/planning/flight_providers/airfrance_klm.py`.
- Representative wording: `Mode vols`, `Nb vols utilises`, `Nb colis disponibles`, `Nb benevoles disponibles` at `templates/planning/_version_header.html:47-73`; `Affecter un vol` and `Affecter un benevole` at `templates/planning/_version_unassigned_block.html:42` and `:62`; form labels `Mode vols`, `Batch vols existant`, `Benevole`, `Vol` at `wms/forms_planning.py:42-83`; `Début de la fenêtre de vols à interroger` and `Jours de vol autorisés` at `wms/forms_preparation.py:132-258`; Air France/KLM defaults at `wms/planning/flight_providers/airfrance_klm.py:14-17`.
- Why it matters for white-label: this is not merely wording. Planning currently models flight capacity and volunteer assignments. A generic WMS may need routes, carriers, delivery waves, trucks, containers, or warehouse runs instead of flights.
- Classification: A. Must remain ASF/default wording.
- Recommended next action: keep ASF flight vocabulary until a larger planning product decision is made.
- PR5 suitability: not suitable.

### Finding F11: planning communication drafts expose ASF/Air France/WhatsApp families and shipment subjects

- Surface: planning communication generation and local helper actions.
- Example files: `wms/models_domain/planning.py`, `wms/planning/legacy_communications.py`, `templates/planning/_version_communications_block.html`.
- Representative wording: communication family choices `WhatsApp bénévoles`, `Mail ASF interne`, `Mail Air France`, `Mail Correspondants`, `Mail Expéditeurs`, `Mail Destinataires` at `wms/models_domain/planning.py:66-71`; legacy labels at `wms/planning/legacy_communications.py:30-35`; subject builders `ASF / Expédition ...` and `{party_name} / Expédition ...` at `wms/planning/legacy_communications.py:282-286`; UI actions `Generer tous les WhatsApp` and `Ouvrir WhatsApp` at `templates/planning/_version_communications_block.html:136` and `:236`.
- Why it matters for white-label: these outputs can reach external partners or be copied into operational communication tools. They also couple transport provider and communication channel vocabulary to ASF operations.
- Classification: A. Must remain ASF/default wording.
- Recommended next action: keep as ASF planning preset. Future productization should treat communication templates as a separate template/configuration pack.
- PR5 suitability: not suitable.

### Finding F12: generated print documents contain high-trust legal and logistics vocabulary

- Surface: print templates, print layout catalog, document generation context.
- Example files: `templates/print/partials/donation_certificate_body.html`, `templates/print/partials/shipment_note_body.html`, `templates/print/partials/customs_note_body.html`, `templates/print/partials/packing_list_*.html`, `wms/print_layouts.py`, `wms/print_context.py`.
- Representative wording: `ATTESTATION DE DONATION` at `templates/print/partials/donation_certificate_body.html:7`; `colis`, `expédition`, and `don(s)` at `:20`; `matériel médical et chirurgical envoyés à titre humanitaire` at `:32`; `Valeur uniquement pour la douane` at `:38`; IATA headings at `templates/print/partials/shipment_note_body.html:27-29`; `RESPONSABLE VOL ASF` at `:122`; Air France X-ray statement at `templates/print/partials/customs_note_body.html:123`; layout labels `Bon d'expédition`, `Liste colisage`, `Attestation donation`, `Attestation aide humanitaire`, `Attestation douane`, `Étiquette expédition` at `wms/print_layouts.py:314-320`.
- Why it matters for white-label: document wording is legal, trust-sensitive, and sometimes regulatory. Identity pieces are out of scope, but business terms around donation, customs, medical, shipment, flight, and IATA must not be generalized casually.
- Classification: A. Must remain ASF/default wording.
- Recommended next action: do not touch print vocabulary in PR5. Treat print documents as a later dedicated audit/implementation package.
- PR5 suitability: not suitable.

### Finding F13: business emails include vocabulary beyond the already-configured notification prefix/sender

- Surface: email subjects and text templates.
- Example files: `wms/order_notifications.py`, `wms/signals.py`, `wms/events/handlers_notifications.py`, `templates/emails/*.txt`, volunteer and portal auth views.
- Representative wording: `ASF WMS - Nouvelle commande` at `wms/order_notifications.py:15`; `ASF WMS - Expédition ...` at `wms/events/handlers_notifications.py:49`; `ASF WMS - Suivi correspondant ...` at `wms/signals.py:330`; `Nouvelle commande portail` and `Association` at `templates/emails/order_admin_notification_portal.txt:1` and `:3`; `Votre expédition est marquée comme livrée.` at `templates/emails/shipment_delivery_notification.txt:3`; `Connexion association` at `templates/emails/portal_forgot_password.txt:8`.
- Why it matters for white-label: PR2 and PR3 centralized notification subject prefix and Brevo sender name only. The remaining business vocabulary is still hardcoded in subjects and bodies.
- Classification: B. Should become vocabulary-configurable later.
- Recommended next action: do not mix email vocabulary with the first PR5 if PR5 targets portal UI. A later email vocabulary PR should build on the PR2/PR3 transport boundary.
- PR5 suitability: medium, but better as a separate PR after portal labels.

### Finding F14: billing vocabulary is association- and shipment-centric

- Surface: scan billing editor/settings, portal billing, billing models/forms/document handlers.
- Example files: `templates/scan/billing_editor.html`, `templates/scan/billing_settings.html`, `templates/portal/billing_list.html`, `wms/forms_billing.py`, `wms/models_domain/billing.py`, `wms/billing_document_handlers.py`.
- Representative wording: `surcharges spécifiques aux associations` at `templates/scan/billing_settings.html:13`; `Surcharges association` at `:250`; `Génération de brouillons à partir des expéditions éligibles d'une association` and label `Association` at `templates/scan/billing_editor.html:13` and `:22`; `Consultez vos devis et factures émis par ASF` at `templates/portal/billing_list.html:9`; billing model errors `Receipt source association is required.` and `Shipment shipper association is required.` at `wms/models_domain/billing.py:289-291`; billing rows `Expedition ...` at `wms/billing_document_handlers.py:116` and `:427-428`.
- Why it matters for white-label: billing terms carry legal and financial meaning. A future product may invoice partners, customers, members, shippers, donors, or programs, and the label choice matters.
- Classification: E. Product decision required / ambiguous / risky.
- Recommended next action: keep out of PR5. Decide billing actor vocabulary separately from portal actor vocabulary.
- PR5 suitability: low.

### Finding F15: model-layer choices and validation labels can surface to users through admin/forms/API

- Surface: Django model choices, admin-visible values, form selections, validation errors.
- Example files: `contacts/models.py`, `wms/models_domain/portal.py`, `wms/models_domain/shipment.py`, `wms/models_domain/inventory.py`, `wms/models_domain/billing.py`.
- Representative wording: contact capabilities at `contacts/models.py:13-17`; legal form `Association` at `contacts/models.py:21-22`; `PublicAccountRequestType` labels at `wms/models_domain/portal.py:135-138`; portal access roles at `wms/models_domain/portal.py:256-258`; receipt choices at `wms/models_domain/inventory.py:127-130`; shipment statuses and roles at `wms/models_domain/shipment.py:21-27` and `:228-241`; billing choices such as `Per shipment` and `Shipped units` at `wms/models_domain/billing.py:14-34`.
- Why it matters for white-label: choices are often rendered by `get_FOO_display()` in templates/admin/API. Changing them at the model layer can alter many surfaces at once and may change semantics, not just wording.
- Classification: E. Product decision required / ambiguous / risky.
- Recommended next action: prefer UI-level formatting before model-level semantic changes. Do not rename choices or database values in PR5.
- PR5 suitability: low.

### Finding F16: UI API and static JS contain visible labels that are easy to miss

- Surface: UI API payloads, serializers, scan static JavaScript.
- Example files: `api/v1/ui_views.py`, `api/v1/serializers.py`, `wms/static/scan/scan.js`, `wms/static/scan/modules/cartons-ready.js`.
- Representative wording: dashboard API labels `OK mise a bord -> Recu escale`, `Creation expedition`, `Commande`, `Debloquer creation expedition` at `api/v1/ui_views.py:324-345`; API messages `Expedition introuvable.`, `Expedition creee.`, `Commande envoyee.`, `Escale de livraison requise.` at `api/v1/ui_views.py:1144`, `:1547`, `:2272`, `:2368`; serializer error `Choisissez un carton OU creez un colis depuis un produit.` at `api/v1/serializers.py:229`; JS strings `Ce colis est déjà affecté...`, `Entrer un produit ou choisir un colis prêt`, `Colis prepare` at `wms/static/scan/scan.js:2356`, `:2511`, `:2680`; module message text in `wms/static/scan/modules/cartons-ready.js:176`.
- Why it matters for white-label: a future front end may display API labels directly, while JS strings are definitely user-visible. API field names may be technical contracts, but labels/messages require audit.
- Classification: E. Product decision required / ambiguous / risky.
- Recommended next action: treat UI API labels as displayed unless proven otherwise; do not rename payload keys in PR5.
- PR5 suitability: low to medium only for a very narrow displayed message.

### Finding F17: medical, humanitarian, donation, and beneficiary vocabulary defines product positioning

- Surface: generated documents, contact profile fields, recipient portal, print context, order documents.
- Example files: `templates/print/partials/donation_certificate_body.html`, `templates/print/partials/packing_list_*.html`, `wms/print_context.py`, `contacts/models.py`, `wms/models_domain/portal.py`, `templates/portal/recipient_profile.html`.
- Representative wording: `matériel médical et chirurgical envoyés à titre humanitaire` at `templates/print/partials/donation_certificate_body.html:32`; `Dons humanitaires non destinés à être revendus` at `templates/print/partials/packing_list_carton_body.html:7`; print context defaults `Aide humanitaire` and `Materiel medical` at `wms/print_context.py:364`, `:575-576`; model fields `beneficiary_count` and `is_humanitarian_attestation_exempt` at `contacts/models.py:57-58`; order document type `Attestation aide humanitaire` at `wms/models_domain/portal.py:825`.
- Why it matters for white-label: these terms may be core product positioning for humanitarian logistics, but they may also be ASF/Messagerie Médicale defaults. Replacing them could affect donor trust, customs interpretation, and medical/privacy expectations.
- Classification: E. Product decision required / ambiguous / risky.
- Recommended next action: require product/legal judgment before any runtime consumer touches this family.
- PR5 suitability: not suitable.

## 6. Classification A-E

Each finding family from Section 5 appears exactly once below.

| Classification | Finding family | Surface | Rationale | Suggested action |
|---|---|---|---|---|
| C | F1: public home WMS copy | Public home | The WMS nouns are mostly generic and not tied to model semantics, while identity is out of scope. | Generalize later if home/shell gets an identity pass; not PR5. |
| B | F2: portal shell association labels | Portal shell/account | Visible concentrated labels should likely be driven by vocabulary config later. | Best PR5 candidate, one label family only. |
| E | F3: portal order flow | Portal order | `commande`, parcel source, ASF stock, and transport instructions require product taxonomy decisions. | Decide order/request/source vocabulary before implementation. |
| E | F4: portal recipient vocabulary | Portal recipient | Recipient/beneficiary/patient/structure labels are not safely interchangeable. | Product decision before changes. |
| B | F5: scan navigation WMS nouns | Scan nav | Operational terms may become configurable, but defaults must remain stable. | Later narrow PR with scan UI tests. |
| E | F6: shipment/carton/tracking vocabulary | Scan shipment/tracking | Terms encode workflow and aviation status semantics. | Keep current behavior; do not use as first consumer. |
| E | F7: contact and party-role vocabulary | Scan contact/admin/model | Central vocabulary seam but tied to permissions, party graph, and billing. | Design taxonomy first; UI labels before model changes. |
| E | F8: receipt vocabulary | Receipt/inbound | Intake types affect operations and billing. | Separate source-type labels from partner labels. |
| B | F9: volunteer vocabulary | Volunteer/scan/planning | Existing vocabulary field suggests later configurability; visible module is bounded. | Candidate after partner/association. |
| A | F10: planning cockpit aviation vocabulary | Planning | Flight vocabulary matches current ASF operations and changing it would alter semantics. | Keep ASF defaults; larger planning product decision later. |
| A | F11: planning communications | Planning communications | ASF/Air France/WhatsApp drafts are current operational presets. | Dedicated communication-template productization later. |
| A | F12: generated print documents | Print/documents | Legal, customs, donation, medical, IATA, and flight terms must remain ASF defaults. | Dedicated print/legal audit before runtime changes. |
| B | F13: business email vocabulary | Emails | Business nouns should become configurable later, separate from prefix/sender config. | Later email vocabulary PR; keep PR5 UI-only. |
| E | F14: billing vocabulary | Billing | Financial/legal actor vocabulary is product-sensitive. | Decide billing actor taxonomy separately. |
| E | F15: model-layer choices | Models/forms/admin | Model choices can surface broadly and may define semantics. | Avoid model-level changes in first runtime consumer. |
| E | F16: UI API and static JS labels | API/JS | API visibility is mixed; JS is visible; payload keys are contracts. | Treat labels as visible but do not rename keys. |
| E | F17: medical/humanitarian/donation vocabulary | Documents/contacts/portal | Product positioning, legal, donor, customs, and medical implications. | Human product/legal decision required. |

## 7. High-priority candidates for PR5

PR5 should be intentionally small: one user-visible surface, one vocabulary field, default ASF value identical to current behavior, no mass replacement, and dedicated tests.

| Candidate | Surface | Proposed vocabulary key | Default ASF value | Why this is safe or useful | Risks |
|---|---|---|---|---|---|
| Recommended: portal partner noun for `association` | Portal shell/account only: `Portail association`, `Compte association`, account label `Association` | `installation.vocabulary.partner_label` or a more explicit `portal_partner_label` | `association` | High visible white-label value, concentrated templates, no DB/model rename required. | Existing config default is `partenaire`, so consuming it blindly would change ASF behavior. PR5 must resolve the default mismatch first and test exact strings. |
| Secondary: portal shipper noun | Portal FAQ/shell references to `expéditeur` scope | `installation.vocabulary.shipper_label` | `expéditeur` | Aligns with existing domain field and portal scope. | May not fix the highest blocker because `association` remains. Needs casing/accent rules. |
| Secondary: volunteer noun | Volunteer portal title/login/request labels | `installation.vocabulary.volunteer_label` | `bénévole` | Bounded module and relatively low semantic blast radius. | Lower white-label value than partner labels; planning/preparateur also use volunteer terms, so surface must be strictly limited. |
| Avoid for PR5: `commande` | Portal orders/dashboard | `installation.vocabulary.order_label` | `commande` | Would address a widespread term. | Key does not exist; product has not decided order vs request vs shipment request; touches many flows. |
| Avoid for PR5: `expédition` | Scan/portal/tracking/documents/API | `installation.vocabulary.shipment_label` | `expédition` | High-volume term. | Too broad and semantics-heavy; documents, statuses, APIs, planning, and billing all depend on it. |

Recommended PR5 direction: use the portal shell/account `association` label family only, and make the ASF default exactly match the current visible string. If the existing `partner_label` key is used, update its default and tests in PR5 before consuming it. If product wants `partner_label` to stay generic (`partenaire`), add a more precise future key instead, such as `portal_partner_label`, with default `association`.

## 8. Terms explicitly out of scope because identity-related

Pure identity terms encountered:

- `ASF`, for example in public copy, emails, print logo alt text, and admin validation text.
- `ASF WMS`, for example in `templates/home.html:6`, email subjects, and signatures.
- `Aviation Sans Frontières` / `Aviation Sans Frontieres`, for example in print-document identity lines.
- `Messagerie Médicale`, for example in donation certificate role/title wording.

These are not classified as vocabulary findings by themselves. They belong to `installation.identity` or a future identity/legal audit.

Identity-adjacent phrases that remain vocabulary-relevant:

- `stock ASF` in `templates/portal/includes/order_create_shipper_inbound_card.html:9`: `ASF` is identity, but the concept of platform stock versus partner-prepared parcels is vocabulary/product behavior.
- `RESPONSABLE VOL ASF` in `templates/print/partials/shipment_note_body.html:122`: `ASF` is identity, but `vol` and flight-manager wording are aviation vocabulary.
- donation certificate phrasing in `templates/print/partials/donation_certificate_body.html:20`: organization identity is out of scope, but `colis`, `expédition`, and `don(s)` are vocabulary.
- public account validation copy in `templates/scan/includes/public_account_request_intro.html:8-12`: `ASF` is identity, but `compte expéditeur` and account role language are vocabulary.

## 9. Risky or ambiguous E decisions requiring human product judgment

1. Should the external portal actor be called `association`, `partenaire`, `organisation`, `expéditeur`, `client`, or something else?
   - Unblocks: safe PR5 selection for the portal shell/account label.

2. Should `commande` mean a true order, a shipment request, a logistics request, or a partner demand?
   - Unblocks: future portal dashboard/order vocabulary without changing workflow semantics.

3. Is `destinataire` the receiving organization, the final beneficiary, the patient, or the delivery contact?
   - Unblocks: recipient profile and preference wording.

4. Is `bénéficiaire` appropriate for all recipient organizations, or only for certain humanitarian contexts?
   - Unblocks: recipient form fields and generated documents.

5. Is `bénévole` a core product module term, or should future deployments call this actor helper, courier, staff, driver, or operator?
   - Unblocks: volunteer-label consumption after PR5.

6. Are `expédition`, `colis`, and `carton` stable product-wide nouns, or should they vary by installation?
   - Unblocks: scan/portal/API label strategy.

7. Is aviation vocabulary (`vol`, `escale`, `IATA`, `mise à bord`) an ASF-only operational preset or a mandatory product capability?
   - Unblocks: planning and tracking white-label strategy.

8. Should generated donation/customs/humanitarian documents be part of a generic product pack or an ASF-specific document pack?
   - Unblocks: print-document productization without legal drift.

9. Is medical/humanitarian wording core positioning for the product, or should it be configurable per organization?
   - Unblocks: document and portal copy around medical supplies, humanitarian attestations, and donor trust.

10. Should billing actors follow portal vocabulary (`association`/`partner`) or use legal/financial vocabulary (`client`, `customer`, `account`)?
    - Unblocks: billing label and document changes.

11. Are Django admin labels important for white-label presentation, given operational teams may use admin or scan-admin pages?
    - Unblocks: whether model choice labels need runtime vocabulary or can stay as legacy internals.

12. Which API strings are display labels versus technical contracts for future front-end consumers?
    - Unblocks: safe UI API label formatting without breaking payload keys.

13. Should existing `installation.vocabulary` defaults represent current ASF visible wording or generic target product wording?
    - Unblocks: safe consumption of `partner_label`, `volunteer_label`, `shipper_label`, and `recipient_label`.

## 10. Recommended implementation strategy for the first vocabulary runtime consumer

Use a conservative PR5:

- choose one surface only, preferably portal shell/account labels around `association`;
- introduce or consume one vocabulary key only;
- keep the default ASF visible value identical to current production wording;
- consume from `installation.vocabulary`;
- add narrow regression tests that assert the exact rendered ASF default strings;
- do not migrate all strings;
- do not rename code symbols, classes, routes, fields, payload keys, tests, or files;
- do not alter database choices unless explicitly required and separately tested;
- prefer UI-level label formatting before model-level semantic changes;
- keep `wms/config/installation.py` as a leaf dependency;
- avoid mixing identity work with vocabulary work;
- avoid mixing email vocabulary with portal UI vocabulary in the same PR;
- explicitly handle casing, accents, pluralization, and gender at the surface level.

PR5 must not blindly consume the current `partner_label="partenaire"` default for current `association` strings. That would violate the "preserve current ASF behavior" constraint. Either the key default must be aligned with the exact current ASF visible wording for the chosen surface, or a more precise key must be introduced with an ASF-compatible default.

## 11. Non-goals

This audit does not:

- implement vocabulary config;
- change visible strings;
- rename code;
- rename models, fields, choices, routes, classes, functions, or variables;
- migrate data;
- alter email sender or subject-prefix behavior from PR2/PR3;
- address `sender_email` or `reply_to_email`;
- address identity configuration;
- address logo, legal identity, signatory, or organization contact identity;
- restart translation/i18n work;
- define the final white-label product taxonomy;
- decide whether future clients should use aviation planning, volunteer coordination, billing, or document packs;
- change runtime behavior.

## 12. Open questions

1. Should PR5 use existing `installation.vocabulary.partner_label`, or should it introduce a more specific portal key?
   - Unblocks: the exact implementation shape for the first runtime consumer.

2. If `partner_label` is used, should the ASF default be `association` rather than the current read-only default `partenaire`?
   - Unblocks: preserving current ASF behavior while consuming config.

3. Should portal users see themselves primarily as `associations`, `expéditeurs`, or `partenaires`?
   - Unblocks: portal shell/account wording.

4. Should `compte association` and `Portail association` be governed by the same vocabulary key?
   - Unblocks: how narrow PR5 can safely be.

5. Is `commande` the long-term product word for portal submissions?
   - Unblocks: future portal order/dashboard wording.

6. Should `destinataire` describe a recipient organization, a recipient contact, or both?
   - Unblocks: recipient profile and access-scope labels.

7. Are `correspondant` and `contact réception escale` ASF-specific labels or generic logistics roles?
   - Unblocks: contact-party taxonomy and tracking labels.

8. Should `donateur` remain a first-class contact capability for generic deployments?
   - Unblocks: contact forms and receipt intake labels.

9. Should the volunteer module remain visible in every installation, or become a feature/capability with its own vocabulary?
   - Unblocks: volunteer-label runtime consumption and feature-flag presentation.

10. Should print document vocabulary be configurable by installation or by document template pack?
    - Unblocks: safe document productization.

11. Should UI API response labels be generated from the same vocabulary layer as HTML templates?
    - Unblocks: API/UI consistency without changing technical field names.

12. Should billing actor vocabulary follow portal vocabulary, or have its own legal/financial terms?
    - Unblocks: billing white-label plan.

13. Is aviation planning a permanent ASF preset or a configurable transport mode?
    - Unblocks: planning vocabulary and future feature-flag work.

## 13. Evidence appendix

Search strategy:

- Read repository reference and guardrails before audit: `docs/repo-reference/README.md`, relevant `00`, `01`, `02`, `03x`, `04` files, and `docs/policies/agent-guardrails.md`.
- Started with the requested targeted search over terms such as `aviation`, `aérien`, `vol`, `IATA`, `association`, `bénévole`, `humanitaire`, `colis`, `expédition`, `commande`, `transport`, `patient`, and `médical`.
- Narrowed by likely visibility instead of listing every occurrence.
- Inspected templates, model choices, forms, scan JS, UI API labels/messages, emails, billing, print documents, and planning modules.
- Excluded docs, tests, migrations, cache files, static vendor files, locale files, and Next/React migration scope unless the surface mirrored visible runtime content.

Representative evidence by area:

| Area | Evidence | Included / excluded note |
|---|---|---|
| Installation vocabulary | `wms/config/installation.py:37-41`, `:109-113` | Included because this is the future vocabulary domain, even though it is not runtime-consumed for labels. |
| Public home | `templates/home.html:200`, `:227` | Included because public first screen is visible. Identity `ASF WMS` is excluded as identity. |
| Portal shell | `templates/portal/base.html:7`, `templates/includes/secondary_shell_masthead.html:61-66`, `:173-185` | Included because navigation and page titles are partner-visible. |
| Portal account | `templates/portal/includes/account_intro_card.html:3`, `templates/portal/includes/account_profile_card.html:19` | Included because account labels are visible to external users. |
| Portal dashboard | `templates/portal/dashboard.html:4-50`, `:100` | Included because dashboard labels are visible to partner users. |
| Portal order flow | `templates/portal/includes/order_create_intro_card.html:3-5`, `templates/portal/includes/order_create_shipper_inbound_card.html:9`, `:24`, `:45`, `:59-60`, `templates/portal/includes/order_create_review_card.html:46`, `:75`, `:80` | Included because order creation is an external workflow. |
| Portal recipient | `templates/portal/recipient_profile.html:42`, `:61`, `templates/portal/recipients.html:58`, `:100`, `:125`, `templates/portal/recipient_preferences.html:24`, `:41` | Included because recipient labels are visible and product-sensitive. |
| Scan sidebar | `templates/scan/includes/scan_sidebar_navigation.html:58`, `:91`, `:113`, `:137`, `:158`, `:189` | Included because it is the primary operational navigation. |
| Scan shipment | `templates/scan/shipment_tracking.html:39`, `:267-284`, `templates/scan/shipments_ready.html:26`, `:61-65`, `:116` | Included because staff and tracking users see it. |
| Scan contact roles | `wms/forms_admin_contacts_contact.py:13-20`, `:52`, `:67`, `:105`, `templates/scan/includes/admin_contacts_shipment_cockpit.html:5`, `:51`, `:95`, `:130`, `:227`, `:267` | Included because scan admin is visible to operational teams. |
| Receipt intake | `templates/scan/includes/receive_association_create_card.html:7`, `:39`, `:112-117`, `templates/scan/includes/receive_pallet_create_card.html:5`, `:81-84`, `templates/scan/includes/receive_association_workflow_card.html:3`, `:14`, `:31` | Included because receipt wording affects classification and workflow. |
| Volunteer portal | `templates/benevole/base.html:7`, `templates/benevole/login.html:7`, `:28`, `templates/benevole/request_account.html:4`, `:8-9`, `templates/benevole/request_account_done.html:9` | Included because volunteer users see the portal. |
| Preparateur volunteer selection | `templates/scan/preparateur_home.html:9`, `:11`, `wms/pack_handlers.py:417`, `:687` | Included because scan operators/preparateurs see the volunteer term. |
| Planning cockpit | `templates/planning/_version_header.html:47-73`, `templates/planning/_version_unassigned_block.html:6`, `:42`, `:62`, `wms/forms_planning.py:42-83`, `wms/forms_preparation.py:132-138`, `:258`, `:275-278` | Included because planning users see aviation and volunteer allocation terms. |
| Planning communications | `wms/models_domain/planning.py:66-71`, `wms/planning/legacy_communications.py:30-35`, `:282-286`, `templates/planning/_version_communications_block.html:136`, `:236`, `:246` | Included because drafts/actions can be operator-visible and externally copied. |
| Flight provider | `wms/planning/flight_providers/airfrance_klm.py:14-17`, `:82`, `wms/runtime_settings.py:266-275` | Included as product/transport vocabulary and provider assumption. Not proposed for PR5. |
| Print documents | `templates/print/partials/donation_certificate_body.html:7`, `:15-20`, `:32`, `:38`, `templates/print/partials/shipment_note_body.html:27-29`, `:74`, `:111`, `:122`, `templates/print/partials/customs_note_body.html:123` | Included because generated documents are high-trust external artifacts. |
| Print layout catalog | `wms/print_layouts.py:53-55`, `:100-135`, `:314-320`, `:351`, `:449` | Included because template editor/layout choices can display these labels. |
| Print context defaults | `wms/print_context.py:362-364`, `:574-576` | Included because defaults appear in generated documents or previews. |
| Emails | `wms/order_notifications.py:15-16`, `wms/events/handlers_notifications.py:49`, `:103`, `wms/signals.py:157`, `:292`, `:330`, `:471`, `templates/emails/order_admin_notification_portal.txt:1-3`, `templates/emails/shipment_delivery_notification.txt:3`, `templates/emails/account_request_approved.txt:4`, `:8` | Included because subjects/bodies are recipient-visible. Identity prefix is out of scope except surrounding vocabulary. |
| Billing | `templates/scan/billing_settings.html:13`, `:250`, `templates/scan/billing_editor.html:13`, `:22`, `:70`, `:145`, `templates/portal/billing_list.html:9`, `wms/forms_billing.py:274-275`, `:329`, `wms/models_domain/billing.py:289-299`, `wms/billing_document_handlers.py:116`, `:427-428` | Included because financial wording is user/admin-visible and legally meaningful. |
| Contact model choices | `contacts/models.py:13-22`, `:57-59`, `:131` | Included because choices can render in forms/admin and IDs are identity-adjacent. |
| Portal model choices | `wms/models_domain/portal.py:135-138`, `:220-222`, `:256-258`, `:823-827` | Included because choices/errors can surface through admin/forms/API. |
| Shipment model choices | `wms/models_domain/shipment.py:21-27`, `:38`, `:47`, `:228-241` | Included because status and role displays are visible. |
| Inventory model choices | `wms/models_domain/inventory.py:120-130`, `:179`, `:281-291` | Included because receipt choices and donor sequences affect admin/forms/exports. |
| UI API labels/messages | `api/v1/ui_views.py:324-345`, `:1144-1146`, `:1547`, `:1758`, `:2170`, `:2272`, `:2368-2370`, `api/v1/serializers.py:229`, `:304-306` | Included when likely displayed by UI. Technical payload keys are not implementation targets. |
| Static JS messages | `wms/static/scan/scan.js:895`, `:1485`, `:1651`, `:2356`, `:2511`, `:2557-2559`, `:2680`, `wms/static/scan/modules/cartons-ready.js:176`, `:300` | Included because these are browser-visible strings. |
| Internal-only examples | class names such as `AssociationProfile`, file names under `templates/benevole/`, route names, comments, tests, migrations | Excluded unless the same string is rendered by a visible surface. |

Documentation impact check:

- This PR is the documentation artifact requested by the audit task.
- No runtime behavior changed.
- No user-visible workflow changed.
- No roles, permissions, access rules, shared service boundaries, model meanings, deployment expectations, or security behavior changed.
- No repository reference update is required because this audit does not alter architecture, contracts, routes, workflows, or runtime behavior.
