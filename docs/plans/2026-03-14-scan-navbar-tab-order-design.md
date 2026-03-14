# Scan Navbar Tab Order Design

## Contexte

La navbar principale du stack Django legacy est definie directement dans
`templates/scan/base.html`.

Le besoin est de reordonner les onglets de premier niveau sans toucher a la
pile Next/React en pause, et d'harmoniser leurs libelles en casse titre.

## Objectif

Appliquer a tous les profils le meme ordre de navigation principal:

- `Tableau De Bord`
- `Voir Les Etats`
- `Reception`
- `Preparation`
- `Planning`
- `Suivi Des Expeditions`
- `Facturation`
- `Gestion`
- `Admin`
- `Compte`

Contraintes retenues:

- `Facturation` reste conditionnel et ne s'affiche qu'aux profils autorises;
- `Admin` reste conditionnel et ne s'affiche qu'aux superusers;
- quand un onglet conditionnel est absent, les autres conservent leur ordre
  relatif;
- seul le premier niveau de navigation change, pas les sous-menus ni les
  routes.

## Approche retenue

Approche retenue:

- reordonner directement les blocs `<li class="nav-item">` dans
  `templates/scan/base.html`;
- mettre a jour les libelles des onglets de premier niveau en casse titre;
- ajouter un test de rendu qui verrouille l'ordre pour un profil standard, un
  profil facturation et un superuser.

Approches ecartees:

- introduire une structure Python dediee pour decrire la navbar, car cela
  serait surdimensionne pour un simple changement d'ordre;
- imposer l'ordre via CSS, car l'ordre visuel divergerait du DOM et de
  l'accessibilite.

## Impact UI

Les sous-menus restent inchanges.

Les libelles de premier niveau deviennent:

- `Tableau De Bord`
- `Voir Les Etats`
- `Reception`
- `Preparation`
- `Planning`
- `Suivi Des Expeditions`
- `Facturation`
- `Gestion`
- `Admin`
- `Compte`

Dans le template final, les accents existants sont conserves sur les libelles
francais rendus a l'ecran.

## Tests

Ajouter une couverture dans `wms/tests/views/tests_scan_bootstrap_ui.py` pour:

- verifier l'ordre des onglets sans `Facturation` ni `Admin`;
- verifier l'insertion de `Facturation` avant `Gestion` pour un profil
  autorise facturation;
- verifier l'insertion de `Facturation` et `Admin` aux positions attendues pour
  un superuser;
- verifier les nouveaux libelles en casse titre.
