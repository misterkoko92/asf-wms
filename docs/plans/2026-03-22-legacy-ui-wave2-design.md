# Legacy UI Wave 2 Design

## Contexte

La wave 1 a fixe le socle:
- primitives partagees cote Django legacy avec `wms_ui` (`ui_button`, `ui_field`, `ui_switch`, `ui_status_badge`),
- `scan/ui-lab/` repositionne comme catalogue en lecture seule,
- migrations deja faites sur `planning`, `benevole`, `portal`, des pages `scan` simples, et les templates admin custom.

Le code restant le plus dense n'est pas uniforme:
- `templates/scan/pack.html` reste un gros ecran de preparation avec variantes staff / preparateur, actions documentaires, modal de succes et beaucoup de hooks JS;
- `templates/scan/public_account_request.html` reste un gros formulaire standalone avec sections conditionnelles et beaucoup d'attributs metier;
- `templates/scan/admin_contacts.html` et `templates/scan/imports.html` sont plus gros encore, mais deja partiellement structures et plus risques a bouger trop tot.

Observation importante: la bibliotheque actuelle est tres adaptee aux "leaf components" autonomes, mais Django templates gerent mal les wrappers arbitraires avec contenu libre. `ui_field` est tres utile quand le HTML du champ existe deja en contexte; il est moins adapte a des formulaires ecrits champ par champ dans le template.

## Approches Etudiees

### 1. Tout convertir en template tags

Idee:
- ajouter `ui_panel`, `ui_toolbar`, `ui_action_group`, `ui_alert`,
- migrer les gros templates vers des tags partout.

Avantages:
- API unique,
- impression de "vraie design system library".

Inconvenients:
- Django n'est pas un bon fit pour des wrappers avec contenu arbitraire,
- forte complexite pour conserver le HTML exact, les data attrs, les IDs et les hooks JS,
- risque de sur-abstraction et de composants peu lisibles.

### 2. Ne rien ajouter a la library, refactor uniquement les pages

Idee:
- decouper `pack` et `public_account_request` en partials,
- conserver seulement les classes CSS partagees deja existantes.

Avantages:
- risque faible,
- migration rapide.

Inconvenients:
- la library ne progresse presque pas,
- les alerts/notices restent dupliquees,
- le `UI Lab` ne couvre pas les prochains patterns.

### 3. Approche hybride, recommandee

Idee:
- continuer la library seulement pour les "leaf components" qui ont un vrai retour sur investissement,
- standardiser les wrappers via contrats HTML/CSS partages (`ui-comp-card`, `ui-comp-panel`, `ui-comp-toolbar`, `ui-comp-actions`) plutot que via gros template tags,
- decomposer les gros templates en partials metier lisibles.

Avantages:
- compatible avec les contraintes reelles des templates Django,
- propagation simple pour les boutons et alerts,
- meilleur equilibre entre homogenite, maintenabilite et stabilite.

Inconvenients:
- la library sera volontairement hybride,
- il faut accepter que certains wrappers restent du HTML structurel documente plutot qu'un tag.

## Decision Recommandee

Prendre l'approche hybride.

Regle cible:
- leaf primitives partagees: template tags `wms_ui`,
- wrappers et layouts repetes: contrats HTML/CSS et partials,
- decomposition des gros ecrans pilotee par usage reel, pas par exhaustivite du design system.

## Scope De La Wave 2

### A ajouter a la library

- `ui_alert` comme nouvelle primitive partagee.

But:
- unifier les messages `error`, `warning`, `info`, `success`,
- reduire la duplication entre `scan-message`, `alert`, et les messages inline des gros formulaires,
- garder une API simple sans essayer de generaliser tout le rendu des formulaires.

### A documenter explicitement dans le UI Lab

Pas de nouveaux template tags pour ces wrappers. On documente et verrouille leurs contrats:
- `ui-comp-card`
- `ui-comp-panel`
- `ui-comp-toolbar`
- `ui-comp-actions`

