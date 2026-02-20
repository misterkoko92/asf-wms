# Audit complet des flux email - ASF WMS

Date: 2026-02-20

## 1) Perimetre et methode

Objectif:
- Auditer toutes les regles, logiques et fichiers relies aux envois d'email.
- Identifier les cassures et axes d'amelioration.
- Proposer un plan d'action priorise.

Methode:
- Lecture du code applicatif et templates email.
- Verification des points d'entree (views, signals, admin, commandes).
- Verification des reglages runtime/env et de l'operabilite.
- Execution de tests cibles.

Tests executes:
- `./.venv/bin/python manage.py test wms.tests.emailing wms.tests.public.tests_public_order_handlers wms.tests.admin.tests_account_request_handlers`
- Resultat: 55 tests, OK.
- `./.venv/bin/python manage.py test wms.tests.emailing.tests_signal_notifications_queue wms.tests.emailing.tests_email_flows_e2e api.tests.tests_views_extra`
- Resultat: 19 tests, OK.
- `./.venv/bin/python manage.py test wms.tests.emailing.tests_signals_extra`
- Resultat: 8 tests, OK.
- `./.venv/bin/python manage.py test wms.tests.emailing`
- Resultat: 43 tests, OK.
- `./.venv/bin/python manage.py test wms.tests.emailing`
- Resultat: 45 tests, OK.
- `./.venv/bin/python manage.py test wms.tests.emailing.tests_notifications_queue wms.tests.public.tests_public_order_handlers`
- Resultat: 12 tests, OK.
- `./.venv/bin/python manage.py test wms.tests.emailing.tests_emailing_extra`
- Resultat: 14 tests, OK.
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAccountViewsTests`
- Resultat: 17 tests, OK.
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAccountViewsTests`
- Resultat: 15 tests, OK.
- `./.venv/bin/python manage.py test wms.tests.emailing wms.tests.public.tests_public_order_handlers wms.tests.admin.tests_account_request_handlers wms.tests.views.tests_views_public_order wms.tests.views.tests_views_portal api.tests.tests_views_extra wms.tests.views.tests_views_scan_dashboard`
- Resultat: 153 tests, OK.
- `./.venv/bin/python manage.py test wms.tests.core.tests_models_methods`
- Resultat: 11 tests, OK.

## 2) Inventaire des fichiers lies aux emails

### 2.1 Coeur d'envoi et file d'attente

- `wms/emailing.py`
- `wms/models_domain/integration.py`
- `wms/runtime_settings.py`
- `wms/forms_scan_settings.py`
- `wms/views_scan_settings.py`
- `wms/management/commands/process_email_queue.py`
- `asf_wms/settings.py`
- `.env.example`

### 2.2 Producteurs d'emails metier

- `wms/order_notifications.py`
- `wms/public_order_handlers.py`
- `wms/views_public_order.py`
- `wms/views_portal_orders.py`
- `wms/account_request_handlers.py`
- `wms/admin_account_request_approval.py`
- `wms/admin.py`
- `wms/signals.py`

### 2.3 Donnees de destinataires / regles portail

- `wms/models_domain/portal.py`
- `wms/views_portal_account.py`
- `wms/view_permissions.py`
- `wms/portal_recipient_sync.py`

### 2.4 Monitoring et operations

- `wms/views_scan_dashboard.py`
- `wms/admin_misc.py` (admin IntegrationEvent)
- `templates/scan/dashboard.html`
- `templates/scan/settings.html`
- `README.md`
- `docs/operations.md`

### 2.5 Surface API autour des IntegrationEvent

- `api/v1/views.py`
- `api/v1/serializers.py`
- `api/v1/permissions.py`

### 2.6 Templates email

- `templates/emails/account_request_admin_notification.txt`
- `templates/emails/account_request_received.txt`
- `templates/emails/account_request_approved.txt`
- `templates/emails/account_request_approved_user.txt`
- `templates/emails/order_admin_notification_portal.txt`
- `templates/emails/order_admin_notification_public.txt`
- `templates/emails/order_confirmation.txt`
- `templates/emails/shipment_delivery_notification.txt`
- `templates/emails/shipment_status_admin_notification.txt`
- `templates/emails/shipment_tracking_admin_notification.txt`

### 2.7 Tests email et flux associes

