# Legacy UI Next Waves Design

## Contexte

La gouvernance UI du depot est deja fixee:
- stack cible: Django legacy + Bootstrap-only,
- migration Next/React en pause hors scope,
- reprise traduction FR/EN en pause hors scope,
- noyau stable limite aux primitives et wrappers deja documentes dans le `UI Lab`,
- promotion d'un pattern seulement apres usages reels multiples.

Les derniers lots ont valide le socle:
- `pack`, `public_account_request` et `shipment_create` ne sont plus des monolithes opaques,
- `scan/ui-lab/` documente maintenant `Core stable` et `En convergence`,
- la checklist de gouvernance formalise le tri `Core stable` / `En convergence` / `Local au workflow`.

Le prochain enjeu n'est donc plus de "mettre Bootstrap partout". Cette passe a deja ete faite sur beaucoup d'ecrans. Le vrai chantier restant est de simplifier les gros templates encore denses sans recreer de faux composants generiques.

Etat reel des surfaces encore lourdes cote legacy:
- `templates/scan/imports.html`: 542 lignes,
- `templates/scan/admin_contacts.html`: 574 lignes,
- `templates/portal/order_create.html`: 641 lignes,
- `templates/portal/account.html`: 297 lignes,
- `templates/scan/receive_pallet.html`: 684 lignes,
- `templates/scan/receive.html`: 277 lignes,
- `templates/scan/receive_association.html`: 269 lignes.

## Objectif

Definir les prochaines waves du refactor UI pour:
- simplifier les gros ecrans encore monolithiques,
- harmoniser les contrats HTML/CSS autour du `Core stable`,
- laisser les patterns encore mouvants en `En convergence`,
- garder les assemblages metier denses en `Local au workflow`,
- produire une sequence de travail plus fine que l'ancien bloc wave 4 unique.

## Approches Etudiees

### 1. Garder une wave 4 unique `imports + admin_contacts`

Avantages:
- colle au premier handoff wave 4,
- donne l'impression de solder le backlog Scan rapidement.

Inconvenients:
- deux monolithes differents dans le meme lot,
- signal de tests plus diffus,
- risque de melanger un ecran d'import surtout structurel et un cockpit CRUD beaucoup plus metier.

### 2. Basculer tout de suite sur le portail

Avantages:
- attaque vite `portal/order_create.html`, qui est aujourd'hui le plus gros template portal,
- prepare une harmonisation plus visible entre Scan et Portal.

Inconvenients:
- laisse `imports` et `admin_contacts` a moitie traites alors qu'ils sont deja explicitement identifies par la gouvernance,
- casse la continuité du refactor legacy Scan,
- retarde les arbitrages concrets sur `Toolbar`, `Table` et `PageHeader`.

### 3. Scinder la suite en waves plus courtes par retour sur investissement, recommandee

Ordre:
1. wave 4A: `imports`
2. wave 4B: `admin_contacts`
3. wave 5: surfaces portal denses
4. wave 6: surfaces reception/import palette

Avantages:
- respecte la logique deja ecrite dans la gouvernance,
- garde des lots testables et lisibles,
- permet de valider les patterns `En convergence` sur Scan puis Portal avant promotion,
- evite de figer une pseudo-library de formulaires trop tot.

Inconvenients:
- il faut accepter une numerotation plus fine que le premier handoff wave 4,
- certains patterns resteront volontairement mouvants jusqu'a la wave 6.

## Decision Recommandee

Prendre l'approche 3.

Concretement, l'ancien bloc wave 4 devient une sequence plus executable:
- wave 4A: `imports` seulement,
- wave 4B: `admin_contacts` seulement.

Puis la suite recommandee est:
- wave 5: `portal/order_create` puis `portal/account`,
- wave 6: `receive_pallet`, `receive`, `receive_association`.

Cette sequence garde la gouvernance comme contrainte de conception:
- reutiliser d'abord le `Core stable`,
- documenter au `UI Lab` seulement si un vrai contrat transverse emerge,
- preferer des partials metier explicites a des template tags generiques,
- promouvoir uniquement apres repetition sur plusieurs ecrans.

## Wave 4A: Imports

### Target Screen

- `templates/scan/imports.html`

### Pourquoi Maintenant

- ecran encore monolithique malgre une premiere harmonisation Bootstrap,
- beaucoup de sections repetitives faciles a separer sans toucher au moteur d'import,
- bon terrain pour clarifier ce qui reste `Local au workflow` dans les imports,
- premier lot ideal pour transformer la wave 4 en sequence plus fine.

### Classification

- page globale: `En convergence`
- formulaires simples, wrappers, CTA: `Core stable`
- revue des matches produit et radio de decision: `Local au workflow`

### Core Stable A Reutiliser

- `ui_button` quand le markup est ferme
- `ui_alert` si un message ferme devient necessaire
- `ui-comp-card`
- `ui-comp-form`
- `ui-comp-actions`

### En Convergence A Observer

- `Table`
- `PageHeader`
- eventuel regroupement visuel des sections import

Regle:
- pas de promotion pendant cette wave sans second usage reel hors imports.

### Local Au Workflow A Conserver

- matrice `Source / Existant` de confirmation import produits,
- radio groups `Mettre a jour / Creer`,
- bloc `stock_mode`,
- JSON `scan-import-selector-data`,
- liens template/export specifiques a chaque famille d'import.

### Tests Cibles

