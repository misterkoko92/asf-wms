# Legacy UI Stabilization Phase Design

**Date:** 2026-03-24

## Goal

Define the short stabilization phase that follows legacy UI waves 4A to 6 so the repository can absorb review feedback and merge safely without reopening a new round of opportunistic refactors.

## Context

The current branch and PR already deliver the planned sequence:
- wave 4A: `scan/imports`
- wave 4B: `scan/admin_contacts`
- wave 5: `portal/order_create` and `portal/account`
- wave 6: `scan/receive_pallet`, `scan/receive`, and `scan/receive_association`

The refactor goal for those waves was structural simplification and contract harmonization, not library expansion. The remaining risk is no longer "missing one more split", but overreacting to review feedback by:
- promoting unstable patterns too early,
- starting a fresh wave on adjacent screens,
- or hiding workflow-local complexity behind new generic abstractions.

## Scope

### In Scope

- PR exit criteria for the legacy UI wave branch
- classification of review findings during PR review
- limited post-merge stabilization for the touched legacy surfaces
- explicit rules for what may still change during stabilization
- explicit rules for what must be deferred to a future sequence

### Affected Surfaces

- `templates/scan/imports.html`
- `templates/scan/admin_contacts.html`
- `templates/portal/order_create.html`
- `templates/portal/account.html`
- `templates/scan/receive_pallet.html`
- `templates/scan/receive.html`
- `templates/scan/receive_association.html`
- the workflow-local includes and regression tests introduced by waves 4A to 6

### Out of Scope

- any new wave on untouched screens
- any new shared `wms_ui` primitive
- any `UI Lab` promotion not already justified by multiple real usages
- any Next/React work
- any translation/parity work
- any broad visual redesign outside the current legacy Bootstrap contracts

## Approaches Considered

### 1. Passive wait for PR review

Idea:
- merge if checks pass,
- react case by case to review comments.

Pros:
- minimal upfront effort,
- no additional docs.

Cons:
- no shared threshold for "fix now" versus "defer",
- high risk of ad hoc refactor requests during review,
- no explicit anti-overshoot guardrail.

### 2. Two separate documents: PR gate and post-merge stabilization

Idea:
- one doc for the open PR,
- one doc for the short post-merge window.

Pros:
- strict separation of phases,
- clean ownership per phase.

Cons:
- too much process for a short sequence,
- duplicate rules about acceptable fixes and governance,
- higher chance that one doc drifts from the other.

### 3. One timeboxed stabilization document with two phases, recommended

Idea:
- keep one source of truth covering both:
  - the PR exit gate,
  - the short post-merge stabilization window.

Pros:
- one decision framework,
- simpler handoff for reviewers and implementers,
- stronger protection against review-driven overshoot.

Cons:
- requires a clear section split inside the document,
- must stay concise enough to remain operational.

## Recommended Decision

Take approach 3.

The stabilization phase should be treated as a single sequence with two explicit stages:
- `Phase 1: PR exit gate`
- `Phase 2: Post-merge stabilization window`

Both phases must stay subordinate to the existing UI governance:
- reuse `Core stable`,
- keep current patterns `En convergence`,
- leave workflow-local structures local,
- do not open a new extraction or generalization track during stabilization.

## Phase 1: PR Exit Gate

### Purpose

Decide whether the current PR is ready to merge, or whether a review finding is serious enough to require a focused corrective patch before merge.

### Merge Blockers

The following stay blocking until fixed:
- functional regression on the touched workflows,
- broken form actions, IDs, data attributes, or local JS hooks,
- Bootstrap-only contract breakage,
- responsive or accessibility regression introduced by the refactor,
- tests/checks failing on the touched surfaces,
- governance violation such as a premature shared abstraction or undocumented promotion attempt.

### Acceptable Before-Merge Fixes

The following are acceptable during stabilization if they remain local and minimal:
- missing or weak regression assertions,
- small template-shell or include-boundary fixes,
- class-level Bootstrap contract fixes,
- documentation clarifications for the wave sequence or stabilization rules,
- narrow naming clarifications inside the touched templates.

### Explicitly Deferred

