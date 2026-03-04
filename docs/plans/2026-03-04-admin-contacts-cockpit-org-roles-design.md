# Admin Contacts Org-Role Cockpit Design

## Contexte

- Ecran cible: `scan/admin/contacts/`.
- Direction validee: abandon rapide du legacy et passage a une UX orientee operations metier org-role.
- Objectif produit: couvrir les operations quotidiennes sans passer par l'admin Django sauf secours temporaire.

## Objectifs fonctionnels

1. Modifier un contact/organisation existant selon les besoins metier:
- changer les roles (shipper, recipient, correspondent, donor, transporter),
- lier une personne a une organisation,
- gerer les liens role-contact,
- filtrer les destinataires d'un expediteur,
- gerer scopes expediteur et bindings shipper-recipient-destination.
2. Creer un contact avec options conditionnelles selon l'action voulue.
3. Reduire au maximum la dependance a l'interface admin Django.

## Hors scope

- Frontend Next/React (`frontend-next/`, etc.)
- Refonte d'autres ecrans scan/portal non lies a `Admin > Contacts`

## Architecture cible

- URL conservee: `/scan/admin/contacts/`.
- La page devient un cockpit metier unique en 4 zones:
1. Recherche/Filtres.
2. Fiche organisation selectionnee.
3. Actions metier.
4. Creation guidee.
- Le legacy devient un fallback court terme:
1. si `legacy_contact_write_enabled=False`, les formulaires legacy sont masques et leurs actions rejetees,
2. des liens admin Django restent disponibles en secours transitoire.

## Structure UI detaillee

### 1) Barre de pilotage

Filtres rapides:
- role (shipper/recipient/correspondent/donor/transporter),
- statut (actif / en revue / non conforme),
- scope destination (escale cible / toutes escales),
- mode "shipper -> destinataires".

Recherche unifiee:
- nom organisation,
- ASF ID,
- email,
- IATA.

### 2) Tableau resultat

Colonnes:
- organisation,
- roles actifs,
- contact principal par role,
- scopes shipper,
- nb de destinataires lies,
- etat revue/conformite,
- actions.

Actions rapides par ligne:
- gerer roles,
- gerer contacts organisation,
- gerer scopes,
- gerer bindings,
- creer contact personne.

### 3) Panneau "Gerer roles"

- Activation/desactivation par role.
- Blocage inline si activation impossible (pas de primary email actif).

### 4) Panneau "Gerer contacts organisation"

- CRUD `OrganizationContact`.
- Lien/delien avec `OrganizationRoleContact`.
- Gestion du `primary`.
- Activation/desactivation.
- Action explicite: lier une personne existante a l'organisation.

### 5) Panneau "Gerer scopes shipper"

- Mode global (`all_destinations=True`) ou granularite par escale.
- Fenetres de validite (`valid_from`, `valid_to`).
- Validation des conflits en inline.

### 6) Panneau "Gerer bindings recipient"

- Grille editable `(shipper, recipient, destination, actif, validite)`.
- Creation, cloture (valid_to), reactivation via nouvelle version.
- Vue derivee "tous les destinataires d'un shipper".

### 7) Bloc "Creation guidee"

Assistant court:
- "Je cree": organisation/personne,
- "Usage": role(s),
- "Lien": rattachement org pour personne,
- "Configurer maintenant": scopes/bindings.

Les champs affiches s'adaptent a l'intention.

## Flux de donnees

Lectures principales:
- `contacts.Contact` (base organisation/personne),
- `wms.OrganizationRoleAssignment`,
- `wms.OrganizationContact`,
- `wms.OrganizationRoleContact`,
- `wms.ShipperScope`,
- `wms.RecipientBinding`,
- `wms.MigrationReviewItem` (etat revue).

Commandes metier (POST) prevues:
- `assign_role`, `unassign_role`,
- `upsert_org_contact`,
- `link_role_contact`, `unlink_role_contact`, `set_primary_role_contact`,
- `upsert_shipper_scope`, `disable_shipper_scope`,
- `upsert_recipient_binding`, `close_recipient_binding`,
- `create_guided_contact`.

Chaque commande est transactionnelle et renvoie des messages explicites.

## Regles metier et validations

- Un role actif requiert un contact principal actif avec email.
- Le role-contact doit appartenir a la meme organisation.
- Shipper scope:
1. soit global,
2. soit une destination obligatoire.
- Recipient binding:
1. shipper et recipient doivent etre des organisations actives,
2. validite temporelle coherente (`valid_to > valid_from`).
- Legacy:
1. quand `legacy_contact_write_enabled=False`, les ecritures legacy sont bloquees,
2. l'UI cockpit reste operationnelle.

## Erreurs et retours UX

- Erreurs affichees au niveau du panneau/du champ.
- Message normalise:
1. cause,
2. impact,
3. correction attendue.

## Traçabilite

- Minimum: `messages` + `updated_at`.
- Recommande: audit metier dedie (acteur, objet, avant/apres) pour sortie complete de l'admin Django.

## Plan de livraison

1. V1: cockpit lecture + filtres + permissions.
2. V2: actions roles + contacts organisation.
3. V3: scopes shipper + bindings recipient.
4. V4: creation guidee + retrait final du legacy.

## Strategie de test

- Tests vue/permissions/filtres sur `scan_admin_contacts`.
- Tests actions metier par commande (cas nominal + erreurs).
- Tests regressions des regles org-role (primary email, scope, binding).
- Tests de bascule runtime (`legacy_contact_write_enabled`).

## Definition of Done

- Les operations metier quotidiennes contacts/roles/scopes/bindings se font dans `Admin > Contacts` sans detour admin Django.
- Les validations metier existantes sont preservees.
- Le fallback legacy est desactive proprement via runtime flag.
