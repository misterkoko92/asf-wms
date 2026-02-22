# P0 - Inventaire fonctionnel (legacy Benev/Classique)

## 1) Contrôle d'accès et rôles

## Scan (opérations internes)

- Décorateur principal: `scan_staff_required`
- Règle: utilisateur authentifié + `is_staff=True`
- Source: `wms/view_permissions.py:17`

## Portal (associations)

- Décorateur principal: `association_required`
- Règles:
  - profil association obligatoire,
  - changement de mot de passe forcé possible,
  - blocage si aucun destinataire `is_delivery_contact=True`.
- Source: `wms/view_permissions.py:28`

## Admin requis

- Imports scan: superuser obligatoire.
- Paramètres runtime: superuser obligatoire.
- Templates d'impression: superuser obligatoire.

## 2) Modes UI et thème à reproduire à l'identique

- UI supportée aujourd'hui: `classic`, `nova`, `studio`, `benev`, `timeline`, `spreadsheet`
- Reset par défaut: `benev + classic`
- Sources:
  - `wms/static/scan/scan.js:80`
  - `wms/static/scan/scan.js:138`
  - `templates/portal/base.html:108`
  - `templates/portal/base.html:160`

## 3) Statuts métier à reprendre strictement

## Expédition

- `draft`, `picking`, `packed`, `planned`, `shipped`, `received_correspondent`, `delivered`
- Source: `wms/models_domain/shipment.py:16`

## Suivi expédition

- `planning_ok`, `planned`, `moved_export`, `boarding_ok`, `received_correspondent`, `received_recipient`
- Source: `wms/models_domain/shipment.py:173`

## Colis

- `draft`, `picking`, `packed`, `assigned`, `labeled`, `shipped`
- Source: `wms/models_domain/shipment.py:238`

## Réception

- `draft`, `received`, `cancelled`
- Source: `wms/models_domain/inventory.py:136`

## Commande portail (revue)

- `pending_validation`, `approved`, `rejected`, `changes_requested`
- Source: `wms/models_domain/portal.py:21`

## Documents (revue)

- `pending`, `approved`, `rejected`
- Source: `wms/models_domain/portal.py:416`

## 4) Écrans et vues legacy (source de vérité P0)

## Scan - écrans principaux

- Dashboard: `scan_dashboard` -> `scan/dashboard.html`
  - source: `wms/views_scan_dashboard.py:320`
- Stock: `scan_stock` -> `scan/stock.html`
  - source: `wms/views_scan_stock.py:50`
- MAJ stock: `scan_stock_update` -> `scan/stock_update.html`
  - source: `wms/views_scan_stock.py:56`
- Création colis: `scan_pack` -> `scan/pack.html`
  - source: `wms/views_scan_shipments.py:340`
- Création expédition: `scan_shipment_create` -> `scan/shipment_create.html`
  - source: `wms/views_scan_shipments.py:400`
- Édition expédition: `scan_shipment_edit` -> `scan/shipment_create.html`
  - source: `wms/views_scan_shipments.py:432`
- Suivi liste: `scan_shipments_tracking` -> `scan/shipments_tracking.html`
  - source: `wms/views_scan_shipments.py:271`
- Suivi détail: `scan_shipment_track` -> `scan/shipment_tracking.html`
  - source: `wms/views_scan_shipments.py:538`

## Scan - écrans secondaires

- Colis prêts: `scan_cartons_ready`
- Expéditions prêtes: `scan_shipments_ready`
- Réceptions: `scan_receipts_view`, `scan_receive`, `scan_receive_pallet`, `scan_receive_association`
- Commandes: `scan_order`, `scan_orders_view`
- Paramètres: `scan_settings`
- Imports: `scan_import`
- Templates docs: `scan_print_templates`, `scan_print_template_edit`, `scan_print_template_preview`

## Portal

- Login: `portal_login`
  - source: `wms/views_portal_auth.py:62`
- Dashboard commandes: `portal_dashboard`
  - source: `wms/views_portal_orders.py:405`
- Nouvelle commande: `portal_order_create`
  - source: `wms/views_portal_orders.py:414`
- Détail commande + upload docs: `portal_order_detail`
  - source: `wms/views_portal_orders.py:519`
