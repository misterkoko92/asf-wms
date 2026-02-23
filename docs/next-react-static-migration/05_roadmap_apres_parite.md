# 05 - Roadmap après parité: UI ciblée + éditeur de templates

## Précondition d'entrée

Ce document s'active **apres** validation de la parite stricte (phase 3/4).

Etat au 2026-02-23: parite stricte non validee, roadmap encore en attente.

## 1) Séquence recommandée

1. **Parité stricte** Benev/Classique (obligatoire).
2. **Ajustements visuels ciblés** (boutons, cards, barres, densité).
3. **Nouveau module d'édition de templates**.

## 2) Ajustements UI ciblés (sans casser les flux)

## Objectif

Moderniser progressivement l'interface sans modifier la logique métier.

## Livrables

- Design tokens: couleurs, radius, spacing, typo.
- Bibliothèque de composants réutilisables:
  - `Button`,
  - `Card`,
  - `Table`,
  - `FormField`,
  - `Alert`,
  - `StatusBadge`.
- Système de variantes:
  - `legacy-compatible`,
  - `modern-calm`,
  - `dense-pro`.

## Méthode

- Tu fournis référence de style (lien, capture ou fichier).
- Intégration sous forme de variante activable par feature flag.
- Validation écran par écran (pas de big-bang visuel).

## 3) Chantier éditeur de templates documentaire

## 3.1 Constat

L'éditeur actuel n'est pas assez souple. Ce chantier est traité après stabilisation du front next.

Etat reel:

- base technique API templates deja livree (`/api/v1/ui/templates/*`),
- UI actuelle Next = editeur JSON technique (utile pour MVP, pas encore UX cible metier).

## 3.2 Objectifs V1

- Éditeur hybride:
  - blocs structurés (en-tête, tableaux, signatures),
  - zones libres éditables.
- Variables métier insérables:
  - expédition,
  - colis,
  - destinataire/expéditeur/correspondant,
  - documents douane/donation.
- Prévisualisation live PDF.
- Versioning:
  - brouillon,
  - publié,
  - rollback version.

## 3.3 Types documentaires à couvrir

Obligatoires:

- packing list expédition,
- packing list colis,
- attestation de donation,
- bon de livraison,
- attestation douane.

Optionnels:

- certificats complémentaires (sécurité/authenticité).

## 3.4 Architecture recommandée

- Front Next:
  - éditeur WYSIWYG structuré,
  - palette de blocs,
  - panneau variables.
- Backend Django:
  - stockage template versionné,
  - moteur rendu HTML/PDF,
  - règles de validation avant publication.

## 3.5 Critères d'acceptation

- création/édition template sans intervention développeur,
- aperçu PDF fidèle avant publication,
- compatibilité avec impressions existantes,
- permissions et audit conformes.

## 4) Backlog d'amélioration V2

- raccourcis clavier desktop,
- command palette globale,
- suggestions automatiques d'affectation colis,
- mode daltonisme,
- signatures électroniques (si besoin confirmé),
- export récap clôture.