- `wms/tests/emailing/tests_emailing.py`
- `wms/tests/emailing/tests_emailing_extra.py`
- `wms/tests/emailing/tests_notifications_queue.py`
- `wms/tests/emailing/tests_signal_notifications_queue.py`
- `wms/tests/emailing/tests_signals_extra.py`
- `wms/tests/emailing/tests_email_flows_e2e.py`
- `wms/tests/public/tests_public_order_handlers.py`
- `wms/tests/admin/tests_account_request_handlers.py`
- `wms/tests/views/tests_views_public_order.py`
- `wms/tests/views/tests_views_portal.py`
- `wms/tests/views/tests_views.py`
- `api/tests/tests_views_extra.py`

## 3) Architecture email actuelle

### 3.1 Moteur d'envoi

Reference: `wms/emailing.py:349`

Strategie:
- `send_email_safe()` tente Brevo en premier (`_send_with_brevo`).
- En fallback, utilise `django.core.mail.send_mail`.
- Retourne `True/False` sans lever d'exception au caller.

Details:
- Endpoint Brevo hardcode + validation host/path (`wms/emailing.py:24`, `wms/emailing.py:329`).
- Fallback SMTP avec `DEFAULT_FROM_EMAIL` (`wms/emailing.py:362`).

### 3.2 File d'attente email (IntegrationEvent)

References:
- `wms/emailing.py:376`
- `wms/models_domain/integration.py:46`

Modele:
- `IntegrationEvent` outbound, source `wms.email`, event_type `send_email`.
- Payload standard:
  - `subject`
  - `message`
  - `recipient` (liste)
  - optionnel `html_message`
  - optionnel `tags`
  - meta `_queue` avec `attempts` et `next_attempt_at`

Traitement:
- Commande `process_email_queue` (`wms/management/commands/process_email_queue.py:6`)
- Fonction coeur `process_email_queue()` (`wms/emailing.py:399`)
- Claim optimiste en DB (`wms/emailing.py:200`)
- Reclaim des events `processing` bloques via timeout (`wms/emailing.py:174`, `wms/emailing.py:416`)
- Backoff exponentiel: `retry_base_seconds * 2^(attempts-1)`, cap `retry_max_seconds` (`wms/emailing.py:149`)
- Echec definitif si `attempts >= max_attempts` (`wms/emailing.py:243`)

## 4) Flux email metier (bout en bout)

### 4.1 Flux "Commande portail association"

Entree:
- `wms/views_portal_orders.py:486` appelle `send_portal_order_notifications()`.

Generation:
- `wms/order_notifications.py:56`
- Email admin:
  - template `emails/order_admin_notification_portal.txt` (`wms/order_notifications.py:7`)
  - destinataires: superusers actifs via `get_admin_emails()` (`wms/order_notifications.py:66`)
- Email confirmation association:
  - template `emails/order_confirmation.txt` (`wms/order_notifications.py:8`)
  - destinataires:
    - `profile.contact.email` ou fallback `request.user.email`
    - plus `profile.get_notification_emails()` (`wms/order_notifications.py:50`)

### 4.2 Flux "Commande publique"

Entree:
- `wms/views_public_order.py:265` appelle `send_public_order_notifications()`.

Generation:
- `wms/public_order_handlers.py:113`
- Email admin:
  - sujet `ASF WMS - Nouvelle commande publique`
  - template `emails/order_admin_notification_public.txt`
  - destinataires superusers
- Email confirmation association:
  - sujet `ASF WMS - Confirmation de commande`
  - template `emails/order_confirmation.txt`
  - destinataire unique: `association_email` sinon `contact.email` (`wms/public_order_handlers.py:65`)
  - si enqueue impossible: warning UI (`wms/public_order_handlers.py:128`)

### 4.3 Flux "Demande de compte public"

Entree:
- `wms/account_request_handlers.py:387`

Regles:
- Validation champs selon type (`association` vs `user`) (`wms/account_request_handlers.py:139`)
- Throttling IP + email (`wms/account_request_handlers.py:307`)
- Verification pending existant email/username (`wms/account_request_handlers.py:190`, `wms/account_request_handlers.py:197`)
- Uploads valides selon type de compte (`wms/account_request_handlers.py:162`)

Emails:
- Queues en `transaction.on_commit` (`wms/account_request_handlers.py:384`)
- Admin notification:
  - template `emails/account_request_admin_notification.txt`
  - superusers
- Accuse reception demandeur:
  - template `emails/account_request_received.txt`
  - destinataire `email` du formulaire

### 4.4 Flux "Approbation demande de compte (admin)"

Entree:
- Admin action/save_model dans `wms/admin.py` via `approve_account_request()` (`wms/admin.py:279`, `wms/admin.py:329`)

