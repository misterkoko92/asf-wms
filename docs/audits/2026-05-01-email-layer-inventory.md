# Audit couche email ASF-WMS - inventaire sujets et points d'envoi

Date: 2026-05-01

Branche d'audit: `codex/email-layer-inventory`

Classification AGENTS.md: B. capacite reutilisable generique, E. reduction de dette legacy. L'audit prepare une future consommation controlee de `wms/config/installation.py` sans changement runtime.

## 0. Méthode de recherche

Commandes et recherches utilisees:

- `git status --short` puis `git log --oneline -5` avant audit: working tree propre, tete de `main` au commit `0978b70a`.
- `rg -n "send_mail|EmailMessage|EmailMultiAlternatives|mail_admins|mail_managers|get_connection" .`
- `rg -n "DEFAULT_FROM_EMAIL|SERVER_EMAIL|EMAIL_BACKEND|EMAIL_SUBJECT_PREFIX|BREVO|brevo|Brevo|sendinblue|Sendinblue|sib_api" .`
- `rg -n "subject" wms asf_wms templates api --glob '*.py' --glob '*.html' --glob '*.txt'`
- `rg -n "enqueue_email|send_.*email|email_.*send|process_email|EmailQueue|outbox|IntegrationEvent|notification|notify" wms asf_wms api --glob '*.py'`
- `rg -n "send_email_safe\\(|enqueue_email_safe\\(|send_or_enqueue_email_safe\\(|enqueue_email\\(|send_volunteer_access_email\\(|send_portal_order_notifications\\(|send_public_order_notifications\\(|notify_preparateur_product_review_needed\\(" wms api --glob '*.py'`
- `rg -n "render_to_string\\(|emails/" wms templates --glob '*.py' --glob '*.html' --glob '*.txt'`
- `rg --files templates/emails`
- `rg -n "ASF WMS|subject|payload__subject|call_args\\.kwargs\\[\\\"subject\\\"\\]|RECOVERY_EMAIL_SUBJECT|SUBJECT_|VOLUNTEER_.*SUBJECT" wms/tests api/tests --glob '*.py'`
- Lectures ciblees avec numeros de ligne: `wms/emailing.py`, `wms/signals.py`, `wms/events/handlers_notifications.py`, producteurs d'email, settings, runtime settings, jobs, templates email, planning communications.

Couverture:

- Les appels directs Django (`send_mail`) sont couverts.
- Les abstractions maison (`send_email_safe`, `send_or_enqueue_email_safe`, `enqueue_email_safe`) sont couvertes.
- Les producteurs par vue, action admin, signal modele, handler runtime event, API et job queue sont couverts.
- Les templates sous `templates/emails/` sont couverts.
- Les sujets de communications planning sont couverts comme angle mort: ils construisent des payloads/action helper `email`, mais aucun envoi Django/Brevo direct n'a ete trouve.

Limites:

- Audit en lecture statique uniquement; aucun test ni envoi email reel execute.
- Les recipients reels dependent des donnees de production et des groupes Django.
- `wms/static/wms/planning_communications_helper.js` peut transmettre des payloads `action: "email"` a un helper local externe; aucun transport email serveur n'a ete trouve dans le repo. `hypothèse à vérifier`

Resultats negatifs explicites:

- Aucun usage runtime trouve de `EmailMessage`, `EmailMultiAlternatives`, `mail_admins`, `mail_managers` ou `get_connection`.
- Aucun setting `EMAIL_SUBJECT_PREFIX` trouve.
- Aucun setting `SERVER_EMAIL` trouve.
- Aucune occurrence `sendinblue`, `Sendinblue` ou `sib_api` trouvee dans le code runtime.
- Aucun webhook entrant/sortant envoyant un email n'a ete trouve.

## 1. Inventaire des points d'envoi d'email

### Socle technique d'envoi

