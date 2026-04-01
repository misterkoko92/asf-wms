# ASF WMS V2 Phase 2 Global Pilotage Design

**Status:** local-first design, April 1, 2026

**Goal:** faire passer ASF WMS V2 d'un ensemble de cockpits locaux utiles mais encore ponctuels à un vrai pilotage transverse, historisé et actionnable sur `scan`, `portal`, `planning`, les queues techniques, et les exports planning.

**Current baseline:** la phase 1 locale a déjà livré le dashboard `scan` actionnable, le cockpit portail, le centre litiges, les alertes SLA, la file de blocages workflow, les projections shipment/destination, le cockpit capacité planning, et l'export planning strict `xlsx + pdf`.

---

## 1. Problem Statement

Le repo dispose maintenant de bons signaux opérationnels, mais ils restent surtout:

- instantanés, avec peu d'historique exploitable
- dispersés entre plusieurs surfaces
- partiellement manuels pour l'escalade et le suivi
- insuffisamment corrélés entre planning, risques destination, litiges, SLA, et communications planning

La phase 2 doit donc privilégier la persistance du signal, l'escalade locale, puis une lecture transverse quotidienne, avant d'ouvrir un moteur de règles plus riche.

## 2. Design Options

### Option A: cockpit transverse d'abord

- construire immédiatement un grand cockpit daily ops
- bénéfice visuel rapide
- mais faible robustesse si le cockpit consomme uniquement des instantanés calculés à la volée

### Option B: historique + escalades d'abord

- historiser les KPI clés
- construire une couche d'escalade locale sur anomalies persistantes
- alimenter ensuite un cockpit transverse daily ops
- laisser l'industrialisation PDF/mail et le moteur de règles comme suites logiques

### Option C: moteur de règles d'abord

- introduire tôt des seuils et politiques configurables
- mais trop risqué tant que les signaux et la charge réelle ne sont pas encore stabilisés

## 3. Recommendation

Retenir l'option B.

Ordre recommandé:

1. `P2.1` Historique KPI pilotage
2. `P2.2` Escalades automatiques locales
3. `P2.3` Cockpit transverse daily ops
4. `P2.4` Industrialisation planning PDF/mail
5. `P2.5` Règles et calibration pilotage

Ce séquencement protège le repo contre deux dérives:

- empiler des widgets sans mémoire
- introduire trop tôt un moteur de règles sans signal d'exploitation fiable

## 4. Architectural Principles

### Legacy Django remains the visible surface

La phase 2 reste sur le stack legacy:

- `templates/scan/`
- `templates/portal/`
- `templates/planning/`
- `wms/views_scan_*`
- `wms/views_portal_*`
- `wms/views_planning.py`
- `api/v1/ui_views.py`
- `api/v1/views.py`

La migration Next/React reste hors scope.

### Reuse read models and helpers already in place

Les nouvelles briques doivent s'appuyer sur:

- `ShipmentWorkflowProjection`
- agrégats destination et destination-week
- KPI dashboard `scan`
- cockpit planning/capacité
- exports planning stricts

La phase 2 ne doit pas recalculer côté template des règles déjà stabilisées ailleurs.

### Prefer derived, inspectable, rebuildable data

La persistance phase 2 doit privilégier:

- read models dérivés
- snapshots rejouables
- commandes de rebuild
- règles explicites et documentées

Objectif: garder une boucle locale de calibration simple.

## 5. Target Architecture

### 5.1 Pilotage Snapshot Layer

Ajouter une couche de snapshots journaliers dans `wms/models_domain/integration.py`, par exemple autour d'un modèle `OpsPilotageSnapshot`.

Intention:

- stocker les KPI quotidiens sans multiplier les tables spécialisées trop tôt
- permettre des tendances simples et des comparaisons inter-runs locaux
- alimenter digest, cockpit transverse et export pilotage

Champs recommandés:

- `snapshot_date`
- `scope_type` (`global`, `destination`, `flight`, `portal`, `queue`, `planning_export`)
- `scope_key`
- `metric_key`
- `metric_value`
- `payload`
- `captured_at`

Sources principales:

- `wms/workflow_projection.py`
- `wms/views_scan_dashboard.py`
- `wms/planning/stats.py`
- `wms/planning/exports.py`
- queues email / document scan

### 5.2 Escalation Layer

Ajouter une couche d'escalades locales persistées, par exemple `OpsEscalation`, distincte des litiges métier et des claims de blocage workflow.

Intention:

- suivre les anomalies persistantes entre deux captures
- porter un owner, une sévérité, un statut, et un horodatage
- éviter de déduire l'historique d'escalade uniquement depuis le dashboard du moment

Catégories recommandées:

- `sla_persistent`
- `dispute_unassigned`
- `workflow_blockage_unclaimed`
- `planning_capacity_overload`
- `planning_pdf_missing`
- `queue_backlog`
- `portal_stalled`