Traitement:
- `wms/admin_account_request_approval.py:52`
- Type `USER`:
  - creation/mise a jour user staff
  - envoi `emails/account_request_approved_user.txt` (`wms/admin_account_request_approval.py:110`)
- Type `ASSOCIATION`:
  - creation/mise a jour contact + user + profile
  - `must_change_password=True`
  - envoi `emails/account_request_approved.txt` (`wms/admin_account_request_approval.py:199`)

### 4.5 Flux "Suivi expedition / statut expedition"

Declenchement signals:
- `wms/signals.py:42` (changement de statut shipment)
- `wms/signals.py:91` (creation tracking event)

Emails:
- Admins uniquement (`get_admin_emails()`)
- Queue via `transaction.on_commit`
- Templates:
  - `emails/shipment_status_admin_notification.txt`
  - `emails/shipment_tracking_admin_notification.txt`

## 5) Regles de destinataires et de configuration

### 5.1 Superusers admins

Reference: `wms/emailing.py:49`

Regle:
- superusers actifs seulement
- email non vide seulement

### 5.2 Notification emails de profil association

References:
- `wms/models_domain/portal.py:207`
- `wms/views_portal_account.py:394`

Regles:
- Priorite aux `portal_contacts` actifs.
- Dedup case-insensitive dans ce chemin.
- Fallback sur `notification_emails` (split virgule/newline).

### 5.3 Flags destinataires portail

References:
- `wms/models_domain/portal.py:348`
- `wms/views_portal_account.py:132`
- `wms/view_permissions.py:44`

Regles observees:
- `notify_deliveries`: valide seulement la presence d'au moins un email en saisie.
- `is_delivery_contact`: utilise pour debloquer l'acces portail (guard).
- Aucune logique d'envoi email ne lit ces flags.

### 5.4 Reglages runtime queue email

References:
- `asf_wms/settings.py:232`
- `wms/runtime_settings.py:68`
- `wms/forms_scan_settings.py:6`

Parametres:
- `email_queue_max_attempts`
- `email_queue_retry_base_seconds`
- `email_queue_retry_max_seconds`
- `email_queue_processing_timeout_seconds`

Editable:
- UI `/scan/settings/` (superuser) via `WmsRuntimeSettings`.

## 6) Observabilite et operations

Dashboard:
- Snapshot queue email: pending/processing/failed/stale (`wms/views_scan_dashboard.py:199`, `wms/views_scan_dashboard.py:608`)

Commande d'exploitation:
- `python manage.py process_email_queue --limit=100`
- `python manage.py process_email_queue --include-failed --limit=100`

Runbook:
- Commandes de diagnostic et cron documentes dans `docs/operations.md`.

## 7) Cassures et risques identifies

### [C1] Flag "Avertir ce contact des livraisons" non branche a un flux d'envoi (constat initial)

Constat initial:
- `notify_deliveries` existe en modele/UI/validation (`wms/models_domain/portal.py:348`, `wms/views_portal_account.py:163`).
- Aucune occurrence dans les producteurs d'emails (order/account/signal) en dehors de saisie/admin.

Impact:
- Incoherence fonctionnelle: l'UI promet une alerte livraison, mais aucune alerte n'est envoyee a partir de ce flag.

Severite:
- Haute (fonctionnalite visible non effective).

Statut:
- Corrige le 2026-02-20 (suite): envoi actif au passage `ShipmentStatus.DELIVERED` via `wms/signals.py`, filtre `AssociationRecipient` (`is_active`, `notify_deliveries`, destination), dedup des emails, template dedie `templates/emails/shipment_delivery_notification.txt`.
- Couverture ajoutee: `wms/tests/emailing/tests_signal_notifications_queue.py` et E2E `wms/tests/emailing/tests_email_flows_e2e.py`.

### [C2] Template admin commande ambigu pour les commandes portail (constat initial)

Constat initial:
- `templates/emails/order_admin_notification.txt:1` commencait par "Nouvelle commande publique".
- Ce template etait reutilise par flux public ET flux portail (`wms/public_order_handlers.py`, `wms/order_notifications.py`).

Impact:
- Message faux/ambigu pour les commandes portail (non publiques).

Severite:
- Moyenne (erreur de contenu metier).

Statut:
- Traite en P0: separation des templates `order_admin_notification_public.txt` et `order_admin_notification_portal.txt`.

### [C3] Echecs d'enqueue silencieux dans certains flux (constat initial)

