# Cross-Surface Select Contract Design

**Date:** 2026-04-03

## Goal

Standardize all legacy Django `<select>` controls across `scan`, `portal`, `planning`, and `benevole` so they share the same visual contract and predictable ordering rules:
- alphabetical ordering by default
- preserved `optgroup` structure with alphabetical ordering inside each group
- a visible dropdown affordance on the right side
- fixed widths that do not resize based on the selected value
- explicit per-select exceptions when business needs differ, such as reverse shipment ordering

## Working Constraints

- Stay on the legacy Django stack only.
- Translation scope remains paused.
- Next/React migration scope remains paused.
- Prefer native `<select>` elements and existing Bootstrap `form-select` usage.
- Do not introduce a JS custom select widget.
- Keep room for explicit business exceptions without weakening the default contract.

## Problem Summary

Current select behavior is inconsistent across the repo:
- many selects already use `form-select`, but sizing is ad hoc
- some selects inherit browser-native affordances without a strong shared visual cue
- ordering logic is split between `queryset.order_by(...)`, ad hoc choice sorting helpers, and template-built options
- grouped options exist in some places and must not be flattened
- some screens use auto-width helpers such as `w-auto`, which makes the control width change visually with context

The result is a weak cross-surface contract:
- users cannot reliably predict option order
- select controls do not always read as a clickable dropdown at first glance
- screens with several adjacent filters look unstable because select widths vary too much

## Approaches Considered

### 1. Standardize existing native selects, recommended

Idea:
- keep native `<select>` controls
- add a shared CSS contract on top of `.form-select`
- centralize sort helpers in Python
- apply explicit size classes and exception markers where needed

Pros:
- lowest implementation risk
- broad coverage with limited markup churn
- accessible by default
- compatible with current Django forms and template rendering

Cons:
- does not fully eliminate existing per-template variation in how options are built
- still requires touching many forms/templates to adopt size classes consistently

### 2. Promote a new template component or tag for all selects

Idea:
- create a new `ui_select` abstraction and migrate all select rendering to it

Pros:
- strongest long-term uniformity

Cons:
- too much migration cost right now
- high regression risk across many forms and templates
- unnecessary if the immediate goal is consistency rather than re-platforming

### 3. Replace native selects with a custom JS/select library

Idea:
- use a custom dropdown widget everywhere

Pros:
- maximum visual control

Cons:
- accessibility cost
- much higher complexity
- not justified for the current need

## Recommended Decision

Take approach 1.

Build a light shared contract around the existing native select stack:
- CSS establishes the visual/select-width rules
- Python helpers establish ordering defaults and grouped sorting behavior
- templates and forms opt into named size classes
- exceptions remain explicit and rare

## Target Design

## 1. Shared Visual Contract

All core selects continue to use `.form-select`.

The shared contract adds:
- fixed right-side dropdown affordance via CSS background icon
- reserved right padding so text never overlaps the icon
- stable width classes using named sizes:
  - `ui-select--sm`
  - `ui-select--md`
  - `ui-select--lg`
  - `ui-select--xl`
- optional per-select width override only for edge cases

Width behavior:
- widths are fixed by class, not by selected content
- different selects can use different named widths
- `w-auto` should be removed from core workflow selects where it currently causes unstable sizing

## 2. Ordering Contract

Ordering is primarily a backend concern.

Default rules:
- sort `A-Z` by visible label
- keep the empty placeholder option first
- if the control uses groups, preserve the groups
- sort options alphabetically inside each group

Exception model:
- default sort mode is ascending
- explicit exceptions may request descending order
- example: the shipment selector on `/scan/cartons/` should support `Z-A` ordering

The template layer should not invent ordering behavior.
Templates may render grouped data, but sorting should happen before render.

## 3. Shared Helper Strategy

Add or extend shared Python helpers so the repo has one canonical way to order select choices.

The helper contract should support:
- flat choices
- grouped choices
- placeholder-first behavior
- `asc` and `desc`

This shared helper becomes the preferred path for:
- view-built option lists
- manual choice tuples
- grouped option blocks prepared before template rendering

For `ModelChoiceField` cases, keep using queryset ordering where it already maps cleanly to the intended label ordering.
Use shared helper normalization only where queryset ordering alone is insufficient or where grouped/template-built choices are involved.

## 4. Adoption Strategy Across Surfaces

### Scan

- adopt shared width classes for operational filters and action selects
- remove auto-width on bulk-action selects that should stay visually stable
- apply explicit descending exception to the editable shipment selector in `Vue Colis`

### Portal

- keep grouped destination selects as grouped
- ensure options are alphabetized within each `optgroup`
- apply shared size classes to routing/account selects

### Planning

- align inline planning assignment/select controls with the same width contract
- preserve existing dense layout, using `sm` where appropriate

### Benevole

- align volunteer week/time/week-picker selects with the same width contract
- keep compact controls where the layout is intentionally narrow

## 5. Runtime Areas Expected To Change

### Shared styling and helpers

- `wms/static/scan/scan-bootstrap.css`
- `wms/static/portal/portal-bootstrap.css` only if a portal-specific override is still needed after the shared scan bootstrap update
- `wms/view_utils.py` and/or a nearby shared form/view helper module for canonical select sorting

### Forms and server-built choices

- `wms/forms.py`
- `wms/forms_volunteer.py`
- `wms/forms_admin_contacts_*.py` where select widgets are configured
- targeted view/helper modules that build manual option lists or grouped destination/shipment choices

### Templates

- `templates/scan/...` for operational filters and batch-action selects
- `templates/portal/...` for grouped destination/recipient/account selects
- `templates/planning/...` for inline assignment/status controls
- `templates/benevole/...` for week and time selection controls

## 6. Test Strategy

### Helper-level tests

- flat choice sorting `A-Z`
- flat choice sorting `Z-A`
- placeholder option stays first
- grouped choices keep group structure
- grouped choices sort alphabetically within each group

### UI contract tests

Update or add tests on the main legacy surfaces to assert:
- core select classes are present on representative controls
- group markup remains intact where expected
- shipment selector exception paths still use the intended descending order
- no regression on pages that already render Bootstrap-styled selects

Likely reference suites:
- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`
- `wms/tests/views/tests_views_planning.py`
- `wms/tests/views/tests_views_volunteer.py`

## Documentation Propagation Planned During Implementation

- `docs/repo-reference/04-shared-contracts.md` because this becomes a cross-surface UI rule
- `docs/repo-reference/03-impact-map.md` if the shared UI checklist should explicitly call out select-ordering/select-width propagation
- `templates/scan/ui_lab.html` only if the design-system lab should showcase the new select contract

## Non-Goals

- no custom JS dropdown system
- no Select2/Chosen-style plugin adoption
- no Next/React work
- no translation/parity work
- no universal single-width rule for every select in the app
