# Planning Phase 3 Recipe Observation Grid

## Usage

Cette grille sert pendant les deux paliers de recette pour noter rapidement:
- les points satisfaisants
- les reserves
- les blocages
- les contournements

Recommendation:
- une ligne par observation concrete
- pas de reformulation longue
- noter l'observation au moment ou elle apparait

## Echelle de statut

- `OK`: le point est exploitable sans reserve
- `RESERVE`: le point passe, mais reste fragile ou peu confortable
- `BLOQUE`: le point empeche d'aller plus loin ou invalide la recette

## Tableau d'observation

| Palier | Etape | Observation | Statut | Impact operateur | Contournement | Suivi requis |
| --- | --- | --- | --- | --- | --- | --- |
| A ou B | Preparation / Generation / Relecture / Ajustement / Publication / Communications / Diff / Export | Decrire le fait observe | OK / RESERVE / BLOQUE | Faible / Moyen / Fort | Si un contournement existe | Action ou ticket de suivi |

## Decision intermediaire ou finale

### Palier A
- `Palier B autorise`
- `Palier B a suspendre`

### Palier B
- `Pret pour usage encadre`
- `Pret avec reserves`
- `Pas encore pret`

## Regles de redaction

- un fait, une ligne
- pas de theorie
- pas de "semble"
- si un point est `RESERVE` ou `BLOQUE`, decrire le contournement reel ou l'absence de contournement