Constat initial:
- Flux portail commande: retour `enqueue_email_safe()` ignore (`wms/order_notifications.py:63`, `wms/order_notifications.py:74`).
- Flux commande publique: echec confirmation gere (warning), echec admin ignore (`wms/public_order_handlers.py:123`).

Impact:
- Perte silencieuse de notifications.
- Difficultes de diagnostic en prod.

Severite:
- Haute.

Statut:
- Traite en P0: warning explicite quand un enqueue echoue sur flux portail/public (admin + confirmation).
- Couverture existante et validee: `wms/tests/emailing/tests_notifications_queue.py`, `wms/tests/public/tests_public_order_handlers.py`.

### [C4] Surface API pouvant modifier les IntegrationEvent outbound (dont queue email) (constat initial)

Constat initial:
- `IntegrationEventViewSet` expose `UpdateModelMixin` (`api/v1/views.py:156`).
- `perform_update` accepte update statut/error_message/processed_at (`api/v1/views.py:191`).
- Pas de garde explicite sur `direction/source/event_type` outbound email.

Impact:
- Un client avec cle integration valide (ou staff) peut modifier des events email en file (ex: marquer processed).

Severite:
- Haute (risque integrite/operabilite).

Statut:
- Corrige le 2026-02-20 (suite): `api/v1/views.py` refuse les updates sur `outbound + wms.email + send_email`.
- Couverture ajoutee: `api/tests/tests_views_extra.py` (tentative PATCH rejetee).

### [C5] Normalisation recipients incomplète (constat initial)

Constat initial:
- `_normalize_recipients` filtre seulement les valeurs truthy (`wms/emailing.py:58`).
- Pas de strip, pas de dedup, pas de validation syntaxique.

Impact:
- Doublons possibles.
- Espaces parasites possibles.
- Qualite d'envoi dependante du transport aval.

Severite:
- Moyenne.

Statut:
- Corrige le 2026-02-20 (suite): `_normalize_recipients` applique trim, ignore les valeurs non-string/vides, dedup case-insensitive.
- Couverture ajoutee/ajustee: `wms/tests/emailing/tests_emailing_extra.py`.

### [C6] Endpoint legacy "update_notifications" non visible en UI et non valide

Constat:
- Action backend presente (`wms/views_portal_account.py:248`).
- Aucun champ/form correspondant dans `templates/portal/account.html`.
- Couvert par test legacy (`wms/tests/views/tests_views_portal.py:1135`).

Impact:
- Dette technique.
- Ecriture de `notification_emails` possible sans validation email dans ce chemin.

Severite:
- Basse a moyenne.