- Destinataires: `portal_recipients`
  - source: `wms/views_portal_account.py:544`
- Compte: `portal_account`
  - source: `wms/views_portal_account.py:603`

## 5) Champs/validations critiques (flux cible)

## 5.1 MAJ stock

Formulaire: `ScanStockUpdateForm` (`wms/forms.py:289`)

Champs:

- `product_code`: requis + produit doit exister (`clean_product_code`)
- `quantity`: requis, `min_value=1`
- `expires_on`: requis
- `lot_code`: optionnel
- `donor_contact`: optionnel

Règles serveur:

- emplacement produit obligatoire (via `product.default_location`)
- erreurs métier via `StockError`
- source: `wms/stock_update_handlers.py`

## 5.2 Création/édition expédition

Formulaire: `ScanShipmentForm` (`wms/forms.py:376`)

Champs requis:

- `destination`
- `shipper_contact`
- `recipient_contact`
- `correspondent_contact`
- `carton_count >= 1`

Validations de cohérence (`wms/forms.py:483`):

- expéditeur compatible destination,
- destinataire compatible expéditeur,
- destinataire compatible destination,
- correspondant compatible destination.

Règles création (`wms/scan_shipment_handlers.py:171`):

- affectation colis existants seulement si `packed` et non affectés,
- création colis mono-produit possible pendant la création,
- save draft supporté (`EXP-TEMP-XX`),
- synchro état prêt après mutation.

Règles édition (`wms/scan_shipment_handlers.py:261`):

- modification interdite si statut verrouillé (`planned/shipped/received_correspondent/delivered`),
- modification interdite si litige actif,
- retrait impossible d'un colis déjà expédié,
- colis déjà affecté à une autre expédition interdit.

## 5.3 Suivi expédition + litige + clôture

Formulaire: `ShipmentTrackingForm` (`wms/forms.py:530`)

Champs:

- `status` (filtré selon statuts autorisés),
- `actor_name` requis,
- `actor_structure` requis,
- `comments` optionnel.

Transitions:

- validation des transitions autorisées par état courant,
- garde-fou: planification impossible si colis non affectés/étiquetés.
- source: `wms/shipment_tracking_handlers.py:105`

Litiges:

- `set_disputed` bloque la progression,
- `resolve_dispute` remet l'expédition à `packed` selon règle.
- source: `wms/shipment_tracking_handlers.py`

Clôture:

- autorisée seulement si toutes étapes tracking complètes + livré + pas litige + non déjà clos.
- source:
  - `wms/views_scan_shipments_support.py:149`
  - `wms/shipment_view_helpers.py:364`

## 5.4 Portal - création commande

Vue: `portal_order_create` (`wms/views_portal_orders.py:414`)

Contraintes:

- destination obligatoire,
- destinataire obligatoire et compatible destination,
- au moins 1 produit,
- adresse association requise pour destinataire "self",
- vérification de stock via logique métier (`StockError`).

## 5.5 Portal - destinataires / compte

Destinataires (`portal_recipients`):

- escale requise,
- nom structure requis,
- adresse requise,
- emails validés,
- si notification active -> au moins un email.

Compte (`portal_account`):

- nom association requis,
- adresse requise,
- au moins un contact email,
- chaque contact doit avoir au moins un type (administratif/shipping/billing).

## 6) Actions UI critiques détectées dans les templates

- Dashboard scan: filtres période/destination.
- Stock: filtres + tri + reset.
- MAJ stock: scan produit + enregistrement.
- Expédition:
  - `save_draft`,
  - `save_draft_pack`,
  - création/modification.
- Suivi:
  - `set_disputed`,
  - `resolve_dispute`,
  - `close_shipment_case` depuis liste suivi.
- Portal:
  - `update_profile`,
  - `upload_docs`,
  - `create_recipient`/`update_recipient`.

## 7) PWA/offline existant (legacy scan)

- Manifest existant: `wms/static/scan/manifest.json`
- Service worker existant (cache assets scan): `wms/views_scan_misc.py`

Implication migration:

- le mode offline actuel est limité au cache d'assets/navigation,
- la V1 Next devra ajouter une vraie file d'attente d'actions offline (stock/update statut).
