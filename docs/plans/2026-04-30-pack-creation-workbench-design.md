# Pack Creation Workbench Design

Date: 2026-04-30

## Status

Approved concept. This supersedes the guided linear pack page direction documented in
`docs/plans/2026-04-30-pack-creation-guided-flow.md`.

## Goal

Make `/scan/pack/` behave like a concrete carton workbench: operators compose a draft
carton plan, adjust individual or selected cartons, review a final summary, then create
the real cartons.

## Problem

The guided linear page separates content, distribution, assignment, output, and validation.
That is technically explicit, but operationally heavy. In the warehouse, the user thinks in
cartons:

- "I have 32 syringe cartons to prepare."
- "These two go to ABJ."
- "These two go to shipment 003."
- "These four are documentary only."

The UI should show the future cartons before stock is written.

## Core Model

The page maintains a client-side draft plan. Each draft row represents one future carton.

Each draft carton has:

- content: one or more product lines with quantities;
- destination: optional;
- shipment: optional;
- output mode: `available` or `without_conditioning`;
- location: optional, mainly for available cartons;
- carton format: defaulted from the global format but editable in batch or per row;
- internal note: optional future extension, not required for first implementation.

The server creates stock/carton records only after the confirmation step.

## Primary Flow

1. Build cartons from a quick generator, or add a blank carton.
2. Review the draft carton plan.
3. Edit one carton, duplicate one carton into a requested total count, or select several rows.
4. Apply batch actions to selected rows.
5. Open the final confirmation summary.
6. Confirm creation.

## Mockup

```text
Préparer des colis

Créer à partir d’un modèle
Produit / contenu        Qté totale      Qté par colis      Nb colis
[ scan / recherche... ]  [ 320      ]    [ 10          ]    [ 32 ]
[ Générer l’aperçu ]     [ + Ajouter produit au modèle ]

ou
[ + Ajouter un colis vide ]   [ Dupliquer le colis sélectionné ]

------------------------------------------------------------
Plan des colis à créer                         32 colis

Actions sur sélection :
[ Destination... ] [ Expédition... ] [ Sortie... ] [ Emplacement... ] [ Format... ] [ Dupliquer ] [ Supprimer ]

[ ] #1  Seringues x10     Dest: —      Exp: —      Sortie: Disponible
[ ] #2  Seringues x10     Dest: —      Exp: —      Sortie: Disponible
[ ] #3  Seringues x10     Dest: ABJ    Exp: —      Sortie: Disponible
[ ] #4  Seringues x10     Dest: ABJ    Exp: —      Sortie: Disponible
[ ] #5  Seringues x10     Dest: —      Exp: 003    Sortie: Disponible
[ ] #6  Seringues x10     Dest: —      Exp: 003    Sortie: Disponible
[ ] #7  Seringues x10     Dest: —      Exp: —      Sortie: Sans conditionnement
[ ] #8  Seringues x10     Dest: —      Exp: —      Sortie: Sans conditionnement

[ Créer les 32 colis selon ce plan ]
```

## Duplication

Duplication uses a target total count, not an additional count.

```text
Colis #12
Seringues x10

Dupliquer ce colis pour obtenir [15] colis identiques au total
=> 14 nouveaux colis seront ajoutés
```

If several rows are selected, batch duplication repeats each selected row with the same
content, destination, shipment, output mode, location, and format.

## Batch Action Rules

Batch actions are field-scoped and cumulative:

- applying destination changes only destination;
- applying shipment changes only shipment;
- applying output mode changes only output mode;
- applying location changes only location;
- applying format changes only format;
- deleting removes only selected draft rows;
- duplicating adds rows and does not mutate the source rows.

Example:

- select A+B, set destination ABJ;
- select C+D, set shipment 003;
- select E+F, set output `available`;
- select G+H, set output `without_conditioning`.

These operations must not overwrite unrelated fields on other rows.

## Individual Editing

Each row can expand into an editor:

```text
Colis #8
Destination : ABJ
Expédition  : —
Sortie      : Disponible
Format      : Standard

Contenu :
- Seringues x10
- Compresses x20
[ + Ajouter produit ]
```

The list row remains compact:

```text
#8   2 produits   Seringues x10, Compresses x20   ABJ   —   Disponible
```

## Final Confirmation

The final confirmation is mandatory before stock is changed.

```text
Confirmer la création

32 colis seront créés :
- 24 disponibles libres
- 2 disponibles pré-affectés ABJ
- 2 disponibles affectés à expédition 003
- 4 sans conditionnement

Stock consommé :
- Seringues : 320
- Compresses : 40

Points d’attention :
- 3 colis sans destination ni expédition
- 1 produit sans dimensions/poids, valeurs standard appliquées

[ Retour modifier ] [ Confirmer la création ]
```

## Operational Constraints

- Barcode scanning remains available on product inputs.
- Quantity semantics remain stock-safe: quantities are explicit product units per draft carton.
- The quick generator can still accept total quantity and quantity per carton to create many
  identical rows.
- Vue Colis remains the after-the-fact assignment surface for cartons that stay free.
- The old exact stock and carton validation rules still apply server-side.

## Non-Goals

- Do not introduce a persistent draft model in the first implementation.
- Do not change stock reservation or shipment status semantics.
- Do not remove Vue Colis assignment flows.
- Do not introduce a React/Next surface; this stays in the legacy Django scan UI.
