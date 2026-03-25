# UI Lab WorkflowActionBar Demo Design

**Date:** 2026-03-25

## Goal

Add a single recommended workflow-action-bar demo to `scan/ui-lab/` so the team can evaluate a realistic legacy `WorkflowActionBar` contract before adopting anything on production screens.

## Context

The legacy UI refactor waves are complete and the convergence checkpoint concluded that `WorkflowActionBar` must stay `En convergence`.

That means the next useful move is not a shared sticky footer or a cross-screen action-bar refactor. The useful move is a controlled demo that:
- stays in `UI Lab`,
- remains staff-only and non-runtime,
- validates a real end-of-step action cluster,
- and clarifies the boundary between `WorkflowActionBar`, `Toolbar`, `PageHeader`, and `DocumentActions`.

The repository already contains many action clusters near the end of dense forms and workflow panels, especially around shipment creation, quick output, and scan forms. What is still missing is an explicit recommended contract in `UI Lab`.

The missing piece is a recommended `WorkflowActionBar` demo that focuses on:
- one short context reminder,
- one primary action,
- one secondary action,
- and an optional low-emphasis fallback action,
without drifting into filtering, document access, or selection-based bulk actions.

## Scope

### In Scope

- one new recommended workflow-action-bar demo inside `templates/scan/ui_lab.html`
- local demo CSS in `wms/static/scan/ui-lab.css`
- regression tests in `wms/tests/views/tests_scan_bootstrap_ui.py`
- optional tiny helper labels in `wms/views_scan_misc.py`

### Out of Scope

- production screen changes
- a new shared `wms_ui` primitive
- `WorkflowActionBar` promotion to `Core stable`
- sticky behavior
- loading/disabled runtime logic
- destructive confirmation flows
- selection-based bulk actions
- Next/React work
- translation/parity work

## Approaches Considered

### 1. End-of-step action bar, recommended

Idea:
- demonstrate a compact action cluster that closes a form step or workflow panel.

Pros:
- matches the most stable repository usage,
- clearly distinct from toolbar and document-access patterns,
- useful on both desktop and mobile.

Cons:
- intentionally narrower than a full-screen sticky action system,
- does not cover selection-driven states.

### 2. Contextual action bar after selection

Idea:
- demonstrate actions that appear after choosing rows or items.

Pros:
- can be useful later for denser admin flows.

Cons:
- too close to a bulk-actions pattern,
- not yet stable enough as a first demo.

### 3. Sticky workflow footer

Idea:
- demonstrate a persistent footer action bar pinned to the viewport.

Pros:
- attractive for long forms.

Cons:
- adds behavior and layout risk too early,
- needs stronger production evidence first.

## Recommended Decision

Take approach 1.

The demo should show one recommended `WorkflowActionBar` pattern for the dominant case:
- end-of-step actions for a dense form or workflow section

The result should feel:
- compact,
- operational,
- obviously action-oriented,
- and clearly separate from headers, toolbars, and document groups.

## Recommended Contract

### WorkflowActionBar Role

The workflow-action bar concludes a form step or workflow section.

Allowed responsibilities:
- restate one short context reminder
- expose one primary workflow action
- expose one secondary workflow action
- optionally expose one low-emphasis fallback action

Explicitly excluded:
- search
- filters
- document links
- selection-based actions
- summaries of the whole page
- sticky behavior in this first demo

### Anatomy

The demo should render three layers:

1. Context reminder
   - one short sentence
   - states what the operator is about to confirm or save

2. Action cluster
   - one primary action
   - one secondary action
   - zero or one tertiary fallback action

3. End-of-step surface
   - visually distinct but sober
   - reads as the conclusion of a workflow section

### Responsive Rules

Desktop expectations:
- actions can stay aligned on one line
- hierarchy remains immediately readable
- the primary action is clearly dominant
- the bar stays compact

Mobile expectations:
- wrap or simple stacking is acceptable
- the primary action remains clearly visible
- controls stay comfortable to tap
- the bar must not feel like a toolbar row

### Tone Rules

Recommended:
- direct
- action-oriented
- concise
- operational

Not recommended:
- navigation language
- document-access wording
- dashboard styling
- a long explanatory block

## Demo Content

The demo should use a realistic workflow example such as:
- finalizing a shipment preparation step

The recommended content should include:
- one short context reminder
- one primary action such as `Valider l'étape`
- one secondary action such as `Enregistrer un brouillon`
- one low-emphasis fallback action such as `Revenir`

The demo must remain read-only and non-runtime.

## Implementation Boundaries

### Markup

Add one dedicated article in `templates/scan/ui_lab.html`.

Keep it separate from:
- the page-header demo
- the document-actions demo
- the toolbar demo
- the table demo
- the empty-state demo

That separation matters because the goal is to validate the `WorkflowActionBar` contract itself.

### CSS

Add demo-local classes in `wms/static/scan/ui-lab.css`.

The CSS should validate:
- a compact end-of-step layout
- clear hierarchy between context and actions
- clean desktop/mobile wrapping
- visual distinction from toolbar and document-actions patterns

### JS

No custom JS is recommended for this demo.

The contract should be evaluable from static rendering alone.

## Verification Strategy

Automated verification should confirm:
- the new demo article renders in `scan_ui_lab`
- the workflow-action-bar demo contains context and expected actions
- the demo does not drift into filters, document links, or selection controls
- the previous `UI Lab` catalog contracts still render

Manual verification should cover:
- desktop readability
- mobile wrapping
- clear distinction from the page-header and document-actions demos
