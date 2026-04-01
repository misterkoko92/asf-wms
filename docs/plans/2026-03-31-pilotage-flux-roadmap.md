# Pilotage Et Gestion Des Flux Roadmap

**Goal:** renforcer le pilotage opérationnel du WMS sans ouvrir un chantier de refonte large, en capitalisant d'abord sur les surfaces déjà présentes (`scan`, `portal`, `planning`, `api/v1/ui`, `runtime settings`, `workflow logs`).

**Approach:** livrer d'abord un pilotage actionnable sur le legacy Django existant, puis industrialiser la gestion des exceptions, puis ouvrir la couche prédictive et d'intégration externe. La roadmap évite de réinventer un front ou un moteur complet trop tôt; elle pousse les briques déjà en place jusqu'au point où un moteur de règles et une API v2 deviennent justifiés.

**Tech Stack:** Django 4.2 legacy templates, DRF (`api/v1/ui`, `api/v1/integrations/*`), modèles `wms/models_domain/*`, planning cockpit, runtime settings, queues `IntegrationEvent`, journalisation `wms.workflow`.

---

## Scope And Success Criteria

### Business objective

- réduire le temps entre détection d'un blocage et action opérateur
- rendre visibles les goulots d'étranglement par flux, pas seulement par écran
- donner aux associations une visibilité utile sur leurs dossiers
- mieux piloter l'affectation planning/capacité
- préparer une couche de reporting/BI sans casser les flux legacy

### Non-goals

- pas de reprise Next/React
- pas de réouverture du scope traduction
- pas de moteur de workflow générique en vague 1
- pas de réécriture des domaines shipment/portal/planning tant qu'un besoin de variabilité métier n'est pas prouvé

### Program-level KPIs

- délai moyen de prise en charge d'un blocage
- volume d'items sans propriétaire
- part des SLA en dépassement par segment
- délai moyen de résolution des litiges
- délai entre commande approuvée et création d'expédition
- taux de surcharge ou quasi-surcharge planning
- volume d'actions manuelles évitables

## Delivery Options

### Option A: cockpit d'action d'abord

- focus sur le dashboard scan, le portail et les actions rapides
- ROI rapide côté ops
- ne traite pas assez tôt la gouvernance des litiges et SLA

### Option B: centre litiges d'abord

- améliore bien la gestion des exceptions
- risque d'arriver trop tôt sans file d'action transverse ni reporting homogène

### Option C: visibilité actionnable -> centre d'exception -> pilotage prédictif

- progression la plus sûre
- réutilise les briques existantes
- prépare proprement l'API v2 et le moteur de règles

### Recommendation

- retenir l'option C

## Wave 1: Visibilite Actionnable

**Intent:** transformer les signaux déjà présents en file d'action exploitable par les équipes sans changer encore le moteur métier de fond.

**Target duration:** 2 à 4 semaines

**Exit criteria:**

- un opérateur voit sur `scan/dashboard` les priorités avec âge, propriétaire, dernière étape, CTA direct
- la santé email et document scan est visible au même endroit
- le portail association montre un vrai cockpit de dossier et pas seulement l'historique des commandes
- les nouveaux indicateurs ont une couverture de tests UI/API et des règles de smoke

### Ticket W1.1: File d'action transverse sur le dashboard scan

**Why now:** l'UI API produit déjà une `timeline` et des `pending_actions`, mais le dashboard legacy affiche surtout des cartes agrégées.

**Impact:** très élevé

**Effort:** M

**Suggested owner:** produit/ops + backend legacy

**Dependencies:** none

**Likely touchpoints:**

- `wms/views_scan_dashboard.py`
- `templates/scan/dashboard.html`
- `api/v1/ui_views.py`
- `wms/tests/views/tests_views_scan_dashboard.py`
- `api/tests/tests_ui_endpoints.py`
- `docs/release_checklist.md`

**Deliverables:**

- bloc "À traiter maintenant" avec items triés par priorité et ancienneté
- drill-down par type: stock bas, commandes en attente, litiges, suivi en retard, dossiers clôturables
- CTA explicites et cohérents avec les surfaces réelles
- filtres par destination et éventuellement par owner

**Validation:**

- tests HTML dashboard
- tests API UI dashboard
- smoke manuel: navigation depuis chaque item vers la bonne surface

### Ticket W1.2: Observabilité unifiée des queues email et document scan

**Why now:** l'exploitation suit déjà les deux queues dans le runbook, mais seule la queue email remonte dans le cockpit.

**Impact:** élevé

**Effort:** S

**Suggested owner:** backend ops

**Dependencies:** W1.1 recommandé, non bloquant

**Likely touchpoints:**

- `wms/views_scan_dashboard.py`
- `templates/scan/dashboard.html`
- `wms/document_scan_queue.py`
- `wms/tests/views/tests_views_scan_dashboard.py`
- `docs/operations.md`
- `docs/release_checklist.md`

**Deliverables:**

- cartes `document scan` pending/processing/failed/stale
- état agrégé "queues saines / incident"
- CTA vers procédures de replay ou d'investigation

**Validation:**

