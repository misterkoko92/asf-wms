# Shipment Contact Model Design

## Contexte

- La gestion actuelle des contacts d'expedition repose sur un moteur generique `org-roles`.
- Ce moteur couvre aujourd'hui `shipper`, `recipient`, `correspondent`, `donor`, `transporter`, avec des couches dediees aux contacts primaires, scopes expediteur, bindings destinataire, synchronisation portail, validation ASF et correspondants de destination.
- La douleur principale exprimee est d'abord ergonomique (`admin` et `portail`), mais elle se retrouve aussi dans le code et les donnees.
- Le perimetre cible de cette refonte est strictement le sous-domaine expedition sur la stack Django legacy. `donateur` et `transporteur` sortent du probleme.

## Probleme Avec Le Modele Actuel

Le probleme principal n'est pas le nombre de tables. Le probleme est que l'abstraction centrale est mal alignee avec le metier.

Le moteur `org-roles` raisonne surtout en:
- structure qui porte un role,
- contact principal d'un role,
- scope d'autorisation par destination,
- binding expediteur -> destinataire,
- correspondant gere a part.

Le metier reel de l'expedition raisonne plutot en:
- structure expediteur,
- structure destinataire partagee,
- relation explicite expediteur -> structure destinataire,
- referents destinataire autorises pour cette relation,
- correspondant unique par escale, mais traite comme un destinataire particulier.

Le decalage cree plusieurs couts:
- l'UI expose des concepts techniques qui ne correspondent pas au langage metier,
- le code disperse les regles sur plusieurs objets et services,
- les donnees dupliquent ou recouvrent plusieurs notions de "personne rattachee a une structure",
- certaines regles essentielles, comme "le referent destinataire depend de l'expediteur", sont mal exprimees par un modele centre sur le role global.

## Regles Metier Validees

Les regles ci-dessous ont ete validees au cadrage.

- Une expedition comporte toujours un expediteur, un destinataire et un correspondant.
- L'expediteur et le destinataire sont toujours des structures.
- Le correspondant peut etre une structure ou une personne.
- Si le correspondant est une personne seule, elle est rattachee par defaut a la structure support `ASF - CORRESPONDANT`.
- Dans une expedition, chaque role doit etre affiche comme `referent + structure`.
- Une structure destinataire appartient toujours a une seule escale.
- Une structure destinataire est globale et partagee entre expediteurs.
- Un expediteur peut creer lui-meme une structure destinataire et ses referents dans le portail.
- Les admins ASF peuvent fusionner des doublons et forcer les corrections de donnees.
- Une structure proposee dans le portail doit reutiliser si possible un existant, mais la creation d'un doublon reste possible.
- Une structure expediteur ou destinataire creee via portail doit etre validee par ASF avant usage.
- Une structure deja validee reste validee apres modification, avec alertes aux autres expediteurs et aux admins.
- Les referents d'une structure destinataire ne demandent pas de validation ASF individuelle.
- Un meme referent destinataire peut etre autorise pour plusieurs expediteurs.
- Un referent peut etre actif globalement sur la structure, mais actif ou inactif differemment selon l'expediteur.
- Pour un meme couple `(expediteur, structure destinataire)`, plusieurs referents peuvent etre autorises, avec un referent par defaut.
- En V1, l'expediteur a un seul referent actif par defaut.
- En V1, le correspondant est unique par escale.
- Un correspondant doit aussi etre selectionnable comme destinataire de son escale.
- Ce destinataire "correspondant" n'est pas autorise automatiquement pour tous les expediteurs: il suit les memes liens explicites que les autres destinataires.
- Une expedition doit stocker un instantane fige des parties choisies, independant des evolutions ulterieures du referentiel.

## Decision D'Architecture

Le sous-domaine expedition sort du moteur `org-roles`.

Le moteur `org-roles` n'est plus la source de verite pour:
- expediteur,
- destinataire,
- correspondant.

`Contact` reste la base generique du referentiel personne/structure. Le nouveau modele expedition repose sur des objets dedies a la relation metier expedition.

## Modele Cible V1

### 1. Base de referentiel

`contacts.Contact` reste l'entite generique:
- structure = `Contact` de type `organization`,
- personne = `Contact` de type `person`,
- rattachement d'une personne a une structure via `Contact.organization`.

