# Legacy UI Adoption Note

**Date:** 2026-03-25

## Goal

Define how the repository should adopt the current legacy UI base after:
- the legacy refactor waves,
- the convergence checkpoint,
- and the `UI Lab` demo series merge.

This note is intentionally short and operational. It is not a new wave plan.

## Current State

The repository now has two distinct UI levels:

### 1. Core stable

These contracts are considered shared and reusable now:
- `ui_button`
- `ui_field`
- `ui_alert`
- `ui_status_badge`
- `ui_switch`
- `ui-comp-card`
- `ui-comp-panel`
- `ui-comp-actions`

They are the default base for all touched legacy surfaces.

### 2. En convergence

These patterns now exist as explicit references in `scan/ui-lab/`, but are not yet promoted as stable shared primitives:
- `Toolbar`
- `Table`
- `EmptyState`
- `PageHeader`
- `ConfirmModal`
- `WorkflowActionBar`
- `DocumentActions`

They should guide implementation when relevant, but remain local unless a later checkpoint promotes them.

## Adoption Rule

The base UI must be applied across legacy surfaces, but only through normal product or maintenance work.

That means:
- yes to reusing `Core stable` everywhere,
- yes to aligning local implementations with `UI Lab`,
- no to launching a repo-wide retrofit just because the reference now exists.

The adoption default is:
1. a ticket touches a page,
2. that page reuses `Core stable`,
3. if needed, the page aligns locally with the relevant `UI Lab` demo,
4. the pattern stays local until stronger evidence exists.

## Surface Rules

### Scan

`scan/` is the most direct adoption surface.

Default rule:
- use `Core stable` immediately,
- use `Toolbar`, `Table`, `EmptyState`, `PageHeader`, `WorkflowActionBar`, and `DocumentActions` as direct reference patterns when a screen needs them.

No extra refactor wave should be opened only to spread those patterns.

### Portal

`portal/` follows the same rule as `scan/`.

Default rule:
- use `Core stable` immediately,
- align local page structures with `UI Lab` when a ticket naturally touches the page.

`portal/` is especially relevant for:
- `PageHeader`
- `Table`
- `EmptyState`
- `DocumentActions`

### Admin

`admin/` should adopt the same contracts, but through the existing admin bridge.

Default rule:
- keep using the admin Bootstrap layer in `wms/static/wms/admin-bootstrap.css`,
- adapt `Core stable` semantics and spacing rules there,
- do not copy `UI Lab` markup blindly into Django admin templates.

`admin/` should consume the same language, but with admin-aware translation of layout constraints.

### Benevole

`benevole/` is inside scope for adoption, but more selectively.

Default rule:
- use `Core stable` everywhere,
- use convergence patterns only on genuine workflow pages,
- keep auth-style pages simpler than `scan/` or `portal/` operator screens.

Good candidates for convergence-pattern adoption:
- `templates/benevole/dashboard.html`
- `templates/benevole/availability_list.html`
- `templates/benevole/availability_form.html`
- `templates/benevole/profile.html`

Pages that should remain mostly `Core stable` only:
- `templates/benevole/login.html`
- `templates/benevole/access_recovery.html`
- `templates/benevole/set_password.html`
- `templates/benevole/change_password.html`

## Ticket-Level Rule

For any future legacy UI ticket, the PR should state which level it uses:
- `Core stable`
- `En convergence`
- `Local au workflow`

Expected behavior:
- if the need is covered by `Core stable`, use it directly,
- if the need matches an `UI Lab` demo, align locally with that demo,
- if the need is workflow-specific, keep it local and avoid inventing a hidden mini-library.

## What Not To Do

Do not:
- open a massive harmonization pass across `scan`, `portal`, `admin`, and `benevole`,
- promote convergence patterns to shared primitives without a fresh checkpoint,
- copy `UI Lab` demos literally where the page context differs,
- create a second parallel component library outside `wms_ui`, `ui-comp-*`, and the current Bootstrap bridges.

## Next Checkpoint Trigger

A future promotion or new UI sequence should happen only if one of these appears:
- the same convergence pattern survives on several real screens,
- repeated product work shows a missing shared contract,
- admin or benevole adoption reveals a stable cross-surface contract,
- a future cleanup target becomes a clear monolith again.

Until then, the right move is simple:
- keep using the base,
- let real tickets supply evidence,
- and avoid speculative UI expansion.