| fichier:ligne | fonction/classe | mécanisme | destinataire(s) typique(s) | déclencheur |
|---|---|---|---|---|
| `wms/emailing.py:382` | `_send_with_brevo` | autre, Brevo API HTTP | utilisateur final, admin, partenaire externe, bénévole, expéditeur, destinataire | autre, appele par `send_email_safe` |
| `wms/emailing.py:419` | `send_email_safe` | abstraction maison | utilisateur final, admin, partenaire externe, bénévole, expéditeur, destinataire | action utilisateur, action admin, signal modèle, API, cron/job |
| `wms/emailing.py:438` | `send_email_safe` | `django.core.mail.send_mail` | utilisateur final, admin, partenaire externe, bénévole, expéditeur, destinataire | fallback apres echec/absence Brevo |
| `wms/emailing.py:479` | `enqueue_email_safe` | abstraction maison, queue/outbox, direct en `EMAIL_DELIVERY_MODE=direct_only` | utilisateur final, admin, partenaire externe, bénévole, expéditeur, destinataire | action utilisateur, action admin, signal modèle, API |
| `wms/emailing.py:293` | `_send_event_payload` | abstraction maison, job | utilisateur final, admin, partenaire externe, bénévole, expéditeur, destinataire | cron/job via `process_email_queue` |
| `wms/jobs/email_queue.py:24`, `wms/management/commands/process_email_queue.py:47` | `run_email_queue_job`, `Command.handle` | job | utilisateur final, admin, partenaire externe, bénévole, expéditeur, destinataire | cron/job, commande management |

### Producteurs métier

| fichier:ligne | fonction/classe | mécanisme | destinataire(s) typique(s) | déclencheur |
|---|---|---|---|---|
| `wms/account_request_handlers.py:430` | `_queue_account_request_emails` | abstraction maison | admin | action utilisateur, formulaire public de demande de compte, `transaction.on_commit` |
| `wms/account_request_handlers.py:435` | `_queue_account_request_emails` | abstraction maison | utilisateur final, partenaire externe | action utilisateur, formulaire public de demande de compte, `transaction.on_commit` |
| `wms/admin_account_request_approval.py:184` | `approve_account_request` | abstraction maison, action admin | utilisateur final | action admin, validation compte utilisateur WMS |
| `wms/admin_account_request_approval.py:264` | `approve_account_request` | abstraction maison, action admin | partenaire externe, expéditeur, destinataire | action admin, validation compte portail |
| `wms/public_order_handlers.py:142` | `send_public_order_notifications` | abstraction maison | admin | action utilisateur, commande publique |
| `wms/public_order_handlers.py:152` | `send_public_order_notifications` | abstraction maison | partenaire externe, expéditeur | action utilisateur, commande publique |
| `wms/order_notifications.py:82` | `send_portal_order_notifications` | abstraction maison | admin | action utilisateur, API, commande portail |
| `wms/order_notifications.py:98` | `send_portal_order_notifications` | abstraction maison | partenaire externe, expéditeur | action utilisateur, API, commande portail |
| `wms/events/handlers_notifications.py:48` | `handle_shipment_status_changed_event` | signal, abstraction maison | admin | signal modèle, changement statut expédition |
| `wms/signals.py:156` | `_notify_shipment_delivery` | signal, abstraction maison | partenaire externe, destinataire | signal modèle, expédition livrée |
| `wms/signals.py:266` | `_queue_deduped_email` | signal, abstraction maison | expéditeur, destinataire | signal modèle, changement statut expédition vers statut notifiable |
| `wms/signals.py:329` | `_queue_shipment_correspondant_notification` | signal, abstraction maison | admin, partenaire externe, destinataire | signal modèle, expédition planifiée ou événement de suivi correspondant |
| `wms/events/handlers_notifications.py:102` | `handle_tracking_event_created_event` | signal, abstraction maison | admin | signal modèle, événement de suivi expédition créé |
| `wms/events/handlers_notifications.py:114` | `handle_tracking_event_created_event` | signal | admin, partenaire externe, destinataire | signal modèle, événement de suivi `BOARDING_OK`, delegue vers `_queue_shipment_correspondant_notification` |
| `wms/signals.py:470` | `_notify_order_status_change` | signal, abstraction maison | admin, partenaire externe, expéditeur, destinataire | signal modèle, changement statut/revue commande |
| `wms/views_portal_auth.py:197` | `_send_recovery_email` | abstraction maison | utilisateur final, partenaire externe | action utilisateur, mot de passe portail |
| `wms/views_volunteer_auth.py:167` | `_send_recovery_email` | abstraction maison | bénévole | action utilisateur, mot de passe bénévole |
| `wms/views_shipment_tracking_access.py:349` | `_send_tracking_access_recovery_email` | abstraction maison | bénévole, expéditeur, destinataire, partenaire externe | action utilisateur, récupération accès suivi expédition |
| `wms/views_scan_shipments.py:1066` | `_send_pending_tracking_access_email` | abstraction maison | bénévole, expéditeur, destinataire, partenaire externe | action utilisateur, création compte de suivi en attente |
| `wms/pack_handlers.py:192` | `notify_preparateur_product_review_needed` | abstraction maison | admin | action utilisateur, préparateur crée un produit incomplet |
| `wms/views_volunteer_account_request.py:89` | `_notify_admins_of_request` | abstraction maison | admin | action utilisateur, demande de compte bénévole |
| `wms/views_volunteer_account_request.py:103` | `_notify_requester_of_request` | abstraction maison | bénévole | action utilisateur, demande de compte bénévole |
| `wms/volunteer_account_request_handlers.py:94` | `approve_volunteer_account_request` | abstraction maison, action admin | bénévole | action admin, approbation demande bénévole |
| `wms/volunteer_access.py:64` | `send_volunteer_access_email` | abstraction maison, action admin | bénévole | action admin, `VolunteerProfileAdmin.send_access_email` a `wms/admin.py:1349` |

