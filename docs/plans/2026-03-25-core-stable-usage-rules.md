# Core Stable Usage Rules

**Date:** 2026-03-25

## Purpose

This note freezes the usage rules for the current `Core stable` legacy UI contracts.

It complements:
- `docs/plans/2026-03-22-ui-library-governance-design.md`
- `docs/plans/2026-03-25-legacy-ui-adoption-note.md`

This is a working rulebook for future tickets, not a new UI wave.

## Scope

Stable contracts covered here:
- `ui_button`
- `ui_field`
- `ui_alert`
- `ui_status_badge`
- `ui_switch`
- `ui-comp-card`
- `ui-comp-panel`
- `ui-comp-actions`

Out of scope:
- `Toolbar`
- `Table`
- `EmptyState`
- `PageHeader`
- `ConfirmModal`
- `WorkflowActionBar`
- `DocumentActions`

Those remain `En convergence`.

## Shared Rules

All `Core stable` contracts must:
- stay Bootstrap-only and Django-legacy friendly,
- remain short and composable,
- be reusable across `scan`, `portal`, `admin`, and `benevole`,
- avoid local variants that change semantics without a governance decision,
- remain visible and understandable in `scan/ui-lab/`.

When a page needs more than the stable primitive itself, compose locally first.

## ui_button

**Role**
Trigger a clear user action or represent a navigational link with button styling.

**Use it for**
- primary page or section action,
- secondary or tertiary actions,
- explicit navigational CTAs that need button treatment.

**Do not use it for**
- decorative controls,
- status display,
- document clusters without local grouping logic,
- implicit links disguised as buttons without a real CTA role.

**Allowed variants**
- `primary`
- `secondary`
- `tertiary`
- domain variants already supported by the stable contract

**Composition**
- prefer one dominant primary action per local action zone,
- use links when the destination is navigational,
- use buttons when the action mutates state or submits work.

**Anti-patterns**
- multiple competing primary buttons in the same zone,
- using danger or warning styling as default emphasis,
- mixing raw button markup and `ui_button` without justification.

**Responsive / accessibility**
- labels must stay explicit,
- actions must remain tap-friendly on mobile,
- icon-only usage is discouraged unless the context is already obvious.

## ui_field

**Role**
Provide the standard field structure for dense legacy forms.

**Use it for**
- most form controls in `scan`, `portal`, `admin`, and `benevole`,
- fields needing a stable `label + control + help/error` structure.

**Do not use it for**
- pure layout wrappers,
- free-floating controls without a real field role,
- highly custom workflow composites that need local markup.

**Allowed variants**
- standard field with help text,
- field with validation errors,
- stable field rendering around existing Django controls.

**Composition**
- label first,
- control second,
- help and errors in the documented order,
- avoid naked inputs inside dense legacy pages.

**Anti-patterns**
- placing help text above the label without a specific reason,
- skipping the label when the screen is not purely decorative,
- splitting one field across multiple unrelated wrappers.

**Responsive / accessibility**
- labels must remain explicit,
- help text should stay concise,
- errors must stay close to the relevant control.

## ui_alert

**Role**
Expose page- or section-level feedback with a clear tone.

**Use it for**
- informational messages,
- warnings,
- success feedback,
- non-inline error feedback.

**Do not use it for**
- field-level validation that belongs next to the input,
- empty states,
- persistent decorative banners without useful feedback content.

**Allowed variants**
- `info`
- `warning`
- `error`
- `success`

**Composition**
- one clear title and short body,
- tone must match the message purpose,
- prefer one alert per concern.

**Anti-patterns**
- stacking several alerts for small local issues,
- using alerts as layout separators,
- turning alerts into mini dashboards.

**Responsive / accessibility**
- alert text must stay concise,
- tone must not rely on color alone,
- content should remain readable without expanding the block excessively.

## ui_status_badge

**Role**
Show a short, stable status label.

**Use it for**
- state indication in tables,
- workflow status,
- compact read-only status summaries.

