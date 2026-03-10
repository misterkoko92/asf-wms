# Planning S10 Golden Case Design

## Context
La phase solveur du module `planning` a deja franchi deux jalons importants dans `asf-wms`:
- le golden case reel `legacy_session_s11_2026` est strictement aligne avec le legacy
- le provider API vols interchangeable est merge sur `main`, ce qui ferme le chantier d'acquisition des vols

Il reste toutefois une lacune importante de preuve metier:
- `legacy_session_s10_2026` n'est aujourd'hui qu'une reference partielle
- le test associe dans `wms/tests/planning/tests_solver_reference_cases.py` ne verrouille qu'une affectation critique (`260098 -> AF908 -> COURTOIS Alain`)
- la note [2026-03-09-planning-solver-parity-validation.md] documente explicitement que `s10` n'est pas encore un vrai golden case hebdomadaire complet

Le besoin valide pour cette phase est de faire de `s10` une deuxieme semaine oracle complete, en egalite stricte avec le legacy sur toutes les affectations attendues.

## Goal
Transformer `legacy_session_s10_2026` en golden case hebdomadaire complet dans `asf-wms`, avec comparaison stricte de toutes les affectations legacy, sans casser `legacy_session_s11_2026`.

## Non-Goals
- ajouter de nouveaux providers de vols
- faire evoluer l'UI planning
- introduire une comparaison floue ou des matchings "equivalents"
- patcher artificiellement la fixture pour qu'elle colle au comportement WMS
- ajouter des exceptions specifiques au nom de semaine dans le solveur

## Problem Statement
Le module planning dispose deja d'un harnais de reference robuste:
- `wms/planning/reference_case_builder.py` peut extraire une fixture JSON depuis une session legacy
- `wms/tests/planning/reference_cases.py` peut rejouer cette fixture dans un `PlanningRun`
- `wms/tests/planning/tests_solver_reference_cases.py` compare deja strictement `s11`

Mais `s10` reste traite comme un mini-probe partiel. Tant qu'il ne devient pas un vrai golden case complet:
- la parite solveur n'est prouvee que sur une seule vraie semaine complete
- on peut sur-apprendre sur `s11`
- les ecarts restants sur les arbitrages hebdomadaires ne sont pas verrouilles

## Recommended Approach
Traiter `s10` exactement comme `s11`, pas comme un cas special.

Concretement:
- regenerer ou revalider une fixture hebdomadaire complete `legacy_session_s10_2026.json`
- durcir le test `s10` pour comparer toute la liste triee des affectations attendues
- utiliser les outils de diff solveur uniquement comme aide de travail
- ne declarer la phase terminee que si `s10` et `s11` passent tous les deux en strict

## Options Considered
### Option 1: porter les regles manquantes jusqu'a parite stricte complete
Avantages:
- vraie preuve metier
- generalisable
- coherent avec l'idee de golden case

Inconvenients:
- peut necessiter plusieurs tours de correction solveur

### Option 2: canonicaliser les matchings equivalents
Avantages:
- plus rapide pour faire passer certains cas

Inconvenients:
- contredit l'exigence d'egalite stricte complete
- masque potentiellement un vrai ecart legacy

### Option 3: post-traitement specifique a `s10`
Avantages:
- peut faire passer la semaine rapidement

Inconvenients:
- fragile
- non generalisable
- dette technique immediate

## Reference Artifacts
La phase doit figer exactement trois artefacts de reference:

1. la fixture hebdomadaire complete `wms/tests/planning/fixtures/solver_reference_cases/legacy_session_s10_2026.json`
2. la liste complete des affectations legacy attendues dans cette fixture
3. la note de validation solveur mise a jour avec les ecarts residuels a zero pour `s10`

Pendant le travail, on peut produire des diffs intermediaires lisibles, mais ils ne doivent pas devenir la definition finale du succes.

## Target Test Contract
Le test `s10` doit converger vers le meme modele que `s11`:
- charger la fixture complete
- executer `solve_run(case.run)`
- trier les affectations WMS
- comparer strictement avec `case.expected_assignments`
- comparer aussi les champs solveur attendus presents dans `expected_result`

Le test partiel actuel sur l'affectation `NSI` doit disparaitre une fois la parite complete obtenue.

## Data Flow
1. Rejouer la session legacy `2026-03-02 -> 2026-03-08`.
2. Regenerer la fixture `legacy_session_s10_2026.json` si necessaire.
3. Charger cette fixture via `load_reference_case("legacy_session_s10_2026")`.
4. Executer le solveur WMS.
5. Capturer un diff exact:
   - affectations manquantes
   - affectations en trop
   - differences de vol
   - differences de benevole
6. Corriger uniquement les causes structurelles:
   - payload incomplet
   - regle solveur manquante
   - tie-break legacy absent
   - priorisation legacy mal reproduite
7. Valider en strict sur `s10`, puis reverifier `s11`.

## Correction Strategy
La boucle de travail doit rester disciplinée:
- pas de patch de fixture pour s'adapter au WMS
- pas d'exception `if case_name == "legacy_session_s10_2026"`
- pas de degradation du test en "assez proche"

Les seuls correctifs acceptables sont:
- corrections du payload de comparaison
- corrections du builder de reference si la fixture n'exprime pas encore le bon contexte legacy
- corrections generalisables dans `wms/planning/rules.py` ou `wms/planning/solver.py`

## Risks
### Fixture incomplete ou non representatif
Mitigation:
- repartir d'une session hebdomadaire complete, pas du mini-corpus reduit
- verifier que `build_legacy_planning_reference_case` transporte bien les parametres utiles

### Regression sur `s11`
Mitigation:
- garder `s11` comme garde-fou strict a chaque iteration
- ne pas accepter un patch solveur qui ne generalise pas

### Sur-apprentissage a `s10`
Mitigation:
- interdire les exceptions specifiques a la semaine
- documenter toute nouvelle regle avec sa justification legacy

## Success Criteria
La phase est consideree terminee seulement si:
- `legacy_session_s10_2026.json` est une fixture hebdomadaire complete versionnee
- le test `s10` compare strictement toutes les affectations attendues
- `s10` passe en egalite stricte complete
- `s11` reste strictement vert
- la note de validation solveur indique que `s10` est devenu un vrai golden case complet
