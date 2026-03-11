# Planning Bilan Destination Summary Design

## Contexte

L'ecran `planning:version_detail` affiche deja un bloc `Bilan Planning` avec un tableau de synthese par benevole. Le besoin est d'ajouter sous ce premier tableau un second tableau centre sur les destinations et les expeditions disponibles pour la version de planning courante, sans toucher au scope Next/React en pause.

Le nouvel affichage doit permettre:
- de visualiser une vue reduite par destination;
- de deplier chaque destination pour voir le detail par expedition;
- de tout developper ou tout reduire en un clic;
- de trier toutes les colonnes, y compris les lignes expedition a l'interieur d'une destination developpee.

## Sources de donnees

Le tableau s'appuie sur les snapshots deja disponibles dans le cockpit planning:
- `version.assignments` pour les expeditions planifiees;
- `version.run.shipment_snapshots` pour l'ensemble des expeditions disponibles sur le run;
- `version.run.solver_result.unassigned_reasons` pour reutiliser la notion de non-affectation quand utile.

Le backend preparera une nouvelle structure dans `dashboard["planning_summary"]` en complement de `volunteer_rows`.

## Regles metier

Chaque expedition disponible du run apparait dans exactement une destination.

Le statut affiche dans la colonne `Etat` est defini comme suit:
- `Planifie` si l'expedition a une affectation dans la version courante;
- `Non partant` sinon.

Les lignes destination sont des agregats calcules sur toutes les expeditions de la destination:
- `Destination`: code destination;
- `BE_Numero`: `nb_partants / nb_total`;
- `Etat`: `nb_partants / nb_total`;
- `BE_Nb_Colis`: `somme_colis_partants / somme_colis_total`;
- `BE_Nb_Equiv`: `somme_equiv_partants / somme_equiv_total`;
- `BE_Type`: vide;
- `BE_Expediteur`: vide;
- `BE_Destinataire`: vide.

Les lignes expedition affichees en mode developpe utilisent les valeurs propres de l'expedition:
- `Destination`;
- `BE_Numero`;
- `Etat`;
- `BE_Nb_Colis`;
- `BE_Nb_Equiv`;
- `BE_Type`;
- `BE_Expediteur`;
- `BE_Destinataire`.

## Structure backend proposee

`build_version_dashboard()` exposera une nouvelle cle, par exemple `dashboard["planning_summary"]["destination_rows"]`, avec une liste ordonnee de groupes:

```python
{
    "destination_rows": [
        {
            "destination_iata": "NSI",
            "is_expanded": False,
            "summary": {
                "destination_iata": "NSI",
                "shipment_reference_display": "5 / 8",
                "status_display": "5 / 8",
                "carton_display": "42 / 51",
                "equivalent_units_display": "42 / 51",
                "shipment_type": "",
                "shipper_name": "",
                "recipient_label": "",
                "planned_count": 5,
                "total_count": 8,
            },
            "shipments": [
                {
                    "destination_iata": "NSI",
                    "shipment_reference": "260128",
                    "status_label": "Planifie",
                    "carton_count": 10,
                    "equivalent_units": 10,
                    "shipment_type": "MM",
                    "shipper_name": "ASF",
                    "recipient_label": "CORRESPONDANT",
                }
            ],
        }
    ]
}
```

Le backend ne porte pas l'etat ouvert/ferme interactif. Il fournit uniquement des donnees stables; l'etat d'expansion reste cote navigateur, initialise a `reduit`.

## Rendu template

Le bloc `templates/planning/_version_planning_summary_block.html` conservera le premier tableau benevoles puis ajoutera:
- un titre ou intertitre court pour le second tableau;
- un bouton global `Tout developper` / `Tout reduire`;
- un second `table.scan-table` avec ses huit colonnes:
  - `Destination`
  - `BE_Numero`
  - `Etat`
  - `BE_Nb_Colis`
  - `BE_Nb_Equiv`
  - `BE_Type`
  - `BE_Expediteur`
  - `BE_Destinataire`

Les lignes destination et expedition seront rendues dans le meme `tbody` afin de reutiliser les styles de tableau existants. Chaque destination formera un groupe compose:
- d'une ligne parent destination;
- de zero a n lignes enfant expedition.

La ligne parent contiendra un bouton de repli/depli dans la colonne `Destination`.

## Interaction frontend

Un script local au template, ou un petit script inline dedie au bloc, gerera:
- l'etat initial reduit pour toutes les destinations;
- le bouton global de bascule;
- le depliage d'une destination a la fois;
- le tri des groupes.

Le tri doit respecter deux niveaux:
- tri principal entre lignes destination sur la colonne choisie;
- tri secondaire des expeditions a l'interieur de chaque destination, sur la meme colonne, quand le groupe est developpe.

Les colonnes vides des lignes destination (`BE_Type`, `BE_Expediteur`, `BE_Destinataire`) restent triables mais n'apportent pas de valeur de comparaison utile pour l'agregat, donc l'ordre restera stable.

Le script ne doit pas impacter le premier tableau benevoles ni les autres tableaux planning. Il doit cibler uniquement le nouveau tableau via des attributs `data-*` dedies.

## Strategie de tri

Le systeme `data-table-tools="1"` existant dans `scan.js` traite deja des groupes `primary + extras`, mais repose sur une detection implicite du groupe via le nombre de cellules. Le nouveau tableau a besoin d'un controle explicite de groupes et de lignes masquees, donc il est preferable d'ajouter un script specifique au bloc plutot que de generaliser immediatement la logique globale de `scan.js`.

Ce script doit:
- capturer la liste des groupes destination au chargement;
- memoriser l'ordre d'origine;
- recalculer l'ordre des destinations selon la colonne courante;
- recalculer l'ordre des lignes expedition a l'interieur de chaque groupe;
- reappliquer l'affichage selon l'etat developpe/reduit apres chaque tri.

## Tests

Tests backend:
- verifier la construction de la synthese par destination;
- verifier les statuts `Planifie` et `Non partant`;
- verifier les compteurs `partants / total`;
- verifier les totaux `colis partants / colis total` et `equiv partants / equiv total`.

Tests de vue:
- verifier la presence du second tableau et de ses colonnes;
- verifier la presence du bouton global;
- verifier le rendu des valeurs agregees de type `5 / 8`.

La logique JS restera suffisamment legere pour etre couverte indirectement par le rendu HTML et une verification manuelle locale si necessaire.