**Do not use it for**
- actions,
- long explanations,
- multi-line summaries,
- replacing alerts or empty states.

**Allowed variants**
- stable status domains already supported by the contract.

**Composition**
- keep content short,
- attach the badge to the item it qualifies,
- pair with surrounding text when more explanation is needed.

**Anti-patterns**
- verbose labels,
- several badges used as a paragraph,
- custom one-off badge semantics hidden in CSS only.

**Responsive / accessibility**
- label must remain legible on small screens,
- status meaning should stay understandable from nearby context.

## ui_switch

**Role**
Represent a simple boolean toggle.

**Use it for**
- true/false settings,
- explicit opt-in or opt-out controls.

**Do not use it for**
- navigation,
- multi-state filters,
- workflow step changes,
- unclear binary choices.

**Allowed variants**
- standard switch,
- wide switch when the stable contract already supports it.

**Composition**
- always provide an explicit label,
- place the switch close to the setting it controls,
- keep the surrounding explanation short.

**Anti-patterns**
- unlabeled switches,
- using a switch to mimic tabs,
- wrapping several unrelated toggles as one control.

**Responsive / accessibility**
- state must stay explicit,
- touch targets must remain comfortable,
- labels should make sense without relying on nearby guesswork.

## ui-comp-card

**Role**
Provide the first-level structural container for a coherent page block.

**Use it for**
- main sections of dense legacy pages,
- top-level containers that group a meaningful piece of content or workflow.

**Do not use it for**
- decorative nesting,
- fake segmentation without semantic grouping,
- marketing-style visual cards.

**Allowed variants**
- standard card shell as documented in `UI Lab`.

**Composition**
- one coherent content purpose per card,
- title/help/actions only when they add structural value,
- avoid gratuitous nested card stacks.

**Anti-patterns**
- card inside card inside card without a real boundary,
- using cards only for margin,
- turning every row into its own card on dense screens.

**Responsive / accessibility**
- cards should preserve reading order,
- spacing should stay structural, not decorative.

## ui-comp-panel

**Role**
Provide a second-level structural grouping inside a dense page or card.

**Use it for**
- sub-sections inside a larger workflow,
- grouped controls or grouped information under one local theme.

**Do not use it for**
- top-level screen framing when a card is the right level,
- styling a single field that does not need grouping,
- building a hidden local component library.

**Allowed variants**
- standard grouped panel shell as shown in `UI Lab`.

**Composition**
- panel content should stay coherent,
- use panels inside cards or comparable local blocks,
- prefer one topic per panel.

**Anti-patterns**
- panel used only to force a border,
- panel nesting without a clear structure change,
- panel as a substitute for proper page decomposition.

**Responsive / accessibility**
- grouped content should remain scan-friendly,
- titles/help text should stay near the content they describe.

## ui-comp-actions

**Role**
Provide a coherent local action group.

**Use it for**
- grouped workflow actions,
- grouped section actions,
- grouped document actions only when a higher-level local contract owns the block.

**Do not use it for**
- mixed filter controls,
- mixed status and actions,
- unrelated button piles with no hierarchy,
- substituting for `Toolbar`, `DocumentActions`, or `WorkflowActionBar` when one of those local patterns is the real shape.

**Allowed variants**
- local action group with primary/secondary hierarchy,
- dense inline or wrapped action zones already aligned with the stable contract.

**Composition**
- actions in the same group must belong to the same decision area,
- hierarchy must remain obvious,
- prefer one primary action per group.

**Anti-patterns**
- mixing documents, filters, and workflow-final actions in one unmanaged row,
- uncontrolled action sprawl,
- using action groups as general layout wrappers.

**Responsive / accessibility**
- actions must wrap cleanly,
- the primary action must remain easy to spot,
- tap comfort matters more than over-compression.

## UI Lab Proof

`scan/ui-lab/` remains the visible proof for the stable base.

Minimum expectation:
- the stable primitives remain visible there,
- the stable-vs-converging boundary stays explicit,
- and future tickets can point to `UI Lab` plus this note instead of inventing local interpretations.
