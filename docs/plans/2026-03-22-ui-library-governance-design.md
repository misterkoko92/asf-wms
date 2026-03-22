# UI Library Governance Design

## Contexte

Le depot a valide une direction claire:
- UI produit servie par Django legacy,
- socle visuel Bootstrap-only,
- migration Next/React en pause hors scope,
- premiers composants partages deja exposes via `wms_ui`,
- `scan/ui-lab/` deja positionne comme catalogue de reference.

Le refactor UI a deja commence en plusieurs vagues. Le risque n'est plus de "choisir une stack", mais de finir le nettoyage avec deux problemes classiques:
- trop de variantes locales qui dupliquent les memes composants,
- ou, a l'inverse, une library figee trop tot avec des abstractions artificielles.

Le besoin valide est donc de definir une gouvernance simple pour toute la suite:
- comment choisir les sources d'inspiration,
- quels composants sont consideres stables maintenant,
- quels composants doivent encore converger par usage reel,
- et comment les prochaines vagues doivent renforcer la library au lieu de la contourner.

## Objectif

Definir une gouvernance praticable pour une library de composants Django + Bootstrap couvrant tous les types d'ecrans:
- public,
- auth / portail,
- back-office,
- workflows metier denses.

La gouvernance doit:
- rester compatible avec le rendu Bootstrap-only actuel,
- s'appuyer sur les composants et contrats deja presents dans le depot,
- guider les prochaines waves de refactor sans lancer une refonte theorique parallele.

## Approches Etudiees

### 1. Bootstrap comme source unique

Idee:
- utiliser uniquement les composants, exemples et patterns Bootstrap comme reference externe,
- garder la library interne comme simple couche de commodite.

Avantages:
- tres simple,
- faible cout cognitif,
- alignement parfait avec la stack actuelle.

Inconvenients:
- peu d'inspiration pour les ecrans operatoires denses,
- risque d'ecrans trop generiques,
- moins d'aide pour dashboards, toolbars, panneaux d'actions et workflows.

### 2. Bootstrap + Tabler + library interne, recommandee

Idee:
- Bootstrap reste la source primaire des primitives et du HTML de base,
- Tabler sert de source secondaire pour les patterns d'ecrans metier et back-office,
- la source de verite finale reste la library interne Django (`wms_ui`, `templates/wms/components/*`, `ui-comp-*`, `scan/ui-lab/`).

Avantages:
- bon compromis entre stabilite technique et qualite visuelle,
- meilleure couverture pour tous les types d'ecrans,
- faible friction de transposition vers Django legacy,
- coherence renforcee par la source de verite interne.

Inconvenients:
- demande une discipline explicite pour ne pas copier Tabler tel quel,
- implique de documenter les contrats internes plutot que de suivre aveuglement une galerie externe.

### 3. Mix libre de sources

Idee:
- piocher selon les besoins dans Bootstrap, Tabler, PatternFly, shadcn et autres galeries.

Avantages:
- riche en inspiration,
- utile pour des cas ponctuels tres specifiques.

Inconvenients:
- forte derive de coherence,
- cout de traduction plus eleve,
- trop de debats de style et pas assez de contrats stables.

## Decision Recommandee

Prendre l'approche 2.

Hierarchie source:
- source primaire: Bootstrap pour les primitives, le HTML de base, l'accessibilite et les etats standard;
- source secondaire: Tabler pour les ecrans complets, dashboards, toolbars et patterns back-office;
- source ponctuelle: PatternFly ou autres seulement quand Bootstrap et Tabler ne suffisent pas;
- source de verite finale: la library interne du depot.

Concretement:
- les composants ne sont jamais adoptes directement depuis une source externe;
- ils sont traduits dans les contrats internes du depot;
- le refactor restant doit consommer ces contrats internes et les faire converger.

## Source De Verite Interne

Les points d'ancrage actuels sont deja corrects:
- primitives partagees dans `wms/templatetags/wms_ui.py`,
- templates de composants dans `templates/wms/components/`,
- contrats CSS/HTML via les classes `ui-comp-*`,
- catalogue visuel dans `templates/scan/ui_lab.html`,
- ponts Bootstrap dans `wms/static/scan/scan-bootstrap.css`, `wms/static/portal/portal-bootstrap.css` et `wms/static/wms/admin-bootstrap.css`.

Regle cible:
- tout composant officiellement partage doit avoir un contrat identifiable dans un de ces points,
- aucune source externe ne devient la reference finale a la place de la library interne.

## Gouvernance A Trois Niveaux

### 1. Core stable

Ce niveau contient les primitives deja assez comprises pour etre gelees comme contrats publics.

Regles:
- API simple,
- responsabilite unique,
- plusieurs usages reels ou evidence transverse immediate,
- documentation dans le `UI Lab`,
- tests cibles.

Composants a figer maintenant:
- `Button`
- `Field`
- `Alert`
- `Card / Panel` via contrat HTML/CSS documente
- `StatusBadge`
- `ActionsGroup` via contrat HTML/CSS documente
- `Switch`

### 2. Composants en convergence

