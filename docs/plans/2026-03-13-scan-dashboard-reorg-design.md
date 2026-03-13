# Scan Dashboard Reorg Design

## Contexte

Le dashboard legacy scan expose aujourd'hui:
- une carte `Tableau de bord` avec un filtre global `period` et un filtre `destination`;
- une carte `KPI période (...)` basee sur des plages predefinies;
- une carte `Graphique expéditions` agregee par statut d'expedition;
- plusieurs autres cartes qui reutilisent le filtre destination du haut.

Le besoin est de reorganiser le dashboard sans toucher a la pile Next/React en pause, en conservant la vue Django legacy et ses tests.

## Objectif UX

La carte `Tableau de bord` reste visuellement en place et garde son filtre `destination`, ses actions et sa structure globale.

Changements demandes:
- la carte `KPI période (Semaine en cours)` devient `KPI`;
- cette carte expose un selecteur de periode par `date de debut` et `date de fin`;
- la periode par defaut est la semaine en cours, du lundi au dimanche inclus;
- la carte `Graphique expéditions` expose un filtre par etat d'expedition;
- la carte `Graphique expéditions` expose aussi un selecteur de periode;
- par defaut, la periode du graphique s'aligne sur celle des KPI;
- le graphique affiche les destinations en abscisse;
- le graphique affiche pour chaque destination le nombre d'expeditions et le nombre de colis equivalent.

La recommandation retenue est de supprimer uniquement l'ancien selecteur `period` de la premiere carte, car il deviendrait redondant avec les nouveaux filtres locaux.

## Approche retenue

Approche retenue:
- rester en rendu serveur GET sur la vue legacy `scan_dashboard`;
- introduire des filtres de dates explicites au lieu de la logique `today/7d/30d/week`;
- calculer les `equivalent_units` en live dans le dashboard en reutilisant la logique du planning via `resolve_shipment_unit_count(...)`;
- conserver les autres cartes et le filtre `destination` existant pour ne pas etendre le chantier au reste du dashboard.

Approches ecartees:
- reutiliser le dernier `PlanningShipmentSnapshot.equivalent_units`, car la valeur peut etre absente ou obsolete si un run planning n'a pas ete rejoue;
- persister `equivalent_units` directement sur `Shipment`, car cela ouvrirait un chantier de synchronisation metier hors scope.

## Regles de periode

Le dashboard doit parser quatre parametres GET:
- `kpi_start`
- `kpi_end`
- `chart_start`
- `chart_end`

Regles:
- les dates utilisateur sont interpretees dans le fuseau courant;
- `start` est converti en debut de jour local;
- `end` est converti en fin de jour local, borne incluse;
- si `chart_start` et `chart_end` sont absents, le graphique reprend les bornes KPI;
- si une date est invalide ou si `start > end`, fallback sur la semaine courante;
- la semaine courante est calculee du lundi au dimanche inclus.

## KPI

La carte `KPI` expose les indicateurs suivants:
- `Nb Commandes reçues`
- `Nb commandes en traitement`
- `Nb commandes a valider / corriger`
- `Nb Colis créés`
- `Nb Colis affectés`
- `Nb Expéditions prêtes`

Sources de calcul:
- `Nb Commandes reçues`: `Order.created_at` dans la periode KPI;
- `Nb commandes en traitement`: `Order.status in {reserved, preparing}` et `Order.created_at` dans la periode KPI;
- `Nb commandes a valider / corriger`: `Order.review_status in {pending_validation, changes_requested}` et `Order.created_at` dans la periode KPI;
- `Nb Colis créés`: `Carton.created_at` dans la periode KPI;
- `Nb Colis affectés`: `CartonStatusEvent.new_status = assigned` dans la periode KPI;
- `Nb Expéditions prêtes`: `Shipment.ready_at` dans la periode KPI.

Raisons metier:
- `commandes en traitement` doit refleter le flux operationnel reserve/preparing, distinct du flux de revue ASF;
- `colis affectes` doit s'appuyer sur l'evenement de transition vers `assigned`, pas sur un simple etat courant;
- `expeditions prêtes` correspond au passage a l'etat pret a planifier, deja materialise par `Shipment.ready_at`.

## Graphique expeditions

