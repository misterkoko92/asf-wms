# Migration i18n Django native (legacy) - Design

## Contexte

Le site legacy Django expose aujourd'hui un selecteur FR/EN, mais l'anglais repose en grande partie sur le middleware [wms/middleware_runtime_translation.py](/Users/EdouardGonnu/asf-wms/wms/middleware_runtime_translation.py), qui remplace des fragments HTML a la volee.

Ce mecanisme a permis une premiere couverture rapide, mais il cree un anglais artificiel et fragile:
- libelles incoherents selon les ecrans,
- messages partiellement traduits,
- dependance a des remplacements de sous-chaines sans contexte,
- impossibilite de garantir un anglais metier idiomatique sur 100% des pages.

Le depot n'a pas encore de vrai catalogue [`locale/`](/Users/EdouardGonnu/asf-wms/locale) et utilise tres peu les primitives natives Django (`{% trans %}`, `{% blocktrans %}`, `gettext`, `gettext_lazy`) en dehors de la configuration langue dans [asf_wms/settings.py](/Users/EdouardGonnu/asf-wms/asf_wms/settings.py).

## Objectif

Obtenir un site legacy Django 100% traduit proprement en anglais, avec:
- une i18n Django native sur toutes les pages HTML legacy,
- des messages de formulaires, erreurs, notifications et emails egalement nativement internationalises,
- un glossaire metier unique et coherent,
- la suppression finale du middleware de traduction runtime.

## Perimetre

Inclus:
- templates legacy sous [`templates/portal/`](/Users/EdouardGonnu/asf-wms/templates/portal), [`templates/scan/`](/Users/EdouardGonnu/asf-wms/templates/scan), [`templates/admin/`](/Users/EdouardGonnu/asf-wms/templates/admin), [`templates/emails/`](/Users/EdouardGonnu/asf-wms/templates/emails), [`templates/print/`](/Users/EdouardGonnu/asf-wms/templates/print),
- textes Python visibles utilisateur dans [`wms/forms.py`](/Users/EdouardGonnu/asf-wms/wms/forms.py), handlers, vues, admin custom, notifications, documents,
- tests de rendu et de non-regression i18n.

Exclus:
- tout le scope pause Next/React (`frontend-next/`, [`wms/views_next_frontend.py`](/Users/EdouardGonnu/asf-wms/wms/views_next_frontend.py), [`wms/ui_mode.py`](/Users/EdouardGonnu/asf-wms/wms/ui_mode.py), tests Next associes),
- execution de migration front hors stack legacy.

## Decisions validees

- Cible retenue: vraie i18n Django native, pas d'amelioration cosmetique du middleware runtime.
- Langue source conservee: francais.
- Anglais produit via catalogues Django relus.
- Migration par vagues courtes, testables et reversibles.
- Le middleware runtime reste uniquement comme filet transitoire et doit etre retirable a tout moment via setting.

## Architecture cible

### 1. Source de verite des textes

Tous les textes visibles utilisateur doivent provenir de primitives Django i18n:
- templates: `{% trans %}` et `{% blocktrans %}`,
- Python: `gettext` / `gettext_lazy`,
- metadata admin/formulaires: `gettext_lazy`,
- messages calcules au runtime: `gettext`.

Objectif architectural: plus aucun texte visible utilisateur ne doit rester code en dur sans wrapper i18n.

### 2. Catalogue de traduction natif

Creer un vrai arbre [`locale/`](/Users/EdouardGonnu/asf-wms/locale) contenant au minimum:
- `locale/fr/LC_MESSAGES/django.po`
- `locale/en/LC_MESSAGES/django.po`

Le francais reste la langue de reference fonctionnelle. L'anglais devient une vraie traduction revue, pas un derive de remplacements HTML.

### 3. Middleware runtime transitoire

Le middleware [wms/middleware_runtime_translation.py](/Users/EdouardGonnu/asf-wms/wms/middleware_runtime_translation.py) ne doit plus etre considere comme le moteur EN du produit.

Pendant la migration:
- il est gardee uniquement pour les ecrans non encore convertis,
- il doit etre desactivable par setting,
- les tests doivent pouvoir s'executer sans lui.

Etat final:
- middleware retire du `MIDDLEWARE` dans [asf_wms/settings.py](/Users/EdouardGonnu/asf-wms/asf_wms/settings.py),
- fichier supprime une fois la couverture i18n native complete.

### 4. Glossaire metier unique

Les termes critiques doivent etre harmonises une seule fois et relus metier:
- `Reception` -> `Receiving`
- `Expedition` -> `Shipment`
- `Colis` -> `Parcel`
- `Carton` -> `Carton` ou `Parcel carton` selon contexte d'usage a fixer
- `Destinataire` -> `Recipient`
- `Correspondant` -> `Correspondent`
- `Litige` -> `Dispute`
- `Cloture` -> `Closure` ou `Closed` selon contexte