Ce niveau couvre les composants utiles mais pas encore assez stables pour etre traites comme primitives definitives.

Regles:
- on les laisse evoluer pendant les prochaines waves,
- ils doivent reposer autant que possible sur le `Core stable`,
- promotion seulement apres validation sur plusieurs ecrans reels.

Composants a laisser converger:
- `Table`
- `Toolbar`
- `EmptyState`
- `ConfirmModal`
- `PageHeader`
- `WorkflowActionBar`
- `DocumentActions`

### 3. Patterns metier

Ce niveau couvre les assemblages propres a un workflow.

Regles:
- reutiliser les primitives stables,
- rester local si le besoin n'est pas encore transversal,
- ne pas devenir une "mini library cachee" dans un template de page.

Exemples:
- `AuthCard`
- `DashboardKpiCard`
- panneaux de preparation expedition,
- panneaux de documents ou d'allocations propres a un flux.

## Regles D'Entree Dans La Library

Un composant entre dans la library si:
- il sert au moins sur deux ecrans ou deux flux,
- son role est clairement nommable,
- son API reste courte et lisible,
- il peut etre montre proprement dans le `UI Lab`,
- il peut etre teste sans dependre d'une page metier complete.

Un composant reste local si:
- il est tres specifique a un workflow,
- sa structure n'est pas stabilisee,
- il assemble des primitives stables sans porter un contrat transverse autonome.

Un composant doit etre refuse ou differe si:
- il duplique un composant existant sous un autre nom,
- il accumule des options pour contourner un mauvais design,
- il melange structure, style et logique metier,
- il demande une API plus complexe que le probleme qu'il resout.

## Regles D'Evolution

Quand un nouveau besoin apparait:
1. verifier si le `Core stable` couvre deja l'essentiel;
2. sinon, construire un assemblage local en reutilisant le `Core stable`;
3. attendre un second usage reel avant d'extraire un nouveau composant partage;
4. simplifier l'API avant promotion;
5. ajouter au `UI Lab` et aux tests seulement quand le contrat devient durable.

Un composant stable peut evoluer si:
- le changement ameliore plusieurs usages reels,
- l'API reste plus simple qu'avant,
- les ecrans existants ne regressent pas,
- le contrat reste aligne avec Bootstrap-only et les classes `ui-comp-*`.

Sinon, il faut preferer:
- une composition locale,
- ou un composant composite au-dessus du noyau stable.

## Workflow Pour Les Prochaines Waves

### Maintenant

Le noyau stable est fige comme reference de depart.

Cela signifie:
- les prochaines waves doivent passer prioritairement par ces primitives,
- on evite d'ajouter de nouvelles primitives sans besoin transversal prouve,
- le `UI Lab` devient une reference de contrats, pas seulement un bac a sable.

### Pendant une wave

Sequence recommandee:
1. refactorer l'ecran avec le `Core stable` existant;
2. identifier les manques reels;
3. introduire si besoin un assemblage local au workflow;
4. promouvoir seulement apres repetition sur plusieurs ecrans;
5. documenter dans le `UI Lab` uniquement ce qui a vocation a durer.

### Fin de wave

Chaque wave doit produire un petit tri explicite:
- `a promouvoir`,
- `a garder en convergence`,
- `a laisser local`.

## Garde-Fous Qualite

Tout changement UI doit etre classe explicitement:
- `Core stable`,
- `En convergence`,
- `Local au workflow`.

Si le changement touche le `Core stable`, il doit inclure:
- mise a jour du composant partage ou du contrat officiel,
- demonstration dans `scan/ui-lab/`,
- tests cibles,
- verification sur au moins un ecran reel.

Si le changement touche un composant en convergence, il doit inclure:
- un usage reel,
- une API encore simple,
- aucune promesse de stabilite prematuree.

Si le changement est local au workflow, il doit:
- reutiliser au maximum les primitives stables,
- eviter les abstractions locales cachees,
- rester candidat explicite a extraction seulement si le pattern revient.

Checklist de qualite minimale:
- compatible Bootstrap-only,
- aucune dependance Next/React,
- responsive desktop/mobile,
- etats essentiels couverts,
- accessibilite minimale correcte,
- pas de duplication inutile d'un contrat deja partage.

## Impact Sur Les Sources Externes

Regle pratique pour les inspirations futures:
- lien Bootstrap: tres bon pour un composant simple ou canonique;
- lien Tabler: tres bon pour un ecran ou un bloc back-office plus structure;
- lien PatternFly: utile pour la structure d'un ecran dense, pas comme style principal;
- lien shadcn: acceptable comme inspiration visuelle ponctuelle, jamais comme contrat technique primaire.

## Critere De Sortie

La gouvernance est consideree comme correctement mise en place si:
- le `Core stable` est explicitement identifie et documente,
- le `UI Lab` expose les contrats de reference,
- les prochaines waves utilisent ces primitives au lieu de recreer du markup ad hoc,
- les composants composites sont promus seulement apres validation sur plusieurs usages reels,
- les ecarts locaux deviennent l'exception et non la norme.
