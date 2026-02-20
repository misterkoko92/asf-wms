# Audit complet des flux email - cloture

Date: 2026-02-20

## 1) Objectif et methode

Objectif:
- Verifier l'etat reel de tous les flux emails apres corrections.
- Valider la couverture E2E + intermediaire + logique coeur.

Methode:
- Relecture code + templates + points d'entree.
- Verification des regles de routage destinataires.
- Execution d'une campagne de tests multi-niveaux.

## 2) Perimetre fichiers

Coeur queue/envoi:
- `wms/emailing.py`
- `wms/models_domain/integration.py`
- `wms/management/commands/process_email_queue.py`
- `wms/runtime_settings.py`
- `wms/views_scan_settings.py`

Producteurs metier:
- `wms/order_notifications.py`
- `wms/public_order_handlers.py`
- `wms/account_request_handlers.py`
- `wms/admin_account_request_approval.py`
- `wms/signals.py`

Portail / destinataires:
- `wms/models_domain/portal.py`
- `wms/views_portal_account.py`
- `wms/views_portal_orders.py`

API integration:
- `api/v1/views.py`
- `api/v1/serializers.py`

Templates email:
- `templates/emails/order_admin_notification_public.txt`
- `templates/emails/order_admin_notification_portal.txt`
- `templates/emails/order_confirmation.txt`
- `templates/emails/account_request_admin_notification.txt`
- `templates/emails/account_request_received.txt`
- `templates/emails/account_request_approved.txt`
- `templates/emails/account_request_approved_user.txt`
- `templates/emails/shipment_status_admin_notification.txt`
- `templates/emails/shipment_tracking_admin_notification.txt`
- `templates/emails/shipment_delivery_notification.txt`

## 3) Cartographie des flux

1. Commande publique:
- Producteur: `wms/public_order_handlers.py`.
- Emails emis: admin + confirmation association.
- Queue: `IntegrationEvent` outbound `source=wms.email`, `event_type=send_email`.

2. Commande portail association:
- Producteur: `wms/order_notifications.py`.
- Emails emis: admin + confirmation association (email compte + emails de notification du profil).

3. Demande de compte:
- Producteur: `wms/account_request_handlers.py`.
- Emails emis: admin + accuse reception demandeur.

4. Approbation demande compte (admin):
- Producteur: `wms/admin_account_request_approval.py`.
- Emails emis: confirmation approbation user/association selon type.

5. Suivi expedition:
- Producteur: `wms/signals.py`.
- Emails emis:
  - changement statut shipment -> notification admin.
  - creation tracking event -> notification admin.
  - passage `ShipmentStatus.DELIVERED` -> notification destinataires opt-in (`notify_deliveries`) filtree par destination.

## 4) Regles et securite verifiees

Queue email:
- Retry/backoff et statut `pending/processing/processed/failed` operationnels.
- Reclaim d'events `processing` stale operationnel.

Destinataires:
- Normalisation queue globale (`_normalize_recipients`): trim, dedup case-insensitive, filtrage valeurs invalides/non-string.
- Livraison: selection `AssociationRecipient` avec `is_active=True`, `notify_deliveries=True`, et scope destination coherent.

API:
- Update des events queue email outbound bloque via `api/v1/views.py` pour `outbound + wms.email + send_email`.

Portail:
- Chemin legacy `update_notifications` desactive (plus d'ecriture de `notification_emails` par ce chemin).
- `notification_emails` reste alimente via le flux principal `update_profile` (contacts portail).

## 5) Campagne de tests executee

Campagne principale (E2E + intermediaire + API):
- Commande:
  - `./.venv/bin/python manage.py test wms.tests.emailing wms.tests.public.tests_public_order_handlers wms.tests.admin.tests_account_request_handlers wms.tests.views.tests_views_public_order wms.tests.views.tests_views_portal api.tests.tests_views_extra wms.tests.views.tests_views_scan_dashboard`
- Resultat:
  - 153 tests, OK.

Couverture logique coeur:
- Commande:
  - `./.venv/bin/python manage.py test wms.tests.core.tests_models_methods`
- Resultat:
  - 11 tests, OK.

Validation ciblage portail legacy:
- Commande:
  - `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalAccountViewsTests`
- Resultat:
  - 15 tests, OK.

Validation normalisation queue:
- Commande:
  - `./.venv/bin/python manage.py test wms.tests.emailing.tests_emailing_extra`
- Resultat:
  - 14 tests, OK.

## 6) Conclusion

Etat global:
- Aucun blocant critique identifie sur les flux mails.
- Les corrections C1/C3/C4/C5/C6 sont en place et couvertes.
- Couverture de verification conforme a la demande:
  - E2E: OK.
  - Intermediaire (producteurs/handlers/signaux/views): OK.
  - Logique coeur queue/API/destinataires: OK.

Amelioration non bloquante restante:
- Supprimer definitivement le branchement legacy `ACTION_UPDATE_NOTIFICATIONS` apres periode de transition (le chemin est deja desactive).

## 7) Mise a jour regles (post-cloture)

Ajouts appliques apres cloture initiale:
- Ciblage groupes metier:
  - `Account_User_Validation`
  - `Shipment_Status_Update`
  - `Shipment_Status_Update_Correspondant`
- Notification commande validation/statut:
  - superusers + association liee a la commande.
- Notification shipment parties:
  - expediteur + destinataire sur statuts cibles.
- Notification shipment correspondant:
  - planifie + OK mise a bord pour groupe correspondant + correspondant shipment.

Reference detaillee:
- `docs/email_flows_target_matrix_2026-02-20.md`

## 8) Verification finale de regression

Verification complete executee apres implementation des nouvelles regles:
- `./.venv/bin/python manage.py test wms.tests.emailing wms.tests.admin.tests_account_request_handlers wms.tests.public.tests_public_order_handlers wms.tests.orders.tests_order_view` -> OK.
- `./.venv/bin/python manage.py test wms.tests` -> OK (914 tests, 2 skips).
- `./.venv/bin/python manage.py makemigrations --check --dry-run` -> No changes detected.

Mise a jour transport email:
- Tous les flux passent en "direct d'abord, queue en fallback".
