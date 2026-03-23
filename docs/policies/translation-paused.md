# Translation Pause Policy

## Status

French / English translation work is paused until further notice.

## Goal

Protect delivery focus on the stabilized legacy Django product by preventing accidental work on translation scope while it is dormant.

## Default execution rule

For any request that does not explicitly ask to resume translation work:

- do not re-enable or redesign the visible language selector;
- do not implement FR/EN parity tasks;
- do not add or maintain translation-focused tests;
- do not include i18n verification steps in routine validation;
- implement requested behavior in the default legacy Django flow without translation follow-up work.

## Paused scope list

- `templates/includes/language_switch.html`
- `templates/includes/language_switch_short.html`
- `locale/`
- `wms/tests/views/tests_i18n_language_switch.py`
- `wms/tests/management/tests_management_audit_i18n_strings.py`
- related translation and i18n execution plans in `docs/plans/` containing `i18n` or `translation`

## Allowed by default

- legacy Django feature work outside translation-specific behavior
- business logic work that is language-agnostic
- removing or simplifying dormant translation-only coverage

## Override

Translation scope can be re-enabled only when the user explicitly asks in the current request (for example: "reprendre la traduction", "reactiver le switch de langue", "corriger la version anglaise").