Base du graphique:
- expeditions non archivees;
- filtre optionnel par `Shipment.status`;
- filtre de periode du graphique applique sur `Shipment.created_at`.

L'usage de `Shipment.created_at` pour le graphique est retenu pour garder une lecture simple: nombre d'expeditions creees sur une periode. Il ne faut pas melanger cette lecture avec `ready_at`, qui sert deja au KPI `Expéditions prêtes`.

Aggregation:
- regrouper par destination;
- serie 1: nombre d'expeditions;
- serie 2: somme des `equivalent_units` des expeditions du groupe.

Libelle destination:
- preferer `destination.iata_code`;
- completer avec `destination.city` si disponible;
- fallback sur `destination_address` puis `-`.

Calcul `equivalent_units`:
- charger les regles actives `ShipmentUnitEquivalenceRule`;
- construire les `ShipmentUnitInput` a partir des `CartonItem` lies aux cartons de chaque expedition;
- appliquer `resolve_shipment_unit_count(...)`;
- si une expedition n'a aucun contenu colis, la somme vaut `0`.

## Architecture backend

La vue reste dans `wms/views_scan_dashboard.py`.

La logique doit etre refactorisee en helpers pour limiter la croissance de `scan_dashboard()`:
- normalisation des bornes de dates utilisateur;
- calcul de la semaine courante par defaut;
- construction des cartes KPI;
- construction des choix de statuts expedition pour le graphique;
- calcul live des `equivalent_units` par expedition;
- aggregation du graphique par destination.

Le filtre `destination` existant reste rattache a la premiere carte et continue de piloter les widgets historiques qui en dependent. Le nouveau graphique utilise son propre filtre `shipment_status`.

## Rendu template

Dans `templates/scan/dashboard.html`:
- supprimer le selecteur `period` dans la premiere carte;
- conserver le selecteur `destination` et les actions appliquer/reinitialiser de cette premiere carte;
- ajouter un formulaire GET local a la carte `KPI` avec `kpi_start` et `kpi_end`;
- renommer le titre de la carte en `KPI`;
- afficher les six indicateurs definis ci-dessus;
- ajouter un formulaire GET local a la carte `Graphique expéditions` avec `shipment_status`, `chart_start` et `chart_end`;
- preremplir `chart_start` et `chart_end` depuis les bornes KPI quand aucun filtre propre au graphique n'est fourni;
- remplacer le graphique par statut par un rendu groupe par destination avec deux series visibles: expeditions et equivalent colis.

Le rendu doit rester compatible avec les classes Bootstrap/scan deja testees, notamment les classes de lignes et champs de formulaires du dashboard.

## Cas limites

Le rendu doit rester robuste dans les cas suivants:
- dates invalides ou inversees;
- filtre `shipment_status` invalide;
- destination absente ou sans IATA;
- expedition sans carton ou sans carton item;
- aucune donnee sur la periode selectionnee.

Dans ces cas:
- fallback silencieux vers les valeurs par defaut pour les dates et statuts invalides;
- carte et graphique rendus avec etat vide sans erreur serveur.

## Tests

Tests vue/backend a ajouter ou adapter dans `wms/tests/views/tests_views_scan_dashboard.py`:
- bornes KPI par defaut sur lundi-dimanche inclus;
- recalcul des KPI sur periode personnalisee;
- separation `commandes en traitement` vs `commandes a valider / corriger`;
- comptage `colis affectes` base sur `CartonStatusEvent`;
- comptage `expeditions prêtes` base sur `ready_at`;
- alignement par defaut des dates du graphique sur les dates KPI;
- filtre du graphique par statut expedition;
- aggregation du graphique par destination;
- somme correcte des `equivalent_units` par destination.

Tests template/UI a adapter dans `wms/tests/views/tests_scan_bootstrap_ui.py`:
- presence des nouveaux controles de dates sur la carte KPI;
- presence du selecteur de statut expedition et des dates sur la carte graphique;
- maintien des classes `scan-dashboard-filter-row`, `scan-dashboard-filter-actions-inline` et `scan-dashboard-field` pour les lignes existantes ou leurs nouvelles variantes.

Le changement reste couvert sans extension du scope vers Next/React.