Categories sans envoi direct trouve:

- `EmailMessage`: aucun envoi direct.
- `EmailMultiAlternatives`: aucun envoi direct.
- `mail_admins` / `mail_managers`: aucun envoi direct.
- `get_connection`: aucun usage.
- Webhook: aucun envoi email declenche directement par webhook trouve.

## 2. Inventaire des subjects

| point d'envoi | subject actuel | construction actuelle | préfixe existant | source du préfixe | vocabulaire métier renommable |
|---|---|---|---|---|---|
| `wms/account_request_handlers.py:430` | `ASF WMS - Nouvelle demande de compte` | literal `gettext` | `ASF WMS -` | hardcodé | compte |
| `wms/account_request_handlers.py:435` | `ASF WMS - Demande de compte reçue` | literal `gettext` | `ASF WMS -` | hardcodé | compte |
| `wms/admin_account_request_approval.py:184` | `ASF WMS - Compte utilisateur valide` | literal `gettext` | `ASF WMS -` | hardcodé | compte, utilisateur |
| `wms/admin_account_request_approval.py:264` | `ASF WMS - Compte valide` | literal `gettext` | `ASF WMS -` | hardcodé | compte |
| `wms/public_order_handlers.py:23`, envoye a `:142` | `ASF WMS - Nouvelle commande publique` | constante module `SUBJECT_PUBLIC_ORDER_ADMIN` | `ASF WMS -` | constante hardcodée | commande |
| `wms/public_order_handlers.py:24`, envoye a `:152` | `ASF WMS - Confirmation de commande` | constante module `SUBJECT_PUBLIC_ORDER_CONFIRMATION` | `ASF WMS -` | constante hardcodée | commande |
| `wms/order_notifications.py:15`, envoye a `:82` | `ASF WMS - Nouvelle commande` | constante module `SUBJECT_NEW_ORDER` | `ASF WMS -` | constante hardcodée | commande |
| `wms/order_notifications.py:16`, envoye a `:98` | `ASF WMS - Commande reçue` | constante module `SUBJECT_ORDER_CONFIRMATION` | `ASF WMS -` | constante hardcodée | commande |
| `wms/events/handlers_notifications.py:49` | `ASF WMS - Expédition %(reference)s : statut mis à jour` | literal `gettext` + interpolation `%` | `ASF WMS -` | hardcodé | expédition |
| `wms/signals.py:157` | `ASF WMS - Expedition %(reference)s : livraison confirmee` | literal `gettext` + interpolation `%` | `ASF WMS -` | hardcodé | expédition, livraison |
| `wms/signals.py:292` | `ASF WMS - Expédition %(reference)s : statut %(status)s` | variable locale `subject`, literal `gettext` + interpolation `%` | `ASF WMS -` | hardcodé | expédition |
| `wms/signals.py:330` | `ASF WMS - Suivi correspondant %(reference)s : %(status)s` | literal `gettext` + interpolation `%` | `ASF WMS -` | hardcodé | correspondant, suivi |
| `wms/events/handlers_notifications.py:103` | `ASF WMS - Suivi expédition %(reference)s` | literal `gettext` + interpolation `%` | `ASF WMS -` | hardcodé | expédition, suivi |
| `wms/signals.py:471` | `ASF WMS - Commande %(reference)s : validation/statut mis à jour` | literal `gettext` + interpolation `%` | `ASF WMS -` | hardcodé | commande |
| `wms/views_portal_auth.py:59`, envoye a `:197` | `ASF WMS - Mot de passe oublié / Première connexion portail` | constante module `RECOVERY_EMAIL_SUBJECT` | `ASF WMS -` | constante hardcodée | portail |
| `wms/views_volunteer_auth.py:48`, envoye a `:167` | `ASF WMS - Mot de passe oublié / Première connexion bénévole` | constante module `RECOVERY_EMAIL_SUBJECT` | `ASF WMS -` | constante hardcodée | bénévole |
| `wms/views_shipment_tracking_access.py:55`, envoye a `:349` | `ASF WMS - Accès suivi expédition` | constante module `RECOVERY_EMAIL_SUBJECT` | `ASF WMS -` | constante hardcodée | expédition, suivi |
| `wms/views_scan_shipments.py:1067` | `ASF WMS - Accès suivi expédition créé` | literal `gettext` | `ASF WMS -` | hardcodé | expédition, suivi |
| `wms/pack_handlers.py:193` | `Revue produit requise : %(sku)s` | literal `gettext` + interpolation `%` | aucun | aucun | produit, SKU |
| `wms/views_volunteer_account_request.py:18`, envoye a `:89` | `ASF WMS - Nouvelle demande benevole` | constante module `ADMIN_NOTIFICATION_SUBJECT` | `ASF WMS -` | constante hardcodée | bénévole |
| `wms/views_volunteer_account_request.py:19`, envoye a `:103` | `ASF WMS - Demande de compte benevole recue` | constante module `REQUESTER_CONFIRMATION_SUBJECT` | `ASF WMS -` | constante hardcodée | bénévole, compte |
| `wms/volunteer_account_request_handlers.py:12`, envoye a `:94` | `ASF WMS - Demande benevole approuvee` | constante module `VOLUNTEER_ACCOUNT_APPROVED_SUBJECT` | `ASF WMS -` | constante hardcodée | bénévole |
| `wms/volunteer_access.py:11`, envoye a `:64` | `ASF WMS - Acces benevole` | constante module `VOLUNTEER_ACCESS_EMAIL_SUBJECT` | `ASF WMS -` | constante hardcodée | bénévole |
| `wms/emailing.py:293` | `payload["subject"]` | valeur stockee dans `IntegrationEvent.payload` | depend du producteur | concat/constante amont | depend du producteur |

