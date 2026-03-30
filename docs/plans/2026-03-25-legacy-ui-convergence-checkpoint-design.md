# Legacy UI Convergence Checkpoint Design

**Date:** 2026-03-25

## Goal

Define the next UI step after the completion of legacy UI waves 4A to 6: run a convergence checkpoint that decides, with evidence, whether any current UI pattern should be promoted, kept in convergence, or left local to a workflow.

## Context

The legacy UI refactor sequence has been completed and merged:
- wave 4A: `scan/imports`
- wave 4B: `scan/admin_contacts`
- wave 5: `portal/order_create` and `portal/account`
- wave 6: `scan/receive_pallet`, `scan/receive`, and `scan/receive_association`

The repository has already documented the important governance constraints:
- legacy Django + Bootstrap-only remains the target stack,
- Next/React migration stays paused,
- translation work stays paused,
- stable primitives are limited to the current `Core stable`,
- promotion requires multiple real usages and explicit evidence.

The stabilization phase also established a hard boundary:
- no new wave should be opened just because momentum exists,
- no pattern should be promoted during stabilization without fresh proof,
- no adjacent screen should be pulled into refactor scope opportunistically.

So the next step is not another screen-by-screen refactor. The next step is a decision checkpoint.

## Scope

### In Scope

- patterns already observed across waves 4A to 6,
- the current `En convergence` candidates,
- the workflow-local structures introduced during the merged waves,
- the current `UI Lab`, governance docs, and regression tests as evidence sources,
- a decision artifact that classifies patterns into:
  - `Promote to Core stable`
  - `Keep in En convergence`
  - `Keep local`
  - `No action`

### Primary Evidence Sources

- `docs/plans/2026-03-22-ui-library-governance-design.md`
- `docs/checklists/legacy-ui-component-governance.md`
- `docs/plans/2026-03-24-legacy-ui-stabilization-design.md`
- `templates/scan/ui_lab.html`
- merged scan and portal templates touched by waves 4A to 6
- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`

### Out of Scope

- a new UI wave on untouched screens,
- a broad visual redesign,
- any immediate component extraction not backed by the checkpoint evidence,
- any Next/React work,
- any translation work.

## Approaches Considered

### 1. Freeze immediately with no checkpoint

Idea:
- stop UI work entirely,
- treat the merged state as sufficient,
- revisit only when a new feature forces attention.

Pros:
- zero immediate cost,
- no risk of over-processing the refactor.

Cons:
- leaves the current `En convergence` layer unresolved,
- loses the opportunity to turn recent evidence into explicit decisions,
- makes future UI work re-open the same discussion from scratch.

### 2. Promote likely patterns immediately

Idea:
- use the recent waves as implicit proof,
- promote patterns like `Table`, `Toolbar`, `PageHeader`, or `EmptyState` now.

Pros:
- fast path to a more explicit shared library,
- gives a feeling of closure.

Cons:
- too optimistic,
- high risk of promoting abstractions that survived only because the refactor was recent,
- violates the anti-overshoot rule set by stabilization.

### 3. Run a convergence checkpoint before any new UI move, recommended

Idea:
- treat the merged waves as the evidence base,
- audit the candidate patterns,
- decide explicitly what is stable enough and what is not,
- then pause the refactor unless a new product need appears.

Pros:
- closes the loop cleanly,
- turns merged work into governance-backed decisions,
- preserves the distinction between `Core stable`, `En convergence`, and `Local au workflow`,
- avoids both premature promotion and endless refactor continuation.

Cons:
- requires one more planning/execution pass,
- may legitimately end with "promote nothing for now".

## Recommended Decision

Take approach 3.

The next UI step should be a short convergence checkpoint with one expected output: a decision matrix backed by real evidence from Scan and Portal.

The checkpoint is successful even if the result is conservative. In particular, the repository should accept a final output such as:
- promote nothing now,
- keep `Table`, `Toolbar`, `PageHeader`, and `EmptyState` in convergence,
- keep workflow cards local,
- pause further UI refactor until a new business need appears.

## Candidate Patterns To Evaluate

### Current Convergence Candidates

The checkpoint should explicitly evaluate the patterns already named by governance:
- `Table`
- `Toolbar`
- `EmptyState`
- `PageHeader`
- `ConfirmModal`
- `WorkflowActionBar`
- `DocumentActions`

The goal is not to force all of them through the same decision. Some may have enough evidence; others may have little or no cross-screen signal.

### Workflow-Local Families That Must Be Protected

The checkpoint should also confirm that the following remain local unless strong evidence says otherwise:
- import review and matching flows,
- admin contacts cockpit blocks,
- portal order/account workflow cards,
- receiving upload/mapping/review/line-entry/allocation blocks.

## Decision Rules

### Promote To `Core stable` Only If All Conditions Hold

- at least two real usages across distinct screens or flows,
- the role is clearly nameable,
- the API is shorter and clearer than the local markup it replaces,
- targeted regression coverage already exists or can be added without depending on one dense workflow,
- the contract can be documented cleanly in `scan/ui-lab/`.

### Keep In `En convergence` If Evidence Is Real But Not Stable Enough

- repeated usage exists,
- but the markup or semantics still drift across screens,
- or the contract is still too coupled to page context,
- or the repository would need artificial options to unify it.

### Keep Local If The Pattern Is Still Workflow-Shaped

- mostly tied to one business workflow,
- hard to name without referencing the workflow,
- or only reusable by stretching the abstraction.

### `No action` Is A Valid Outcome

If a candidate does not have enough signal, the correct answer is to leave it alone.

## Expected Deliverable

The checkpoint should end with one concise artifact containing:
- the patterns reviewed,
- the screens or flows used as evidence,
- the classification decision,
- the rationale,
- the required follow-up, if any.

The follow-up options are intentionally narrow:
- `promote now`
- `leave in convergence`
- `keep local`
- `defer without action`

## Exit Criteria

The convergence checkpoint is complete when:
- all named candidates have an explicit status,
- no promotion is proposed without full governance evidence,
- no new wave is opened as a side effect of the review,
- the repository has a clear UI pause point after the merged refactor.

## Expected Outcome

This checkpoint should produce clarity, not momentum.

The intended result is:
- a small, explicit decision layer on top of the merged waves,
- a justified pause on further UI refactor,
- and a cleaner starting point for the next real product-driven UI need.
