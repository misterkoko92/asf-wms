# P0 - Baseline visuelle Benev/Classique (checklist)

## But

Créer une référence visuelle fiable de l'interface legacy pour comparer la parité Next.

## 1) Règles de capture

- Forcer UI:
  - `data-ui="benev"`
  - `data-theme="classic"`
- Résolutions cibles:
  - desktop: `1440x900`
  - tablet: `1024x768`
  - mobile: `390x844`
- Capturer sans données personnelles.
- Inclure états:
  - nominal,
  - erreur formulaire,
  - liste vide,
  - mode litige.

## 2) Écrans à capturer en priorité (V1)

Scan:

- `/scan/dashboard/`
- `/scan/stock/`
- `/scan/stock-update/`
- `/scan/pack/`
- `/scan/shipment/`
- `/scan/shipments-tracking/`
- `/scan/shipment/track/<token>/`

Portal:

- `/portal/`
- `/portal/orders/new/`
- `/portal/orders/<id>/`
- `/portal/recipients/`
- `/portal/account/`

## 3) États obligatoires par écran

- Dashboard:
  - filtres par défaut,
  - filtre destination actif.
- Vue stock:
  - filtre vide,
  - filtre catégorie + entrepôt.
- MAJ stock:
  - produit reconnu,
  - produit inconnu (message erreur).
- Création expédition:
  - formulaire initial,
  - destination sélectionnée (champs parties visibles),
  - erreur de validation contact.
- Suivi:
  - expédition normale (update possible),
  - expédition en litige.
- Clôture:
  - bouton clos actif,
  - bouton clos désactivé.

## 4) Convention de nommage

```
baseline/<date>/<module>/<screen>__<state>__<viewport>.png
```

Exemple:

`baseline/2026-02-22/scan/shipment_create__validation_error__desktop.png`

## 5) Checklist de validation visuelle

- [ ] hiérarchie titres/sections identique,
- [ ] densité/espacement comparable,
- [ ] composants boutons/tables/champs alignés,
- [ ] couleurs/states (success/warn/error) cohérents,
- [ ] textes et libellés métier inchangés.

## 6) Outil de comparaison recommandé

- diff pixel:
  - seuil faible pour parité stricte,
  - seuil plus souple sur anti-aliasing typographique.
- contrôle manuel final sur écrans critiques.

## 7) Critère de sortie P0 visuel

La baseline est considérée prête quand:

- toutes les captures prioritaires existent pour les 3 viewports,
- chaque écran a au moins 1 état nominal + 1 état d'erreur pertinent,
- les fichiers sont versionnés dans un dossier de référence dédié.
