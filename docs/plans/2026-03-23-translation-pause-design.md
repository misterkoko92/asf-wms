# Pause traduction legacy Django - Design

## Contexte

Le depot legacy Django expose aujourd'hui un selecteur de langue FR/EN sur plusieurs surfaces partagees: scan, portail association, espace benevole, planning, pages publiques, et admin. En parallele, une partie non triviale de la suite de tests valide encore explicitement le rendu anglais et les audits i18n.

La traduction est maintenant mise en pause. Pendant cette pause, le produit ne doit plus exposer le choix de langue, et le depot ne doit plus traiter FR/EN comme un scope actif de developpement, de test, ou de verification courante.

## Objectif

Mettre en sommeil le scope traduction sans casser les flux legacy existants:

- masquer le choix de langue sur toutes les pages legacy visibles;
- documenter un gel explicite du scope FR/EN dans les guardrails du depot;
- retirer des suites de tests courantes les validations dont l'objet principal est l'i18n FR/EN;
- conserver l'infrastructure technique Django i18n existante en dormance pour une reprise ulterieure.

## Decision retenue

Le gel adopte une strategie "strict" mais non destructive:

- les partials de switch de langue ne rendent plus rien;
- les futures interventions doivent exclure par defaut le scope traduction;
- les tests et verifications i18n dedies sont retires ou reduits a un contrat minimal sur l'absence du switch;
- la route `set_language`, les primitives `{% trans %}`/`gettext`, et le reste de l'infrastructure i18n ne sont pas supprimes.

Cette approche aligne le produit et le depot sans introduire un chantier de desactivation profonde plus risquee.

## Impacts

### UI

Le switch disparait partout via les partials partagees:

- `templates/includes/language_switch.html`
- `templates/includes/language_switch_short.html`

Toutes les pages qui les incluent herediteront automatiquement ce masquage, y compris scan, portail, benevole, planning, admin, et les ecrans standalone.

### Guardrails

Le depot doit formaliser la pause traduction dans:

- `AGENTS.md`
- `docs/policies/translation-paused.md`

Les regles doivent indiquer que le scope FR/EN est hors perimetre par defaut pour l'analyse, les devs, les tests, et les verifications.

### Tests

La grosse suite `wms/tests/views/tests_i18n_language_switch.py` ne doit plus valider le rendu anglais des pages. Elle devient une suite legere qui verifie seulement que le selecteur n'est plus rendu sur les surfaces partagees.

Les tests dont l'objet principal est la traduction FR/EN dans les ecrans legacy et documents associes doivent etre retires des suites courantes pour alleger les PR et rendre le gel explicite.

## Hors scope

- suppression du support technique Django i18n;
- suppression de la route `set_language`;
- relecture ou correction des contenus anglais existants;
- reprise du chantier de traduction ou de couverture FR/EN.
