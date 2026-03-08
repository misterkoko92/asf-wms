# Benevole Integration Design

## Context
`asf-benev` fonctionne aujourd'hui comme un projet Django autonome deploye sur Render, avec ses propres `settings`, `urls`, templates `registration/*` et un `AUTH_USER_MODEL` custom (`accounts.User`). `asf-wms` expose deja des surfaces legacy Django distinctes pour `/scan/`, `/portal/` et `/admin/`, avec un flux d'authentification et d'approbation admin mature cote portail association.

Objectif produit valide:
- centraliser les deploiements en integrant le portail benevole dans `asf-wms`
- exposer une nouvelle surface `/benevole/` au meme niveau que `/portal/`
- conserver une V1 simple avec comptes crees par l'admin WMS
- preparer tres vite une V1.5 ou le benevole demande son compte, puis un superuser valide
- garder la migration Next/React hors scope; toute l'integration reste sur la pile Django legacy

## Decision Summary
Decision retenue:
- integrer le metier de `asf-benev` dans `asf-wms` comme un nouveau domaine Django legacy
- conserver le modele utilisateur actuel de `asf-wms`
- ne pas embarquer `asf-benev` tel quel comme sous-projet ou sous-application montee sous `/benevole/`

Decision explicite:
- URL publique en francais: `/benevole/`
- modules Python en anglais pour rester coherents avec la base existante (`volunteer`, `volunteer_urls`, `views_volunteer_auth`, etc.)

Decision rejetee:
- reutiliser `accounts.User` de `asf-benev`
Pourquoi:
- conflit structurel avec l'utilisateur actuel de `asf-wms`
- risque eleve sur l'authentification, les migrations, les tests et les imports existants

## Why The Direct Include Does Not Work
L'inclusion "repo tel quel sous `/benevole/`" echoue sur plusieurs points:
- `asf-benev` est un projet Django complet, pas une app Django plug-and-play
- `asf-benev` definit `AUTH_USER_MODEL = "accounts.User"`
- les templates `registration/*` et les noms d'URL `login`, `logout`, `password_reset` entrent en collision avec les routes existantes
- les settings statiques, middleware et comportements de deploiement Render sont propres au projet autonome

La bonne approche est donc une absorption domaine par domaine:
- reprendre le metier utile
- rebrancher sur les conventions `asf-wms`
- conserver un seul processus web et une seule base

## Scope
### V1
- nouveau portail `/benevole/`
- login dedie, logout, changement de mot de passe
- tableau de bord benevole
- edition du profil
- edition des contraintes
- CRUD des disponibilites
- recap hebdomadaire
- creation des comptes par l'admin WMS

### V1.5
- page publique `/benevole/request-account/`
- modele de demande de compte benevole
- validation par superuser
- creation automatique du compte et du profil
- lien de definition du mot de passe

### V2
- rattachement progressif du benevole au referentiel `contacts.Contact`
- role metier "benevole" ou equivalent dans le referentiel WMS
- exploitation de ce rattachement pour les flux expedition et suivi

### Out Of Scope
- migration Next/React
- fusion UX entre `/portal/` et `/benevole/`
- synchronisation cross-database avec l'ancienne base `asf-benev`
- reimport automatique integral des utilisateurs historiques sans cadrage dedie

## Target Architecture
`asf-wms` ajoute une troisieme surface legacy cote utilisateur final:
- `/portal/` pour les associations
- `/benevole/` pour les benevoles
- `/scan/` et `/admin/` pour les operations internes

Architecture proposee:
1. `asf_wms/urls.py` inclut `path("benevole/", include("wms.volunteer_urls"))`
2. `wms.volunteer_urls` declare toutes les routes benevoles
3. `wms.views_volunteer_auth` gere login/logout/changement de mot de passe
4. `wms.views_volunteer` gere dashboard, profil, contraintes et disponibilites
5. `wms.models_domain.volunteer` porte les modeles du domaine
6. `wms.view_permissions` expose un decorateur `volunteer_required`
7. `templates/benevole/*` heberge l'UI dediee

Mutualisation autorisee:
- helpers d'authentification
- mecanique de `must_change_password`
- emails transactionnels
- patterns de throttling et de set-password
- conventions admin

Separation a conserver:
- URLs
- permissions
- templates
- modeles de domaine
- requetes admin d'approbation

## Domain Model
Je recommande un nouveau module `wms/models_domain/volunteer.py` exporte ensuite via `wms/models.py`.