La regle est simple: une notion metier ne doit pas etre traduite differemment selon la page sans justification explicite.

## Migration par vagues

### Vague 1. Fondation i18n

- creer [`locale/`](/Users/EdouardGonnu/asf-wms/locale),
- activer un flag de desactivation du middleware runtime,
- etablir le glossaire metier,
- poser les premiers tests EN sans dependance implicite au middleware.

### Vague 2. Coquille partagee et pages publiques

Migrer les points d'entree les plus visibles:
- [templates/includes/language_switch.html](/Users/EdouardGonnu/asf-wms/templates/includes/language_switch.html)
- [templates/portal/login.html](/Users/EdouardGonnu/asf-wms/templates/portal/login.html)
- [templates/portal/access_recovery.html](/Users/EdouardGonnu/asf-wms/templates/portal/access_recovery.html)
- [templates/portal/set_password.html](/Users/EdouardGonnu/asf-wms/templates/portal/set_password.html)
- [templates/scan/public_account_request.html](/Users/EdouardGonnu/asf-wms/templates/scan/public_account_request.html)
- [templates/scan/public_order.html](/Users/EdouardGonnu/asf-wms/templates/scan/public_order.html)

### Vague 3. Portail association

Migrer l'UI portail et ses messages serveur:
- [templates/portal/base.html](/Users/EdouardGonnu/asf-wms/templates/portal/base.html)
- [templates/portal/dashboard.html](/Users/EdouardGonnu/asf-wms/templates/portal/dashboard.html)
- [templates/portal/account.html](/Users/EdouardGonnu/asf-wms/templates/portal/account.html)
- [templates/portal/recipients.html](/Users/EdouardGonnu/asf-wms/templates/portal/recipients.html)
- [templates/portal/order_create.html](/Users/EdouardGonnu/asf-wms/templates/portal/order_create.html)
- [templates/portal/order_detail.html](/Users/EdouardGonnu/asf-wms/templates/portal/order_detail.html)
- [wms/views_portal_auth.py](/Users/EdouardGonnu/asf-wms/wms/views_portal_auth.py)
- [wms/views_portal_orders.py](/Users/EdouardGonnu/asf-wms/wms/views_portal_orders.py)
- [wms/views_portal_account.py](/Users/EdouardGonnu/asf-wms/wms/views_portal_account.py)
- [wms/portal_order_handlers.py](/Users/EdouardGonnu/asf-wms/wms/portal_order_handlers.py)

### Vague 4. Scan operationnel

Migrer les ecrans et messages legacy les plus riches en vocabulaire metier:
- [templates/scan/base.html](/Users/EdouardGonnu/asf-wms/templates/scan/base.html)
- [templates/scan/dashboard.html](/Users/EdouardGonnu/asf-wms/templates/scan/dashboard.html)
- [templates/scan/receive.html](/Users/EdouardGonnu/asf-wms/templates/scan/receive.html)
- [templates/scan/receive_pallet.html](/Users/EdouardGonnu/asf-wms/templates/scan/receive_pallet.html)
- [templates/scan/receive_association.html](/Users/EdouardGonnu/asf-wms/templates/scan/receive_association.html)
- [templates/scan/stock.html](/Users/EdouardGonnu/asf-wms/templates/scan/stock.html)
- [templates/scan/stock_update.html](/Users/EdouardGonnu/asf-wms/templates/scan/stock_update.html)
- [templates/scan/orders_view.html](/Users/EdouardGonnu/asf-wms/templates/scan/orders_view.html)
- [templates/scan/order.html](/Users/EdouardGonnu/asf-wms/templates/scan/order.html)
- [templates/scan/shipment_create.html](/Users/EdouardGonnu/asf-wms/templates/scan/shipment_create.html)
- [templates/scan/shipments_ready.html](/Users/EdouardGonnu/asf-wms/templates/scan/shipments_ready.html)
- [templates/scan/shipments_tracking.html](/Users/EdouardGonnu/asf-wms/templates/scan/shipments_tracking.html)
- [templates/scan/faq.html](/Users/EdouardGonnu/asf-wms/templates/scan/faq.html)
- [templates/scan/settings.html](/Users/EdouardGonnu/asf-wms/templates/scan/settings.html)
- [wms/forms.py](/Users/EdouardGonnu/asf-wms/wms/forms.py)
- [wms/views_scan_dashboard.py](/Users/EdouardGonnu/asf-wms/wms/views_scan_dashboard.py)
- [wms/views_scan_receipts.py](/Users/EdouardGonnu/asf-wms/wms/views_scan_receipts.py)
- [wms/views_scan_stock.py](/Users/EdouardGonnu/asf-wms/wms/views_scan_stock.py)
- [wms/views_scan_orders.py](/Users/EdouardGonnu/asf-wms/wms/views_scan_orders.py)
- [wms/views_scan_shipments.py](/Users/EdouardGonnu/asf-wms/wms/views_scan_shipments.py)
- [wms/views_scan_misc.py](/Users/EdouardGonnu/asf-wms/wms/views_scan_misc.py)