The following should not be folded into the PR unless they are required to fix a blocker:
- extracting a new shared component,
- updating `scan/ui-lab/`,
- refactoring untouched screens,
- reworking stable naming across multiple modules,
- broad visual cleanup beyond the touched workflows,
- opening a new "wave 7" inside review comments.

### Review Triage Categories

Each review finding must be classified as one of:
- `Blocker before merge`
- `Allowed stabilization fix`
- `Defer after merge`
- `Reject as overshoot`

The important rule is that "good idea" is not enough. During stabilization, a suggestion must either:
- fix a regression,
- strengthen an already-touched contract,
- or be explicitly deferred.

## Phase 2: Post-Merge Stabilization Window

### Purpose

Keep a short, controlled window after merge for low-risk polish and regression handling without reopening a broader UI program.

### Timebox

The window should remain short:
- start on merge day,
- end after the first review/fix cycle and first post-merge validation pass,
- or close earlier if no accepted follow-up remains.

It must not turn into an open-ended backlog for adjacent cleanup.

### Allowed Post-Merge Changes

- narrow bug fixes on the touched waves,
- missing regression tests discovered during review or first usage,
- local clarity improvements inside existing includes,
- doc clarifications about governance or stabilization decisions.

### Not Allowed During Stabilization

- promoting `Toolbar`, `Table`, `PageHeader`, or `EmptyState` to shared status,
- starting a new refactor on `billing_*`, `admin_design`, or editorial pages,
- re-cutting page boundaries just because another decomposition could exist,
- converting local workflow cards into reusable primitives without fresh multi-screen evidence.

## Governance Rules For Stabilization

### Core Stable

Use only what is already stable.

No stabilization feedback should be used as a pretext to enlarge the stable core unless all governance criteria are met:
- at least two real usages,
- short API,
- targeted tests,
- `UI Lab` documentation,
- proof that the contract survives outside one workflow family.

### En Convergence

Patterns that survived waves 4A to 6 remain in convergence until proven otherwise.

This includes, at minimum:
- `Table`
- `Toolbar`
- `PageHeader`
- `EmptyState`

The stabilization phase may collect evidence about them, but must not force a promotion decision.

### Local To Workflow

The stabilization default is to keep local workflow sections local.

That applies especially to:
- import review/matching blocks,
- admin contact cockpit sections,
- portal order/account workflow cards,
- receiving upload, mapping, line-entry, and allocation cards.

## Verification Strategy

Any accepted stabilization patch must re-run the verification command that proves the touched behavior.

Primary suites for the current waves:
- `wms.tests.views.tests_scan_bootstrap_ui`
- `wms.tests.views.tests_portal_bootstrap_ui`
- `wms.tests.views.tests_views_portal`
- `wms.tests.views.tests_views_scan_receipts`
- `wms.tests.views.tests_views_scan_admin`
- `wms.tests.views.tests_views_scan_admin_contacts_crud`
- `wms.tests.scan.tests_scan_import_handlers`
- `wms.tests.scan.tests_admin_contacts_crud`
- `wms.tests.scan.tests_scan_admin_contacts_cockpit_helpers`
- `wms.tests.views.tests_views`

At stabilization time, the smallest correct verifier should be used first, then the broader suite for the affected area.

## Exit Criteria

The stabilization phase is complete when all of the following are true:
- no unresolved merge blocker remains on the touched workflows,
- any accepted follow-up fix has fresh verification evidence,
- all non-blocking suggestions are explicitly deferred or rejected,
- no new shared component promotion remains pending,
- no additional UI wave is opened from review momentum alone.

## Trigger For A Future Sequence

A future legacy UI sequence may be designed later, but only if new evidence appears, for example:
- the same local pattern reappears on at least two additional real screens,
- repeated review feedback shows a genuine missing shared contract,
- post-merge fixes reveal a stable abstraction that survives both Scan and Portal,
- a business workflow outside the current waves becomes the next clear monolith to simplify.

Absent those signals, starting another wave immediately would be overshoot.

## Expected Outcome

This stabilization phase should:
- protect the current PR from opportunistic refactor creep,
- absorb valid review feedback with minimal local patches,
- preserve the governance line between stable, converging, and workflow-local UI,
- and leave the repository ready to pause UI refactor work until new evidence justifies another sequence.
