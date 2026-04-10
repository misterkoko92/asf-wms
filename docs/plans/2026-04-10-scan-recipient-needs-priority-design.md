# Scan Recipient Needs Priority View - Design

## Contexte

Les preferences produits destinataire existent deja sur les surfaces de maintenance:
- `templates/portal/recipient_preferences.html`
- `templates/portal/recipient_detail.html`
- `templates/scan/admin_recipient_organization_detail.html`
- `wms/recipient_preference_view_helpers.py`
- `wms/recipient_product_preferences.py`

En parallele, le scan dispose deja de signaux d urgence et de retard sur:
- `templates/scan/dashboard.html`
- `templates/scan/pilotage.html`
- `wms/application/scan/dashboard_queries.py`
- `wms/scan_dashboard_sla.py`
- `wms/policies/sla.py`

Le besoin valide est de donner aux operateurs scan une vue de synthese pour repondre a quatre questions:
- qui veut quoi
- quand
- en quelle quantite
- comment prioriser

La nouvelle surface doit rester sur la stack Django legacy `scan`, sans rouvrir le scope Next/React ni le scope traduction.

## Objectif

Ajouter une nouvelle page `scan` dans le groupe `Stocks` afin de lire les besoins produits par destinataire, filtres par destination/destinataire/categorie, avec affichage des expediteurs lies et un tri par priorite operationnelle alignee sur l urgence d expedition.

## Decisions Validees

- la page vit dans le bloc de navigation `Stocks`
- le filtre `destination` fait partie du premier slice
- la vue est une surface de lecture et de priorisation, pas une nouvelle page d edition
- l urgence d expedition pilote le tri principal devant le seul besoin theorique
- la colonne priorite doit exposer les regles de seuils en hover
- la logique de retard doit reutiliser `tracking_alert_hours` pour parler la meme langue que le dashboard/pilotage
- l affichage des expediteurs doit accepter plusieurs liens actifs si necessaire

## Perimetre Du Premier Slice

Le premier slice doit rester fini et exploitable:
- lignes materialisees uniquement pour les preferences explicites produit
- lignes materialisees aussi pour les produits couverts par une preference explicite categorie
- pas de cross-join `tous les destinataires x tout le catalogue` pour les statuts implicites `non precise`
- les lignes `refuse` restent visibles sur demande, mais hors priorisation operationnelle
- pas de miroir API `api/v1/ui/` dans ce premier slice
- pas de nouvel ecran CRUD; les actions renvoient vers les surfaces existantes

Cette limitation est volontaire: un statut `non precise` n est pas actionnable a l echelle catalogue entier et ferait exploser le volume de lignes sans valeur operationnelle.

## Experience Utilisateur

### Placement

Nouvelle entree dans `templates/scan/includes/scan_sidebar_navigation.html`:
- groupe: `Stocks`
- libelle recommande: `Vue Besoins`
- `active` dedie pour que le groupe `Stocks` reste ouvert

### Structure De Page

1. Bandeau de synthese
- nombre de lignes prioritaires
- nombre de destinataires avec besoin urgent
- quantite totale restante a servir
- nombre de lignes couvertes

2. Barre de filtres
- destination
- destinataire
- categorie
- statut besoin: `a_servir`, `couverte`, `refusee`, `toutes`
- niveau priorite: `critique`, `haute`, `normale`, `couverte`, `toutes`

3. Tableau principal
- `Priorite`
- `Destination`
- `Destinataire`
- `Expediteur(s) lie(s)`
- `Produit`
- `Categorie`
- `Preference`
- `Quantite cible`
- `Livre`
- `Pipeline`
- `Reste a servir`
- `Periode`
- `Echeance / retard`
- `Action`

### Tri

Tri par defaut:
1. priorite
2. retard le plus fort
3. echeance la plus proche
4. reste a servir le plus eleve
5. destinataire puis produit

## Modele De Priorite

La priorite combine deux couches:

1. Besoin quantitatif
- `quantite cible`
- `livre`
- `pipeline`
- `reste a servir`
- fenetre de periode issue de `period_unit`