### `VolunteerProfile`
- `user = OneToOneField(settings.AUTH_USER_MODEL)`
- `contact = ForeignKey("contacts.Contact", null=True, blank=True, on_delete=models.SET_NULL)`
- `volunteer_id = PositiveIntegerField(unique=True)`
- `short_name = CharField(max_length=30, blank=True)`
- `phone = CharField(max_length=30, blank=True)`
- `address_line1 = CharField(max_length=255, blank=True)`
- `postal_code = CharField(max_length=20, blank=True)`
- `city = CharField(max_length=100, blank=True)`
- `country = CharField(max_length=100, blank=True)`
- `geo_latitude = DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
- `geo_longitude = DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
- `must_change_password = BooleanField(default=False)`
- `is_active = BooleanField(default=True)`
- `created_at`, `updated_at`

Usage:
- `contact` reste optionnel en V1/V1.5
- `must_change_password` aligne le premier acces sur le pattern portail association

### `VolunteerConstraint`
- `volunteer = OneToOneField(VolunteerProfile)`
- `max_days_per_week`
- `max_expeditions_per_week`
- `max_expeditions_per_day`
- `max_wait_hours`
- `updated_at`

### `VolunteerAvailability`
- `volunteer = ForeignKey(VolunteerProfile)`
- `date`
- `start_time`
- `end_time`
- `created_at`, `updated_at`
- validation anti-chevauchement

### `VolunteerUnavailability`
- `volunteer = ForeignKey(VolunteerProfile)`
- `date`
- `created_at`, `updated_at`
- contrainte unique `(volunteer, date)`

### `VolunteerAccountRequest`
Modele dedie pour V1.5, separe de `PublicAccountRequest`.

Champs recommandes:
- `first_name`
- `last_name`
- `email`
- `phone`
- `address_line1`
- `postal_code`
- `city`
- `country`
- `geo_latitude`, `geo_longitude`
- `notes`
- `status` (`pending`, `approved`, `rejected`)
- `reviewed_at`
- `reviewed_by`
- `created_at`

Pourquoi un modele dedie:
- `PublicAccountRequest` est oriente association et lien de commande public
- les benevoles n'ont ni `association_name` ni pieces jointes obligatoires ni logique shipper
- separer les modeles evite les branches metier bancales et simplifie l'admin

## Authentication And Access Model
Le systeme conserve le `User` de `asf-wms`.

Principes:
- pas de nouvel `AUTH_USER_MODEL`
- `username = email` pour les benevoles
- email comme identifiant de connexion sur `/benevole/login/`
- `VolunteerProfile.must_change_password` force un premier changement de mot de passe

Routes auth V1:
- `/benevole/login/`
- `/benevole/logout/`
- `/benevole/change-password/`

Routes auth V1.5:
- `/benevole/request-account/`
- `/benevole/set-password/<uidb64>/<token>/`

Le decorateur `volunteer_required` doit:
- verifier l'existence de `request.user.volunteer_profile`
- bloquer l'acces si le profil est inactif
- rediriger vers `change-password` si `must_change_password=True`
- ne jamais se melanger avec `association_required`

## UX And URL Structure
Routes V1:
- `/benevole/`
- `/benevole/profil/`
- `/benevole/contraintes/`
- `/benevole/disponibilites/`
- `/benevole/disponibilites/nouveau/`
- `/benevole/disponibilites/recap/`
- `/benevole/disponibilites/<id>/edit/`
- `/benevole/disponibilites/<id>/delete/`

Routes V1.5:
- `/benevole/request-account/`
- `/benevole/request-account/done/`
- `/benevole/set-password/<uidb64>/<token>/`

Templates recommandes:
- `templates/benevole/base.html`
- `templates/benevole/login.html`
- `templates/benevole/change_password.html`
- `templates/benevole/dashboard.html`
- `templates/benevole/profile.html`
- `templates/benevole/constraints.html`
- `templates/benevole/availability_list.html`
- `templates/benevole/availability_form.html`
- `templates/benevole/availability_confirm_delete.html`
- `templates/benevole/availability_recap.html`
- `templates/benevole/request_account.html`
- `templates/benevole/request_account_done.html`

Regle UX:
- surface benevole explicite et autonome
- style visuel coherent avec `asf-wms`
- pas de navigation croisee exposee avec `/portal/`

## Admin Model
V1:
- admin `VolunteerProfile`
- admin `VolunteerConstraint`
- admin `VolunteerAvailability`
- admin `VolunteerUnavailability`
- action admin pour creer ou reinitialiser l'acces benevole

