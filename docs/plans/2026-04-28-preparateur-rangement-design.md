# Rangement préparateur - design

## Objectif

Ajouter au compte préparateur un flux de rangement rapide depuis `/scan/preparateur/`.
Le préparateur scanne jusqu'à cinq produits, voit l'emplacement de rangement, saisit une quantité
optionnelle, et le stock est augmenté pour les produits connus ayant un emplacement défini.

## Design retenu

- Ajouter un bouton `Rangement` sur l'accueil préparateur, au même niveau que les flux commande et colis.
- Ajouter une route legacy Django `/scan/preparateur/rangement/`, réservée au groupe `Preparateur`.
- Réutiliser la résolution produit existante (`SKU`, `barcode`, `EAN`, nom exact, préfixe unique).
- Conserver le récap batch en session afin de garder le contexte après plusieurs scans.
- Limiter le batch à cinq produits distincts. Un même produit rescanné incrémente sa quantité.
- Créer une entrée de stock immédiatement après un scan connu si le produit possède un emplacement par défaut.
- Afficher `Pas d'emplacement défini, demander conseil` si le produit connu n'a pas d'emplacement par défaut.
  Dans ce cas, le produit est ajouté au récap mais aucun stock n'est créé, car `ProductLot` exige un emplacement.
- Si le produit est inconnu, ne pas modifier le stock, afficher le récap déjà scanné, et ouvrir la modale
  d'ajout produit. Le préparateur peut terminer le batch ou créer le produit.
- Réutiliser le formulaire et le service existants de création de produit inconnu préparateur afin de garder
  la création produit incomplète, le stock initial, et la notification de revue.

## Améliorations incluses

- Déduplication par produit dans le récap avec incrément de quantité.
- Affichage explicite du statut de stock pour distinguer les lignes enregistrées et celles sans emplacement.
- Action `Terminer le rangement` pour vider le batch et revenir à l'accueil préparateur.

## Hors périmètre

- Aucun changement Next/React.
- Aucun changement de traduction FR/EN.
- Pas de nouvelle API miroir.
