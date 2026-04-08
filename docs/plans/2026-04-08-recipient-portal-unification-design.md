# Recipient Portal Unification Design

## Contexte

Le depot a deja deux comportements differents autour des destinataires:
- le `portal` expediteur ecrit surtout via `AssociationRecipient`, puis projette vers le runtime shipment-party avec `sync_portal_recipient_graph()`;
- `scan` manipule deja le runtime operationnel partage (`Contact`, `ShipmentRecipientOrganization`, `ShipmentRecipientContact`, liens shipper/recipient, preferences produits).

Le besoin valide est d'ouvrir aussi un acces portal aux destinataires pour:
- mettre a jour leurs informations;
- gerer leurs contacts;
- charger ou revoir leurs documents de structure;
- renseigner leurs besoins et preferences produits;
- retrouver les memes donnees depuis `portal expediteur`, `portal destinataire`, et `scan`.

Le risque principal a eviter est d'avoir trois centres d'ecriture concurrents avec des synchronisations partielles et fragiles.

## Objectif

Definir une architecture cible qui:
- etablit une seule source metier pour les donnees destinataire partagees;
- ouvre un acces portal destinataire sans dupliquer le systeme d'authentification;
- force tous les writes `portal expediteur`, `portal destinataire`, `scan`, et UI API a passer par les memes use cases;
- permet une migration progressive depuis `AssociationProfile` et `AssociationRecipient`;
- laisse la possibilite d'un reset cible du graphe recipient si cela simplifie la coupure du double systeme.

## Contraintes Repo

- stack active: Django legacy;
- scope Next/React hors sujet;
- scope traduction hors sujet;
- les surfaces HTML portal et UI API doivent rester alignees;
- le contrat recipient reste destination-scoped via `(organization, destination)`.

## Approches Etudiees

### 1. Garder `AssociationRecipient` comme source de verite

Idee:
- continuer a faire du portail expediteur la source primaire;
- repropager ensuite les mutations faites ailleurs vers `AssociationRecipient`.

Avantages:
- peu de changement apparent cote portal expediteur a court terme;
- reutilise la forme actuelle du flow.

Inconvenients:
- `scan` travaille deja sur un autre noyau;
- un meme destinataire peut etre partage entre plusieurs expediteurs;
- le retour des mutations `scan` vers un seul `AssociationRecipient` devient ambigu;
- les preferences produits sont deja attachees au runtime shipment-party, pas a `AssociationRecipient`.

Conclusion:
- non retenu.

### 2. Creer un troisieme modele maitre neuf

Idee:
- introduire un nouveau domaine canonique complet pour les destinataires;
- migrer ensuite portal et scan vers lui.

Avantages:
- modele conceptuellement propre;
- separation nette entre legacy et cible.

Inconvenients:
- cout tres eleve;
- risque de faire coexister trop longtemps trois systemes;
- le depot a deja la bonne direction structurelle via `wms/parties/` et `wms/application/parties/`.

Conclusion:
- non retenu.

### 3. Recommandee: faire du runtime shipment-party le noyau canonique

Idee:
- prendre le graphe shipment-party partage comme source metier unique;
- faire des portails et de `scan` des adaptateurs UI avec permissions differentes;
- releguer `AssociationRecipient` au rang de projection ou compatibilite transitoire.

Avantages:
- s'aligne avec l'etat reel du code et de `scan`;
- garde les preferences produits au bon endroit;
- gere naturellement le partage d'une meme structure entre plusieurs expediteurs;
- reduit la logique de synchronisation implicite.

Inconvenients:
- demande une extraction disciplinee des use cases d'ecriture;
- impose de refondre la couche de permissions portal autour d'un scope actif.

Conclusion:
- retenu.

## Decision Recommandee

Le noyau metier canonique devient le runtime shipment-party partage:
- `Contact` pour la structure et les personnes;
- `ShipmentRecipientOrganization` pour la structure destinataire par `(organization, destination)`;
- `ShipmentRecipientContact` pour les contacts destinataire;
- `RecipientStructureDocument` pour les pieces de structure;
- `RecipientProductPreference` pour les besoins et preferences produits;
- `ShipmentShipperRecipientLink` et `ShipmentAuthorizedRecipientContact` pour les relations expediteur <-> destinataire.

