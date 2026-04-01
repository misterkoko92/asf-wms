# W2.1 Centre Litiges Design

**Date:** 2026-03-31

## Goal

Structurer le litige expédition dans le legacy Django existant pour passer d'un simple flag bloquant à un mini cycle de prise en charge exploitable en local: motif, propriétaire, état, échéance, notes de résolution, et visibilité opérateur dans le détail dossier comme dans la liste de suivi.

## Context

L'état actuel couvre déjà le verrou fonctionnel le plus important:
- une expédition peut être marquée `is_disputed`,
- le suivi opérationnel est alors bloqué,
- une résolution remet le dossier à l'état `Prêt`,
- la liste de suivi met déjà le litige en avant comme signal principal.

Ce socle est utile mais reste trop pauvre pour piloter réellement les exceptions:
- aucun motif standardisé,
- aucun owner,
- pas d'état intermédiaire,
- pas de date cible,
- pas de notes de résolution,
- pas de filtre métier pour traiter les litiges ouverts, en retard, ou non assignés.

La contrainte explicitement validée pour cette vague est de rester en local et de ne pas ouvrir tout de suite une nouvelle table de case management. La première itération doit donc enrichir `Shipment` directement.

## Scope

### In Scope

- enrichissement du modèle `Shipment` avec les champs litige structurés,
- formulaire de déclaration et de résolution depuis `scan/shipment_tracking`,
- panneau litige visible dans le détail dossier de suivi,
- mini timeline litige visible dans le même écran,
- filtres liste `ouverts`, `en retard`, `sans owner` sur `scan/shipments_tracking`,
- enrichissement des lignes de suivi pour afficher motif, owner, échéance et état,
- mise à jour des tests de vues et de contrat repo-reference.

### Out Of Scope

- nouvelle table dédiée de type `DisputeCase`,
- assignation à un utilisateur précis avec ACL dédiée,
- notifications automatiques SLA,
- exposition API v2 ou BI,
- réouverture du scope Next/React,
- travail de traduction.

## Approaches Considered

### 1. Nouvelle table litige dédiée maintenant

Avantages:
- historique natif multi-incidents,
- séparation claire entre dossier et exception.

Inconvénients:
- trop lourd pour une phase locale de réglage,
- demande des écrans et règles supplémentaires,
- augmente le coût de test avant même de valider le besoin réel.

### 2. Enrichir `Shipment` directement, recommandé

Avantages:
- rapide à tester en local,
- garde le workflow existant,
- limite la propagation au cluster shipment tracking déjà en place.

Inconvénients:
- ne conserve que le litige courant ou le dernier litige structuré,
- l'historique détaillé reste une timeline dérivée et non un vrai case log.

## Recommended Model

Conserver `is_disputed` comme verrou métier principal et ajouter sur `Shipment`:

- `dispute_reason`
- `dispute_owner`
- `dispute_status`
- `dispute_due_at`
- `dispute_resolution_notes`

Avec deux compléments minimaux utiles au pilotage:

- `dispute_opened_at`
- `dispute_resolved_at`

### Why keep `is_disputed`

- le verrou de progression existe déjà et il est testé,
- plusieurs helpers et badges se branchent déjà dessus,
- cela évite de réinterpréter immédiatement tout le repo sur la seule base de `dispute_status`.

### Proposed vocabularies

#### `dispute_reason`

Choix courts, orientés exploitation:
- `docs_missing`
- `data_mismatch`
- `damage_loss`
- `transport_blocked`
- `delivery_issue`
- `other`

#### `dispute_owner`

Taxonomie de rôle locale, compatible avec le pilotage existant:
- `magasin`
- `qualite`
- `admin`
- `transport`
- `portal`

Valeur vide autorisée pour faire émerger les litiges non assignés.

#### `dispute_status`

États minimaux pour pilotage local:
- `open`
- `in_progress`
- `waiting_external`
- `resolved`

`is_disputed=True` couvre les trois premiers états.
`is_disputed=False` après résolution force `dispute_status=resolved`.

## Behaviour Rules

