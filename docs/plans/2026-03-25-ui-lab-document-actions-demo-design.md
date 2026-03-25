# UI Lab DocumentActions Demo Design

**Date:** 2026-03-25

## Goal

Add a single recommended document-actions demo to `scan/ui-lab/` so the team can evaluate a realistic legacy `DocumentActions` contract before adopting anything on production screens.

## Context

The legacy UI refactor waves are complete and the convergence checkpoint concluded that `DocumentActions` must stay `En convergence`.

That means the next useful move is not a broad document-center refactor or a shared abstraction promoted into the stable core. The useful move is a controlled demo that:
- stays in `UI Lab`,
- remains staff-only and non-runtime,
- validates a real grouped-document-access pattern,
- and clarifies the boundary between `DocumentActions`, `PageHeader`, `Toolbar`, and future workflow action bars.

The repository already contains several document-access clusters, especially in shipment-related screens, where users open generated PDFs, packing lists, or labels from a shared context. What is still missing is an explicit recommended contract in `UI Lab`.

The missing piece is a recommended `DocumentActions` demo that focuses on:
- a clear group title,
- an optional short help line,
- and a homogeneous cluster of tertiary document links,
without drifting into workflow validation, upload handling, or status-heavy document management.

## Scope

### In Scope

- one new recommended document-actions demo inside `templates/scan/ui_lab.html`
- local demo CSS in `wms/static/scan/ui-lab.css`
- regression tests in `wms/tests/views/tests_scan_bootstrap_ui.py`
- optional tiny helper labels in `wms/views_scan_misc.py`

### Out of Scope

- production screen changes
- a new shared `wms_ui` primitive
- `DocumentActions` promotion to `Core stable`
- generation state logic
- destructive document actions
- upload forms
- dropdowns or overflow menus
- Next/React work
- translation/parity work

## Approaches Considered

### 1. Grouped document links, recommended

Idea:
- demonstrate a compact cluster of tertiary actions, each representing one document tied to the same business context.

Pros:
- matches the clearest repository usage,
- stays easy to understand,
- remains distinct from workflow controls.

Cons:
- intentionally narrower than a complete document workflow,
- does not cover unavailable or mixed-status documents.

### 2. Mixed document actions

Idea:
- combine generate, regenerate, download, and remove actions in the same block.

Pros:
- richer and closer to some real-world flows.

Cons:
- mixes access and workflow too early,
- increases the risk of visual hierarchy drift.

### 3. Status-aware document block

Idea:
- display grouped documents with availability or freshness states.

Pros:
- could become useful later for richer flows.

Cons:
- expands the contract too quickly,
- needs stronger evidence from production usage first.

## Recommended Decision

Take approach 1.

The demo should show one recommended `DocumentActions` pattern for the dominant case:
- grouped, homogeneous links to generated documents

The result should feel:
- compact,
- operational,
- immediately scannable,
- and clearly separate from page actions or workflow controls.

## Recommended Contract

### DocumentActions Role

The document-actions block groups access to multiple documents related to the same business object.

Allowed responsibilities:
- title the group
- add one short contextual sentence
- expose several tertiary document actions

Explicitly excluded:
- primary page actions
- destructive actions
- upload or file-picker controls
- workflow validation
- document states or badges in this first demo
- navigation unrelated to documents

### Anatomy

The demo should render three layers:

1. Group title
   - names the document group clearly

2. Help line
   - one short sentence
   - explains what the user can open from this block

3. Document-action cluster
   - multiple homogeneous tertiary actions
   - each action maps to a clear document label

### Responsive Rules

Desktop expectations:
- the group stays compact
- the document links remain easy to scan
- wrapping is acceptable when needed
- no action should look like the page primary action

Mobile expectations:
- simple wrapping across lines
- readable labels
- no excessive button compression
- no modal or overflow behavior required in this first demo

### Tone Rules

Recommended:
- direct
- neutral
- operational
- concise

Not recommended:
- workflow wording
- destructive phrasing
- dashboard or hero styling
- mixed hierarchy between one "important" document and the rest

## Demo Content

The demo should use a realistic shipment-style example such as:
- `Documents d'expédition`

The recommended content should include:
- one group title
- one short help line
- three or four document actions such as:
  - `Bon d'expédition`
  - `Liste colisage`
  - `Étiquettes colis`
  - `Récapitulatif PDF`

The demo must remain read-only and non-runtime.

## Implementation Boundaries

### Markup

Add one dedicated article in `templates/scan/ui_lab.html`.

Keep it separate from:
- the toolbar demo
- the table demo
- the empty-state demo
- the page-header demo

That separation matters because the goal is to validate the `DocumentActions` contract itself.

### CSS

Add demo-local classes in `wms/static/scan/ui-lab.css`.

The CSS should validate:
- a compact grouped-action layout
- clean wrapping on desktop and mobile
- a clear text-to-actions hierarchy
- visual distinction from toolbar and page-header patterns

### JS

No custom JS is recommended for this demo.

The contract should be evaluable from static rendering alone.

## Verification Strategy

Automated verification should confirm:
- the new demo article renders in `scan_ui_lab`
- the document-actions demo contains a title, help line, and expected actions
- the demo does not drift into a primary action, upload form, or mixed workflow block
- the previous `UI Lab` catalog contracts still render

Manual verification should cover:
- desktop readability
- mobile wrapping
- clear distinction from the page-header and toolbar demos