`AssociationRecipient` ne doit plus etre la verite metier. Pendant la transition, il reste:
- soit une projection de compatibilite par expediteur;
- soit un adaptateur legacy permettant a l'existant de continuer a lire/afficher sans casser les pages.

## Proprietaire Des Donnees

### Donnees partagees du destinataire

Une seule version visible partout:
- nom de structure, adresse, pays, forme juridique, nombre de beneficiaires;
- contacts destinataire;
- documents de structure;
- preferences et besoins produits.

Stockage canonique:
- `Contact` organisation;
- `ShipmentRecipientOrganization`;
- `ShipmentRecipientContact`;
- `RecipientStructureDocument`;
- `RecipientProductPreference`.

### Donnees de relation expediteur <-> destinataire

Version propre au lien:
- expediteurs autorises pour une structure destinataire;
- contacts autorises par expediteur;
- contact par defaut pour un expediteur donne.

Stockage canonique:
- `ShipmentShipperRecipientLink`;
- `ShipmentAuthorizedRecipientContact`.

## Regles D'Edition

Recommandation:
- `portal destinataire` et `scan` peuvent editer les donnees partagees;
- `portal expediteur` peut creer un destinataire, gerer les liens, et demander un rattachement;
- quand un acces destinataire est actif pour une structure, les champs partagees deviennent par defaut en lecture seule cote expediteur;
- les preferences produits sont editees par `portal destinataire` et `scan`, pas par l'expediteur;
- les liens expediteur <-> destinataire restent edites par l'expediteur et `scan`.

Cette regle evite qu'un expediteur modifie silencieusement une fiche partagee utilisee aussi par d'autres expediteurs.

## Modele D'Acces Portal

### Recommandation

Conserver un seul `/portal/`, une seule authentification, et une seule gestion de mot de passe.

Introduire un modele d'acces explicite, par exemple `PortalAccessGrant`, avec:
- `user`;
- `role`;
- `shipper` nullable;
- `recipient_organization` nullable;
- `is_active`;
- metadonnees de creation et revue.

Contrainte cible:
- exactement un scope actif entre `shipper` et `recipient_organization`.

### Comportement Au Login

1. authentifier l'utilisateur comme aujourd'hui;
2. resoudre tous ses acces actifs;
3. si aucun acces n'existe, refuser;
4. si un seul acces existe, l'activer en session;
5. si plusieurs acces existent, demander le choix d'espace.

### Scope Actif

Le portal travaille toujours avec un `scope actif` en session:
- scope expediteur;
- scope destinataire.

La navigation, les vues, et les permissions sont derivees de ce scope actif, pas du seul fait d'avoir un `AssociationProfile`.

### Compatibilite

Pendant la transition:
- `AssociationProfile` continue d'etre resolu comme un acces expediteur implicite;
- les decorators de permission evoluent pour accepter soit le nouveau grant, soit la compatibilite legacy;
- le login et la recuperation de mot de passe conservent les routes existantes.

## Ecriture Canonique Et Propagation

Tous les writes doivent passer par les memes use cases dans `wms/application/parties/`.

Flux cible:
1. la surface UI valide les droits et le payload;
2. elle appelle un use case canonique;
3. le use case met a jour le runtime shipment-party;
4. le use case recalcule les liens et autorisations necessaires;
5. le use case met a jour la projection legacy tant que `AssociationRecipient` existe.

Surfaces concernees:
- `portal expediteur`;
- `portal destinataire`;
- `scan`;
- UI API portal.

Consequence:
- plus aucune vue ne doit muter seule `AssociationRecipient` ou `RecipientProductPreference` hors use case partage.

## Gestion Des Conflits

Principe:
- une seule source metier;
- une seule couche d'ecriture;
- dernier write valide gagne.