Champs recommandés:

- `escalation_key`
- `category`
- `scope_type`
- `scope_key`
- `severity`
- `owner`
- `status` (`open`, `acknowledged`, `resolved`, `suppressed`)
- `first_detected_at`
- `last_detected_at`
- `acknowledged_at`
- `resolved_at`
- `payload`

### 5.3 Daily Ops Cockpit

Ajouter un cockpit transverse staff-only, recommandé sous `scan`, par exemple `/scan/pilotage/`.

Rôle:

- point d'entrée quotidien pour le pilotage global
- lecture croisée `scan`, `portal`, `planning`, queues, exports
- navigation rapide vers les écrans de traitement déjà existants

Sections recommandées:

- `Priorités du jour`
- `Escalades persistantes`
- `Risques destination`
- `Capacité vols`
- `Backlog portail`
- `Santé technique`
- `Exports planning`

Le cockpit doit rester un orchestrateur de lecture et d'actions, pas un second workflow engine.

### 5.4 Planning Communication Hardening

La phase 1 a introduit un export strict `xlsx + pdf`, mais la génération PDF reste dépendante d'un contexte desktop Excel fragile.

La phase 2 doit:

- rendre l'état des artefacts planning visible et pilotable
- garder l'xlsx comme source de vérité de rendu à court terme
- isoler le backend PDF pour permettre ensuite un remplacement plus robuste
- préparer la diffusion mail PDF-first

Un petit read model d'artefact planning est recommandé pour exposer:

- disponibilité du workbook
- disponibilité du PDF
- backend utilisé
- erreur de génération
- dernière génération réussie

### 5.5 Pilotage Runtime Settings

La calibration doit rester locale via `scan/settings`.

La phase 2 ajoute des seuils pilotage simples:

- multiplicateurs d'escalade SLA
- seuil `dispute sans owner`
- seuil `workflow blockage sans prise en charge`
- seuils planning `tension / critique / surcharge`
- seuil backlog queues

Le moteur de règles avancé n'est pas encore requis; cette étape reste une calibration pilotée par presets et compteurs d'impact.

## 6. Proposed Delivery Slices

### Slice P2.1: KPI history

Livrer:

- modèle de snapshot
- capture command
- rebuild command si nécessaire
- premières métriques globales, destination, vol, portail, queues, planning export

### Slice P2.2: local escalations

Livrer:

- modèle d'escalade
- évaluation locale sur snapshots + état courant
- digest preview et file d'escalades
- actions `acknowledge / resolve` minimales

### Slice P2.3: daily ops cockpit

Livrer:

- nouvelle page `scan/pilotage`
- miroir UI API
- sections transverses alimentées par snapshots + escalades

### Slice P2.4: planning PDF/mail hardening

Livrer:

- état d'artefact planning persistant
- escalades `planning_pdf_missing`
- usage mail PDF-first stabilisé
- instrumentation d'erreur backend

### Slice P2.5: runtime rules and presets

Livrer:

- nouveaux seuils runtime
- presets `standard`, `incident_sla`, `pilotage_tendu`
- aperçu d'impact sur escalades et cockpit

## 7. Success Criteria

La phase 2 est considérée complète quand:

- les KPI de pilotage sont historisés et rejouables
- une anomalie persistante reste visible au-delà d'un refresh de page
- un staff a un point d'entrée quotidien transverse
- la santé planning/export PDF remonte comme un signal d'exploitation normal
- la calibration locale des seuils est possible sans éditer le code

## 8. Non-Goals

- pas de migration Next/React
- pas de reprise du scope traduction
- pas de moteur de workflow générique
- pas de BI externe complète dans cette phase
- pas de rollout production ni scheduling infra définitif

## 9. Primary Repo Touchpoints

- `wms/models_domain/integration.py`
- `wms/workflow_projection.py`
- `wms/views_scan_dashboard.py`
- `wms/views_scan_settings.py`
- `wms/scan_urls.py`
- `wms/views_planning.py`
- `wms/planning/stats.py`
- `wms/planning/exports.py`
- `wms/planning/communication_actions.py`
- `wms/views_portal_orders.py`
- `wms/portal_dashboard_helpers.py`
- `api/v1/views.py`
- `api/v1/ui_views.py`
- `docs/operations.md`
- `docs/release_checklist.md`
- `docs/repo-reference/02-key-flows-and-living-tests.md`
- `docs/repo-reference/04-shared-contracts.md`

## 10. Verification Strategy

Chaque slice doit garder la même discipline locale:

- tests read model ou helper ciblés
- tests commandes de rebuild/capture
- tests HTML legacy sur la surface visible
- tests DRF sur le miroir API
- runbook et repo-reference mis à jour dans le même lot

La phase 2 doit rester exécutable et réglable en local avant toute discussion de production.
