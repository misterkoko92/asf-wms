# Legacy UI Component Governance Checklist

Use this checklist for any legacy Django UI change that touches shared contracts, introduces a new pattern, or refactors a dense screen.

## 1) Change Classification

- [ ] `Core stable`
- [ ] `En convergence`
- [ ] `Local au workflow`

State explicitly which classification applies and why.

## 2) Stable Core Reuse

- [ ] Existing stable primitives were reused where possible (`ui_button`, `ui_field`, `ui_alert`, `ui_status_badge`, `ui_switch`)
- [ ] Existing wrapper contracts were reused where possible (`ui-comp-card`, `ui-comp-panel`, `ui-comp-actions`)
- [ ] Any local markup duplication that remains is justified

## 3) New Component Or New Option

- [ ] No new component was introduced
- [ ] If a new component was introduced, it serves at least two real screens or flows
- [ ] If a new option was added to an existing component, it improves multiple real usages
- [ ] The API stays simpler than the problem it solves

## 4) UI Lab Impact

- [ ] No `UI Lab` update was needed
- [ ] `UI Lab` was updated because the contract is now stable enough to document
- [ ] The change affects only a local workflow and does not belong in `UI Lab` yet

## 5) Test Impact

- [ ] Template-tag tests were updated if a shared primitive changed
- [ ] View or template regression tests were updated for the affected screen
- [ ] The verification command used for this change is recorded in the plan or PR

## 6) Promotion Decision

- [ ] Keep local
- [ ] Keep in `En convergence`
- [ ] Promote to `Core stable`

If promotion is requested, confirm all of the following:
- [ ] at least two real usages
- [ ] clear and short API
- [ ] `UI Lab` coverage exists
- [ ] targeted tests exist

## 7) Review Gate

- [ ] Bootstrap-only compatibility preserved
- [ ] No Next/React dependency introduced
- [ ] Responsive behavior checked
- [ ] Accessibility basics checked
- [ ] The change strengthens the library instead of hiding more local complexity