Creation admin V1:
1. creation ou selection du `User`
2. creation du `VolunteerProfile`
3. activation `must_change_password=True`
4. email de premier acces ou reset envoye au benevole

V1.5:
- admin `VolunteerAccountRequest`
- actions `approve_requests` et `reject_requests`

Approving a volunteer request:
1. verifier qu'aucun compte staff/superuser n'utilise deja l'email
2. creer ou reactiver le `User`
3. creer le `VolunteerProfile`
4. initialiser `must_change_password=True`
5. marquer la demande `approved`
6. envoyer l'email contenant le lien `set-password`

## Relationship With `contacts.Contact`
La V1 ne doit pas dependre du referentiel contacts pour livrer vite. En revanche, il faut reserver la trajectoire V2.

Decision:
- `VolunteerProfile.contact` est nullable des la V1
- la liaison n'est pas obligatoire pour le fonctionnement du portail benevole

Strategie V2:
- representer le benevole comme un `Contact` de type `person`
- rattacher ce contact a une organisation si necessaire
- utiliser cette relation pour les futurs flux expedition, suivi et permissions transverses

Cette decision evite:
- une migration schema lourde des maintenant
- l'invention prematuree d'un role organisationnel "benevole" sans besoin concret stabilise

## Code Reuse From `asf-benev`
Code a reprendre ou adapter:
- modeles benevoles
- formulaires de profil, contraintes et disponibilites
- logique de recap hebdomadaire
- validation anti-chevauchement
- ecrans metier benevoles

Code a ne pas importer tel quel:
- `accounts/`
- `AUTH_USER_MODEL`
- `registration/*`
- `asf_benev/settings.py`
- `asf_benev/urls.py`

## Risks And Mitigations
### Risque 1: Melanger benevoles et associations dans les memes modeles
Mitigation:
- modeles distincts
- permissions distinctes
- templates distincts

### Risque 2: Refaire l'authentification completement alors que `portal` a deja les bonnes briques
Mitigation:
- mutualiser les helpers de login email, set-password, throttling, mails
- ne pas mutualiser les modeles ni les URLs

### Risque 3: Couplage trop fort a `contacts.Contact` trop tot
Mitigation:
- FK nullable
- migration V2 explicite

### Risque 4: Reprise trop litterale de `asf-benev`
Mitigation:
- reprendre uniquement le metier stable
- adapter aux conventions `asf-wms`

## Test Strategy
### Model tests
- auto-generation ou validation de `volunteer_id`
- anti-chevauchement des disponibilites
- unicite des indisponibilites
- comportement `must_change_password`

### View tests
- login benevole
- logout benevole
- redirection si non connecte
- redirection vers changement de mot de passe
- profil et contraintes
- CRUD disponibilites
- recap hebdomadaire

### Admin tests
- creation d'un benevole depuis l'admin
- reinitialisation d'acces
- approbation d'une demande benevole

### Email and request tests
- email de premier acces
- email apres approbation
- page publique de demande de compte
- refus si email deja reserve

## Rollout Plan
1. Livrer V1 avec comptes admin et portail benevole complet
2. basculer les utilisateurs pilotes sur `/benevole/`
3. ajouter la V1.5 de demande de compte publique
4. planifier la V2 de liaison `Contact`

## Recommended Implementation Shape
Structure recommandee:
- `wms/models_domain/volunteer.py`
- `wms/forms_volunteer.py`
- `wms/views_volunteer_auth.py`
- `wms/views_volunteer.py`
- `wms/volunteer_urls.py`
- `templates/benevole/*`
- nouveaux tests sous `wms/tests/volunteer/`, `wms/tests/views/` et `wms/tests/admin/`

Cette structure reste compatible avec l'organisation actuelle du code:
- domaines metier dans `models_domain`
- facade de modeles dans `wms/models.py`
- vues segmentees par surface
- URLs dediees par portail

## Conclusion
La centralisation dans `asf-wms` est faisable et techniquement saine, a condition d'integrer `asf-benev` comme domaine metier et non comme sous-projet encapsule. La V1 doit livrer rapidement un portail benevole authentifie et administre. La V1.5 doit reutiliser la logique d'approbation deja eprouvee cote portail association, mais dans un modele de demande de compte specifique aux benevoles. La V2 pourra ensuite brancher progressivement le benevolat sur le referentiel contacts sans remettre en cause la V1.