- tests dashboard ciblés
- seed locale avec backlog mixte
- relecture du runbook après livraison

### Ticket W1.3: Cockpit portail association

**Why now:** le portail expose un historique, mais peu d'aide réelle au pilotage côté association.

**Impact:** élevé

**Effort:** M

**Suggested owner:** backend portal + produit

**Dependencies:** none

**Likely touchpoints:**

- `wms/views_portal_orders.py`
- `templates/portal/dashboard.html`
- `api/v1/ui_views.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`
- `api/tests/tests_ui_endpoints.py`

**Deliverables:**

- KPI visibles en HTML: en attente de validation, corrections demandées, avec expédition, livrées
- statut de dossier plus lisible: étape atteinte, attente suivante, documents attendus
- messages d'action contextualisés: "compléter", "attendre validation", "suivre livraison"

**Validation:**

- tests portail bootstrap/UI
- test API dashboard portail
- smoke manuel sur un compte avec plusieurs états de commande

### Ticket W1.4: Référentiel minimum des propriétaires et files d'attente

**Why now:** l'API UI emploie déjà des owners textuels (`magasin`, `qualite`, `admin`) mais sans contrat produit stable.

**Impact:** moyen

**Effort:** S

**Suggested owner:** backend + ops lead

**Dependencies:** W1.1

**Likely touchpoints:**

- `api/v1/ui_views.py`
- `docs/repo-reference/04-shared-contracts.md`
- `docs/operations.md`

**Deliverables:**

- taxonomie courte des owners et priorités
- mapping owner -> surface d'action
- contrat stable pour les listes "à traiter"

**Validation:**

- revue produit/ops
- mise à jour doc repo-reference si le contrat est officialisé

## Wave 2: Centre D'Exception Et SLA Proactifs

**Intent:** ne plus seulement voir les problèmes, mais les prendre en charge, les assigner et mesurer leur résolution.

**Target duration:** 3 à 5 semaines

**Exit criteria:**

- un litige porte un motif, un propriétaire, un état, un historique
- les retards SLA produisent des alertes exploitables et pas seulement des ratios
- les blocages majeurs ont un cycle de vie de traitement

### Ticket W2.1: Centre litiges

**Why now:** le litige est aujourd'hui un overlay puissant mais pauvre en structure métier.

**Impact:** très élevé

**Effort:** L

**Suggested owner:** backend shipment

**Dependencies:** W1.1 recommandé

**Likely touchpoints:**

- `wms/shipment_tracking_handlers.py`
- `wms/models_domain/shipment.py`
- `templates/scan/shipment_tracking.html`
- `templates/scan/shipments_tracking.html`
- `wms/views_scan_shipments.py`
- `wms/tests/views/tests_views_tracking_dispute.py`
- `docs/repo-reference/04-shared-contracts.md`

**Deliverables:**

- motifs normalisés
- notes de résolution
- propriétaire/responsable
- date cible de traitement
- timeline d'actions litige visible depuis le dossier
- vues filtrées "litiges ouverts / en retard / sans owner"

**Validation:**

- tests de transitions litige
- tests UI dossier/liste
- contrôle de non-régression sur verrouillages shipment/carton

### Ticket W2.2: Alertes SLA proactives

**Why now:** les SLA sont calculés mais pas suffisamment pilotés.

**Impact:** élevé

**Effort:** M

**Suggested owner:** backend ops

**Dependencies:** W1.1

**Likely touchpoints:**

- `wms/views_scan_dashboard.py`
- `wms/runtime_settings.py`
- `wms/views_scan_settings.py`
- `wms/models_domain/integration.py`
- `wms/tests/views/tests_views_scan_dashboard.py`
- `docs/operations.md`

**Deliverables:**

- alertes par segment et par criticité
- seuils configurables par profil standard/incident
- digest ops quotidien ou périodique
- vues "retards nouveaux" vs "retards persistants"

**Validation:**

- tests calcul SLA + dashboard
- revue presets runtime
- runbook incident mis à jour

### Ticket W2.3: File de traitement des blocages workflow

**Why now:** les blocages existent déjà en KPI, pas encore comme objets de travail.

**Impact:** élevé

**Effort:** M

**Suggested owner:** backend ops/product

**Dependencies:** W1.1

**Likely touchpoints:**

- `wms/views_scan_dashboard.py`
- `templates/scan/dashboard.html`
- `wms/views_scan_shipments.py`
- `wms/views_portal_orders.py`
- `api/v1/ui_views.py`

**Deliverables:**

- liste des blocages avec owner, âge, catégorie, CTA
- séparation blocages "création expédition", "commande", "suivi", "clôture", "queue"
- possibilité de marquer "pris en charge"

**Validation:**

- tests dashboard/action list
- vérification manuelle du tri/priorisation

### Ticket W2.4: Projection exploitable des événements workflow

**Why now:** les logs structurés existent, mais ils ne sont pas encore une vraie couche de pilotage.

**Impact:** moyen à élevé

**Effort:** M

**Suggested owner:** backend platform

**Dependencies:** W2.1 recommandé

