# 05 - Roadmap apres parite fonctionnelle: refonte UI + editeur de templates

## Precondition d'entree

Ce document s'active apres validation de la parite fonctionnelle complete sur l'ensemble de la matrice (scan + portal + routes dynamiques), puis pilote limite sans blocant metier.

Etat au 2026-02-26: parite fonctionnelle encore en cours, roadmap de refonte preparee.

## 1) Sequence recommandee

1. **Parite fonctionnelle stricte complete** Benev/Classique (obligatoire sur tous ecrans/boutons/fonctions).
2. **Pilote controle + stabilisation** sur groupe restreint.
3. **Refonte visuelle progressive** (tokens + composants + ecran par ecran, via feature flag).
4. **Nouveau module d'edition de templates**.

## 2) Refonte UI progressive (sans casser les flux)

## Objectif

Moderniser l'interface tout en preservant les actions et regles metier deja validees en parite fonctionnelle.

## Livrables

- Design tokens: couleurs, radius, spacing, typo.
- Bibliotheque de composants reutilisables:
  - `Button`,
  - `Card`,
  - `Table`,
  - `FormField`,
  - `Alert`,
  - `StatusBadge`.
- Systeme de variantes:
  - `legacy-compatible`,
  - `modern-calm`,
  - `dense-pro`.

## Methode

- Tu fournis reference de style (lien, capture ou fichier).
- Integration sous forme de variante activable par feature flag.
- Validation ecran par ecran (pas de big-bang visuel).
- Verification systematique de non-regression metier (`make test-next-ui` + recette manuelle ciblee).

## 3) Chantier editeur de templates documentaire

## 3.1 Constat

L'editeur actuel n'est pas assez souple. Ce chantier demarre apres stabilisation du front Next en mode refonte progressive.

Etat reel:

- base technique API templates deja livree (`/api/v1/ui/templates/*`),
- UI actuelle Next = editeur JSON technique (utile pour MVP, pas encore UX cible metier).

## 3.2 Objectifs V1

- Editeur hybride:
  - blocs structures (en-tete, tableaux, signatures),
  - zones libres editables.
- Variables metier inserables:
  - expedition,
  - colis,
  - destinataire/expediteur/correspondant,
  - documents douane/donation.
- Previsualisation live PDF.
- Versioning:
  - brouillon,
  - publie,
  - rollback version.

## 3.3 Types documentaires a couvrir

Obligatoires:

- packing list expedition,
- packing list colis,
- attestation de donation,
- bon de livraison,
- attestation douane.

Optionnels:

- certificats complementaires (securite/authenticite).

## 3.4 Architecture recommandee

- Front Next:
  - editeur WYSIWYG structure,
  - palette de blocs,
  - panneau variables.
- Backend Django:
  - stockage template versionne,
  - moteur rendu HTML/PDF,
  - regles de validation avant publication.

## 3.5 Criteres d'acceptation

- creation/edition template sans intervention developpeur,
- apercu PDF fidele avant publication,
- compatibilite avec impressions existantes,
- permissions et audit conformes.

## 4) Backlog d'amelioration V2

- raccourcis clavier desktop,
- command palette globale,
- suggestions automatiques d'affectation colis,
- mode daltonisme,
- signatures electroniques (si besoin confirme),
- export recap cloture.
