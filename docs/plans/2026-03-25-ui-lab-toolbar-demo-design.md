# UI Lab Toolbar Demo Design

**Date:** 2026-03-25

## Goal

Add a single recommended toolbar demo to `scan/ui-lab/` so the team can evaluate a realistic responsive toolbar contract on desktop and mobile before adopting anything on production screens.

## Context

The legacy UI refactor waves are complete and the convergence checkpoint concluded that `Toolbar` must stay `En convergence`.

That means the next useful move is not a new wave or a shared primitive promotion. The useful move is a controlled demo that:
- stays in `UI Lab`,
- remains staff-only and non-runtime,
- exercises a realistic toolbar shape,
- and helps validate responsive behavior before any local product adoption.

The current `UI Lab` already exposes a minimal `ui-comp-toolbar` contract. It does not yet demonstrate the recommended "list control" case with a visible primary action, secondary filters, active chips, and a small content context underneath.

## Scope

### In Scope

- one new recommended toolbar demo inside `templates/scan/ui_lab.html`
- local demo CSS in `wms/static/scan/ui-lab.css`
- zero or minimal demo-only JS if required for an inline filter toggle
- regression tests in `wms/tests/views/tests_scan_bootstrap_ui.py`
- optional supporting context values in `wms/views_scan_misc.py`

### Out of Scope

- production screen changes
- a new shared `wms_ui` primitive
- `Toolbar` promotion to `Core stable`
- bulk actions, document actions, or workflow action bars
- Next/React work
- translation/parity work

## Approaches Considered

### 1. Toolbar-only demo

Idea:
- show only the toolbar shell.

Pros:
- smallest implementation.

Cons:
- weak evaluation signal,
- hard to judge if the toolbar still reads correctly once paired with content.

### 2. Toolbar plus lightweight list context, recommended

Idea:
- show one recommended toolbar above a small table with active chips and a secondary filter panel.

Pros:
- realistic enough to validate mobile and desktop behavior,
- still narrow enough to stay focused on `Toolbar`,
- fits the existing role of `UI Lab`.

Cons:
- more markup and CSS than a shell-only example.

### 3. Rich workflow demo

Idea:
- include bulk actions, document actions, multiple states, and workflow cards.

Pros:
- broad inspiration surface.

Cons:
- collapses several convergence candidates into one demo,
- weakens the contract boundary,
- encourages overshoot.

## Recommended Decision

Take approach 2.

The demo should show one recommended toolbar pattern for the dominant case:
- `list + search + filters + primary action`

It should remain a design reference, not a production-ready component extraction.

## Recommended Contract

### Toolbar Role

The toolbar controls a list or result set. It does not act as a generic action bar for long forms or document workflows.

Allowed responsibilities:
- search
- primary filter
- secondary filters
- light sorting/scope controls
- neutral secondary actions
- one primary action

Explicitly excluded:
- save/cancel/delete form actions
- row actions
- document actions
- selection-driven bulk actions

### Anatomy

The demo should render three visible layers:

1. Main toolbar line
   - search
   - one visible primary filter
   - compact secondary actions
   - one visible primary action
   - a `Filtres` toggle for secondary filters

2. Inline secondary filter panel
   - opens below the main line
   - contains lower-priority filters such as warehouse, owner, or sort
   - remains inline, not modal

3. Controlled content context
   - active filter chips
   - a compact read-only demo table

### Responsive Rules

The toolbar is not "mobile first" in the sense of shrinking desktop design into a phone layout. It must work as a balanced contract on both desktop and mobile.

Desktop expectations:
- search can take the widest slot
- primary action stays visually distinct
- secondary actions remain compact
- the secondary filter panel can expand below the main line without breaking hierarchy

Mobile expectations:
- the main line can wrap cleanly
- search can move to full width
- primary action remains immediately visible
- `Filtres` remains immediately accessible
- secondary filters open inline below the main line
- the toolbar must not rely on dense rows of tiny adjacent controls

### Density Rules

Use compact spacing deliberately, not globally.

Recommended:
- compact spacing for neutral secondary action groups
- standard readable width for inputs and selects
- wrap or inline expansion before global over-compression

Not recommended:
- applying a `small column gap` feel to every control in the toolbar
- compressing touch targets on mobile just to keep one rigid row

## Demo Content

The demo should use fake list-management content, for example:
- search field
- visible `Statut` select
- `Filtres` button
- neutral secondary actions such as `Exporter` and `Réinitialiser`
- primary action such as `Nouvelle commande`
- secondary filter fields such as warehouse, owner, and sort
- active chips under the toolbar
- a small table with a few fake rows

The demo must avoid any real submit or runtime business action.

## Implementation Boundaries

### Markup

Add one new dedicated article in `templates/scan/ui_lab.html`.

Keep it separate from the current minimal toolbar contract so the catalog still shows:
- the basic contract,
- and the recommended richer demo.

### CSS

Add demo-local classes in `wms/static/scan/ui-lab.css`.

The CSS should validate:
- stable hierarchy,
- balanced spacing,
- inline panel behavior,
- clean wrap on smaller screens,
- readable alignment on larger screens.

### JS

Prefer zero custom JS.

If an interactive toggle is necessary, use the smallest possible demo-only mechanism, ideally a Bootstrap-native collapse pattern or a minimal `ui-lab.js` hook with no business state.

## Verification Strategy

Automated verification should confirm:
- the new demo article renders in `scan_ui_lab`
- the new toolbar demo contains search, `Filtres`, primary action, active chips, and the table shell
- the page remains free of runtime action names or business submit hooks
- the previous `UI Lab` catalog contracts still render

Manual verification should cover:
- desktop layout
- narrow tablet width
- mobile width with wrapped main line and visible primary action

## Success Criteria

The work is successful if:
- `UI Lab` contains one recommended responsive toolbar demo
- the demo is understandable on desktop and mobile
- no new shared primitive is introduced
- the result strengthens `Toolbar` as a convergence candidate without promoting it