Le `UI Lab` doit montrer:
- un exemple d'alert,
- un panel simple,
- une toolbar avec filtres,
- un action group simple.

### A refactorer dans cette wave

1. `templates/scan/pack.html`

Pourquoi:
- gros volume de markup,
- duplication d'actions,
- messages warning/error manuels,
- switch manuel,
- surface centrale cote exploitation.

Objectif:
- migrer boutons, switch et alerts vers primitives partagees,
- decouper le template en partials lisibles,
- conserver strictement les data attrs et hooks JS existants.

2. `templates/scan/public_account_request.html`

Pourquoi:
- gros formulaire standalone,
- beaucoup de repetition structurelle,
- bon candidat pour valider l'approche "partials + leaf primitives" hors ecran staff.

Objectif:
- migrer les actions et alerts,
- decouper les sections association / utilisateur / documents en partials,
- conserver strictement les IDs, noms de champs et data attrs attendus par le JS.

### A differer

- `templates/scan/admin_contacts.html`
- `templates/scan/imports.html`
- `templates/scan/shipment_create.html`

Raison:
- surfaces plus lourdes, plus risquees, ou deja en partie structurees,
- meilleur retour sur investissement apres avoir valide `ui_alert` et l'approche hybride sur `pack` et `public_account_request`.

## Architecture Cible

### 1. Leaf components seulement quand le markup est ferme

On etend `wms_ui` uniquement quand le composant a:
- un HTML stable,
- peu de variantes,
- une vraie duplication transverse.

`ui_alert` remplit ce critere.

### 2. Wrappers par contrat, pas par magie

Pour `Panel`, `Toolbar` et `ActionGroup`, on prefere:
- classes partagees,
- conventions de structure,
- exemples dans `UI Lab`,
- assertions de tests sur les classes et zones.

On evite un `ui_panel` ou `ui_toolbar` trop generique qui rendrait les templates moins lisibles.

### 3. Gros ecrans decomposes par zones metier

Pour `pack`:
- resultat de packing,
- modal de succes preparateur,
- bloc dimensions / lignes,
- bloc expeditions / actions.

Pour `public_account_request`:
- intro / navigation,
- section association,
- section utilisateur WMS,
- bloc documents,
- footer actions.

## Strategie De Test

### Contrats library

Ajouter des tests dans `wms/tests/templatetags/tests_wms_ui.py` pour:
- `ui_alert` avec niveaux et attributs,
- preservation des classes et du texte,
- securite des attributs HTML.

### Contrats UI scan

Ajouter ou durcir les tests dans `wms/tests/views/tests_scan_bootstrap_ui.py` pour verifier:
- le `UI Lab` expose `ui-comp-alert`, `ui-comp-panel`, `ui-comp-toolbar`, `ui-comp-actions`,
- `scan_pack` utilise les classes et primitives partagees pour ses zones d'action et de message,
- `scan_public_account_request` garde ses actions partagees et son rendu de formulaire.

### Regression metier

Conserver les tests metier existants sur:
- `wms/tests/views/tests_views_scan_shipments.py`
- `wms/tests/views/tests_views_public_account.py`

But:
- prouver que le refactor n'altere ni la logique du handler ni les variantes preparateur/staff.

## Risques

- sur-abstraction des champs de formulaire bruts: a eviter dans cette wave;
- regression JS si un `id`, `name`, `data-*` ou ordre DOM change dans `pack` ou `public_account_request`;
- tentation de faire entrer `admin_contacts` dans la meme wave alors que son ratio risque / gain est moins bon.

## Critere De Sortie

La wave 2 est consideree comme bonne si:
- `ui_alert` existe et est teste,
- le `UI Lab` documente clairement les wrappers de cette wave,
- `pack` et `public_account_request` sont plus lisibles via partials,
- les contrats UI et les regressions metier restent verts,
- `admin_contacts` et `imports` restent hors scope immediat.
