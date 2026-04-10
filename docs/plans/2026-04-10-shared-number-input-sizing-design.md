# Shared Number Input Sizing Design

## Goal

Stabilize the shared legacy `ui-number-input` contract so the `+ / -` controls never overlap number values, while making button sizing easier to tune globally and for constrained table cells.

## Current State

- Eligible legacy `input[type="number"]` controls are progressively enhanced by the shared runtime in `wms/static/scan/modules/core.js`.
- Shared number-input styling lives in `wms/static/scan/scan-bootstrap.css` and is inherited by scan, portal, planning, and benevole surfaces through their base templates.
- The current contract already expects left-side controls and extra left padding so the value stays clear of the buttons.
- The runtime and CSS already support one size variant through `form-control-sm`, but the geometry is still mostly hard-coded in CSS.

## Problem

- Several numeric fields now receive the shared `+ / -` controls, but some values become hard to read because the button area and the value area are too tight.
- The current CSS couples button size and reserved value padding through fixed values such as `4.25rem`, `3.5rem`, `1.4rem`, and `1.2rem`.
- Screens with narrow quantity columns, especially recipient preference tables, are the first to break because the field width is constrained independently from the button geometry.
- Adjusting button size currently requires touching multiple unrelated CSS declarations instead of one shared contract.

## Decision

Keep the enhancement logic in the shared core runtime and finish the component centralization by moving the number-input geometry to shared CSS variables, with a smaller default button size and an explicit compact mode for tight contexts.

## Why This Approach

### Recommended approach: shared variables plus compact sizing

- Preserves the existing repository-wide contract instead of creating another local widget system.
- Fixes the real source of drift: duplicated hard-coded geometry values in the shared CSS.
- Makes button size changes cheap and safe because the reserved text area is derived from the same variables.
- Lets constrained contexts stay readable without forcing wider table columns.

### Rejected approach: per-screen CSS overrides

- Would keep the overlap bug latent on every new page that adopts the shared number input.
- Makes maintenance harder because each screen would need its own button and padding math.

### Rejected approach: template component migration first

- A dedicated include or template tag could be useful later, but the repository already has a working runtime enhancement contract.
- Replacing all numeric fields at template level is more invasive than needed for the current bug.

## Target UX

- The `+ / -` buttons remain on the left side of enhanced number inputs.
- Buttons become smaller by default because they do not need to dominate the field visually.
- The input value always starts to the right of the button cluster, with guaranteed reserved space.
- Constrained contexts can opt into a compact geometry without inventing local padding rules.
- Large or future contexts can still override sizing through shared variables rather than hard-coded pixel math.

No change to:

- validation semantics for numeric fields
- native `min`, `max`, `step`, `disabled`, and `readonly` behavior
- Next/React paused scope
- translation-paused scope

## Runtime Design

### Shared geometry variables

Introduce number-input contract variables in `wms/static/scan/scan-bootstrap.css`, for example:

- button width
- button height
- gap between buttons
- left inset inside the field
- total reserved start padding for the text area

The reserved text padding must be computed from the same shared variables that size the controls.

### Shared size variants

- Reduce the default button size globally.
- Keep the existing small variant behavior, but make it derive from variables instead of a second set of hard-coded measurements.
- Add an explicit compact modifier on the wrapper for tight table-cell contexts where the default size still wastes space.

### Core runtime integration

- Keep `enhanceNumberInput(...)` in `wms/static/scan/modules/core.js` as the single enhancement entry point.
- Continue assigning `is-sm` from `form-control-sm`.
- Add compact-class propagation only if a local context cannot be expressed cleanly through existing classes.
- Do not move step/min/max/change behavior out of core.

### Surface coverage

Because the shared assets are loaded by:

- `templates/scan/base.html`
- `templates/portal/base.html`
- `templates/planning/base.html`
- `templates/benevole/base.html`

the contract remains repository-wide once the shared CSS and runtime are updated.

## Local UI Adjustments

- Keep the recipient preference quantity cells under review because their width is explicitly constrained in shared CSS and they are the most obvious regression point.
- Re-check small number fields rendered in portal order tables, print-template sequence fields, import/review tables, and custom carton fields after the shared reduction lands.
- Prefer local width tuning only when a screen is unusually narrow after the shared compact sizing is in place.

## Tests

Update or add tests for:

- shared CSS variable-backed number-input geometry
- smaller default and small/compact variants in the shared CSS contract
- UI Lab number-input contract markup
- runtime enhancement still adding the wrapper and controls
- constrained template surfaces still rendering readable quantity inputs after enhancement

## Docs Impact

Update:

- `docs/repo-reference/04-shared-contracts.md` to describe the variable-backed shared sizing contract and the compact variant expectations
- `templates/scan/ui_lab.html` if the visible contract example needs to demonstrate the new sizing behavior
