# Scan Expandable Sidebar Local Design

**Date:** 2026-03-25

## Goal

Tester localement une variante `scan` inspirée de la navigation PatternFly `Expandable nav`, avec une vraie sidebar métier sur desktop et un offcanvas sur mobile, sans engager encore la prod.

## Scope

- `scan` uniquement
- shell global legacy Django uniquement
- branche locale de la PR `#85`

## Out Of Scope

- `portal`
- `benevole`
- `admin` Django
- persistance `localStorage`
- promotion immédiate en prod

## Architecture

Le shell `scan` passe d'une navigation horizontale principale à une structure en deux couches :

- un `masthead utilitaire` horizontal
- un `workspace shell` avec `sidebar expandable` à gauche et contenu principal à droite

Le masthead conserve la marque et les utilitaires (`langue`, `planning`, `admin`, `compte`). La sidebar porte exclusivement la navigation métier.

## Navigation Model

Les sections de premier niveau sont :

- `Tableau de bord`
- `Stocks`
- `Réception`
- `Préparation`
- `Expéditions`
- `Gestion`

Les sections `Stocks`, `Réception`, `Préparation` et `Gestion` deviennent expandables. `Tableau de bord` et `Expéditions` restent des entrées simples.

Les enfants restent limités à un seul niveau de profondeur.

## Behavior

### Desktop

- la sidebar reste visible en permanence
- le groupe contenant la page active est ouvert par défaut
- les autres groupes restent fermés par défaut
- plusieurs groupes peuvent être ouverts, sans accordéon forcé

### Mobile

- la sidebar devient un `offcanvas`
- la hiérarchie reste identique
- les groupes restent expandables
- le bouton d'ouverture du menu vit dans le masthead

## Active State Rules

- une entrée simple active est surlignée clairement
- si un enfant est actif, le parent est aussi marqué actif
- l'état actif du parent ne doit pas ressembler à un bouton primaire

## Visual Direction

La sidebar doit rester sobre et compatible avec le langage UI legacy déjà convergé :

- surface mate, légèrement différenciée du contenu
- items de navigation en style lien structuré, pas en style bouton
- accent actif net via fond doux et bordure latérale
- sous-entrées légèrement en retrait, plus discrètes que les parents
- masthead utilitaire plus léger que la sidebar

## Implementation Strategy

- réutiliser Bootstrap pour `collapse` et `offcanvas`
- éviter tout JS métier dédié
- conserver le plus possible la logique de permissions et d'états actifs existante
- adapter les tests du shell `scan` au nouveau contrat

## Validation

La variante locale sera considérée exploitable si :

- le shell `scan` reste lisible sur desktop et mobile
- la hiérarchie `utilitaire / métier` est plus claire que dans la nav actuelle
- les tests `scan` ciblés passent
- la revue locale visuelle permet de décider si la sidebar mérite une adoption prod
