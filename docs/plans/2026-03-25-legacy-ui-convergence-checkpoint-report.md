# Legacy UI Convergence Checkpoint Report

**Date:** 2026-03-25

## Summary

Checkpoint scope:
- merged legacy UI waves 4A to 6,
- current governance docs,
- `scan/ui-lab/`,
- scan and portal Bootstrap regression tests,
- workflow-local includes introduced by the merged waves.

Final result:
- promote nothing to `Core stable` at this stage,
- keep `Table` and `Toolbar` in `En convergence`,
- keep `EmptyState`, `ConfirmModal`, `WorkflowActionBar`, and `DocumentActions` local or without action,
- pause further UI refactor work until a new product-driven need creates fresh evidence.

## Hard Constraints Used

- promotion requires at least two real usages,
- the promoted contract must be short, nameable, and cleaner than the local markup it replaces,
- targeted tests must exist or be addable without binding the pattern to one dense workflow,
- `UI Lab` coverage must exist or be addable cleanly,
- no new wave is justified by checkpoint momentum alone.

## Candidate Review

### `Table`

**Real usages**
- strong real usage across scan and portal,
- present in merged wave surfaces such as `admin_contacts`, `receive_pallet` review, `receive_lines`, `receive_association` allocations, `portal/account` billing/documents, and `portal/order_create` ready lists,
- also present on pre-existing scan and portal state pages.

**Contract stability**
- partially stable at the markup level:
  - repeated `scan-table`,
  - repeated `table table-sm table-hover`,
  - repeated `scan-table-wrap table-responsive`,
  - frequent `data-table-tools="1"`.
- still drifting at the contract level:
  - some tables are plain read-only lists,
  - others include row actions, accordion wrappers, counters, or import-specific columns,
  - no shared API or isolated template contract exists yet.

**Current test signal**
- strong regression signal in:
  - `wms/tests/views/tests_scan_bootstrap_ui.py`
  - `wms/tests/views/tests_portal_bootstrap_ui.py`
- current tests prove the Bootstrap table shell is reused on real screens.

**`UI Lab` status**
- yes,
- `scan/ui_lab.html` includes a data-table example via `ui-comp-data-table`.

**Recommended decision**
- `Keep in En convergence`

**Rationale**
- the pattern is clearly real and cross-surface,
- but the repository still lacks a short, explicit, reusable contract beyond a class bundle,
- promotion now would freeze markup that is still shaped by workflow-specific needs.

### `Toolbar`

**Real usages**
- explicit contract in `scan/ui-lab/`,
- indirect adjacent usage in many filter/action rows,
- but no direct `ui-comp-toolbar` adoption inside the merged wave 4A to 6 screens.

**Contract stability**
- conceptually useful,
- practically still unstable:
  - current real screens often use local `scan-filter-actions`,
  - field layouts and CTA groupings vary by workflow,
  - merged waves preferred local filter/action rows over one reusable toolbar shell.

**Current test signal**
- `wms/tests/views/tests_scan_bootstrap_ui.py` asserts the `UI Lab` toolbar contract exists,
- no equivalent targeted tests prove a stable toolbar contract across real wave screens.

**`UI Lab` status**
- yes,
- `scan/ui_lab.html` exposes `ui-lab-contract-toolbar`.

**Recommended decision**
- `Keep in En convergence`

**Rationale**
- the candidate remains useful as a reference contract,
- but the merged waves do not provide enough real adoption to justify promotion,
- forcing extraction now would create an artificial abstraction over still-drifting filter rows.

### `EmptyState`

**Real usages**
- one explicit card in `scan/includes/receive_empty_card.html`,
- multiple local `{% empty %}` branches in admin contacts and portal order/account tables,
- no single repeatable empty-state shell across the merged waves.

**Contract stability**
- low,
- current implementations vary between:
  - full card,
  - inline help paragraph,
  - table-row fallback,
  - workflow-specific copy blocks.

**Current test signal**
- narrow signal only:
  - `wms/tests/views/tests_scan_bootstrap_ui.py` locks `scan-receive-empty-card`.
- no targeted cross-screen empty-state contract coverage.

**`UI Lab` status**
- listed in the governance tier,
- but no explicit rendered contract in `scan/ui_lab.html`.

**Recommended decision**
- `Keep local`

**Rationale**
- the idea exists, but the actual implementations are still strongly workflow-shaped,
- there is not yet a stable cross-screen HTML contract to promote or even keep as a named shared pattern.

### `ConfirmModal`

