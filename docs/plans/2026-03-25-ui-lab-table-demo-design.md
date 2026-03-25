# UI Lab Table Demo Design

**Date:** 2026-03-25

## Goal

Add a single recommended dense table demo to `scan/ui-lab/` so the team can evaluate a realistic legacy data-table contract on desktop and mobile before adopting anything on production screens.

## Context

The legacy UI refactor waves are complete and the convergence checkpoint concluded that `Table` must stay `En convergence`.

That means the next useful move is not a table extraction or a promotion to `Core stable`. The useful move is a controlled demo that:
- stays in `UI Lab`,
- remains staff-only and non-runtime,
- validates a dense business-table shape,
- and checks how the contract behaves on desktop and mobile without rewriting the structure per breakpoint.

The repository already contains:
- a minimal `ui-comp-data-table` example in `UI Lab`,
- and a richer `Toolbar` demo that pilots a small fake list context underneath.

What is still missing is a dedicated recommended table demo that focuses on the table contract itself instead of leaving the table as supporting context for another pattern.

## Scope

### In Scope

- one new recommended table demo inside `templates/scan/ui_lab.html`
- local demo CSS in `wms/static/scan/ui-lab.css`
- regression tests in `wms/tests/views/tests_scan_bootstrap_ui.py`
- optional small supporting context values in `wms/views_scan_misc.py`

### Out of Scope

- production screen changes
- a new shared `wms_ui` primitive
- `Table` promotion to `Core stable`
- selection, bulk actions, or document actions
- inline editing, pagination, or sticky header behavior
- Next/React work
- translation/parity work

## Approaches Considered

### 1. Small responsive table with few columns

Idea:
- optimize for a table that naturally collapses well on mobile.

Pros:
- easy to present,
- low CSS cost.

Cons:
- weak fit for the product's real dense business screens,
- pushes the design toward a generic consumer-style table.

### 2. Dense business table with managed horizontal overflow, recommended

Idea:
- build a dense, desktop-priority table that remains mobile-compatible through a clean responsive wrapper and disciplined column design.

Pros:
- closest to real legacy use cases,
- keeps a true tabular structure,
- validates the right tradeoff for operational screens.

Cons:
- requires tighter judgment on column density,
- mobile review depends on overflow quality instead of structural transformation.

### 3. Rich data grid with selection and contextual actions

Idea:
- include checkboxes, bulk action affordances, and row menus.

Pros:
- broader inspiration.

Cons:
- mixes `Table` with other convergence candidates,
- creates pressure toward premature abstraction,
- overreaches for this phase.

## Recommended Decision

Take approach 2.

The demo should show one recommended table pattern for the dominant case:
- `dense business table, desktop-first but mobile-compatible`

The mobile strategy should be:
- preserve the real table,
- keep the structure legible,
- and allow clean horizontal overflow when needed.

## Recommended Contract

### Table Role

The table is for consulting a dense business list. It is not a miniature application inside a grid.

Allowed responsibilities:
- stable column headers
- compact text content
- status display
- numbers or priority markers
- one lightweight row action

Explicitly excluded:
- inline editing
- multi-select
- bulk actions
- document actions
- upload controls
- complex row menus

### Anatomy

The demo should render five contract layers:

1. Responsive wrapper
   - `table-responsive`
   - explicit minimum width expectation
   - preserved tabular structure on all breakpoints

2. Visible caption
   - explains what the table represents
   - gives short business context

3. Header
   - clear stable labels
   - ordered by business importance
   - optional lightweight emphasis, not fake grid complexity

4. Body
   - dense but readable rows
   - no over-decorated cells
   - one primary datum per cell

5. Special cells
   - status cell using the existing status-pill language
   - a lightweight tertiary row action

### Column Shape

The recommended demo should use a dense but realistic column set, for example:
- reference
- association
- destination
- volume or priority
- status
- action

One or two text cells may use a title plus a short secondary line if needed, but the table should remain primarily text-first and scannable.

### Responsive Rules

Desktop expectations:
- the table reads naturally without tricks
- dense columns stay aligned and distinct
- action remains visually secondary
- status remains instantly scannable

Mobile expectations:
- the table keeps its structure
- the wrapper allows horizontal scrolling cleanly
- no card conversion
- no hidden-row transformation
- column verbosity stays disciplined enough that overflow remains usable

### Density Rules

The table should be compact, but not cramped.

Recommended:
- restrained padding
- concise cell copy
- narrow action cell
- visible separation between dense text and status cells

Not recommended:
- stacking too much meaning in one cell
- turning mobile into a different component
- adding decorative UI that competes with data scanning

## Demo Content

The demo should use fake operational data such as:
- order reference
- association name
- destination
- priority or volume
- status
- a small tertiary row action like `Voir`

The content should stay read-only and must not suggest real workflow submission.

## Implementation Boundaries

### Markup

Add one dedicated article in `templates/scan/ui_lab.html`.

Keep it separate from:
- the existing minimal table example,
- the `Toolbar` recommended demo.

That separation matters because the new demo is meant to validate the table contract itself, not a combined screen pattern.

### CSS

Add demo-local classes in `wms/static/scan/ui-lab.css`.

The CSS should validate:
- dense but legible row rhythm,
- minimum table width,
- clean caption spacing,
- balanced status and action cells,
- mobile overflow that still feels deliberate.

### JS

No custom JS is recommended for this demo.

The table contract should be evaluable from static rendering alone.

## Verification Strategy

Automated verification should confirm:
- the new demo article renders in `scan_ui_lab`
- the new dense-table demo contains a caption, the expected columns, at least one status cell, and a lightweight row action
- the page remains free of selection controls and bulk-action affordances for this demo
- the previous `UI Lab` catalog contracts still render

Manual verification should cover:
- desktop layout
- narrow tablet width
- mobile width with horizontal overflow still usable

## Success Criteria

The work is successful if:
- `UI Lab` contains one recommended dense table demo
- the table is credible for operational use on desktop
- the table remains consultable on mobile via controlled overflow
- no new shared primitive is introduced
- the result strengthens `Table` as a convergence candidate without promoting it