Le sous-domaine expedition ne repose plus sur `OrganizationContact` ni `OrganizationRoleContact`.

### 2. Expediteur

Nouvel objet metier `ShipmentShipper`:
- reference la structure expediteur,
- porte le referent expediteur par defaut en V1,
- porte le statut `active / inactive`,
- porte le statut ASF `pending / validated / rejected`,
- porte une capacite speciale `can_send_to_all` pour `Aviation Sans Frontieres`.

### 3. Structure destinataire

Nouvel objet metier `ShipmentRecipientOrganization`:
- reference la structure destinataire,
- porte une unique escale,
- porte `active / inactive`,
- porte `pending / validated / rejected`,
- peut etre marquee `is_stopover_correspondent`.

La structure destinataire est globale et partagee.

### 4. Referent destinataire

Nouvel objet `ShipmentRecipientContact`:
- reference une personne (`Contact`) rattachee a la structure destinataire,
- porte seulement `active / inactive`.

Ce referent est global a la structure et donc reutilisable par plusieurs expediteurs.

### 5. Lien expediteur -> structure destinataire

Nouvel objet `ShipmentShipperRecipientLink`:
- relie un expediteur a une structure destinataire,
- porte `active / inactive`.

Ce lien exprime l'autorisation metier principale:
- "ASF peut envoyer a Hopital de Bamako",
- "MSF peut envoyer a Hopital de Bamako".

### 6. Referent autorise par lien

Nouvel objet `ShipmentAuthorizedRecipientContact`:
- relie un `ShipmentShipperRecipientLink` a un `ShipmentRecipientContact`,
- porte `active / inactive`,
- porte `is_default`.

Contraintes:
- un referent destinataire peut etre autorise sur plusieurs liens,
- un seul referent par defaut actif par lien,
- la desactivation au niveau du lien n'affecte pas les autres expediteurs.

### 7. Correspondant d'escale

Le correspondant devient un cas particulier de `ShipmentRecipientOrganization`:
- un seul correspondant actif par escale,
- il reste selectionnable comme destinataire,
- il n'est pas autorise automatiquement pour tous les expediteurs,
- ses liens expediteur -> destinataire sont geres comme pour tout autre destinataire.

## UX Cible

### Creation d'expedition

Sequence conservee:
- escale,
- expediteur,
- structure destinataire,
- referent destinataire.

Comportement:
- l'escale filtre les expediteurs autorises,
- l'expediteur filtre les structures destinataires liees et actives sur cette escale,
- la structure destinataire filtre les referents autorises et actifs pour cet expediteur,
- le referent par defaut du lien est preselectionne,
- le correspondant est derive automatiquement de l'escale en V1 et non selectionnable.

### Portail expediteur

Le portail est centre sur la structure destinataire, pas sur un couple structure + referent.

Pour chaque structure destinataire, l'expediteur peut:
- reutiliser ou creer la structure,
- ajouter des referents a cette structure,
- autoriser ou retirer des referents pour lui,
- choisir le referent par defaut,
- modifier les informations communes de la structure.

Le portail doit:
- proposer une structure existante sur la meme escale avant creation,
- autoriser la creation d'un doublon si necessaire,
- rendre les modifications visibles aux autres expediteurs concernes et aux admins via alertes.

### Admin ASF

Le cockpit admin devient centre sur:
- expediteurs,
- structures destinataires,
- liens expediteur -> destinataire,
- referents destinataire,
- correspondants d'escale,
- fusion des structures,
- fusion ou reassignment de referents,
- validation ASF des structures.

## Historique Et Instantane

L'expedition stocke un instantane metier immuable.

Pour chaque partie:
- identifiant technique facultatif pour navigation,
- libelle fige au format `referent + structure`,
- emails/telephones utiles si necessaire pour documents ou notifications.

Les vues, exports, PDFs et emails doivent lire d'abord cet instantane. Le referentiel courant ne doit jamais reecrire l'historique d'une expedition deja creee.

## Statuts

### Structures expediteurs et destinataires

- `is_active`
- `asf_validation_status in {pending, validated, rejected}`

### Liens

- `ShipmentShipperRecipientLink.is_active`
- `ShipmentAuthorizedRecipientContact.is_active`
- unicite du referent par defaut actif par lien

### Referents

- `ShipmentRecipientContact.is_active`
- pas de validation ASF individuelle en V1

## Gain Reel Par Rapport A Org-Roles

