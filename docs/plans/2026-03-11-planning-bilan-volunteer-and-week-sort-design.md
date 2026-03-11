# Planning Bilan Volunteer And Week Sort Design

## Contexte

Le cockpit `planning:version_detail` expose deja:
- deux tableaux dans `Vue Semaine`;
- un premier tableau `Bilan Planning` par benevole;
- un second tableau `Bilan Planning` par destination/expedition avec tri groupe local.

Le besoin est de rendre triables sur toutes les colonnes:
- les deux tableaux `Vue Semaine`;
- le premier tableau `Bilan Planning`.

Le besoin inclut aussi des ajustements de libelles et de colonnes dans le premier tableau `Bilan`.

## Objectif UX

`Vue Semaine`:
- `Disponibilites benevoles (vue semaine)` triable sur toutes les colonnes;
- `Vols disponibles (vue semaine)` triable sur toutes les colonnes;
- aucun filtre ajoute;
- aucun changement au rendu des donnees hors tri.

`Bilan Planning`:
- premier sous-titre: `Bilan Bénévoles`;
- second sous-titre: `Bilan Expéditions`;
- premier tableau triable sur toutes les colonnes;
- suppression de la colonne `Disponibilites`;
- ajout des colonnes `Nb Colis Affecté` et `Nb Equiv Affecté` juste apres `Nb_BE_Affectes`.

## Strategie de tri

Le mecanisme global `data-table-tools="1"` de `scan.js` ajoute une ligne de filtres. Ce comportement ne correspond pas au besoin. Il ne faut donc pas etendre `scan.js` pour ce cas.

Approche retenue:
- conserver le tri groupe local existant pour `Bilan Expéditions`;
- ajouter un script local planning pour les tableaux simples seulement;
- marquer explicitement les tableaux simples triables via un attribut `data-planning-simple-table="1"`.

Le script simple doit:
- cibler uniquement les tableaux du cockpit planning;
- rendre chaque cellule d'en-tete triable;
- supporter texte, nombres, dates courtes et cellules enrichies par badges/texte compose;
- ne jamais inserer de ligne de filtre;
- conserver un ordre stable quand deux valeurs sont identiques.

## Donnees backend

`dashboard["planning_summary"]["volunteer_rows"]` doit etre enrichi avec:
- `assigned_carton_count`;
- `assigned_equivalent_units`.

Calcul:
- `assigned_carton_count` = somme des `assignment.assigned_carton_count` du benevole;
- `assigned_equivalent_units` = somme des `assignment.shipment_snapshot.equivalent_units` pour les BE affectes au benevole.

Les autres compteurs existants restent inchanges.

## Rendu template

Dans `templates/planning/_version_planning_summary_block.html`:
- ajouter le sous-titre `Bilan Bénévoles` au-dessus du premier tableau;
- transformer le premier tableau en tableau simple triable via `data-planning-simple-table="1"`;
- remplacer les colonnes du premier tableau par:
  - `Benevole`
  - `Nb_Dispo`
  - `Nb_Jours_Affectes`
  - `Nb_Vols_Affectes`
  - `Nb_BE_Affectes`
  - `Nb Colis Affecté`
  - `Nb Equiv Affecté`
- renommer le second sous-titre en `Bilan Expéditions`.

Dans `templates/planning/_version_week_view_block.html`:
- marquer les deux tableaux comme tableaux simples triables via `data-planning-simple-table="1"`;
- conserver `data-table-tools="1"` seulement pour la mise en page existante si necessaire, mais le tri effectif reste gere localement.

## Tests

Tests dashboard:
- verifier que le premier bilan expose `assigned_carton_count`;
- verifier que le premier bilan expose `assigned_equivalent_units`.

Tests vue:
- verifier les nouveaux sous-titres `Bilan Bénévoles` et `Bilan Expéditions`;
- verifier l'absence de `Disponibilites` dans le premier tableau;
- verifier la presence des nouvelles colonnes `Nb Colis Affecté` et `Nb Equiv Affecté`;
- verifier la presence des hooks `data-planning-simple-table="1"` sur les deux tableaux `Vue Semaine` et le premier tableau `Bilan`.

Le tri JS reste valide indirectement par les hooks et le rendu serveur; aucun test navigateur supplementaire n'est ajoute dans cette iteration.
