# Legacy UI Wave 4 Design

## Contexte

Les waves precedentes ont deja valide une partie utile de la gouvernance:
- `pack` a confirme qu'un workflow dense peut rester lisible avec des partials metier et des contrats partages,
- `public_account_request` a valide un ecran standalone/public base sur `ui_alert`, `ui_button` et `ui-comp-actions`,
- `shipment_create` a valide les contrats de workflow expedition, les groupes documentaires et l'overlay de confirmation dans le `UI Lab`.

Le reste du legacy scan ne doit plus etre traite comme une simple liste de "gros fichiers". Les deux surfaces encore a fort retour sur investissement sont:
- `templates/scan/imports.html`
- `templates/scan/admin_contacts.html`

Elles n'ont pas le meme profil:
- `imports` reste surtout un monolithe formulaire + tableaux de confirmation;
- `admin_contacts` est plus couple au cockpit metier contacts, avec plus de sections deja structurees et un risque plus fort de faire fuiter la logique metier dans la library.

La wave 4 doit donc prendre la gouvernance comme contrainte de conception, pas comme documentation annexe.

## Objectif

Finir le nettoyage des plus grosses surfaces legacy restantes sans recreer de nouveaux monolithes ni sur-abstracter la library.

Le resultat attendu:
- `imports` et `admin_contacts` deviennent plus lisibles par zones,
- le `Core stable` est reutilise partout ou il couvre deja le besoin,
- les patterns encore mouvants restent `En convergence`,
- les blocs tres metier restent `Local au workflow`,
- les tests UI et metier verrouillent explicitement ces choix.

## Approches Etudiees

### 1. Refactorer `imports` et `admin_contacts` ensemble comme un seul lot "gestion"

Avantages:
- sensation de solder les derniers gros fichiers d'un coup,
- reduction visible du nombre de templates massifs.

Inconvenients:
- trop de sujets differents dans une seule wave,
- signal de test moins lisible,
- risque de melanger formulaires d'import, cockpit contacts et contrats de library dans le meme lot.

### 2. Standardiser encore la library avant de toucher ces ecrans

Avantages:
- impression de design system plus complet.

Inconvenients:
- risque de figer des composants avant assez d'usages reels,
- faible retour sur investissement tant que `imports` et `admin_contacts` n'ont pas force les vrais arbitrages.

### 3. Wave 4 sequentielle, recommandee

Ordre:
1. `imports`
2. `admin_contacts`

Avantages:
- `imports` offre un gain de lisibilite rapide avec un risque surtout structurel,
- `admin_contacts` profite ensuite des contrats confirms pendant `imports`,
- la wave reste comprehensible, testable et sans faux composants generiques.

Inconvenients:
- la wave 4 doit accepter d'etre heterogene,
- certains motifs resteront volontairement en `En convergence` ou `Local au workflow`.

## Decision Recommandee

Prendre l'approche 3.

Ordre de travail:
1. traiter `templates/scan/imports.html` en premier;
2. traiter `templates/scan/admin_contacts.html` ensuite;
3. utiliser `pack`, `public_account_request` et `shipment_create` comme ecrans de reference, pas comme scope de refactor supplementaire.

## Target Screens

### 1. `templates/scan/imports.html`

Role:
- premier objectif de la wave 4.

Pourquoi:
- template encore monolithique,
- nombreuses sections formulaire repetitives,
- tableau de confirmation import produits melange au reste,
- bon candidat pour decomposer sans bouleverser la logique metier.

Classification:
- page globale: `En convergence`
- formulaires simples et actions: `Core stable`
- decisions de correspondance import produit: `Local au workflow`

Core stable a reutiliser:
- `ui_button`
- `ui_alert`
- `ui-comp-card`
- `ui-comp-actions`
- `ui-comp-form`

En convergence a valider:
- `Table`
- `EmptyState`
- eventuel `PageHeader` si l'ecran merite une structure plus uniforme

Local au workflow a conserver:
- les radio groups de decision de correspondance,
- la matrice source/existant pour les matches,
- les blocs fichier + mode de stock importe.

### 2. `templates/scan/admin_contacts.html`

Role:
- second objectif de la wave 4.

