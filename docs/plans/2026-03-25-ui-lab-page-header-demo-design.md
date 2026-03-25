# UI Lab PageHeader Demo Design

**Date:** 2026-03-25

## Goal

Add a single recommended page-header demo to `scan/ui-lab/` so the team can evaluate a realistic legacy page-header contract for "title + context + actions" before adopting anything on production screens.

## Context

The legacy UI refactor waves are complete and the convergence checkpoint concluded that `PageHeader` must stay `En convergence`.

That means the next useful move is not a shared header abstraction or a refactor pass across every page title in the repository. The useful move is a controlled demo that:
- stays in `UI Lab`,
- remains staff-only and non-runtime,
- validates a real work-page header shape,
- and helps clarify the boundary between `PageHeader`, `Toolbar`, and local section headers.

The repository already has many page titles and top-of-page blocks across `scan` and `portal`, but no explicit `UI Lab` contract dedicated to a page header.

The missing piece is a recommended page-header demo that focuses on:
- a clear title,
- a short contextual sentence,
- and high-level page actions,
without slipping into hero design, filtering controls, or breadcrumbs.

## Scope

### In Scope

- one new recommended page-header demo inside `templates/scan/ui_lab.html`
- local demo CSS in `wms/static/scan/ui-lab.css`
- regression tests in `wms/tests/views/tests_scan_bootstrap_ui.py`
- optional small supporting context values in `wms/views_scan_misc.py`

### Out of Scope

- production screen changes
- a new shared `wms_ui` primitive
- `PageHeader` promotion to `Core stable`
- breadcrumbs
- filters, search, or toolbar controls
- KPIs, badges, or summary metrics inside the header
- Next/React work
- translation/parity work

## Approaches Considered

### 1. Title plus context plus actions, recommended

Idea:
- demonstrate a compact page-work header with one title block and a small action cluster.

Pros:
- best fit for real legacy screens,
- clarifies the boundary with toolbar and hero sections,
- useful on both `scan` and `portal`.

Cons:
- more restrained than a full "app shell" header,
- requires discipline to keep the action count short.

### 2. Breadcrumb-rich page header

Idea:
- demonstrate a fuller header with breadcrumbs and top-of-page actions.

Pros:
- familiar in many design systems.

Cons:
- breadcrumbs do not yet appear stable enough across the repository,
- adds complexity too early.

### 3. Minimal title-only header

Idea:
- demonstrate a title and short meta line only.

Pros:
- very easy to implement.

Cons:
- too weak to validate whether `PageHeader` deserves a real convergence contract.

## Recommended Decision

Take approach 1.

The demo should show one recommended page-header pattern for the dominant case:
- `title + short context + page-level actions`

The result should feel like:
- a work-page header,
- compact,
- operational,
- and clearly distinct from a toolbar.

## Recommended Contract

### PageHeader Role

The page header presents the page itself and exposes its high-level actions.

Allowed responsibilities:
- title the page
- add one short contextual sentence
- expose one primary action
- expose up to two secondary actions

Explicitly excluded:
- filters
- search
- sorting
- metrics
- breadcrumbs in this first demo
- section-local actions
- selection-driven actions

### Anatomy

The demo should render three layers:

1. Title block
   - dominant heading
   - no decorative hero treatment

2. Context block
   - one short sentence
   - explains what the page is for or what the operator is expected to do

3. Actions block
   - one primary action
   - zero to two secondary actions
   - clear visual hierarchy

### Responsive Rules

Desktop expectations:
- title and context stay grouped
- actions stay visually separate
- the primary action remains easy to spot
- the header stays compact and does not become a banner

Mobile expectations:
- clean vertical stacking
- title first
- context second
- actions last
- actions may wrap or stretch only if this improves readability

### Tone Rules

Recommended:
- direct
- helpful
- concise
- work-oriented

Not recommended:
- hero copy
- onboarding language
- toolbar-like density
- "dashboard" decoration in the header itself

## Demo Content

The demo should use a realistic page-work example such as:
- `Gestion des expéditions`
- or another operational legacy title

The recommended content should include:
- a clear title
- one short context sentence
- one primary action
- one or two secondary actions

The demo must remain read-only and non-runtime.

## Implementation Boundaries

### Markup

Add one dedicated article in `templates/scan/ui_lab.html`.

Keep it separate from:
- the toolbar demo
- the table demo
- the empty-state demo

That separation matters because the goal is to validate the `PageHeader` contract itself.

### CSS

Add demo-local classes in `wms/static/scan/ui-lab.css`.

The CSS should validate:
- compact header layout
- clear hierarchy between title, context, and actions
- responsive action wrapping
- visual distinction from hero or toolbar patterns

### JS

No custom JS is recommended for this demo.

The contract should be evaluable from static rendering alone.

## Verification Strategy

Automated verification should confirm:
- the new demo article renders in `scan_ui_lab`
- the page-header demo contains title, context, and actions
- the page remains free of filter/search inputs and breadcrumb affordances for this demo
- the previous `UI Lab` catalog contracts still render

Manual verification should cover:
- desktop compactness
- mobile stacking
- visual distinction from the toolbar demo

## Success Criteria

The work is successful if:
- `UI Lab` contains one recommended page-header demo
- the header is readable and compact on desktop and mobile
- the header is clearly distinct from a toolbar
- no new shared primitive is introduced
- the result strengthens `PageHeader` as a convergence candidate without promoting it