Statut:
- Corrige le 2026-02-20 (suite): action legacy `update_notifications` desactivee (plus d'ecriture via ce chemin).
- Couverture ajoutee: `wms/tests/views/tests_views_portal.py` (action legacy refusee, donnees conservees).
- Le champ `notification_emails` reste alimente via le flux principal `update_profile` (contacts portail).

## 8) Plan d'action recommande

## Phase P0 (immediat, 1-2 jours)

1. Corriger les echanges silencieux:
- `wms/order_notifications.py`: verifier retour des 2 `enqueue_email_safe`, logger warning explicite en cas de `False`.
- `wms/public_order_handlers.py`: faire pareil pour notification admin.

2. Corriger le template admin commande:
- Soit dupliquer template public vs portail.
- Soit rendre titre/context dynamique (`commande publique` vs `commande portail`).

3. Ajouter tests de non-regression:
- Cas `enqueue_email_safe=False` sur flux portail et admin-public.
- Cas contenu template correct par type de flux.

## Phase P1 (court terme, 2-4 jours)

1. Brancher `notify_deliveries` sur une vraie logique:
- Option A: envoi lors transitions shipment (ex: `delivered`, `received_correspondent`).
- Option B: envoi lors creation/MAJ suivi selon `is_delivery_contact` + `notify_deliveries`.

2. Definir les destinataires metier precis:
- `AssociationRecipient` filtres: `is_active=True`, `notify_deliveries=True`, destination coherente.
- Strategie fallback si aucun destinataire eligible.

3. Ajouter templates dedies livraison:
- un template "alerte livraison correspondant"
- un template "confirmation livraison destinataire"

4. Ajouter tests:
- eligibilite destinataires par destination et flags.
- non-envoi si flags absents.

## Phase P2 (securite/robustesse, 1-3 jours)

1. Verrouiller update API IntegrationEvent:
- Interdire update des events outbound `wms.email/send_email` via API integration.
- Ou limiter updates a `direction=inbound` seulement.

2. Ajouter audit log sur updates IntegrationEvent API:
- user/cle/source, event_id, champs modifies.

3. Ajouter tests API:
- tentative patch d'un event outbound email -> refuse.

## Phase P3 (qualite des destinataires, 1-2 jours)

1. Durcir `_normalize_recipients`:
- trim chaque adresse
- supprimer doublons case-insensitive
- ignorer chaines vides apres trim

2. (Optionnel) validation syntaxique minimale:
- Validation light cote enqueue pour reduire bruit.
- Logger adresses ignorees invalides.

3. Harmoniser `notification_emails`:
- deprecier action `update_notifications` non exposee UI
- ou la conserver avec validation email explicite.

## Phase P4 (ops, 0.5-1 jour)

1. Ajouter controle de "cron actif":
- indicator operationnel (doc + check list release).

2. Ajouter metriques queue:
- compte events ajoutes / traites / retries / fails par heure.

## 9) Priorisation finale

Priorite immediate:
- Aucune cassure critique ouverte.

Priorite ensuite:
- Aucune cassure critique ouverte.

Dette a planifier:
- Suppression definitive du branchement legacy `ACTION_UPDATE_NOTIFICATIONS` apres periode de transition.

## 10) Resume executif

Le socle technique email est solide (queue + retries + fallback Brevo/SMTP + monitoring dashboard + tests cibles OK).

Etat apres la suite de travaux:
- C1 est corrige (notifications livraison branchees).
- C3 est corrige (echecs d'enqueue journalises).
- C4 est corrige (API verrouillee sur la queue outbound email).
- C5 est corrige (normalisation recipients renforcee).
- C6 est corrige (chemin legacy desactive).

## 11) Mise en oeuvre realisee apres P0

Realise dans cette suite:
- C1 traite: notifications de livraison branchees sur `notify_deliveries` pour les expeditions livrees.
- C3 valide: warnings d'enqueue deja en place et couverts par tests.
- C4 traite: verrouillage API sur la queue email outbound.
- C5 traite: normalisation recipients (trim + dedup case-insensitive + filtrage valeurs invalides).
- C6 traite: desactivation de `update_notifications` (legacy non expose en UI).
- E2E mails deja presents dans le repo (`wms/tests/emailing/tests_email_flows_e2e.py`) et etendus avec un scenario livraison.

Reste recommande:
- Nettoyage final: supprimer completement le code legacy `ACTION_UPDATE_NOTIFICATIONS` apres communication/versionning.

## 12) Re-audit complet de cloture (2026-02-20)

Objectif de verification:
- Confirmer qu'aucune cassure email critique ne reste ouverte.
- Verifier les flux en 3 niveaux: E2E, intermediaire metier, logique coeur.

Matrice de verification:

1. E2E (de bout en bout, creation event -> traitement queue):
- `wms/tests/emailing/tests_email_flows_e2e.py`
- Couvre: commande publique, commande portail, demande de compte, livraison shipment.
- Statut: OK.

2. Intermediaire (producteurs d'emails metier + signaux + vues):
- `wms/tests/emailing/tests_notifications_queue.py`
- `wms/tests/emailing/tests_signal_notifications_queue.py`
- `wms/tests/public/tests_public_order_handlers.py`
- `wms/tests/admin/tests_account_request_handlers.py`
- `wms/tests/views/tests_views_public_order.py`
- `wms/tests/views/tests_views_portal.py`
- `wms/tests/views/tests_views_scan_dashboard.py`
- Statut: OK.

3. Logique coeur / robustesse:
- `wms/tests/emailing/tests_emailing.py`
- `wms/tests/emailing/tests_emailing_extra.py`
- `api/tests/tests_views_extra.py`
- `wms/tests/core/tests_models_methods.py`
- Statut: OK.

Campagne complete executee:
- `./.venv/bin/python manage.py test wms.tests.emailing wms.tests.public.tests_public_order_handlers wms.tests.admin.tests_account_request_handlers wms.tests.views.tests_views_public_order wms.tests.views.tests_views_portal api.tests.tests_views_extra wms.tests.views.tests_views_scan_dashboard`
- Resultat: 153 tests, OK.

Conclusion de cloture:
- Les flux emails sont operationnels et couverts a plusieurs niveaux (E2E + intermediaire + logique).
- Les cassures C1/C3/C4/C5/C6 sont traitees.
- Aucun blocant critique identifie dans le perimetre email.