Sujets construits mais non envoyes par la couche email Django/Brevo:

| fichier:ligne | usage | subject actuel | construction | risque white-label |
|---|---|---|---|---|
| `wms/planning/legacy_communications.py:273` | brouillon planning email ASF interne | `Planning SEMAINE {week} - {year}` | f-string | faible/moyen, pas de prefix ASF-WMS |
| `wms/planning/legacy_communications.py:277` | brouillon planning Air France | `Aviation Sans Frontires / Planning S{week}` | f-string | eleve, marque Air France et nom ASF historique |
| `wms/planning/legacy_communications.py:281` | brouillon planning correspondant | `ASF / Expédition {destination_city} / Semaine {week}` | f-string | eleve, prefix `ASF`, vocabulaire expédition |
| `wms/planning/legacy_communications.py:285` | brouillon planning expéditeur/destinataire | `{party_name} / Expédition {destination_city} / Semaine {week}` | f-string | moyen, vocabulaire expédition |
| `wms/planning/communications.py:201` | template planning DB | `template.subject` rendu via `django.template.Template` | template DB | variable, `hypothèse à vérifier` selon donnees prod |
| `wms/planning/communications.py:177` | suffixe version planning | ajoute ` v{version.number}` si channel email | helper maison | faible, mais peut casser tests planning |

## 3. Configuration email actuelle

Settings Django pertinents:

- `asf_wms/settings.py:378`: `EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")`.
- `asf_wms/settings.py:379`: `DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@example.com")`.
- `asf_wms/settings.py:380-385`: `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`.
- `asf_wms/settings.py:386-387`: `EMAIL_DELIVERY_MODE`, defaut `direct_or_queue`.
- `asf_wms/settings.py:389-392`: `BREVO_API_KEY`, `BREVO_SENDER_EMAIL`, `BREVO_SENDER_NAME`, `BREVO_REPLY_TO_EMAIL`.
- `asf_wms/settings.py:393-405`: groupes de notification `ORDER_NOTIFICATION_GROUP_NAME`, `ACCOUNT_REQUEST_VALIDATION_GROUP_NAME`, `SHIPMENT_STATUS_UPDATE_GROUP_NAME`, `SHIPMENT_STATUS_CORRESPONDANT_GROUP_NAME`.
- Aucun `EMAIL_SUBJECT_PREFIX`.
- Aucun `SERVER_EMAIL`.

Variables d'environnement liees a l'email:

