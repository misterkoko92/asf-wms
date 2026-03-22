# Legacy UI Wave 3 Design

## Contexte

La wave 1 a posé le socle des primitives legacy (`ui_button`, `ui_field`, `ui_switch`, `ui_status_badge`) et la wave 2 a validé l'approche hybride avec:
- `ui_alert` comme nouvelle primitive leaf,
- `scan/ui-lab/` comme catalogue vivant,
- le découpage de `scan/pack` et `scan/public_account_request` en partials métier.

Le reste du legacy scan n'a pas le même profil de risque:
- `templates/scan/shipment_create.html` fait encore environ 366 lignes et mélange création, édition, documents, overlay de confirmation, aide locale d'impression et hooks JS;
- `templates/scan/imports.html` dépasse 540 lignes avec beaucoup de blocs hétérogènes;
- `templates/scan/admin_contacts.html` dépasse 570 lignes, mais contient déjà plusieurs includes et un couplage métier plus fort avec le cockpit contacts.

Le meilleur prochain levier n'est donc pas "le plus gros fichier", mais l'écran qui combine:
- valeur métier élevée,
- vrai gain de lisibilité,
- risque de refactor encore maîtrisable,
- bon potentiel de réutilisation des contrats UI existants.

`shipment_create` coche ces critères.

## Approches Etudiées

### 1. Faire une grosse wave "scan gestion" avec `shipment_create`, `imports` et `admin_contacts`

Avantages:
- attaque les derniers gros monolithes d'un coup,
- donne une impression d'accélération.

Inconvénients:
- lot trop large pour un écran aussi sensible que `shipment_create`,
- signal de test plus diffus,
- risque élevé de mélanger plusieurs styles de refactor dans une même wave,
- probabilité forte d'ouvrir des sous-sujets métier au lieu de rester sur la structure UI.

### 2. Continuer à peupler la library avant tout nouveau refactor

Idée:
- ajouter d'abord de nouveaux composants "wizard", "document list", "modal", "upload row",
- puis migrer les pages plus tard.

Avantages:
- sensation de design system plus complet,
- points d'entrée théoriquement centralisés.

Inconvénients:
- risque de sur-abstraction élevé,
- Django templates reste peu adapté aux wrappers arbitraires avec contenu libre,
- on construirait des composants avant d'avoir validé leur vrai contrat récurrent.

### 3. Wave 3 resserrée sur `shipment_create`, approche hybride, recommandée

Idée:
- ne pas ajouter de gros nouveaux template tags,
- documenter dans le `UI Lab` les contrats visuels spécifiques réellement réutilisables de l'écran expédition,
- découper `shipment_create` en partials par zones métier,
- appliquer les primitives leaf existantes seulement quand le markup est fermé et stable.

Avantages:
- bon ratio impact/risque,
- améliore un écran central côté exploitation,
- garde la library pragmatique,
- prépare proprement la wave 4 sans l'alourdir dès maintenant.

Inconvénients:
- la progression de la library reste volontairement mesurée,
- certaines répétitions resteront des contrats HTML/CSS plutôt que des tags.

## Decision Recommandée

Prendre l'approche 3.

Règle de conception pour cette wave:
- pas de nouveau composant partagé si le pattern n'est pas clairement fermé et déjà récurrent;
- priorité au découpage structurel de `shipment_create`;
- usage de `ui_button` et `ui_alert` partout où le markup peut être fermé sans risque;
- documentation explicite des contrats "workflow expédition" dans le `UI Lab`, sans créer de fausse abstraction.

## Scope De La Wave 3

### 1. Refactorer `templates/scan/shipment_create.html`

Objectif:
- rendre le template lisible par zones métier,
- préserver tous les hooks JS existants,
- faire converger les messages et actions vers les contrats déjà partagés.

Le découpage cible:
- en-tête et panneau helper install,
- panneau destination,
- panneaux expéditeur / destinataire / correspondant,
- panneau détail expédition et actions,
- overlay de pré-affectation,
- panneaux édition: suivi, documents, upload, allocations.

### 2. Etendre le `UI Lab` sur les contrats utiles au flux expédition

Sans créer de nouveaux gros template tags, documenter au moins:
- un groupe d'actions documentaires,
- un panneau de workflow avec aide et CTA primaire/secondaire,
- un overlay de confirmation compatible avec le style scan actuel.

