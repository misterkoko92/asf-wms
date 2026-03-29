# Design: Shipment Grouped Print HTML Bundles

## Goal

Faire évoluer les boutons d'impression groupée des dossiers d'expédition pour ouvrir directement un document HTML/CSS imprimable unique, sans dépendre du rendu PDF, tout en conservant l'exception des listes colisage carton pour l'impression sur rouleau continu.

## Scope

Inclus:

- `Imprimer dossier papier`
- `Imprimer toutes les étiquettes standard`
- `Imprimer tous les documents d'expédition` comme page orchestratrice qui conserve ses trois choix existants

Exclu:

- refonte de la logique PDF/XLSX existante
- surfaces Next/React
- traduction FR/EN

## Current Behavior

- `all` ouvre une page d'orchestration avec trois boutons.
- `paper` ouvre une page intermédiaire avec trois liens vers des documents séparés.
- `standard_labels` ouvre une page intermédiaire avec une ligne par colis et trois liens par ligne.
- `carton_lists` ouvre une page intermédiaire adaptée au flux de listes colisage carton.

Le besoin métier est de supprimer la page intermédiaire pour les lots imprimables sur A4, afin d'obtenir un seul document HTML prêt à lancer dans le navigateur.

## Decision

### 1. Conserver `all` comme orchestrateur

Le bouton `Imprimer tous les documents d'expédition` garde le comportement actuel. Il reste une page de choix avec:

- lot papier A4
- lot rouleau continu
- lot étiquettes standard

Cela respecte la contrainte métier explicitée pendant le cadrage.

### 2. Transformer `paper` en bundle HTML A4 unique

La route `print-bundle/paper` ne doit plus rendre une page de liens. Elle doit rendre un document HTML unique qui enchaîne:

1. bon d'expédition
2. document douane
3. liste générale

Chaque section garde son style actuel et force un saut de page A4 propre entre les documents.

### 3. Transformer `standard_labels` en bundle HTML A4 unique

La route `print-bundle/standard_labels` ne doit plus rendre une page de liens. Elle doit rendre un document HTML A4 avec deux demi-pages A5 par feuille.

Ordre métier retenu:

1. toutes les étiquettes contact
2. toutes les étiquettes colis
3. toutes les attestations de donation

À l'intérieur de chaque groupe, les colis restent triés par code.

Pour une expédition de deux colis, le bundle contient donc six documents A5, imprimés sur trois feuilles A4.

### 4. Garder `carton_lists` sur la logique actuelle

La route `print-bundle/carton_lists` garde la page intermédiaire actuelle, avec une action par colis. C'est l'exception métier autorisée car ces documents visent l'imprimante dédiée à rouleau continu.

## Technical Approach

## Reuse existing print markup via partials

Les templates HTML d'impression existants contiennent déjà le bon rendu visuel, mais ils étendent aujourd'hui des bases complètes (`base_document` ou `base_label`). Pour composer plusieurs documents dans une seule page HTML, il faut factoriser leur contenu central dans des partials réutilisables.

On introduit des partials pour:

- bon d'expédition
- document douane
- liste générale
- étiquette contact
- étiquette expédition
- attestation donation

Chaque template d'impression actuel continue d'exister, mais délègue son corps à un partial partagé. Les nouveaux bundles HTML utilisent ces partials dans un conteneur dédié à l'impression groupée.

## Add dedicated HTML bundle templates

Deux nouveaux templates sont nécessaires:

- un bundle A4 de documents pleine page
- un bundle A4 "2-up" pour les documents A5

Le second impose:

- page A4 portrait
- grille de 2 cellules verticales
- cellule unitaire de taille A5 landscape
- saut de page toutes les 2 cellules

## Build dedicated bundle contexts in Python

Le code de vue doit préparer des contextes HTML, pas des liens:

- `paper` retourne une liste ordonnée de sections documentaires
- `standard_labels` retourne une liste ordonnée d'items A5 avec type, code colis, identifiant et contexte prêt à rendre

La vue doit réutiliser les mêmes helpers de contexte déjà employés pour les impressions unitaires afin de rester alignée avec les documents existants.

## Impact

- `wms/views_print_docs.py`: changement principal du comportement des bundles HTML
- `templates/scan/`: remplacement des pages de liens par de vrais bundles imprimables
- `templates/print/`: extraction de partials et ajout de templates bundle
- `wms/tests/views/tests_views_print_docs.py`: contrat principal à faire évoluer

## Test Strategy

- faire échouer d'abord les tests de vue existants pour `paper` et `standard_labels`
- ajouter des assertions sur l'absence de la page de liens
- vérifier l'ordre et le nombre des sections du bundle
- conserver les tests existants pour `all` et `carton_lists`

## Risks

- conflit de styles d'impression entre documents hétérogènes
- sauts de page incorrects si les partials conservent des règles `@page` incompatibles
- duplication involontaire si les templates unitaires et bundle divergent

## Mitigations

- centraliser le markup dans des partials partagés
- limiter les règles `@page` au niveau des templates bundle
- utiliser les mêmes builders de contexte Python que pour l'impression unitaire
