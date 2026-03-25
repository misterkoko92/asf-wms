# UI Lab EmptyState Demo Design

**Date:** 2026-03-25

## Goal

Add a single recommended empty-state demo to `scan/ui-lab/` so the team can evaluate a realistic legacy empty-state contract for "missing context / nothing selected" before adopting anything on production screens.

## Context

The legacy UI refactor waves are complete and the convergence checkpoint concluded that `EmptyState` must stay `En convergence`.

That means the next useful move is not a shared component promotion or a cleanup pass across every empty message in the repository. The useful move is a controlled demo that:
- stays in `UI Lab`,
- remains staff-only and non-runtime,
- validates the most credible empty-state case for the product,
- and helps decide what level of sobriety and guidance should survive on real workflow screens.

The repository already has several empty-message shapes:
- dedicated empty cards such as `scan/includes/receive_empty_card.html`,
- contextual "nothing selected" screens such as `scan/order.html`,
- filter-result empty rows inside tables,
- and simple paragraph-based messages in portal and scan pages.

The missing piece is a dedicated recommended `EmptyState` demo in `UI Lab` that focuses on the contract itself instead of leaving it scattered across product pages.

## Scope

### In Scope

- one new recommended empty-state demo inside `templates/scan/ui_lab.html`
- local demo CSS in `wms/static/scan/ui-lab.css`
- regression tests in `wms/tests/views/tests_scan_bootstrap_ui.py`
- optional small supporting context values in `wms/views_scan_misc.py`

### Out of Scope

- production screen changes
- a new shared `wms_ui` primitive
- `EmptyState` promotion to `Core stable`
- "no results for filters" empty states
- error-state or failure-state variants
- onboarding or marketing-style empty states
- Next/React work
- translation/parity work

## Approaches Considered

### 1. No-data / onboarding empty state

Idea:
- demonstrate a "nothing exists yet, create your first item" pattern.

Pros:
- common in design systems,
- easy to illustrate.

Cons:
- weaker fit for the most frequent legacy workflow cases,
- drifts toward product onboarding language.

### 2. Missing-context / nothing-selected empty state, recommended

Idea:
- demonstrate a sober block used when the screen expects a prior selection or context before showing details.

Pros:
- strongest fit with existing legacy screens,
- keeps the pattern operational rather than decorative,
- easy to evaluate without mixing in toolbar/list filtering behavior.

Cons:
- visually more restrained than a marketing-style empty state,
- requires discipline to keep the block useful without over-design.

### 3. Filter no-results empty state

Idea:
- demonstrate the empty state used when filters return no rows.

Pros:
- useful for list screens.

Cons:
- coupled more tightly to `Toolbar` and `Table`,
- weaker first candidate than missing-context for current product workflows.

## Recommended Decision

Take approach 2.

The demo should show one recommended empty-state pattern for the dominant case:
- `missing context / nothing selected`

The design should feel operational:
- clear,
- compact,
- lightly directive,
- and not "heroic".

## Recommended Contract

### EmptyState Role

The empty state tells the user that a required context is not yet available, and what the next logical step is.

Allowed responsibilities:
- state what is missing
- give one short next-step instruction
- optionally offer one simple action

Explicitly excluded:
- multiple competing actions
- forms
- document actions
- complex recovery flows
- alarmist error language
- decorative illustration-heavy treatment

### Anatomy

The demo should render four layers:

1. Surface
   - a sober card-like area
   - visually distinct from surrounding content
   - not oversized

2. Title
   - short
   - direct
   - context-oriented

3. Help text
   - one or two short sentences max
   - says what is missing and what to do next

4. Optional action
   - only one
   - only if the next step is obvious
   - visually secondary to the message, not the entire point of the block

### Responsive Rules

Desktop expectations:
- the block stays compact,
- the hierarchy remains readable,
- the empty state does not visually overpower the rest of the page.

Mobile expectations:
- simple vertical stacking,
- readable text line lengths,
- one action can stretch full width only if that improves usability,
- no giant empty card that consumes the whole page just to fill space.

### Tone Rules

Recommended:
- calm
- directive
- operational
- short

Not recommended:
- vague encouragement
- product marketing voice
- "empty but beautiful" composition that adds little guidance

## Demo Content

The demo should use a realistic missing-context case such as:
- no receipt selected
- no order selected
- no shipment chosen yet

The recommended content should include:
- a title like `Aucune réception sélectionnée`
- a short instruction explaining how to continue
- one simple next-step action such as `Voir la liste`

The demo must remain read-only and non-runtime.

## Implementation Boundaries

### Markup

Add one dedicated article in `templates/scan/ui_lab.html`.

Keep it separate from:
- the `Toolbar` demo,
- the `Table` demo,
- and any error or no-results messaging.

That separation matters because the goal is to validate the `EmptyState` contract itself.

### CSS

Add demo-local classes in `wms/static/scan/ui-lab.css`.

The CSS should validate:
- restrained width,
- clear spacing between title, text, and action,
- mobile/desktop coherence,
- visual fit with the rest of the legacy Bootstrap surfaces.

### JS

No custom JS is recommended for this demo.

The contract should be evaluable from static rendering alone.

## Verification Strategy

Automated verification should confirm:
- the new demo article renders in `scan_ui_lab`
- the empty-state demo contains title, help text, and at most one simple action
- the page remains free of error-state or filter-no-results affordances for this demo
- the previous `UI Lab` catalog contracts still render

Manual verification should cover:
- desktop compactness
- mobile readability
- visual distinction from an error alert

## Success Criteria

The work is successful if:
- `UI Lab` contains one recommended empty-state demo
- the block is immediately understandable on desktop and mobile
- the block feels operational rather than decorative
- no new shared primitive is introduced
- the result strengthens `EmptyState` as a convergence candidate without promoting it