But:
- éviter que ces patterns restent implicites dans `shipment_create`,
- fournir une référence avant la wave 4.

### 3. Ne pas ajouter de nouvelle primitive `wms_ui` par défaut

La wave 3 doit d'abord exploiter:
- `ui_button`,
- `ui_alert`,
- les classes de structure `ui-comp-card`, `ui-comp-panel`, `ui-comp-actions`, `ui-comp-note`.

Exception admise uniquement si, pendant l'implémentation, un composant fermé apparaît au moins deux fois sans forcer le template.

## Hors Scope

- refactor structurel de `templates/scan/imports.html`,
- refactor structurel de `templates/scan/admin_contacts.html`,
- extraction de nouvelles abstractions côté JS dans `wms/static/scan/scan.js`,
- modification du flux métier de création d'expédition.

## Architecture Cible

### 1. Découpage par responsabilité métier

Le futur `shipment_create` ne doit plus être lu comme un bloc unique, mais comme un assemblage de sections:
- sélection des parties,
- construction du contenu d'expédition,
- confirmation de pré-affectation,
- opérations d'édition et documents.

Ce découpage doit aider autant la maintenance HTML que la lecture des tests.

### 2. Contrats JS gelés

Cette wave ne doit pas déplacer ou renommer:
- les `id` utilisés par `scan.js`,
- les `name` de champs,
- les `data-*` de guidance et de pré-affectation,
- les conteneurs JSON `json_script`,
- les slots `scan-shipment-contact-slot`,
- les routes documentaires liées au helper local.

Le refactor est structurel, pas comportemental.

### 3. Contrats visuels explicites pour les opérations d'édition

Les blocs édition de `shipment_create` contiennent plusieurs motifs qui doivent devenir plus lisibles:
- listes de documents générés,
- actions documentaires tertiaires,
- upload + action secondaire,
- documents additionnels avec suppression danger.

Plutôt qu'un composant trop générique, on formalise ces motifs comme conventions HTML/CSS testées.

## Strategie De Test

### Contrats UI

Durcir `wms/tests/views/tests_scan_bootstrap_ui.py` pour vérifier:
- la présence des contrats `ui-comp-card`, `ui-comp-panel`, `ui-comp-actions` sur les sections expédition,
- l'usage de `ui_alert` pour les erreurs non liées à un champ et les messages vides critiques,
- la présence des contrats documentaires et de l'overlay dans le `UI Lab`,
- la conservation de l'ordre des CTA primaire / secondaire / tertiaire.

### Régressions métier

Conserver et compléter `wms/tests/views/tests_views_scan_shipments.py` pour verrouiller:
- la copie EN déjà corrigée,
- l'overlay de pré-affectation,
- les marqueurs du mode édition,
- les liens documentaires et métadonnées helper,
- les marqueurs des sélecteurs groupés expéditeur / destinataire / correspondant.

### Vérification ciblée

Le set minimal utile pour cette wave:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments -v 2`

## Risques

- casser un hook JS en changeant un `id` ou un ordre DOM attendu;
- sous-estimer la sensibilité du mode édition, plus chargé que le mode création;
- introduire une pseudo-library de composants documents trop spécifique à une seule page;
- vouloir faire entrer `imports` dans la même wave alors que le signal de risque n'est pas comparable.

## Recommandation Pour La Suite

Si la wave 3 se passe bien, la wave 4 ne doit pas être "imports + admin_contacts" en bloc indistinct.

Ordre recommandé:
1. `templates/scan/imports.html`
2. `templates/scan/admin_contacts.html`

Pourquoi:
- `imports` reste monolithique, mais son découpage est surtout structurel et formulaire;
- `admin_contacts` est plus long, déjà partiellement découpé, et plus couplé au cockpit métier des contacts.

## Critere De Sortie

La wave 3 est bonne si:
- `shipment_create` est découpé en partials lisibles,
- les contrats UI de workflow expédition sont visibles dans le `UI Lab`,
- les hooks JS et documents helper restent inchangés,
- les tests scan UI et shipment restent verts,
- `imports` et `admin_contacts` restent explicitement différés à la wave 4.