- `.env.example:57-64`: `DEFAULT_FROM_EMAIL`, `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`.
- `.env.example:67-80`: `BREVO_API_KEY`, `BREVO_SENDER_EMAIL`, `BREVO_SENDER_NAME`, `BREVO_REPLY_TO_EMAIL`, groupes de notification, tuning queue.
- `deploy/pythonanywhere/asf-wms.env.template:31-57`: valeurs PythonAnywhere generiques, SMTP Brevo, `EMAIL_DELIVERY_MODE='direct_only'`, queue tuning.
- `deploy/pythonanywhere/asf-wms.messmed.env.template:22-46`: valeurs MessMed, Brevo API vide par defaut, SMTP Brevo, `EMAIL_DELIVERY_MODE='direct_only'`.

Providers externes:

- Brevo API: `wms/emailing.py:25-27` fixe `https://api.brevo.com/v3/smtp/email` et valide host/path avant `urlopen`.
- Brevo settings: `wms/emailing.py:366-379`, avec fallback sender vers `settings.DEFAULT_FROM_EMAIL`.
- SMTP/Django fallback: `wms/emailing.py:438-445` appelle `django.core.mail.send_mail` avec `settings.DEFAULT_FROM_EMAIL`.
- SMTP Brevo fallback documente dans `deploy/pythonanywhere/*.env.template` via `smtp-relay.brevo.com`.
- Sendinblue legacy naming: absent du runtime.

Templates email:

- Moteur de rendu: `django.template.loader.render_to_string`.
- Dossier: `templates/emails/`.
- Templates identifies: `account_request_admin_notification.txt`, `account_request_received.txt`, `account_request_approved_user.txt`, `account_request_approved.txt`, `order_admin_notification_public.txt`, `order_admin_notification_portal.txt`, `order_confirmation.txt`, `order_status_association_notification.txt`, `portal_forgot_password.txt`, `shipment_delivery_notification.txt`, `shipment_status_admin_notification.txt`, `shipment_status_party_notification.txt`, `shipment_status_correspondant_notification.txt`, `shipment_tracking_access_recovery.txt`, `shipment_tracking_admin_notification.txt`, `shipment_tracking_pending_created.txt`, `volunteer_access_created.txt`, `volunteer_account_approved.txt`, `volunteer_account_request_confirmation.txt`, `volunteer_account_request_received.txt`, `volunteer_forgot_password.txt`.
- Les subjects ne sont pas dans ces templates; ils sont construits en Python.

Emails construits inline en Python:

- `wms/pack_handlers.py:176-190`: corps inline pour revue produit préparateur, avec subject `Revue produit requise : %(sku)s`.
- Tous les autres bodies runtime identifies passent par `templates/emails/*.txt`.
- Les brouillons planning utilisent des strings HTML inline dans `wms/planning/legacy_communications.py:52-88`, mais ne sont pas envoyes par `wms/emailing.py`.

Abstraction maison:

- `wms/emailing.py` centralise les transports, la queue, la normalisation recipients et les fallbacks.
- `wms/events/outbox.py:6-16` centralise la creation durable d'`IntegrationEvent`.
- `wms/jobs/email_queue.py:5-24` enveloppe `process_email_queue` avec `OperationalJobRun`.
- `wms/management/commands/process_email_queue.py:46-64` expose la commande de traitement.
- Il existe donc une abstraction maison; elle est reelle et deja la meilleure prise pour PR 2.

Queue/outbox:

- `IntegrationEvent` est defini dans `wms/models_domain/integration.py:48-76`.
- Les emails queues ont `source="wms.email"`, `target="smtp"`, `event_type="send_email"` via `wms/emailing.py:28-30`.
- Le payload contient `subject`, `message`, `recipient`, optionnellement `html_message`, `tags`, et meta `_queue` via `wms/emailing.py:40-44` et `:346-363`.
- Retry/backoff et timeout sont controles par `WmsRuntimeSettings` (`wms/models_domain/integration.py:315-318`) et lus par `wms/emailing.py:144-188`.

## 4. Cartographie de la dispersion

Il existe cinq patterns differents pour construire un subject runtime:

1. Literal `gettext` inline directement passe a `send_or_enqueue_email_safe`.
2. Constante module `SUBJECT_*` ou `*_EMAIL_SUBJECT`.
3. Variable locale composee par interpolation, par exemple `subject = _("ASF WMS - Expédition ...") % {...}`.
4. Subject transporte depuis `IntegrationEvent.payload["subject"]` pour la queue.
5. Subject sans prefix ASF-WMS, notamment revue produit préparateur.

Si on inclut les brouillons planning non envoyes par Django/Brevo, deux patterns supplementaires existent: builders f-string dans `legacy_communications.py` et templates DB `CommunicationTemplate.subject`.