**Likely touchpoints:**

- `wms/workflow_observability.py`
- nouvelle couche de projection ou table dédiée
- `api/v1/views.py` ou nouveau endpoint de lecture
- tests métier/reporting

**Deliverables:**

- indicateurs dérivés consultables sans parsing de logs
- lead time par étape
- temps de résolution litige
- retards par destination

**Validation:**

- tests de projection
- cohérence entre événements source et métriques calculées

## Wave 3: Pilotage Predictif Et Ouverture Externe

**Intent:** passer du correctif à l'anticipation, puis ouvrir les données de pilotage aux outils externes.

**Target duration:** 4 à 8 semaines

**Exit criteria:**

- le planning alerte avant surcharge ou sous-capacité
- les acteurs externes peuvent consommer des indicateurs stables
- les règles métier critiques sont configurables là où la variabilité est réelle

### Ticket W3.1: Cockpit capacité planning/vols

**Why now:** le cockpit planning expose déjà la charge, mais peu d'aide à l'arbitrage préventif.

**Impact:** très élevé

**Effort:** M à L

**Suggested owner:** backend planning

**Dependencies:** W1.1, W2.4 recommandé

**Likely touchpoints:**

- `wms/views_planning.py`
- `wms/planning/stats.py`
- `wms/planning/operator_options.py`
- `templates/planning/_version_planning_block.html`
- `templates/planning/_version_stats_block.html`
- `templates/planning/_version_planning_summary_block.html`
- `wms/tests/views/tests_views_planning.py`
- `wms/tests/planning/tests_version_dashboard.py`

**Deliverables:**

- capacité restante par vol
- alertes surcharge / quasi-surcharge
- simulation de re-répartition simple
- vue de saturation par destination et semaine

**Validation:**

- tests planning dashboard
- scénarios de capacité insuffisante
- smoke planning run/version

### Ticket W3.2: API v2 de pilotage et exports BI

**Why now:** l'intégration externe est déjà amorcée, mais l'API actuelle reste surtout transactionnelle ou brute.

**Impact:** élevé

**Effort:** L

**Suggested owner:** backend platform/integration

**Dependencies:** W2.4

**Likely touchpoints:**

- `api/v1/views.py`
- nouveaux endpoints de lecture stables
- `api/tests/`
- `docs/repo-reference/03-impact-map.md`
- docs ops/integration

**Deliverables:**

- endpoints stables pour backlog, SLA, litiges, charge planning, volumes par destination
- filtres temporels et filtres par destination/owner/statut
- contrat versionné orienté CRM/BI/ops

**Validation:**

- tests API de contrat
- documentation d'usage
- contrôle permissions/clé d'intégration

### Ticket W3.3: Règles workflow et SLA configurables

**Why now:** après avoir observé plusieurs cycles, on saura quelles règles méritent vraiment d'être sorties du code.

**Impact:** élevé

**Effort:** L

**Suggested owner:** backend core domain

**Dependencies:** W2.2, W2.4

**Likely touchpoints:**

- `wms/models_domain/*`
- `wms/runtime_settings.py`
- nouveaux objets de configuration
- `wms/views_scan_settings.py`
- tests domaine shipment/portal/planning

**Deliverables:**

- seuils par type de flux ou destination
- transitions/contraintes configurables là où le besoin est démontré
- garde-fous de compatibilité legacy

**Validation:**

- TDD domaine
- migration/seed de réglages
- documentation des contrats modifiés

## Sequencing And Dependencies

### Recommended order

1. W1.1
2. W1.2
3. W1.3
4. W1.4
5. W2.1
6. W2.2
7. W2.3
8. W2.4
9. W3.1
10. W3.2
11. W3.3

### Why this order

- W1 concentre les gains rapides et réutilise l'existant
- W2 transforme les signaux en traitement gouverné
- W3 n'arrive qu'après stabilisation des métriques et du vocabulaire métier

## Suggested Team Split

### Stream A: cockpit ops

- W1.1
- W1.2
- W2.2
- W2.3

### Stream B: portal and exceptions

- W1.3
- W2.1

### Stream C: planning and integration

- W2.4
- W3.1
- W3.2
- W3.3

## Risks And Watchpoints

- ne pas dupliquer un cockpit HTML et un cockpit API sans contrat commun
- ne pas créer un centre litiges riche sans clarifier le propriétaire métier de résolution
- ne pas lancer un moteur de règles avant d'avoir observé quels paramètres varient réellement
- ne pas étendre l'API externe sans geler les définitions métier exposées

## Closure Evidence Per Ticket

- tests ciblés verts
- smoke manuel correspondant à la surface
- doc ops/release mise à jour si comportement de prod impacté
- entrée repo-reference mise à jour si contrat partagé modifié
- note de clôture courte: périmètre, risques résiduels, suites ouvertes

## Recommended Next Step

- cadrer et lancer immédiatement la **Wave 1** avec un lot initial `W1.1 + W1.2 + W1.3`
- garder `W1.4` comme mini-lot transverse pour stabiliser le vocabulaire owner/priorité avant d'ouvrir les vagues suivantes