### Vague 5. Admin et back-office custom

Migrer les vues admin custom et messages associes:
- [templates/admin/base_site.html](/Users/EdouardGonnu/asf-wms/templates/admin/base_site.html)
- [templates/admin/wms/organization_roles_review.html](/Users/EdouardGonnu/asf-wms/templates/admin/wms/organization_roles_review.html)
- [templates/admin/wms/stockmovement/change_list.html](/Users/EdouardGonnu/asf-wms/templates/admin/wms/stockmovement/change_list.html)
- [templates/admin/wms/stockmovement/form.html](/Users/EdouardGonnu/asf-wms/templates/admin/wms/stockmovement/form.html)
- [wms/admin.py](/Users/EdouardGonnu/asf-wms/wms/admin.py)
- [wms/admin_misc.py](/Users/EdouardGonnu/asf-wms/wms/admin_misc.py)
- [wms/admin_stockmovement_views.py](/Users/EdouardGonnu/asf-wms/wms/admin_stockmovement_views.py)
- [wms/admin_account_request_approval.py](/Users/EdouardGonnu/asf-wms/wms/admin_account_request_approval.py)

### Vague 6. Emails, documents et retrait final

Migrer:
- [templates/emails/](/Users/EdouardGonnu/asf-wms/templates/emails)
- [templates/print/](/Users/EdouardGonnu/asf-wms/templates/print)
- [wms/emailing.py](/Users/EdouardGonnu/asf-wms/wms/emailing.py)
- [wms/order_notifications.py](/Users/EdouardGonnu/asf-wms/wms/order_notifications.py)
- [wms/views_print_docs.py](/Users/EdouardGonnu/asf-wms/wms/views_print_docs.py)
- [wms/views_print_labels.py](/Users/EdouardGonnu/asf-wms/wms/views_print_labels.py)

Puis:
- desactiver le middleware dans les tests critiques,
- prouver que l'anglais vient des catalogues,
- retirer le middleware et nettoyer les tests obsoletes.

## Regles de traduction

- Traduire le sens metier, pas les mots.
- Eviter toute traduction litterale si elle nuit au naturel.
- Privilegier des phrases completes dans les catalogues quand le contexte compte.
- Utiliser `blocktrans` pour les phrases avec variables.
- Ne jamais reintroduire un systeme de remplacement de fragments.

## Controle qualite

Une page ne sera consideree comme migree que si:
- son HTML anglais est correct sans aide du middleware,
- ses erreurs de formulaires et messages serveur sont corrects en anglais,
- ses textes FR et EN proviennent bien des primitives Django i18n,
- les tests associes couvrent le rendu EN et l'absence de fuites FR critiques.

Mesures de verification:
- etendre [wms/tests/views/tests_i18n_language_switch.py](/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_i18n_language_switch.py),
- ajouter des tests par domaine (portal, scan, admin, emails, print),
- ajouter une verification automatisee pour reperer les chaines accentuees ou francaises visibles non internationalisees dans les templates et modules legacy,
- executer une passe de smoke tests EN avec middleware coupe.

## Risques et mitigations

### Risque 1. Derive terminologique

Mitigation:
- figer un glossaire metier avant les grosses vagues,
- centraliser les traductions dans les catalogues,
- imposer une relecture humaine des termes sensibles.

### Risque 2. Faux sentiment de couverture

Mitigation:
- considerer une page incomplete tant qu'elle change encore quand le middleware est coupe,
- ajouter un flag de desactivation pour tester explicitement le mode natif.

### Risque 3. Diff trop large et revue difficile

Mitigation:
- travailler par vagues limites,
- maintenir des tests locaux par domaine,
- faire des commits frequents par sous-surface migree.

## Strategie de retrait du middleware

1. Introduire un setting explicite pour l'activer ou non.
2. Migrer les vagues 1 a 5 en gardant le middleware comme filet transitoire.
3. Desactiver le middleware dans les tests critiques EN.
4. Migrer les emails et documents.
5. Retirer l'entree middleware de [asf_wms/settings.py](/Users/EdouardGonnu/asf-wms/asf_wms/settings.py).
6. Supprimer [wms/middleware_runtime_translation.py](/Users/EdouardGonnu/asf-wms/wms/middleware_runtime_translation.py) et les tests devenus sans objet.

## Critere de sortie

Le chantier est termine quand:
- 100% des pages legacy visibles par l'utilisateur rendent un anglais naturel,
- aucune page EN ne depend encore du middleware runtime,
- les emails et documents imprimes suivent la meme logique i18n native,
- le middleware runtime a ete retire du projet.