Les endroits uniques vs duplicatifs:

- 24 points d'envoi metier runtime ont ete identifies.
- 23 passent par le prefix hardcode `ASF WMS -`; un seul n'a pas ce prefix (`wms/pack_handlers.py:193`).
- Les flows commande ont une duplication claire: commande publique et commande portail ont deux helpers separes mais un meme template confirmation et des subjects proches.
- Les flows acces/mot de passe ont trois constantes distinctes mais tres similaires: portail, benevole, suivi expedition.
- Les signaux expedition regroupent plusieurs subjects tres proches autour de `Expédition`, `Suivi`, `statut`.

Tentative de centralisation existante:

- Oui pour le transport, la queue et les retries: `wms/emailing.py`.
- Oui pour l'outbox durable: `wms/events/outbox.py`.
- Non pour le formatting des subjects: aucun helper unique de prefix, aucun `EMAIL_SUBJECT_PREFIX`, aucun usage de `installation.py`.

Endroits propres et faciles a brancher sur `installation.py`:

- `wms/emailing.py`, car tous les producteurs passent par `send_email_safe`, `send_or_enqueue_email_safe` ou `enqueue_email_safe`.
- Les tests `wms/tests/emailing/tests_emailing.py` et `wms/tests/emailing/tests_emailing_extra.py`, car ils couvrent payload queue, direct only, fallback Brevo/SMTP et `send_mail`.
- Les tests config `wms/tests/config/tests_installation_config.py`, car `installation.py` expose deja identity/integrations.

Endroits demandant un refactor prealable:

- Les subjects planning (`wms/planning/legacy_communications.py`, `wms/planning/communications.py`) car ils ne sont pas dans la couche email runtime et melangent aviation, Air France, ASF, planning et helper local.
- Les subjects de signaux si l'objectif depasse le prefix et renomme `Expédition`, `Commande`, `Bénévole`, `Expéditeur` ou `Destinataire`: cela touche vocabulaire metier, i18n, tests de notification et comprehension utilisateur.
- Les templates/body email si la PR veut renommer ASF dans le contenu, pas seulement le subject.

Sujets traitables dans une petite PR sure:

- Prefixer les subjects au plus pres de `wms/emailing.py`, sans modifier les strings metier internes.
- Ajouter un helper pur, teste, qui preserve les subjects deja prefixes par defaut.
- Exclure le subject sans prefix `Revue produit requise` du changement automatique si la regle choisie est "prefixer tous les emails WMS"; ou l'inclure explicitement avec test cible, car c'est le seul outlier.

Sujets a exclure de la PR 2:

- Refactor des communications planning et Air France.
- Renommage de vocabulaire metier dans subjects (`Expédition`, `Commande`, `Bénévole`, `Expéditeur`, `Destinataire`).
- Migration des bodies templates.
- Changement des recipients, groupes, queue, retries, `EMAIL_DELIVERY_MODE`, Brevo/SMTP.

## 5. Risques et angles morts

Tests qui pourraient casser si on change le subject prefix:

- `wms/tests/admin/tests_account_request_handlers.py:147` assert `payload__subject="ASF WMS - Nouvelle demande de compte"`.
- `wms/tests/core/tests.py:707` assert `event.payload.get("subject") == "ASF WMS - Compte valide"`.
- `wms/tests/emailing/tests_notifications_queue.py:253`, `:357`, `:361`, `:387`, `:470` assertent des subjects de commandes en dur.
- `wms/tests/views/tests_views_portal.py:350-379`, `:452-455` assertent le subject portail recovery.
- `wms/tests/views/tests_views_volunteer.py:206-207`, `:247-248` assertent le subject recovery bénévole.
- `wms/tests/emailing/tests_order_status_notifications.py:60`, `:78` assertent un fragment de subject order status.
- `wms/tests/planning/tests_legacy_communications.py:217`, `:231`, `:246`, `:262`, `:284` assertent les subjects planning non runtime email.
- `wms/tests/planning/tests_outputs.py:129` assert le suffixe subject planning.

Endroits ou le subject est asserté en dur:

- Principalement tests emailing, portal, volunteer, admin account request et planning.
- Les tests de transport `wms/tests/emailing/tests_emailing.py` utilisent des subjects artificiels (`Sujet test`, `Sujet direct`, etc.) et peuvent casser si le helper prefixe tous les subjects sans option.

Emails envoyes a des systemes externes pouvant parser le subject:

