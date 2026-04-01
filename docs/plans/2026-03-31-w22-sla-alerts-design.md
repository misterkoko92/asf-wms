# W2.2 SLA Alerts Design

**Date:** 2026-03-31

## Goal

Transformer le dashboard scan local en cockpit SLA actionnable en ajoutant une file d'alertes concrètes sur les retards de suivi, sans créer de table dédiée ni lancer encore de digest ops.

## Context

Le dashboard legacy expose déjà:
- des cartes de suivi retardé par étape,
- des cartes SLA agrégées,
- des seuils runtime `tracking_alert_hours` et `workflow_blockage_hours`,
- une file d'actions transverse.

Ce socle suffit pour la visibilité, mais pas encore pour l'action:
- les cartes SLA restent agrégées,
- aucun dossier concret n'est listé,
- l'opérateur ne distingue pas les retards nouveaux des retards persistants,
- les presets runtime n'aident pas encore à recalibrer rapidement un incident SLA.

La contrainte validée pour cette vague est de rester local-first:
- legacy Django uniquement,
- pas de digest email,
- pas de nouvelle table d'alertes,
- pas de scope Next/React,
- pas de travail de traduction.

## Scope

### In Scope

- bloc `Alertes SLA` dans `scan/dashboard`,
- calcul dérivé des alertes depuis les dates de suivi existantes,
- distinction `nouveau retard` / `retard persistant`,
- classification par segment, criticité, owner, âge et retard,
- remontée des alertes SLA les plus critiques dans `À traiter maintenant`,
- preset runtime `incident_sla`,
- aperçu d'impact settings avec volumes SLA recalculés,
- miroir API UI pour garder le contrat local dashboard cohérent,
- mise à jour repo-reference et runbook ops local.

### Out Of Scope

- digest ops automatique,
- notification push/email,
- table métier dédiée pour les alertes,
- règles SLA par destination ou typologie,
- BI/API v2,
- scope Next/React ou traduction.

## Recommended Approach

Conserver les seuils runtime existants et dériver les alertes au moment de la lecture.

### Base rule

- `tracking_alert_hours` reste le seuil de base.
- un dossier devient une alerte SLA si l'étape attendue n'est pas atteinte après ce seuil.

### Freshness rule

- `new` si retard `> 1 x seuil` et `<= 2 x seuil`
- `persistent` si retard `> 2 x seuil` et `<= 3 x seuil`
- `critical` si retard `> 3 x seuil`

L'objectif est d'avoir des catégories exclusives et lisibles en local.

### Segment rule

Les alertes couvrent trois segments ouverts:
- `Planifié -> OK mise à bord`
- `OK mise à bord -> Reçu escale`
- `Reçu escale -> Livré`

Le segment global `Planifié -> Livré` reste sur les cartes agrégées et ne crée pas de ligne d'alerte dédiée pour éviter les doublons opérateurs.

### Owner rule

Taxonomie volontairement courte, compatible avec la phase 1 locale:
- `magasin` pour `Planifié -> OK mise à bord`
- `qualite` pour `OK mise à bord -> Reçu escale`
- `portal` pour `Reçu escale -> Livré`

## UI Contract

### `scan/dashboard`

Conserver les cartes SLA agrégées existantes, puis ajouter dans le panneau SLA:
- trois cartes de synthèse: `Nouveaux retards`, `Retards persistants`, `Retards critiques`
- une table `Alertes SLA` avec:
  - action
  - référence
  - segment
  - owner
  - criticité
  - retard
  - âge
  - CTA dossier

Les lignes pointent vers `scan/shipment/track/<tracking_token>/`.

### `À traiter maintenant`

Ajouter jusqu'à trois alertes SLA prioritaires en tête de file, avant les actions stock/commande moins critiques.

### `scan/settings`

Ajouter un preset `incident_sla` qui resserre:
- `tracking_alert_hours`
- `workflow_blockage_hours`

L'aperçu d'impact doit afficher:
- retards nouveaux
- retards persistants
- retards critiques

## API Contract

Le miroir `GET /api/v1/ui/dashboard/` doit exposer:
- `sla_alert_summary_cards[]`
- `sla_alert_rows[]`

Le shape des lignes reste court et stable:
- `reference`
- `label`
- `segment`
- `owner`
- `severity`
- `freshness`
- `delay_hours`
- `age_hours`
- `url`

Le contrat existant `pending_actions[]` reste stable; les alertes SLA y sont seulement injectées comme actions prioritaires, sans ajouter de nouvelles clés obligatoires.

## Shared Implementation Strategy

Le calcul SLA est maintenant partagé entre:
- `wms/views_scan_dashboard.py`
- `wms/views_scan_settings.py`
- `api/v1/ui_views.py`

Une extraction légère dans un helper dédié est donc justifiée pour éviter une triple duplication sur:
- l'annotation des dates de suivi,
- les agrégats SLA,
- les lignes d'alertes ouvertes,
- la synthèse `new / persistent / critical`.

## Testing Strategy

TDD minimal:
- vue dashboard scan: présence du bloc et contenu des alertes SLA,
- vue settings: preset SLA et aperçu d'impact,
- API UI dashboard: contrat `sla_alert_summary_cards` et `sla_alert_rows`,
- régression sur les cartes SLA agrégées existantes.

## Risks

- classement criticité trop agressif ou trop faible selon le seed local,
- trop de bruit si les alertes SLA dominent la file d'action,
- divergence HTML/API si le helper partagé n'est pas utilisé partout.

## Deferred Follow-ups

- digest ops local puis non local,
- règles SLA par destination,
- exports BI et API v2,
- couplage litige/SLA pour ouvrir une exception structurée automatiquement.
