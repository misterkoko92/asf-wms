# Shipment Note And Customs Layout Adjustments Design

## Goal

Appliquer une retouche V1 ciblée sur les templates HTML du `bon d'expédition` et du `document douane` pour les rapprocher du rendu métier attendu sans refondre tout le pipeline d'impression.

## Scope

- `templates/print/bon_expedition.html`
- `templates/print/attestation_douane.html`
- Contexte d'impression shipment pour masquer le footer sur ces deux documents
- Tests de fidélité et de rendu liés

## Design

### Header

- Remplacer le header implicite par un header de feuille dédié dans chaque template.
- Garder le logo à gauche.
- Afficher le bloc d'informations Aviation Sans Frontières sur la même ligne, centré verticalement, sur 4 lignes fixes.
- Supprimer le footer pour ces deux documents via le contexte d'impression.

### Bilingual styling

- Tous les segments anglais deviennent explicites et rendus en italique via une classe dédiée.
- Les libellés bilingues restent dans le même ordre que les fichiers `.xlsx`.

### Routing block

- Le bloc principal `Origine` devient une table à largeurs contrôlées:
  - colonne 1 et colonne 3 de même largeur
  - colonne 3 démarrant à la moitié de la page
- Les valeurs des 2 premières lignes passent en rouge, gras, grande taille.
- Les 2 dernières lignes du bloc actuel sont sorties dans un bloc secondaire séparé.

### Party blocks

- Les tableaux `Expéditeur`, `Destinataire`, `Correspondant` réutilisent la même largeur de colonne gauche que le bloc `Origine`.

## Testing

- Vérifier que `shipment_note` et `customs` n'exposent plus de footer.
- Vérifier la présence des nouveaux blocs de structure et des classes de style bilingue.
- Vérifier que le contexte shipment masque bien le footer pour `shipment_note`.