- Aucun parseur externe de subject trouve dans le repo.
- Brevo recoit le subject comme payload API mais ne semble pas le parser.
- Les emails planning Air France/correspondants sont des brouillons pour envoi externe; ils peuvent avoir des conventions humaines attendues. `hypothèse à vérifier`

Indices dans commentaires, noms de fichiers, jobs ou integrations:

- `docs/pythonanywhere_email_setup_step_by_step.md` recommande `EMAIL_DELIVERY_MODE='direct_only'` sur PythonAnywhere gratuit; en direct_only, `enqueue_email_safe` envoie immediatement.
- `docs/email_flows_target_matrix_2026-02-20.md` documente les groupes et le besoin de traiter `process_email_queue`.
- `wms/application/planning_artifacts/use_cases.py:77-94` expose `action: "email"`, `subject`, `body_html`, `attachments` a un helper local, sans transport Django.

gettext/i18n:

- Tous les subjects runtime sauf ceux venant du payload queue sont en `gettext` ou `gettext_lazy`.
- Cela ne fournit pas une configuration white-label: les strings restent hardcodees, traduisibles mais non parametrees par installation.
- Certains subjects utilisent des accents, d'autres non (`Expedition`, `confirmee`, `benevole`, `Acces`), ce qui reflete de l'historique et peut etre stabilise plus tard, mais ce n'est pas necessaire pour PR 2.

Emails multilingues:

- Les templates email utilisent `{% trans %}` dans plusieurs bodies.
- Les subjects sont traduisibles via `gettext`, mais l'audit n'a pas ouvert le scope `locale/` car la traduction est pausee par les guardrails.
- Aucun mecanisme par-recipient de langue email n'a ete trouve.

Pièges Brevo, SMTP fallback, queue/outbox, retries:

- Si le prefix est applique seulement dans `send_email_safe`, les events deja queues en base avec ancien subject seront envoyes avec le nouveau prefix au moment du traitement; c'est souhaitable ou non selon le contrat choisi.
- Si le prefix est applique seulement au moment de l'enqueue, les sends directs `direct_only` ou `send_or_enqueue_email_safe` peuvent diverger.
- Si le helper n'est pas idempotent, les subjects deja prefixes (`ASF WMS - ...`) peuvent devenir doubles.
- `EMAIL_DELIVERY_MODE=direct_only` contourne la queue; PR 2 doit tester ce mode.
- Brevo API et fallback SMTP partagent `send_email_safe`; c'est la bonne surface pour eviter des divergences provider.

Choses surprenantes ou hors-scope:

- Le seul subject runtime sans prefix ASF-WMS est `Revue produit requise : %(sku)s`.
- `EMAIL_SUBJECT_PREFIX` n'existe pas malgre l'intention PR 2.
- `installation.py` expose identity et integrations email, mais aucun champ `email`/`notification` specifique au subject prefix.
- Les communications planning contiennent beaucoup d'identite ASF/Air France, mais ne sont pas des envois email serveur; les traiter avec PR 2 augmenterait fortement le perimetre.

## 6. Recommandations pour la PR 2 d'implémentation

PR 2 minimale recommandee: introduire une fonction idempotente de formatting subject dans `wms/emailing.py` ou un petit module voisin, consommee par `send_email_safe` avant Brevo/SMTP. Garder les producteurs inchanges au maximum. Ajouter tests de direct send, queue processing, direct_only et idempotence.

### 6.1 Contrat d'API recommandé

Option A - `get_email_subject_prefix()` module-level:

- Avantages: simple, facile a tester, expose directement `installation.identity.application_display_name`.
- Inconvenients: ne resout pas l'idempotence ni le formatting complet; chaque producteur doit penser a l'utiliser.
- Risque: dispersion continue si appele dans les producteurs.
- Compatibilite: bonne, mais demande de toucher beaucoup de fichiers si applique au call site.

Option B - `format_email_subject(subject)` centralise:

- Avantages: idempotent possible, appele en un seul point dans `send_email_safe`, couvre Brevo, SMTP, direct_only et queue processing.
- Inconvenients: les payloads queues gardent potentiellement le subject brut si prefix applique a l'envoi; les vues dashboard queue afficheront le brut.
- Risque: risque de double-prefix si mal implemente; risque tests sur subjects artificiels.
- Compatibilite: excellente avec le code actuel car tout converge vers `send_email_safe`.

Option C - Django setting calcule `EMAIL_SUBJECT_PREFIX`:

- Avantages: convention Django comprehensible, stable pour ops.
- Inconvenients: ajoute une source de config parallele a `installation.py`; peut court-circuiter l'objectif white-label.
- Risque: derive entre settings, env et installation config.
- Compatibilite: correcte, mais demande une decision claire de precedence.

