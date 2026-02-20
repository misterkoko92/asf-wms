# Matrice cible des flux email

Date: 2026-02-20

## 1) Regles metier implementees

1. Soumission demande de compte (association + user WMS):
- Destinataires: superusers + groupe `Account_User_Validation`.
- Accuse de reception demandeur maintenu.
- Fichier: `wms/account_request_handlers.py`.

2. Approbation admin d'une demande de compte:
- Destinataire: email du demandeur.
- Fichier: `wms/admin_account_request_approval.py`.

3. Nouvelle commande (public + portail):
- Destinataires admin: superusers + groupe `ORDER_NOTIFICATION_GROUP_NAME` (defaut `Mail_Order_Staff`).
- Confirmation association maintenue.
- Fichiers: `wms/order_notifications.py`, `wms/public_order_handlers.py`.

4. Validation commande et changement de statut commande:
- Destinataires: superusers + association liee a la commande.
- Fichier: `wms/signals.py` (`_notify_order_status_change`).

5. Suivi expedition - changement de statut shipment:
- Destinataires admin: superusers + groupe `Shipment_Status_Update`.
- Fichier: `wms/signals.py` (`_notify_shipment_status_change`).

6. Suivi expedition - statuts `Planifie`, `Expedie`, `Recu escale`, `Livre`:
- Destinataires: expediteur + destinataire.
- Fichier: `wms/signals.py` (`_queue_shipment_party_notification`).

7. Suivi expedition - correspondant:
- `Planifie`: groupe `Shipment_Status_Update_Correspondant` + correspondant shipment.
- `OK mise a bord`: groupe `Shipment_Status_Update_Correspondant` + correspondant shipment.
- Fichier: `wms/signals.py` (`_queue_shipment_correspondant_notification`).

## 2) Variables d'environnement

- `ORDER_NOTIFICATION_GROUP_NAME` (defaut `Mail_Order_Staff`)
- `ACCOUNT_REQUEST_VALIDATION_GROUP_NAME` (defaut `Account_User_Validation`)
- `SHIPMENT_STATUS_UPDATE_GROUP_NAME` (defaut `Shipment_Status_Update`)
- `SHIPMENT_STATUS_CORRESPONDANT_GROUP_NAME` (defaut `Shipment_Status_Update_Correspondant`)

Sources:
- `asf_wms/settings.py`
- `.env.example`
- `deploy/pythonanywhere/asf-wms*.env.template`

## 3) Groupes crees automatiquement

Migration:
- `wms/migrations/0053_notification_groups.py`

Groupes assures:
- `Account_User_Validation`
- `Shipment_Status_Update`
- `Shipment_Status_Update_Correspondant`

## 4) Couverture tests ajoutee/mise a jour

- `wms/tests/admin/tests_account_request_handlers.py`
- `wms/tests/emailing/tests_order_status_notifications.py`
- `wms/tests/emailing/tests_signal_notifications_queue.py`
- `wms/tests/emailing/tests_signals_extra.py`
- `wms/tests/emailing/tests_email_flows_e2e.py`

## 5) Difference commande publique vs commande portail

- Commande publique:
  - Creation depuis lien public `PublicOrderLink` (hors authentification portail).
  - Flux code: `wms/public_order_handlers.py`.
  - Sujet admin: `ASF WMS - Nouvelle commande publique`.

- Commande portail:
  - Creation par utilisateur authentifie du portail association.
  - Flux code: `wms/views_portal_orders.py` + `wms/order_notifications.py`.
  - Sujet admin: `ASF WMS - Nouvelle commande`.

Point commun:
- Les destinataires admin passent dans les deux cas par `get_order_admin_emails()`
  (superusers + groupe `ORDER_NOTIFICATION_GROUP_NAME`).

## 6) Verification finale (audit complet post-implementation)

Campagnes lancees:
- `./.venv/bin/python manage.py test wms.tests.emailing wms.tests.admin.tests_account_request_handlers wms.tests.public.tests_public_order_handlers wms.tests.orders.tests_order_view`
  - Resultat: `OK` (88 tests).
- `./.venv/bin/python manage.py test wms.tests`
  - Resultat: `OK` (914 tests, 2 skips).
- `./.venv/bin/python manage.py makemigrations --check --dry-run`
  - Resultat: `No changes detected`.

Conclusion:
- Les flux emails demandes sont implementes et verifies.
- Les regles de ciblage (superusers + groupes + contacts metier) sont actives.

## 7) Strategie d'envoi (mise a jour)

- Tous les flux emails utilisent la meme strategie:
  1. tentative d'envoi direct (`send_email_safe`)
  2. si echec, fallback queue (`enqueue_email_safe`)
- Le traitement `process_email_queue` reste obligatoire pour evacuer les fallbacks.