- `wms.tests.views.tests_scan_bootstrap_ui`
- `wms.tests.scan.tests_scan_import_handlers`

## Wave 4B: Admin Contacts

### Target Screen

- `templates/scan/admin_contacts.html`

### Pourquoi Ensuite

- reste le deuxieme gros monolithe deja nomme par la gouvernance,
- profite des contrats confirmes pendant `imports`,
- plus couple au cockpit metier, donc meilleur ratio risque/gain apres un lot 4A plus structurel.

### Classification

- page globale: `En convergence`
- filtres, wrappers, groupes d'actions: `Core stable`
- cockpit CRUD et wiring contacts/destinations: `Local au workflow`

### Core Stable A Reutiliser

- `ui_button`
- `ui_alert`
- `ui-comp-card`
- `ui-comp-panel`
- `ui-comp-form`
- `ui-comp-actions`

### En Convergence A Observer

- `Toolbar`
- `Table`
- `PageHeader`

### Local Au Workflow A Conserver

- formulaires destination/contact,
- panneaux merge / deactivate / edit,
- cockpit expediteur / destinataire / correspondant,
- regles de filtrage et details/summary metier.

### Tests Cibles

- `wms.tests.views.tests_scan_bootstrap_ui`
- `wms.tests.views.tests_views_scan_admin`
- suites `wms/tests/scan/tests_admin_contacts_*`

## Wave 5: Portal Dense Surfaces

### Target Screens

- `templates/portal/order_create.html`
- `templates/portal/account.html`

### Pourquoi A Ce Moment-La

- le portail a deja recu les classes `ui-comp-*`, mais pas encore un vrai travail de decomposition structurelle,
- `portal/order_create.html` reste un tres gros ecran avec tables, filtres et actions repetitives,
- c'est le meilleur endroit pour verifier si `PageHeader`, `Toolbar`, `Table` ou `EmptyState` sont reellement transverses entre Scan et Portal.

### Classification

- pages globales: `En convergence`
- wrappers et CTA fermes: `Core stable`
- tables produits, lignes contacts, regles de selection destinataire: `Local au workflow`

### Core Stable A Reutiliser

- `ui_button`
- `ui_field`
- `ui_status_badge`
- `ui-comp-card`
- `ui-comp-panel`
- `ui-comp-actions`
- `ui-comp-form`

### En Convergence A Observer

- `PageHeader`
- `Toolbar`
- `Table`
- `EmptyState`

Promotion envisageable seulement si les memes contrats survivent propres sur Scan et Portal.

### Tests Cibles

- `wms.tests.views.tests_portal_bootstrap_ui`
- `wms.tests.views.tests_views_portal`

## Wave 6: Receiving Surfaces

### Target Screens

- `templates/scan/receive_pallet.html`
- `templates/scan/receive.html`
- `templates/scan/receive_association.html`

### Pourquoi En Dernier

- ces ecrans sont denses, mais une partie a deja recu des ajustements visuels,
- la wave 6 peut reemployer ce qui aura ete confirme sur Scan et Portal,
- bon moment pour trier ce qui reste strictement local au flux de reception.

### Classification

- pages globales: `En convergence`
- wrappers, CTA, panneaux d'etat: `Core stable`
- mapping, recap d'import, upload listing et decisions de reception: `Local au workflow`

### Core Stable A Reutiliser

- `ui_button`
- `ui_alert`
- `ui-comp-card`
- `ui-comp-panel`
- `ui-comp-actions`
- `ui-comp-form`

### En Convergence A Observer

- `Table`
- `EmptyState`
- motifs upload / recap

### Local Au Workflow A Conserver

- mapping colonnes,
- recap import listing,
- sequences de reception don / palette / association,
- formulaires qui pilotent directement les handlers reception.

### Tests Cibles

- `wms.tests.views.tests_scan_bootstrap_ui`
- `wms.tests.views.tests_views_scan_receipts`

## Differe

Doit rester differe tant que les waves 4A a 6 ne sont pas stabilisees:
- `templates/scan/admin_design.html`
- `templates/scan/billing_editor.html`
- autres surfaces billing legacy
- `templates/scan/faq.html`
- ecrans publics deja suffisamment harmonises
- tout scope traduction FR/EN
- tout scope Next/React

## Regles D'Execution Pour Chaque Wave

Chaque wave doit explicitement produire:
- le classement des changements (`Core stable`, `En convergence`, `Local au workflow`),
- les partials metier introduites,
- les patterns candidats a promotion,
- les patterns gardes locaux,
- les suites de tests utilisees pour verrouiller la frontiere.

Checklist d'arret:
- pas de nouvelle primitive partagee sans deux usages reels,
- pas de `UI Lab` update pour un pattern encore local,
- aucun renommage gratuit des hooks JS, noms de champs, IDs ou payloads,
- aucun elargissement vers translation ou Next/React,
- aucune grosse wave fourre-tout melangeant plusieurs ecrans sans logique claire.

## Critere De Sortie

La sequence 4A -> 6 sera consideree comme bonne si:
- les gros templates restants sont decomposes par responsabilite,
- le `Core stable` est vraiment reutilise au lieu d'etre contourne,
- les patterns transverses sont promus seulement apres validation sur Scan et Portal,
- les zones metier denses restent lisibles sans devenir une library cachee,
- le refactor UI redevient un chantier de simplification, pas de speculation design-system.