**Real usages**
- the visible evidence is mostly the shipment overlay/modal family already shown in `scan/ui-lab/`,
- no meaningful reuse signal across the merged wave 4A to 6 screens.

**Contract stability**
- low,
- the current contract behaves more like a shipment-specific choice overlay than a generic confirmation modal.

**Current test signal**
- indirect signal in scan bootstrap tests around the shipment overlay and choice actions,
- no generic confirm-modal test contract.

**`UI Lab` status**
- listed in governance,
- no explicit generic `ConfirmModal` contract rendered under that name.

**Recommended decision**
- `No action`

**Rationale**
- there is not enough checkpoint evidence to justify either promotion or extraction work,
- any real modal convergence should be evaluated later from a broader product need, not inferred here.

### `PageHeader`

**Real usages**
- no explicit cross-screen page-header contract found in the merged wave 4A to 6 screens.

**Contract stability**
- none worth naming yet,
- the merged refactor intentionally centered dense workflow cards rather than header extraction.

**Current test signal**
- no targeted page-header contract coverage in the current scan/portal Bootstrap suites.

**`UI Lab` status**
- listed in governance only,
- no explicit rendered page-header contract in `scan/ui-lab/`.

**Recommended decision**
- `No action`

**Rationale**
- the checkpoint does not show enough evidence that a real `PageHeader` contract exists in the product,
- reopening that discussion now would be pure overshoot.

### `WorkflowActionBar`

**Real usages**
- repeated action groups exist on many screens,
- but they are still materially tied to workflow context:
  - shipment workflow actions,
  - routing/product actions,
  - receiving action rows,
  - import review CTA groups.

**Contract stability**
- low at the named pattern level,
- the stable reusable part is already `ui-comp-actions`,
- the higher-order “workflow action bar” remains page-shaped.

**Current test signal**
- strong signal for `ui-comp-actions`,
- weak signal for a higher-order reusable workflow action bar.

**`UI Lab` status**
- shipment workflow action example exists,
- but as a workflow-specific example rather than a stable generic contract.

**Recommended decision**
- `Keep local`

**Rationale**
- the shared value is already captured by `ui-comp-actions`,
- extracting a second abstraction layer would mostly rename existing local workflow groupings.

### `DocumentActions`

**Real usages**
- clear local usage around shipment-generated documents,
- no meaningful reuse across the merged wave 4A to 6 screens.

**Contract stability**
- still tied to document-heavy shipment workflows,
- not demonstrated on the refactored imports, admin contacts, receiving, or portal account/order screens as a shared contract.

**Current test signal**
- indirect signal through scan UI tests around document action areas,
- no explicit generic `DocumentActions` contract coverage.

**`UI Lab` status**
- shipment document actions example exists,
- but it remains shipment-shaped.

**Recommended decision**
- `Keep local`

**Rationale**
- the current evidence supports a strong shipment-local pattern, not a cross-product primitive,
- promotion would be premature and likely force awkward options later.

## Final Decision Matrix

| Candidate | Decision |
| --- | --- |
| `Table` | `Keep in En convergence` |
| `Toolbar` | `Keep in En convergence` |
| `EmptyState` | `Keep local` |
| `ConfirmModal` | `No action` |
| `PageHeader` | `No action` |
| `WorkflowActionBar` | `Keep local` |
| `DocumentActions` | `Keep local` |

## Check Against Promotion Criteria

No candidate currently satisfies the full promotion bar:
- `Table` has repeated real usage but no short stable reusable API,
- `Toolbar` has `UI Lab` presence but insufficient real-screen adoption in the merged waves,
- the remaining candidates are either too local or too weakly evidenced.

So the checkpoint outcome is intentionally conservative:
- no `UI Lab` expansion,
- no new shared component,
- no follow-up promotion patch now.

## Next UI State

**Decision:** `UI refactor paused`

Meaning:
- no additional wave is justified now,
- no immediate component-promotion follow-up is justified,
- future UI work should resume only when a real product need or repeated cross-screen pattern creates fresh evidence.

## Protected Local Families

The checkpoint explicitly confirms that these remain local:
- import review and matching flows,
- admin contacts cockpit sections,
- portal order/account workflow cards,
- receiving upload, mapping, review, line-entry, and allocation blocks.

## Closing Statement

No further UI wave is justified at this stage.

The repository now has:
- a stable merged refactor baseline,
- a documented stabilization phase,
- and an explicit convergence decision layer.

The correct next move after this checkpoint is to stop UI refactor drift and wait for the next real product-driven UI need.