2. Urgence d expedition
- existence d expeditions ouvertes liees a ce besoin
- age de la plus ancienne expedition ouverte
- retard au regard de `tracking_alert_hours`
- depassement ou proximite de fin de periode

### Niveaux

`Critique`
- `reste_a_servir > 0`
- et fin de periode deja depassee
- ou expedition ouverte deja en retard au dela du seuil SLA

`Haute`
- `reste_a_servir > 0`
- et expedition ouverte en retard mais pas encore critique
- ou aucun pipeline ouvert
- ou fin de periode proche

`Normale`
- `reste_a_servir > 0`
- sans retard courant ni echeance immediate

`Couverte`
- `reste_a_servir = 0`

`Hors priorite`
- `refusee`

### Description Hover

Le badge de priorite doit fournir un texte explicatif complet via tooltip Bootstrap. Exemple:

`Critique: reste a servir 12, fin de periode depassee le 08/04, expedition ouverte en retard de 26h (seuil SLA 24h).`

Le hover doit decrire:
- le niveau calcule
- le ou les seuils appliques
- les donnees qui ont declenche le niveau

## Approche Technique

### Read Model

Creer un helper de composition dedie, recommande sous:
- `wms/application/scan/recipient_needs_queries.py`

Responsabilites:
- parser et normaliser les filtres
- construire les lignes a partir des preferences explicites et categories explicites
- reutiliser `list_recipient_product_coverages(...)`
- agreger les expediteurs actifs via `ShipmentShipperRecipientLink`
- classifier la priorite a partir de `tracking_alert_hours`
- exposer pour chaque ligne un texte tooltip directement exploitable par le template
- construire les cartes de synthese

### View Layer

Le premier slice peut rester dans:
- `wms/views_scan_stock.py`

Avec une nouvelle vue staff:
- route recommande: `scan/recipient-needs/`
- nom recommande: `scan_recipient_needs`

Le cablage devra aussi mettre a jour:
- `wms/views_scan.py`
- `wms/views.py`
- `wms/scan_urls.py`

### Template

Nouveau template recommande:
- `templates/scan/recipient_needs_view.html`

Le template doit:
- reutiliser les selecteurs scan/bootstrap existants
- afficher les badges de priorite avec tooltip
- initialiser localement `bootstrap.Tooltip` dans `extra_scripts`

### Actions

Pas de nouvelle mutation depuis cette page.

Action minimale du premier slice:
- ouvrir la fiche admin scan du destinataire (`scan_admin_recipient_organization_detail`)

Cette action garde la page de synthese centree sur la priorisation et evite de dupliquer les ecrans d edition existants.

## Risques Et Garde-Fous

- risque de volume de lignes: evite en n enumerant pas les produits implicites `non precise`
- risque de score opaque: reduit par le tooltip de seuils et l alignement sur `tracking_alert_hours`
- risque de duplication avec dashboard/pilotage: limite en faisant de cette page une vue detaillee de besoins, pas un second cockpit transverse
- risque de derive UI: la page reste sur les primitives scan/bootstrap existantes

## Tests Cibles

- tests query/helper pour les lignes, les filtres, les expediteurs lies, et la classification de priorite
- tests de vue pour le routage, le contexte, et le tri par defaut
- tests bootstrap/UI pour:
  - le nouveau lien sidebar
  - les colonnes visibles
  - le filtre destination
  - les tooltips de priorite

## Impact Map

Changement sur une page `scan`:
- modifier `wms/scan_urls.py`
- modifier la vue staff `scan`
- ajouter un template `templates/scan/`
- ajouter des tests `wms/tests/views/`

Propagation attendue:
- mettre a jour `docs/repo-reference/02-key-flows-and-living-tests.md` car une nouvelle route/operator read surface apparait dans le flux scan
- mettre a jour `docs/repo-reference/04-shared-contracts.md` car la navigation laterale scan change
- verifier `docs/mvp_spec.md` en cloture pour savoir si la nouvelle vue doit etre mentionnee comme surface officielle

Hors scope confirme:
- pas de page Next/React
- pas de travail FR/EN specifique
- pas de nouveau contrat API
