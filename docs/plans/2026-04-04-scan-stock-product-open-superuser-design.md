# Vue Stock Produit Ouvrir Admin - Design

## Contexte

La vue stock legacy scan affiche deja les produits, leur categorie, le stock consolide et la derniere modification via:
- `wms/views_scan_stock.py`
- `wms/stock_view_helpers.py`
- `templates/scan/stock.html`

Le besoin est d'ajouter un raccourci de pilotage en fin de ligne pour ouvrir la fiche produit, sans creer une nouvelle interface d'edition et sans elargir les permissions de la page stock.

## Objectif

Depuis `Scan > Vue stock`, permettre a un superuser d'ouvrir directement la fiche produit dans l'admin Django depuis chaque ligne du tableau.

## Decisions Validees

- acces a l'action: superuser uniquement
- comportement: simple lien `Ouvrir` vers `admin:wms_product_change`
- aucune nouvelle route scan
- aucune nouvelle logique CRUD cote scan
- la page stock reste accessible selon les regles staff existantes

## Approche Retenue

Ajouter une colonne `Actions` dans le tableau de `templates/scan/stock.html`, rendue uniquement si `request.user.is_superuser`.

Chaque ligne affiche:
- un bouton `Ouvrir`
- cible: `admin:wms_product_change`
- ouverture dans un nouvel onglet pour garder la vue stock comme cockpit

## Impact Technique

- pas de changement sur `build_stock_context`
- pas de changement de permission sur `scan_stock`
- pas de duplication de la logique d'edition produit deja portee par `wms.ProductAdmin`

## Tests

- verifier que le bouton apparait pour un superuser sur la vue stock
- verifier qu'il n'apparait pas pour un staff non superuser
- conserver les contrats bootstrap existants de la table stock

## Impact Map

Changement local a une page scan existante:
- pas d'API a aligner
- pas de nouveau flux metier
- pas de doc `repo-reference` a mettre a jour car aucun contrat partage ou route critique n'est modifie