Pourquoi:
- gros ecran encore dense,
- plusieurs sous-formulaires et tableaux cockpit,
- couplage metier plus fort avec les roles, structures, liens et correspondants.

Classification:
- page globale: `En convergence`
- filtres, actions, panneaux repetes: `Core stable`
- cockpit contacts et formulaires CRUD metier: `Local au workflow`

Core stable a reutiliser:
- `ui_button`
- `ui_alert` quand un message ferme existe
- `ui-comp-card`
- `ui-comp-panel`
- `ui-comp-actions`
- `ui-comp-form`

En convergence a valider:
- `Toolbar`
- `Table`
- `PageHeader`
- `DocumentActions` seulement si un vrai motif transverse apparait

Local au workflow a conserver:
- details/summary CRUD,
- formulaires destination/contact,
- pilotage expediteur/destinataire/correspondant,
- formulaires de binding et de referent par defaut.

## Reference Screens

Ces ecrans ne sont pas le scope principal de la wave 4, mais servent de reference de gouvernance:

### `templates/scan/pack.html`

Classification:
- majoritairement `Local au workflow`

Usage pour la wave 4:
- reference pour le decoupage d'un flux dense,
- reference pour l'usage de `ui_alert` et `ui-comp-actions` sans re-creer un composant generique.

### `templates/scan/public_account_request.html`

Classification:
- bon exemple de `Core stable` assemble proprement sur une page standalone

Usage pour la wave 4:
- reference pour formulaires publics/standalone,
- reference pour la sobriete d'un flux qui n'a pas besoin de nouveaux composants.

### `templates/scan/shipment_create.html`

Classification:
- `En convergence` avec plusieurs contrats deja documentes

Usage pour la wave 4:
- reference pour workflow panels, groupes documentaires et overlays,
- preuve qu'un gros ecran peut etre decoupe sans casser les hooks JS.

## Core Stable Reuse Rules

Pour toute la wave 4:
- pas de nouveau composant partage si `ui_button`, `ui_alert`, `ui-comp-card`, `ui-comp-panel`, `ui-comp-actions` et `ui-comp-form` couvrent deja le besoin;
- preferer des partials metier lisibles a de gros template tags magiques;
- documenter dans le `UI Lab` seulement les contrats devenus clairement transverses apres usage reel.

## En Convergence Candidates

Les patterns suivants peuvent emerger pendant la wave 4 mais ne doivent pas etre geles trop tot:
- `Toolbar`
- `Table`
- `EmptyState`
- `PageHeader`

Regle:
- promotion seulement si le motif apparait dans `imports` et `admin_contacts`, ou s'il est deja coherent avec les references `shipment_create` / `public_account_request`.

## Differe

Doit rester differe pendant la wave 4 sauf signal clair contraire:
- nouvelle abstraction JS transverse,
- nouvelle primitive `wms_ui` non prouvee,
- refactor supplementaire de `pack`,
- refactor supplementaire de `public_account_request`,
- reprise de scope Next/React,
- simplification metier du cockpit contacts au-dela du besoin structurel UI.

## Tests

Suites a renforcer ou reutiliser:
- `wms.tests.views.tests_scan_bootstrap_ui`
- `wms.tests.views.tests_views_scan_shipments`
- `wms.tests.views.tests_views_public_account`

Suites a ajouter ou completer pour la wave 4:
- assertions ciblees sur `scan_imports` dans `wms.tests.views.tests_scan_bootstrap_ui`
- assertions ciblees sur `scan_admin_contacts` dans `wms.tests.views.tests_scan_bootstrap_ui`
- tests metier specifiques si un nouveau decoupage touche les handlers imports ou contacts

Verification minimale attendue par lot:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`
- suites metier ciblees selon l'ecran modifie

## Critere De Sortie

La wave 4 sera consideree comme bonne si:
- `imports` et `admin_contacts` ne sont plus des monolithes opaques,
- le `Core stable` est bien reutilise,
- les motifs encore mouvants restent `En convergence`,
- les blocs metier restent `Local au workflow`,
- les tests UI et metier rendent visibles ces frontieres,
- aucun refactor annexe ne retransforme la wave en chantier transversal flou.