### Open dispute

Déclarer un litige doit:
- activer `is_disputed`,
- renseigner `dispute_opened_at`,
- initialiser ou mettre à jour `dispute_reason`, `dispute_owner`, `dispute_status`, `dispute_due_at`,
- vider `dispute_resolution_notes`,
- conserver le verrou sur le suivi,
- écrire une activité dossier lisible,
- enrichir le log workflow avec le détail du litige.

### Update dispute while still open

Depuis le même écran, un staff peut ajuster:
- owner,
- statut,
- échéance,
- notes de contexte courtes si nécessaire.

Pour la première itération, cette mise à jour peut réutiliser l'action `set_disputed` si `shipment.is_disputed` est déjà vrai. Le bouton reste unique, mais le formulaire doit devenir structuré.

### Resolve dispute

Résoudre un litige doit:
- exiger des notes de résolution,
- passer `is_disputed=False`,
- fixer `dispute_status=resolved`,
- fixer `dispute_resolved_at`,
- conserver motif, owner, échéance et notes pour afficher le dernier litige traité,
- remettre l'expédition à `Prêt` selon la logique existante,
- conserver la remise à niveau des colis déjà expédiés,
- écrire une activité dossier lisible,
- enrichir le log workflow avec la résolution et les métadonnées structurées.

## UI Design

### `scan/shipment_tracking`

Le haut de page garde le statut actuel mais ajoute un panneau litige dédié:
- statut litige,
- motif,
- owner,
- échéance,
- âge du litige,
- notes de résolution si litige résolu,
- CTA de mise à jour ou résolution.

Le formulaire n'est plus un simple bouton binaire. Il devient:
- un petit formulaire de déclaration quand il n'y a pas de litige,
- un formulaire d'édition/résolution quand le litige est ouvert,
- un résumé en lecture seule du dernier litige une fois résolu.

### Litige timeline

Sans créer une nouvelle table, la timeline affichée dans le détail doit être dérivée des timestamps connus:
- ouverture,
- dernière activité dossier liée au litige,
- résolution éventuelle.

L'objectif n'est pas un journal exhaustif mais un repère opérateur immédiat.

### `scan/shipments_tracking`

Ajouter un filtre `dispute` avec trois valeurs:
- `open`
- `overdue`
- `unassigned`

Les lignes litige ouvertes doivent aussi exposer:
- owner,
- motif lisible,
- échéance,
- retard éventuel.

Le `next_action_label` reste prioritaire pour le litige, mais il peut devenir plus précis:
- `Affecter le litige`
- `Traiter le litige`
- `Relancer le litige`

## Testing Strategy

Référence TDD minimale:

- tests handler/vue sur déclaration structurée,
- tests handler/vue sur résolution avec notes obligatoires,
- tests détail tracking pour le panneau litige et la timeline,
- tests liste tracking pour les filtres `open`, `overdue`, `unassigned`,
- tests helper pour l'étiquette d'action prioritaire si nécessaire,
- mise à jour repo-reference sur le contrat litige local.

## Risks

### Single-record history limitation

Le modèle `Shipment` ne garde qu'un litige courant ou dernier litige structuré. Si le besoin devient multi-litiges par dossier, il faudra extraire une table dédiée en vague ultérieure.

### Ambiguous owner semantics

`dispute_owner` représente un rôle ou une file, pas une personne. C'est volontaire pour la phase locale, mais il faudra décider plus tard si une affectation nominative devient nécessaire.

### Timeline is derived, not canonical

La timeline locale sert au pilotage visuel. Elle ne remplace pas un event store ou un journal de cas exhaustif.

## Exit Criteria

La vague `W2.1` sera considérée suffisante en local quand:
- un litige ne peut plus être créé sans motif,
- un litige ouvert expose owner, état et échéance,
- une résolution impose des notes,
- la liste permet de filtrer `ouverts`, `en retard`, `sans owner`,
- le détail dossier montre le dernier litige de manière lisible,
- les tests ciblés couvrent ces scénarios,
- la repo-reference documente le contrat litige local.
