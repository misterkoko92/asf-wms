# Core Stable Contract Freeze Design

**Date:** 2026-03-25

## Goal

Freeze the usage rules for the current `Core stable` legacy UI contracts so future tickets can reuse them consistently across `scan`, `portal`, `admin`, and `benevole` without reopening visual debates or creating local variants by drift.

## Context

The repository has already established:
- the UI library governance,
- the adoption note for legacy surfaces,
- and the `UI Lab` convergence demos for non-stable patterns.

The remaining gap is not another UI wave. The remaining gap is that the stable base is named, visible, and reusable, but its usage rules are not yet frozen with the same precision as the governance language around it.

Without a short contract-freeze pass, the likely failure mode is not "missing a component". The likely failure mode is:
- local misuse of a stable primitive,
- accidental style drift inside shared markup,
- or silent confusion between what is stable and what is only demonstrated in `UI Lab`.

The purpose of this pass is therefore governance hardening, not UI expansion.

## Scope

### In Scope

- one short usage-rules document for the stable contracts
- light clarifications inside `templates/scan/ui_lab.html`
- small matching adjustments to `wms/tests/views/tests_scan_bootstrap_ui.py` if the visible `UI Lab` contract changes
- optional tiny wording tweaks in `wms/static/scan/ui-lab.css` only if the `UI Lab` clarification needs them

### Stable Contracts Covered

- `ui_button`
- `ui_field`
- `ui_alert`
- `ui_status_badge`
- `ui_switch`
- `ui-comp-card`
- `ui-comp-panel`
- `ui-comp-actions`

### Out of Scope

- any new convergence demo
- any promotion of `Toolbar`, `Table`, `EmptyState`, `PageHeader`, `ConfirmModal`, `WorkflowActionBar`, or `DocumentActions`
- any repo-wide retrofit
- any production-screen visual redesign
- any new `wms_ui` primitive
- any Next/React work
- any translation/parity work

## Approaches Considered

### 1. Documentation only

Idea:
- write a single rules document and stop there.

Pros:
- lowest implementation cost,
- no template changes.

Cons:
- weak visual anchoring,
- leaves `UI Lab` slightly too implicit for day-to-day use,
- easier for future tickets to ignore.

### 2. Documentation plus light UI Lab clarification, recommended

Idea:
- write one rules document,
- add a small explicit stable-contract guidance block or annotations in `UI Lab`,
- keep all examples already present.

Pros:
- strong enough to freeze intent,
- low risk,
- keeps `UI Lab` useful as the operational reference.

Cons:
- slightly broader than doc-only,
- still requires discipline not to overgrow the `UI Lab`.

### 3. Documentation plus UI Lab expansion plus reinforced test campaign

Idea:
- fully expand `UI Lab` stable sections,
- add many more assertions for each usage rule.

Pros:
- maximal explicitness.

Cons:
- too heavy for the current need,
- risks turning the freeze into a new mini-program,
- poor cost/benefit right now.

## Recommended Decision

Take approach 2.

The repository should get:
- one operational usage-rules document for `Core stable`,
- one small `UI Lab` clarification pass,
- and only the minimum test updates needed to lock the visible contract.

This keeps the stable base explicit without turning stable primitives into a fresh refactor initiative.

## Frozen Contract Structure

Each stable primitive should follow the same documentation shape:
- `Role`
- `When to use`
- `When not to use`
- `Allowed variants`
- `Expected composition`
- `Anti-patterns`
- `Responsive / accessibility notes`
- `Minimum visible proof in UI Lab`

The document should stay short. It is a working rulebook, not a full design-system bible.

## Component Rules To Freeze

### ui_button

Freeze:
- clear action hierarchy,
- link versus button semantics,
- one primary action per local zone unless justified,
- no decorative button proliferation.

### ui_field

Freeze:
- `label + control + help/error` structure,
- no orphan inputs inside dense legacy screens,
- consistent order for help and error presentation.

### ui_alert

Freeze:
- informational or feedback role,
- tone-based use,
- separation from inline field errors and from empty-state messaging.

### ui_status_badge

Freeze:
- short status-only content,
- no action semantics,
- no verbose summaries inside badges.

### ui_switch

Freeze:
- simple boolean toggle usage,
- explicit label requirement,
- no use as navigation or compound filtering control.

### ui-comp-card

Freeze:
- first-level structural container,
- not a marketing card,
- not a decorative wrapper added without content grouping value.

### ui-comp-panel

Freeze:
- second-level structural grouping inside dense screens,
- coherent grouped content,
- no fake panel nesting just to imitate spacing.

### ui-comp-actions

Freeze:
- one coherent action group,
- visible hierarchy between actions,
- no uncontrolled mixing of filters, document links, and workflow-final actions unless another contract explicitly owns the pattern.

## UI Lab Clarification Strategy

`UI Lab` should be updated lightly, not expanded heavily.

Recommended changes:
- add a short `Core stable usage rules` block near the governance section or stable contract area,
- make the stable contract intent more explicit around the already-rendered examples,
- optionally add short `use for` / `avoid for` language where ambiguity exists.

Not recommended:
- a whole new demo per stable primitive,
- multiple visual variants for every primitive,
- a parallel “do/don’t gallery” that overwhelms the page.

## Verification Strategy

The freeze pass should verify:
- the new rules document exists,
- the `UI Lab` still exposes the stable base clearly,
- any new stable-guidance block is rendered and covered by narrow assertions,
- existing `UI Lab` scan view tests keep passing.

The smallest correct verification scope is enough.

## Success Criteria

This freeze pass is complete when:
- each stable primitive has explicit usage rules,
- `UI Lab` makes the stable-vs-converging boundary easier to apply,
- no new stable primitive has been introduced,
- no convergence pattern has been promoted,
- and future tickets can reference one stable rule source instead of improvising local interpretation.