Le gain reel n'est pas une promesse de "moins de tables". Le gain est une reduction de complexite conceptuelle et operationnelle.

### 1. L'abstraction centrale colle enfin au metier

Avec `org-roles`, le coeur du modele est:
- une structure a un role,
- un role a un contact principal,
- des scopes et bindings reglent l'autorisation.

Avec le nouveau modele, le coeur devient:
- un expediteur est autorise a envoyer a une structure destinataire,
- certains referents de cette structure sont autorises pour cet expediteur,
- un referent par defaut est propose pour cette relation.

Cette formulation correspond exactement aux regles exprimees au cadrage.

### 2. L'UI devient comprehensible

Aujourd'hui, un utilisateur doit raisonner avec:
- role,
- contact d'organisation,
- contact principal de role,
- scope expediteur,
- binding destinataire,
- correspondant de destination.

Demain, il raisonne avec:
- expediteur,
- structure destinataire,
- referents de la structure,
- referents autorises pour cet expediteur.

Le vocabulaire de l'UI redevient le vocabulaire metier.

### 3. Les donnees deviennent plus propres

Le nouveau modele evite:
- de dupliquer une structure destinataire par referent,
- de dupliquer une structure destinataire par expediteur,
- de forcer des contournements via des contacts primaires de role quand la variabilite reelle est au niveau de la relation expediteur -> referent.

Un meme referent de la structure peut etre partage proprement par plusieurs expediteurs.

### 4. Le code se simplifie vraiment

Aujourd'hui, les regles sont diffusees entre plusieurs couches runtime, notamment:
- [wms/models_domain/portal.py](/Users/EdouardGonnu/asf-wms/wms/models_domain/portal.py)
- [wms/organization_role_resolvers.py](/Users/EdouardGonnu/asf-wms/wms/organization_role_resolvers.py)
- [wms/shipment_party_rules.py](/Users/EdouardGonnu/asf-wms/wms/shipment_party_rules.py)
- [wms/portal_recipient_sync.py](/Users/EdouardGonnu/asf-wms/wms/portal_recipient_sync.py)

Le nouveau mode permet de concentrer les regles expedition dans un sous-domaine unique.

### 5. L'evolution V2 devient plus simple

Le modele V1 reste strict sur:
- un seul referent expediteur,
- un seul correspondant par escale.

Mais il laisse une evolution naturelle vers:
- plusieurs referents expediteur,
- exceptions plus fines,
- alertes de gouvernance plus riches,
- fusion et dedoublonnage mieux outilles.

Avec `org-roles`, ces evolutions continueraient d'empiler des exceptions sur un moteur deja trop generique pour ce besoin.

## Couts Et Trade-Offs

- Il faut une vraie migration, pas juste un remaquillage d'ecran.
- Il faudra maintenir une phase transitoire entre ancien et nouveau mode.
- Certaines fonctions existantes de `org-roles` devront etre rebranchees ou explicitement retirees pour l'expedition.
- `donateur` et `transporteur` devront conserver leur propre modele ou garder `org-roles` hors de ce sous-domaine.

## Hors Scope

- Aucun travail Next/React.
- Pas de refonte globale du referentiel `Contact`.
- Pas de migration de `donateur` et `transporteur` dans cette initiative.
- Pas de versioning temporel `valid_from / valid_to` sur les liens en V1.
- Pas de multi-referent expediteur en V1.

## Strategie De Migration

1. Introduire le nouveau sous-domaine expedition sans retirer immediatement `org-roles`.
2. Backfiller les expediteurs, structures destinataires, liens et referents depuis les donnees existantes.
3. Brancher scan et portail sur le nouveau modele, avec instantane fige dans l'expedition.
4. Sortir progressivement l'expedition de `org-roles`.
5. Conserver ou reaffecter `org-roles` uniquement hors du perimetre expedition si necessaire.

## Definition Of Done

- Le parcours expedition n'utilise plus `org-roles` comme source de verite.
- Le portail manipule des structures destinataires partagees et leurs referents.
- Le scan cree des expeditions a partir d'un filtre explicite `escale -> expediteur -> structure destinataire -> referent`.
- Le correspondant est gere comme un destinataire particulier, unique par escale.
- Les expeditions stockent un instantane immuable des parties.
- Les admins peuvent valider, corriger et fusionner les structures et referents.
