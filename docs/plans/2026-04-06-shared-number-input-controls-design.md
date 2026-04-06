# Shared Number Input Controls Design

## Goal

Uniformiser les champs numeriques du legacy Django en remplacant les spinners natifs par un controle partage avec boutons `-` / `+` places a gauche, sans superposition avec la valeur saisie.

## Scope

- surfaces legacy partageant deja `scan.css` / `scan-bootstrap.css`
- `scan`
- `portal`
- `planning`
- `benevole`

Hors scope par defaut:

- migration Next/React
- traduction FR/EN
- composants Django admin qui ne consomment pas le socle legacy partage

## Current State

- Les styles des champs sont deja centralises dans `wms/static/scan/scan-bootstrap.css`.
- Le JS core partage existe dans `wms/static/scan/modules/core.js`, mais il n'est charge aujourd'hui que par `templates/scan/base.html`.
- Plusieurs ecrans utilisent `input[type="number"]` sans wrapper partage.
- Les spinners visibles sont actuellement ceux du navigateur, donc position, taille et reserve d'espace varient selon l'environnement.

## Chosen Approach

Mettre le comportement en core legacy partage via enhancement progressif:

1. masquer les spinners natifs quand le controle partage est actif
2. entourer automatiquement les `input[type="number"]` eligibles par un wrapper partage
3. inserer deux boutons a gauche (`decrease`, `increase`)
4. reserver un padding gauche suffisant dans l'input pour eviter toute superposition texte / boutons
5. laisser l'input natif comme fallback si le JS ne s'execute pas

Cette approche est preferee a une tentative CSS-only sur les spinners natifs, trop fragile selon les navigateurs.

## Runtime Contract

### CSS

- nouveau wrapper partage pour les champs numeriques
- groupe boutons a gauche, aligne verticalement avec l'input
- padding gauche dedie dans l'input quand il est enrichi
- etat visuel coherent avec les autres `form-control`
- support des tailles existantes (`form-control-sm` notamment)

### JS

- detection automatique des `input[type="number"]` eligibles au chargement
- respect de `min`, `max`, `step`, `disabled`, `readonly`
- support des nombres entiers et decimaux
- emission des evenements `input` puis `change` apres clic sur `-` / `+`
- protection contre le double-enrichissement
- possibilite d'opt-out via une classe locale si un ecran doit rester natif

## Integration Points

- `wms/static/scan/modules/core.js`: logique d'enrichissement partagee
- `wms/static/scan/scan-bootstrap.css`: styles partages
- `templates/scan/base.html`: deja branche sur `core.js`
- `templates/portal/base.html`: devra charger `core.js`
- `templates/planning/base.html`: devra charger `core.js`
- `templates/benevole/base.html`: devra charger `core.js`
- `templates/scan/ui_lab.html`: documenter et illustrer le contrat partage

## Test Strategy

### Server-side contract tests

- verifier que les bases legacy qui doivent consommer le core chargent bien `scan/modules/core.js`
- verifier que l'UI Lab expose un bloc de reference pour le controle partage

### Browser/runtime verification

- ajouter un test UI Playwright cible sur l'UI Lab pour verifier que le DOM est enrichi au chargement
- verifier qu'un clic sur `-` / `+` modifie la valeur d'un champ demo sans casser les attributs natifs

## Documentation Impact

Comme il s'agit d'un contrat UI partage:

- mettre a jour `docs/repo-reference/04-shared-contracts.md`
- si utile, etendre la couverture de `templates/scan/ui_lab.html`

## Risks And Mitigations

- Risque: double initialisation JS sur rerender partiel.
  Mitigation: marquer les inputs deja enrichis.
- Risque: regression sur champs `readonly` / `disabled`.
  Mitigation: bloquer les boutons et couvrir le cas dans le helper JS.
- Risque: step decimal mal gere.
  Mitigation: parser `step` proprement et conserver la precision necessaire.