Garde-fous:
- blocage ou lecture seule cote expediteur quand le destinataire a la main sur les donnees partagees;
- usage systematique de la cle `(organization, destination)` pour les destinataires;
- journalisation minimale `qui`, `quoi`, `quand`, `depuis quelle surface` si un audit explicite est ajoute dans la vague d'implementation.

## Strategie De Migration

### Phase 0: Consolider Le Graphe Recipient

Avant le basculement:
- auditer les duplications structure/contact;
- verifier la coherence des `ShipmentRecipientOrganization` par `(organization, destination)`;
- identifier les projections `AssociationRecipient` devenues divergentes.

Option autorisee:
- reset cible du graphe recipient et regeneration de la projection portal si cela simplifie la coupure du double systeme.

Reset non recommande par defaut:
- reset complet de toute la base `contacts`, sauf si un chantier plus large sur shipper/correspondent/donor est volontairement lance.

### Phase 1: Ajouter Les Grants Et Le Scope Actif

- introduire `PortalAccessGrant`;
- ajouter la resolution du scope actif;
- garder `AssociationProfile` en compatibilite temporaire.

### Phase 2: Unifier Les Use Cases D'Ecriture

- extraire les writes partages dans `wms/application/parties/use_cases.py`;
- creer un adaptateur de projection legacy pour `AssociationRecipient`.

### Phase 3: Basculer Les Surfaces Existantes

- `portal expediteur`;
- `scan/admin`;
- UI API portal.

Toutes doivent consommer les memes use cases.

### Phase 4: Ouvrir L'Espace Destinataire

Ordre recommande:
- lecture seule d'abord;
- edition ensuite sur les donnees partagees;
- lecture seule cote expediteur sur les memes champs quand le grant destinataire existe.

### Phase 5: Couper L'Ancien Centre De Gravite

- retirer `AssociationRecipient` du role de source metier;
- le garder seulement comme compatibilite de lecture ou projection si necessaire;
- planifier sa suppression du flux principal quand tous les adapteurs seront migres.

## Risques Principaux

- fusion abusive de deux structures proches mais distinctes;
- oubli du scope destination lors de recherches recipient;
- derive de permissions si `AssociationProfile` et `PortalAccessGrant` coexistent trop longtemps;
- endpoints UI API non migrs en meme temps que les pages HTML;
- pages `scan` qui contournent les nouveaux use cases.

## Verification Cible

Tests a renforcer:
- `wms/tests/portal/tests_portal_recipient_sync.py`
- `wms/tests/portal/tests_portal_shipment_parties.py`
- `wms/tests/portal/tests_portal_permissions.py`
- `wms/tests/views/tests_views_portal.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`
- `wms/tests/views/tests_views_scan_admin.py`
- `wms/tests/views/tests_views_scan_admin_shipment_parties.py`
- `wms/tests/core/tests_parties_destination_scope.py`
- `api/tests/tests_ui_endpoints.py`
- `api/tests/tests_ui_e2e_workflows.py`

Cas essentiels:
- mutation dans `scan` visible dans les deux portals;
- mutation dans `portal destinataire` visible dans `scan` et `portal expediteur`;
- mutation de lien expediteur <-> destinataire visible seulement sur les surfaces legitimes;
- utilisateur multi-acces avec choix de scope actif;
- creation de destinataire partage sans rupture sur plusieurs destinations.

## Hors Scope

- migration Next/React;
- parite FR/EN;
- refonte globale de toute la base `contacts`;
- nouveaux workflows commandes pour les destinataires au-dela de la maintenance de leur fiche et de leurs besoins produits.

## Resultat Attendu

En fin de migration:
- il n'existe plus qu'un seul chemin d'ecriture metier pour les donnees destinataire partagees;
- l'acces portal fonctionne par scope actif, pas par hypothese implicite `user == expediteur`;
- `scan`, `portal expediteur`, `portal destinataire`, et UI API lisent le meme noyau metier;
- `AssociationRecipient` n'est plus un systeme concurrent.
