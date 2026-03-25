# Legacy UI Convergence Checkpoint Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Run the post-wave convergence checkpoint for legacy UI so the repository can decide what, if anything, should move from `En convergence` to `Core stable`, and otherwise pause UI refactor work cleanly.

**Architecture:** Use the merged wave outputs as evidence, not as a trigger for more refactor. Review the current governance docs, `UI Lab`, touched scan/portal screens, and existing regression tests. Build a decision matrix for the current candidate patterns, then either record narrowly justified promotions or explicitly choose no promotion and stop.

**Tech Stack:** Django templates, Bootstrap legacy UI contracts, `scan/ui-lab/`, governance docs, regression test suites, GitHub PR/merge history

---

### Task 1: Gather the evidence base for the checkpoint

**Files:**
- Review: `docs/plans/2026-03-22-ui-library-governance-design.md`
- Review: `docs/checklists/legacy-ui-component-governance.md`
- Review: `docs/plans/2026-03-24-legacy-ui-stabilization-design.md`
- Review: `templates/scan/ui_lab.html`
- Review: `templates/scan/imports.html`
- Review: `templates/scan/admin_contacts.html`
- Review: `templates/scan/receive_pallet.html`
- Review: `templates/scan/receive.html`
- Review: `templates/scan/receive_association.html`
- Review: `templates/portal/order_create.html`
- Review: `templates/portal/account.html`

**Step 1: Re-read the governance constraints**

Read the current rules for:
- `Core stable`
- `En convergence`
- `Local au workflow`
- `UI Lab` eligibility
- promotion criteria

Expected: a short list of hard promotion constraints to use during the checkpoint.

**Step 2: Inventory the touched screens**

List the scan and portal screens changed by the merged waves, plus the workflow-local include families introduced for those screens.

Expected: a bounded evidence set limited to the merged waves.

**Step 3: Capture the named candidate patterns**

Start from the governance candidate list:
- `Table`
- `Toolbar`
- `EmptyState`
- `PageHeader`
- `ConfirmModal`
- `WorkflowActionBar`
- `DocumentActions`

Expected: a candidate set that the checkpoint will evaluate explicitly.

**Step 4: Record where each candidate appears**

For each candidate, note:
- which real screens use it,
- whether the usage is consistent or drifting,
- whether the contract already has `UI Lab` representation,
- whether tests already exercise the contract.

Expected: an initial evidence table, even if some rows remain sparse.

**Step 5: Commit**

No commit in this task.

### Task 2: Build the convergence decision matrix

**Files:**
- Create: `docs/plans/2026-03-25-legacy-ui-convergence-checkpoint-report.md`
- Review: `docs/plans/2026-03-25-legacy-ui-convergence-checkpoint-design.md`
- Review: `docs/checklists/legacy-ui-component-governance.md`

**Step 1: Create the report scaffold**

Create a report with one section per candidate pattern and these fields:
- real usages,
- contract stability,
- current test signal,
- `UI Lab` status,
- recommended decision.

Expected: an empty but structured decision document.

**Step 2: Fill the decision matrix**

For each candidate, choose exactly one outcome:
- `Promote to Core stable`
- `Keep in En convergence`
- `Keep local`
- `No action`

Expected: every candidate has an explicit status.

**Step 3: Add rationale**

For each decision, write the minimum reasoning necessary:
- why the evidence is sufficient or insufficient,
- what blocked promotion if promotion is rejected,
- what follow-up would be required later, if any.

Expected: a report that can be read without reconstructing the full wave history.

**Step 4: Verify the report does not force a promotion**

Check that the report allows the conservative outcome:
- no promotion,
- no new wave,
- no `UI Lab` change.

Expected: a checkpoint report that records decisions rather than manufacturing work.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-25-legacy-ui-convergence-checkpoint-report.md
git commit -m "docs: record legacy ui convergence checkpoint"
```

### Task 3: Validate any proposed promotion against governance

**Files:**
- Review: `docs/plans/2026-03-25-legacy-ui-convergence-checkpoint-report.md`
- Review: `docs/checklists/legacy-ui-component-governance.md`
- Review if needed: `templates/scan/ui_lab.html`
- Review if needed: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Review if needed: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Identify whether the report proposes any promotion**

If no candidate is marked `Promote to Core stable`, skip directly to Task 4.

Expected: either zero promotions or a short list of proposed promotions.

**Step 2: For each proposed promotion, verify the hard criteria**

Confirm all of the following:
- at least two real usages,
- short and nameable contract,
- targeted tests exist or can be added cleanly,
- `UI Lab` coverage exists or can be added cleanly,
- no artificial options are needed to force reuse.

Expected: a pass/fail checklist for each proposed promotion.

**Step 3: Downgrade any weak promotion**

If any criterion fails, change the outcome to:
- `Keep in En convergence`, or
- `Keep local`.

Expected: only genuinely justified promotions survive.

**Step 4: Record the final checkpoint decision**

Update the report so it reflects the final post-validation status rather than a draft.

Expected: one stable source of truth.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-25-legacy-ui-convergence-checkpoint-report.md
git commit -m "docs: finalize legacy ui convergence decisions"
```

### Task 4: Choose the next UI state and stop scope creep

**Files:**
- Review: `docs/plans/2026-03-25-legacy-ui-convergence-checkpoint-report.md`
- Review: `docs/plans/2026-03-25-legacy-ui-convergence-checkpoint-design.md`
- Review: `docs/plans/2026-03-24-legacy-ui-stabilization-design.md`

**Step 1: Derive the next UI state from the report**

Choose one of:
- `UI refactor paused`
- `One narrow promotion follow-up is justified`
- `A future product-driven UI sequence may be designed later`

Expected: one explicit post-checkpoint state.

**Step 2: Reject accidental wave reopening**

Confirm that none of the checkpoint conclusions implicitly asks for:
- a new screen refactor,
- an immediate `wave 7`,
- or a broad cleanup on adjacent untouched pages.

Expected: the checkpoint stays a decision pass, not a disguised implementation wave.

**Step 3: Record the stop point**

Update the report or companion note with a clear closing statement such as:
- `No further UI wave is justified at this stage`
- or `Only the following promotion follow-up is justified`

Expected: a usable handoff for later product work.

**Step 4: Verify repository hygiene**

Run:

```bash
git diff --check
git status --short --branch
```

Expected:
- no patch hygiene issues,
- only intentional checkpoint docs remain.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-25-legacy-ui-convergence-checkpoint-design.md docs/plans/2026-03-25-legacy-ui-convergence-checkpoint-implementation-plan.md docs/plans/2026-03-25-legacy-ui-convergence-checkpoint-report.md
git commit -m "docs: close next-step legacy ui checkpoint"
```