Option D - service injecte:

- Avantages: testable et extensible.
- Inconvenients: trop lourd pour cette PR, pas aligne avec le style actuel de petits helpers.
- Risque: refactor inutile de tous les producteurs.
- Compatibilite: faible/moyenne avec le monolithe legacy.

Recommandation par defaut: Option B, `format_email_subject(subject)`, appelee dans `send_email_safe` juste avant `_send_with_brevo` et `send_mail`. Elle doit etre idempotente et lire un prefix derive de `get_installation_config().identity.application_display_name`, avec default actuel `ASF-WMS` ou `ASF WMS` a trancher explicitement par test de compatibilite.

Point de vigilance: les subjects actuels utilisent `ASF WMS -` avec espace, alors que `installation.identity.application_display_name` vaut `ASF-WMS`. Pour une PR sure, conserver exactement le prefix visible actuel par defaut est probablement preferable, meme si cela demande un champ dedie ou une normalisation documentee.

### 6.2 Où placer le subject prefix dans le modèle installation

Le subject prefix releve principalement d'un futur sous-objet email/notification.

Justification:

- Ce n'est pas seulement `identity`: le prefix est une convention de notification, pas le nom canonique de l'organisation.
- Ce n'est pas `vocabulary`: le prefix ne renomme pas `expédition`, `bénévole`, `association` ou autres labels metier.
- Il depend partiellement de `identity.application_display_name`, car le default ASF actuel doit rester coherent.
- Le meilleur contrat long terme serait `installation.notifications.email_subject_prefix` ou `installation.email.subject_prefix`.

Pour PR 2 minimale, deux chemins acceptables:

- Court terme: helper derive du `identity.application_display_name`, avec compatibilite explicite pour produire le prefix actuel.
- Moyen terme: ajouter un sous-objet email/notification a `installation.py`, mais seulement si la PR assume de modifier le contrat config et ses tests.

### 6.3 No-go zones pour PR 2

- Refactor large de provider email.
- Changement Brevo API, SMTP fallback, URL Brevo, credentials ou `DEFAULT_FROM_EMAIL`.
- Changement `EMAIL_DELIVERY_MODE`, queue/outbox, retries ou `OperationalJobRun`.
- Modification des bodies sous `templates/emails/`.
- Renommage metier de `Expédition`, `Commande`, `Bénévole`, `Expéditeur`, `Destinataire`, `Association`.
- I18n complet, modifications `locale/`, harmonisation accents.
- Communications planning Air France/ASF et helper local.
- Recipients, groupes Django de notification, permissions, signaux.
- Tests sans rapport direct avec subject formatting.

### 6.4 Estimation PR 2

Nombre de fichiers a toucher:

- Minimum: 3 a 5 fichiers.
- Probable: 5 a 8 fichiers si ajout d'un champ installation dedie.

Fichiers probables:

- `wms/emailing.py`
- `wms/tests/emailing/tests_emailing.py`
- `wms/tests/emailing/tests_emailing_extra.py`
- `wms/tests/config/tests_installation_config.py` si `installation.py` evolue.
- `wms/config/installation.py` uniquement si un sous-objet email/notification est ajoute.
- Eventuellement `docs/repo-reference/04-shared-contracts/08-installation-config.md` si le contrat installation change.

Tests a modifier ou ajouter:

- Test idempotence: subject deja prefixe reste inchange.
- Test default ASF: subject non prefixe devient prefixe selon le contrat choisi.
- Test direct_only: `enqueue_email_safe` envoie avec le meme subject formate.
- Test queue processing: payload queue puis `process_email_queue` envoie avec le subject formate.
- Test Brevo payload ou `send_mail` fallback selon le niveau de PR.

Risques principaux:

- Double-prefix ou prefix applique a des subjects artificiels/test-only.
- Divergence entre queue display payload et subject reel envoye.
- Changement visible pour des utilisateurs externes si le default exact passe de `ASF WMS -` a `ASF-WMS -`.

No documentation update required beyond this audit report because no runtime behavior, route, permission, shared contract, data model, business rule, deployment expectation, or security posture was changed. A future PR 2 qui consomme `installation.py` en runtime devra reevaluer `docs/repo-reference/04-shared-contracts/08-installation-config.md`, `docs/repo-reference/03h-impact-email-events.md`, `docs/email_flows_target_matrix_2026-02-20.md`, `docs/operations.md` et `docs/release_checklist.md`.
